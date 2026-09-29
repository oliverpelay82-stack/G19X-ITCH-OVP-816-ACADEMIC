"""
Controlador de Documentos Digitalizados.
Equivalente a @RestController @RequestMapping("/api/v1/documentos") en Spring Boot.
Maneja la carga de archivos (Nivel 1), la verificación de integridad RIE-03 y
la entrega de binarios verificados a los demás microservicios.
"""
import hashlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from config.boveda import ruta_en_boveda
from config.database import get_db
from models.bitacora import EVENTO_INGESTA_DOCUMENTO
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora, cumplimiento, integridad
from schemas.documento_schema import DocumentoResponse, TipoDocumentoEnum

router = APIRouter(prefix="/api/v1/documentos", tags=["Documentos"])

# Límite máximo de tamaño permitido (15 MB) - Nivel 1 Pipeline
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

# Cabeceras mágicas para validación de integridad estructural (Nivel 1 Pipeline)
ALLOWED_MIME_TYPES = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}


def _ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _documento_o_404(db: Session, documento_id: str) -> Documento:
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Documento con ID '{documento_id}' no encontrado.",
        )
    return documento


def _leer_acotado(archivo) -> bytes:
    """
    Lee a lo sumo el límite del Nivel 1 más un byte: basta para saber si el
    archivo lo excede, sin cargar a memoria un archivo arbitrariamente grande.
    """
    return archivo.read(MAX_FILE_SIZE_BYTES + 1)


def _leer_verificado(db: Session, documento: Documento, request: Request) -> bytes:
    """Lectura con RIE-03: 409 si la huella del binario no coincide con la registrada."""
    try:
        return integridad.leer_verificado(db, documento, ip_origen=_ip(request))
    except integridad.DocumentoAlteradoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc


@router.post(
    "/upload",
    response_model=DocumentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un archivo PDF o imagen a un expediente (Validación Nivel 1)",
)
# Función síncrona a propósito: todo su trabajo es bloqueante (consultas
# SQLAlchemy, SHA-256, escritura en la bóveda y la consulta al rules-service al
# reevaluar el semáforo). FastAPI la ejecuta en su pool de hilos; declarada
# `async`, ese trabajo detenía el bucle de eventos y el servicio completo
# dejaba de responder mientras duraba la carga.
def subir_documento(
    request: Request,
    expediente_id: str = Form(..., description="ID del expediente al que se vinculará"),
    tipo_documento: TipoDocumentoEnum = Form(
        TipoDocumentoEnum.CSF_SAT,
        description="Tipo de documento admitido en el catálogo oficial"
    ),
    file: UploadFile = File(..., description="Archivo digitalizado (PDF o Imagen)"),
    usuario: str = Form("OPERADOR", max_length=100, description="Usuario que realiza la carga (bitácora)"),
    db: Session = Depends(get_db),
):
    """
    Carga de archivo con Pipeline de Validación Nivel 1:
    1. Valida que el expediente exista.
    2. Valida tipo documental contra catálogo oficial (TipoDocumentoEnum).
    3. Valida tamaño de archivo (máx. 15 MB) y rechaza archivos vacíos.
    4. Valida MIME Type y cabecera binaria (Magic Bytes) para evitar archivos corruptos o extensiones falsas.
    5. Calcula el Hash criptográfico inmutable SHA-256 (Principio NOM-151).
    6. Almacena el binario en la bóveda 'storage_vault/' con prefijo de hash para evitar colisiones.
    7. Registra metadatos en la tabla 'documentos' y el evento INGESTA_DOCUMENTO en la bitácora.
    8. Reevalúa el semáforo del expediente: la completitud se mide contra los
       documentos obligatorios del catálogo de reglas (rules-service), y subir
       archivos nunca aprueba el expediente por sí solo (RN-01).
    """
    # 1. Validar existencia del expediente
    expediente = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not expediente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expediente con ID '{expediente_id}' no encontrado.",
        )

    # 2. Leer contenido binario (acotado al límite del Nivel 1 más un byte)
    contenido = _leer_acotado(file.file)
    tamanio_bytes = len(contenido)

    # 3. Validación Nivel 1: Archivo vacío o excede tamaño máximo
    if tamanio_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="[Nivel 1] El archivo proporcionado está vacío (0 bytes).",
        )

    if tamanio_bytes > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"[Nivel 1] El archivo supera el tamaño máximo permitido de {MAX_FILE_SIZE_BYTES // (1024*1024)} MB.",
        )

    # 4. Validación Nivel 1: Formato MIME y firma mágica de bytes
    content_type = (file.content_type or "").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"[Nivel 1] Tipo MIME no permitido ('{content_type}'). Formatos válidos: PDF, JPEG, PNG.",
        )

    magic_signatures = ALLOWED_MIME_TYPES[content_type]
    if not any(contenido.startswith(sig) for sig in magic_signatures):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"[Nivel 1] Integridad fallida: El archivo no es un {content_type} válido o su estructura binaria está corrupta.",
        )

    # 5. Nivel 1: Cálculo del Hash SHA-256 inmutable
    hash_sha256 = hashlib.sha256(contenido).hexdigest()

    # 6. Almacenamiento en bóveda física. El nombre se reduce a su base para que
    #    un nombre con separadores de ruta no pueda escribir fuera de la bóveda.
    nombre_original = os.path.basename(file.filename or "documento")
    ruta_guardado = ruta_en_boveda(hash_sha256, nombre_original)
    archivo_nuevo = not os.path.exists(ruta_guardado)
    with open(ruta_guardado, "wb") as f:
        f.write(contenido)

    try:
        # 7. Persistencia del documento y del evento de ingesta
        nuevo_documento = Documento(
            id=str(uuid.uuid4()),
            expediente_id=expediente.id,
            tipo_documento=tipo_documento.value,
            nombre_archivo_original=nombre_original,
            ruta_almacenamiento=ruta_guardado,
            hash_sha256=hash_sha256,
            tamanio_bytes=tamanio_bytes,
            mime_type=content_type,
            estado_integridad=integridad.INTEGRO,
            creado_en=datetime.now(timezone.utc),
        )
        db.add(nuevo_documento)
        bitacora.registrar(
            db,
            EVENTO_INGESTA_DOCUMENTO,
            expediente_id=expediente.id,
            documento_id=nuevo_documento.id,
            usuario=usuario,
            ip_origen=_ip(request),
            detalle={
                "tipo_documento": tipo_documento.value,
                "nombre_archivo_original": nombre_original,
                "hash_sha256": hash_sha256,
                "tamanio_bytes": tamanio_bytes,
                "mime_type": content_type,
            },
        )

        # 8. Semáforo consolidado del expediente (RIE-01 contra el catálogo de reglas)
        cumplimiento.reevaluar(db, expediente, causa="INGESTA_DOCUMENTO", usuario=usuario, ip_origen=_ip(request))
        db.commit()
    except Exception:
        db.rollback()
        # Un binario sin registro sería un huérfano en la bóveda.
        if archivo_nuevo and os.path.exists(ruta_guardado):
            os.remove(ruta_guardado)
        raise

    db.refresh(nuevo_documento)
    return nuevo_documento


@router.get(
    "/expediente/{expediente_id}",
    response_model=list[DocumentoResponse],
    summary="Listar documentos asociados a un expediente",
)
def listar_documentos_de_expediente(expediente_id: str, db: Session = Depends(get_db)):
    """Retorna todos los archivos digitalizados que pertenecen a un expediente."""
    return db.query(Documento).filter(Documento.expediente_id == expediente_id).order_by(Documento.creado_en.desc()).all()


@router.get(
    "",
    response_model=list[DocumentoResponse],
    summary="Listar todos los documentos digitalizados",
)
def listar_todos_documentos(db: Session = Depends(get_db)):
    """Retorna todos los documentos cargados en el sistema con su hash SHA-256."""
    return db.query(Documento).order_by(Documento.creado_en.desc()).all()


@router.get(
    "/{documento_id}",
    response_model=DocumentoResponse,
    summary="Consultar la ficha de un documento",
)
def obtener_documento(documento_id: str, db: Session = Depends(get_db)):
    return _documento_o_404(db, documento_id)


@router.get(
    "/{documento_id}/integridad",
    summary="Verificar la integridad criptográfica del documento (RIE-03)",
    responses={409: {"description": "La huella del binario no coincide con la registrada: documento bloqueado"}},
)
def verificar_integridad(documento_id: str, request: Request, db: Session = Depends(get_db)):
    """
    Recalcula el SHA-256 del binario en la bóveda y lo compara con la huella
    registrada en la carga. Una discrepancia bloquea el documento, emite un
    dictamen NO_CONFORME (RIE-03), la registra en la bitácora y responde 409.
    """
    documento = _documento_o_404(db, documento_id)
    _leer_verificado(db, documento, request)
    return {
        "documento_id": documento.id,
        "regla": "RIE-03",
        "integro": True,
        "hash_sha256": documento.hash_sha256,
        "verificado_en": datetime.now(timezone.utc).isoformat(),
    }


@router.get(
    "/{documento_id}/contenido",
    summary="Descargar el binario verificado del documento (RIE-03)",
    responses={409: {"description": "La huella del binario no coincide con la registrada: documento bloqueado"}},
)
def descargar_contenido(documento_id: str, request: Request, db: Session = Depends(get_db)):
    """Entrega el binario solo si su huella coincide con la registrada (RIE-03)."""
    documento = _documento_o_404(db, documento_id)
    contenido = _leer_verificado(db, documento, request)
    return Response(
        content=contenido,
        media_type=documento.mime_type,
        headers={"X-Hash-SHA256": documento.hash_sha256},
    )
