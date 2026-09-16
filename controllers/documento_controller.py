"""
Controlador de Documentos Digitalizados.
Equivalente a @RestController @RequestMapping("/api/v1/documentos") en Spring Boot.
Maneja la carga de archivos, cálculo de SHA-256 e inserción en base de datos.
"""
import hashlib
import os
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form
from sqlalchemy.orm import Session

from config.database import get_db
from models.expediente import Expediente
from models.documento import Documento
from schemas.documento_schema import DocumentoResponse, TipoDocumentoEnum

router = APIRouter(prefix="/api/v1/documentos", tags=["Documentos"])

# Directorio de almacenamiento seguro en disco (Bóveda física)
STORAGE_VAULT = os.path.join(os.path.dirname(os.path.dirname(__file__)), "storage_vault")
os.makedirs(STORAGE_VAULT, exist_ok=True)

# Límite máximo de tamaño permitido (15 MB) - Nivel 1 Pipeline
MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024

# Cabeceras mágicas para validación de integridad estructural (Nivel 1 Pipeline)
ALLOWED_MIME_TYPES = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}

# Documentos indispensables para considerar completo un expediente B2B (Regla RIE, DOC-05)
DOCUMENTOS_OBLIGATORIOS = {
    TipoDocumentoEnum.CSF_SAT.value,
    TipoDocumentoEnum.COMP_DOMICILIO.value,
    TipoDocumentoEnum.ACTA_CONSTITUTIVA.value,
}


@router.post(
    "/upload",
    response_model=DocumentoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Subir un archivo PDF o imagen a un expediente (Validación Nivel 1)",
)
async def subir_documento(
    expediente_id: str = Form(..., description="ID del expediente al que se vinculará"),
    tipo_documento: TipoDocumentoEnum = Form(
        TipoDocumentoEnum.CSF_SAT,
        description="Tipo de documento admitido en el catálogo oficial"
    ),
    file: UploadFile = File(..., description="Archivo digitalizado (PDF o Imagen)"),
    db: Session = Depends(get_db),
):
    """
    Carga de archivo con Pipeline de Validación Nivel 1:
    1. Valida que el expediente exista en MySQL.
    2. Valida tipo documental contra catálogo oficial (TipoDocumentoEnum).
    3. Valida tamaño de archivo (máx. 15 MB) y rechaza archivos vacíos.
    4. Valida MIME Type y cabecera binaria (Magic Bytes) para evitar archivos corruptos o extensiones falsas.
    5. Calcula el Hash criptográfico inmutable SHA-256 (Principio NOM-151).
    6. Almacena el binario en la bóveda 'storage_vault/' con prefijo de hash para evitar colisiones.
    7. Registra metadatos en la tabla 'documentos'.
    8. Actualiza el porcentaje de completitud y estado del expediente en base a documentos obligatorios DISTINTOS.
    """
    # 1. Validar existencia del expediente
    expediente = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not expediente:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expediente con ID '{expediente_id}' no encontrado.",
        )

    # 2. Leer contenido binario
    contenido = await file.read()
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

    # 6. Almacenamiento en bóveda física con nombre único
    nombre_seguro = f"{hash_sha256[:12]}_{file.filename}"
    ruta_guardado = os.path.join(STORAGE_VAULT, nombre_seguro)
    with open(ruta_guardado, "wb") as f:
        f.write(contenido)

    # 7. Persistencia del documento en MySQL
    nuevo_documento = Documento(
        id=str(uuid.uuid4()),
        expediente_id=expediente.id,
        tipo_documento=tipo_documento.value,
        nombre_archivo_original=file.filename,
        ruta_almacenamiento=ruta_guardado,
        hash_sha256=hash_sha256,
        tamanio_bytes=tamanio_bytes,
        mime_type=content_type,
        creado_en=datetime.now(timezone.utc),
    )
    db.add(nuevo_documento)

    # 8. Cálculo Determinista de Completitud (DOC-05 Regla RIE)
    # Buscamos tipos de documentos distintos existentes en el expediente
    tipos_en_bd = {
        doc[0] for doc in db.query(Documento.tipo_documento).filter(Documento.expediente_id == expediente.id).all()
    }
    tipos_en_bd.add(tipo_documento.value)

    # Evaluar cobertura de documentos obligatorios únicos
    cubiertos = len(DOCUMENTOS_OBLIGATORIOS.intersection(tipos_en_bd))
    progreso = min(100.0, round((cubiertos / float(len(DOCUMENTOS_OBLIGATORIOS))) * 100, 1))

    expediente.porcentaje_completitud = progreso
    if progreso >= 100.0:
        expediente.estado_cumplimiento = "CONFORME"
    else:
        expediente.estado_cumplimiento = "EN_REVISION"

    db.commit()
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
    summary="Listar todos los documentos digitalizados en MySQL",
)
def listar_todos_documentos(db: Session = Depends(get_db)):
    """Retorna todos los documentos cargados en el sistema con su hash SHA-256."""
    return db.query(Documento).order_by(Documento.creado_en.desc()).all()

