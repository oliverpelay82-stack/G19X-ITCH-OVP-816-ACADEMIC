"""
Controlador de Dictámenes de Auditoría (Niveles 2, 4 y 5 del pipeline).

  * ``POST /api/v1/dictamenes`` — el ai-service persiste el dictamen del
    Nivel 4 (IA más reglas RCV del Nivel 2). Antes de guardarlo se verifica la
    integridad del binario (RIE-03): no se dictamina un archivo alterado.
  * ``GET /api/v1/dictamenes`` y ``GET /api/v1/dictamenes/{id}`` — historial.
  * ``POST /api/v1/dictamenes/{id}/ratificar`` — Human-in-the-Loop (RF-14,
    RN-05): el analista confirma o corrige el dictamen con una justificación
    que queda en la bitácora, y el semáforo del expediente se recalcula.
"""
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.bitacora import EVENTO_DICTAMEN_IA, EVENTO_RATIFICACION_HUMANA
from models.dictamen import ORIGEN_NIVEL_1, ORIGEN_NIVEL_3_ILEGIBLE, ORIGEN_NIVEL_4, ORIGEN_RIE_03, DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora, cumplimiento, integridad
from schemas.dictamen_schema import DictamenCreate, DictamenResponse, RatificacionRequest

router = APIRouter(prefix="/api/v1/dictamenes", tags=["Dictámenes de Auditoría"])


class DictamenRegistradoResponse(DictamenResponse):
    """Dictamen más el estado del expediente que resultó de registrarlo."""
    estado_expediente: str
    porcentaje_completitud: float


def _ip(request: Request) -> Optional[str]:
    return request.client.host if request.client else None


def _dictamen_o_404(db: Session, dictamen_id: str) -> DictamenAuditoria:
    dictamen = db.query(DictamenAuditoria).filter(DictamenAuditoria.id == dictamen_id).first()
    if not dictamen:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Dictamen '{dictamen_id}' no encontrado.")
    return dictamen


def _registrado(dictamen: DictamenAuditoria, expediente: Expediente) -> DictamenRegistradoResponse:
    return DictamenRegistradoResponse(
        **DictamenResponse.model_validate(dictamen).model_dump(),
        estado_expediente=expediente.estado_cumplimiento,
        porcentaje_completitud=float(expediente.porcentaje_completitud),
    )


def _reglas_de_contenido(verificaciones: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Verificaciones RSC/RDS del Nivel 4 en el formato de reglas_aplicadas."""
    return [
        {
            "codigo_regla": v.get("codigo_regla"),
            "nombre_regla": v.get("nombre_regla"),
            "familia_regla": v.get("familia_regla"),
            "severidad": v.get("severidad"),
            "resultado": v.get("resultado"),
            "detalle": v.get("observacion"),
            "cita": v.get("cita"),
            "recomendacion": v.get("recomendacion"),
        }
        for v in verificaciones
        if isinstance(v, dict) and v.get("codigo_regla")
    ]


# P2: roles de representación y campos que se aceptan de cada persona.
_ROLES_REPRESENTACION = {"FIRMANTES": "empresa", "APODERADOS": "facultades"}
_MAX_PERSONAS = 8
_MAX_CARACTERES = 300


def _representacion(datos: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """
    Datos de representación legal del Nivel 4 (RSC-02, HU-37) tal como se
    guardan en el dictamen: solo los roles y campos conocidos, con textos
    acotados. El core no confía en el cliente para la forma del dato.
    """
    if not isinstance(datos, dict) or datos.get("rol") not in _ROLES_REPRESENTACION:
        return None
    campo = _ROLES_REPRESENTACION[datos["rol"]]

    def texto(valor: Any) -> Optional[str]:
        return " ".join(valor.split())[:_MAX_CARACTERES] if isinstance(valor, str) and valor.strip() else None

    personas = []
    for p in datos.get("personas") or []:
        if isinstance(p, dict) and texto(p.get("nombre")):
            personas.append({
                "nombre": texto(p.get("nombre")),
                "cargo": texto(p.get("cargo")),
                campo: texto(p.get(campo)),
                "cita": texto(p.get("cita")),
                "cita_verificada": p.get("cita_verificada") is True,
            })
    return {"rol": datos["rol"], "personas": personas[:_MAX_PERSONAS]}


def _reglas_aplicadas(vigencia: Optional[dict[str, Any]], hash_sha256: str) -> tuple[list[dict[str, Any]], str]:
    """Reglas evaluadas en la auditoría y el resultado consolidado de vigencia."""
    reglas: list[dict[str, Any]] = [
        {
            "codigo_regla": "RIE-03",
            "resultado": "CUMPLE",
            "detalle": f"Huella SHA-256 verificada contra la registrada en la carga ({hash_sha256[:16]}…).",
        }
    ]
    if not vigencia or vigencia.get("disponible") is False:
        return reglas, "NO_VERIFICADA"
    for evaluacion in vigencia.get("evaluaciones") or []:
        reglas.append(
            {
                "codigo_regla": evaluacion.get("codigo_regla"),
                "resultado": evaluacion.get("resultado"),
                "detalle": evaluacion.get("detalle"),
                "dias_calculados": evaluacion.get("dias_calculados"),
                "limite_dias": evaluacion.get("limite_dias"),
                # Permite recalcular la vigencia contra la fecha actual (RN-02).
                "criterio": evaluacion.get("criterio"),
            }
        )
    return reglas, vigencia.get("resultado") or "SIN_REGLAS"


@router.post(
    "",
    response_model=DictamenRegistradoResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Persistir el dictamen de un documento (Nivel 4 con reglas del Nivel 2)",
    responses={409: {"description": "El binario del documento está alterado (RIE-03)"}},
)
def registrar_dictamen(dto: DictamenCreate, request: Request, db: Session = Depends(get_db)):
    documento = db.query(Documento).filter(Documento.id == dto.documento_id).first()
    if not documento:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento con ID '{dto.documento_id}' no encontrado."
        )
    ip = _ip(request)
    try:
        integridad.leer_verificado(db, documento, usuario=dto.usuario, ip_origen=ip)
    except integridad.DocumentoAlteradoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    reglas, vigencia_resultado = _reglas_aplicadas(dto.vigencia, documento.hash_sha256)
    reglas += _reglas_de_contenido(dto.verificaciones)
    dictamen = DictamenAuditoria(
        documento_id=documento.id,
        expediente_id=documento.expediente_id,
        estatus=dto.estatus,
        estatus_preliminar=dto.estatus,
        origen=dto.origen or ORIGEN_NIVEL_4,
        nivel_confianza=dto.nivel_confianza,
        requiere_revision_humana=dto.requiere_revision_humana,
        reglas_aplicadas=reglas,
        vigencia_resultado=vigencia_resultado,
        observaciones=dto.observaciones,
        tipo_documento_detectado=dto.tipo_documento_detectado,
        rfc_detectado=dto.rfc_detectado,
        match_titular=dto.match_titular,
        fecha_emision_extraida=dto.fecha_emision,
        fecha_vencimiento_extraida=dto.fecha_vencimiento,
        modelo_utilizado=dto.modelo_utilizado,
        version_lectura=dto.version_lectura,
        version_instrucciones=dto.version_instrucciones,
        version_catalogo=dto.version_catalogo,
        version_reglas_tipo=dto.version_reglas_tipo,
        nombre_documento_real=dto.nombre_documento_real,
        representacion_legal=_representacion(dto.representacion),
        hash_sha256=documento.hash_sha256,
    )
    # P5: con el dictamen guardado, el documento deja de estar diferido.
    documento.procesamiento_diferido = None
    db.add(dictamen)
    db.flush()
    bitacora.registrar(
        db,
        EVENTO_DICTAMEN_IA,
        expediente_id=documento.expediente_id,
        documento_id=documento.id,
        dictamen_id=dictamen.id,
        usuario=dto.usuario,
        ip_origen=ip,
        detalle={
            "estatus": dto.estatus,
            "nivel_confianza": dto.nivel_confianza,
            "requiere_revision_humana": dto.requiere_revision_humana,
            "vigencia_resultado": vigencia_resultado,
            "reglas": [f"{r['codigo_regla']}:{r['resultado']}" for r in reglas],
            "match_titular": dto.match_titular,
            "modelo_utilizado": dto.modelo_utilizado,
            "origen": dto.origen or ORIGEN_NIVEL_4,
            "version_lectura": dto.version_lectura,
            "version_instrucciones": dto.version_instrucciones,
            "version_catalogo": dto.version_catalogo,
            "version_reglas_tipo": dto.version_reglas_tipo,
            **({"nombre_documento_real": dto.nombre_documento_real} if dto.nombre_documento_real else {}),
            "hash_sha256": documento.hash_sha256,
        },
    )
    expediente = db.query(Expediente).filter(Expediente.id == documento.expediente_id).first()
    cumplimiento.reevaluar(db, expediente, causa="DICTAMEN_IA", usuario=dto.usuario, ip_origen=ip)
    db.commit()
    db.refresh(dictamen)
    return _registrado(dictamen, expediente)


@router.get("", response_model=list[DictamenResponse], summary="Historial de dictámenes, del más reciente al más antiguo")
def listar_dictamenes(
    documento_id: Optional[str] = None,
    expediente_id: Optional[str] = None,
    estatus: Optional[str] = None,
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(DictamenAuditoria)
    if documento_id:
        query = query.filter(DictamenAuditoria.documento_id == documento_id)
    if expediente_id:
        query = query.filter(DictamenAuditoria.expediente_id == expediente_id)
    if estatus:
        query = query.filter(DictamenAuditoria.estatus == estatus.upper())
    return query.order_by(DictamenAuditoria.creado_en.desc()).limit(limite).all()


@router.get("/{dictamen_id}", response_model=DictamenResponse, summary="Consultar un dictamen")
def obtener_dictamen(dictamen_id: str, db: Session = Depends(get_db)):
    return _dictamen_o_404(db, dictamen_id)


@router.post(
    "/{dictamen_id}/ratificar",
    response_model=DictamenRegistradoResponse,
    summary="Ratificación humana de un dictamen (Human-in-the-Loop, RN-05)",
    responses={409: {"description": "El dictamen ya fue ratificado, fue sustituido o no admite ratificación"}},
)
def ratificar_dictamen(dictamen_id: str, dto: RatificacionRequest, request: Request, db: Session = Depends(get_db)):
    """
    El analista confirma o corrige el dictamen vigente de un documento. La
    decisión prevalece sobre la del motor (RN-05), pero no borra nada: el
    estatus automático queda en ``estatus_preliminar`` y la bitácora registra
    quién decidió, cuándo, desde qué IP y con qué justificación.

    No admiten ratificación: un dictamen ya ratificado (la decisión humana es
    definitiva), uno sustituido por una auditoría posterior del mismo
    documento, ni una alteración criptográfica RIE-03 (un archivo alterado no
    puede declararse conforme: debe recargarse), ni un PDF protegido con
    contraseña (PLUS-02: su contenido no pudo leerse).
    """
    dictamen = _dictamen_o_404(db, dictamen_id)
    if dictamen.revisado_por_humano:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"El dictamen ya fue ratificado por {dictamen.revisado_por} y su decisión es definitiva.",
        )
    if dictamen.origen == ORIGEN_RIE_03:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="[RIE-03] Una alteración criptográfica no admite ratificación: recargue el archivo original.",
        )
    if dictamen.origen == ORIGEN_NIVEL_3_ILEGIBLE and dto.nuevo_estatus == "CONFORME":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Un documento ilegible no puede ratificarse como conforme: su contenido no se pudo leer. "
                   "Recargue el archivo con mejor resolución.",
        )
    if dictamen.origen == ORIGEN_NIVEL_1:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="[Nivel 1] Un PDF protegido con contraseña no admite ratificación: su contenido no pudo "
                   "leerse. Cargue una versión sin contraseña de apertura.",
        )
    documento = db.query(Documento).filter(Documento.id == dictamen.documento_id).first()
    if documento and documento.estado_integridad == integridad.ALTERADO:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="[RIE-03] El documento está bloqueado por alteración de su binario; no puede ratificarse.",
        )
    ultimo = (
        db.query(DictamenAuditoria)
        .filter(DictamenAuditoria.documento_id == dictamen.documento_id)
        .order_by(DictamenAuditoria.creado_en.desc())
        .first()
    )
    if ultimo is not None and ultimo.id != dictamen.id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Existe un dictamen más reciente de este documento; ratifique el vigente.",
        )

    ip = _ip(request)
    estatus_anterior = dictamen.estatus
    dictamen.estatus = dto.nuevo_estatus
    dictamen.revisado_por_humano = True
    dictamen.justificacion_humana = dto.justificacion
    dictamen.revisado_por = dto.usuario
    dictamen.revisado_en = datetime.now(timezone.utc)
    bitacora.registrar(
        db,
        EVENTO_RATIFICACION_HUMANA,
        expediente_id=dictamen.expediente_id,
        documento_id=dictamen.documento_id,
        dictamen_id=dictamen.id,
        usuario=dto.usuario,
        ip_origen=ip,
        detalle={
            "estatus_anterior": estatus_anterior,
            "estatus_preliminar": dictamen.estatus_preliminar,
            "estatus_nuevo": dto.nuevo_estatus,
            "justificacion": dto.justificacion,
            "nivel_confianza": dictamen.nivel_confianza,
        },
    )
    expediente = db.query(Expediente).filter(Expediente.id == dictamen.expediente_id).first()
    cumplimiento.reevaluar(db, expediente, causa="RATIFICACION_HUMANA", usuario=dto.usuario, ip_origen=ip)
    db.commit()
    db.refresh(dictamen)
    return _registrado(dictamen, expediente)
