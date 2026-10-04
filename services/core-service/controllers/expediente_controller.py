"""
Controlador de Expedientes Documentales.

El estado de cumplimiento que devuelven estas rutas es el consolidado del
semáforo (``motor/cumplimiento.py``): se recalcula en cada consulta contra el
catálogo de reglas vigente y los dictámenes persistidos, de modo que pausar una
regla, ratificar un dictamen o el simple paso del tiempo (un documento que
vence) se reflejan de inmediato.
"""
from datetime import date, datetime, time, timedelta
from dataclasses import asdict
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config.catalogo import TIPOS_EXPEDIENTE
from config.database import get_db
from models.bitacora import EVENTO_ACTUALIZACION_EXPEDIENTE, EVENTO_APERTURA_EXPEDIENTE
from models.titular import TitularExpediente
from models.expediente import Expediente
from motor import bitacora, cumplimiento
from schemas.expediente_schema import (
    EvaluacionExpedienteResponse,
    ExpedienteCreate,
    ExpedienteResponse,
    ExpedienteUpdate,
)
from schemas.titular_schema import TitularResponse

router = APIRouter(prefix="/api/v1/expedientes", tags=["Expedientes"])


def _respuesta(exp: Expediente, evaluacion: cumplimiento.EvaluacionExpediente | None) -> ExpedienteResponse:
    return ExpedienteResponse(
        id=exp.id,
        titular_id=exp.titular_id,
        codigo_expediente=exp.codigo_expediente,
        tipo_expediente=exp.tipo_expediente,
        nombre=exp.nombre,
        estado_cumplimiento=exp.estado_cumplimiento,
        porcentaje_completitud=float(exp.porcentaje_completitud),
        creado_en=exp.creado_en,
        actualizado_en=exp.actualizado_en,
        titular=TitularResponse.model_validate(exp.titular) if exp.titular else None,
        evaluacion=EvaluacionExpedienteResponse.model_validate(asdict(evaluacion)) if evaluacion else None,
    )


def _inicio_del_dia(dia: date) -> datetime:
    """
    Inicio del día del calendario local del servidor, con su zona horaria.
    creado_en es TIMESTAMP sin zona y PostgreSQL lo guarda en la zona de su
    sesión (America/Mexico_City en local, UTC en el contenedor); al comparar
    contra un valor con zona, PostgreSQL convierte con esa misma zona, así que
    el filtro es correcto en ambos despliegues.
    """
    return datetime.combine(dia, time.min).astimezone()


def consultar_expedientes(
    db: Session,
    *,
    q: Optional[str] = None,
    tipo_expediente: Optional[str] = None,
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
) -> list[Expediente]:
    """Búsqueda y filtrado de expedientes (RF-05, HU-04)."""
    query = db.query(Expediente).join(TitularExpediente, Expediente.titular_id == TitularExpediente.id)
    if q and q.strip():
        patron = f"%{q.strip()}%"
        query = query.filter(or_(
            Expediente.codigo_expediente.ilike(patron),
            Expediente.nombre.ilike(patron),
            TitularExpediente.razon_social.ilike(patron),
            TitularExpediente.rfc.ilike(patron),
        ))
    if tipo_expediente:
        tipo = tipo_expediente.strip().upper()
        if tipo not in TIPOS_EXPEDIENTE:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Tipo de expediente no reconocido: '{tipo_expediente}'. "
                       f"Valores válidos: {', '.join(TIPOS_EXPEDIENTE)}.",
            )
        query = query.filter(Expediente.tipo_expediente == tipo)
    if desde:
        query = query.filter(Expediente.creado_en >= _inicio_del_dia(desde))
    if hasta:
        query = query.filter(Expediente.creado_en < _inicio_del_dia(hasta + timedelta(days=1)))
    return query.order_by(Expediente.actualizado_en.desc()).all()


def evaluar_lista(
    db: Session, expedientes: list[Expediente], causa: str
) -> list[tuple[Expediente, cumplimiento.EvaluacionExpediente]]:
    """Reevalúa cada expediente consultando una sola vez el catálogo de cada tipo."""
    cache = cumplimiento.CacheInventarios()
    resultado = []
    for exp in expedientes:
        evaluacion = cumplimiento.reevaluar(db, exp, causa=causa, inventario=cache.para(exp))
        resultado.append((exp, evaluacion))
    db.commit()
    return resultado


@router.post(
    "",
    response_model=ExpedienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aperturar un nuevo expediente para un titular",
)
def crear_expediente(dto: ExpedienteCreate, request: Request, db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Crea un expediente vinculado a un titular existente, con su clasificación
    temática (RF-01). Nace sin documentos, así que su semáforo inicial refleja
    los obligatorios faltantes del catálogo de su tipo (RIE-01, RF-06).
    """
    # 1. Validar que el titular exista
    titular = db.query(TitularExpediente).filter(TitularExpediente.id == dto.titular_id).first()
    if not titular:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Titular con ID '{dto.titular_id}' no encontrado en el sistema.",
        )

    # 2. Generar código legible de expediente (ej. EXP-PLU-202609131745). Si el
    #    titular ya abrió otro en el mismo minuto, se agrega un consecutivo.
    prefijo_rfc = titular.rfc[:4]
    estampa_tiempo = datetime.now().strftime("%Y%m%d%H%M")
    codigo = f"EXP-{prefijo_rfc}-{estampa_tiempo}"
    consecutivo = 1
    while db.query(Expediente.id).filter(Expediente.codigo_expediente == codigo).first():
        consecutivo += 1
        codigo = f"EXP-{prefijo_rfc}-{estampa_tiempo}-{consecutivo}"

    # 3. Crear el modelo
    nuevo_expediente = Expediente(
        titular_id=titular.id,
        codigo_expediente=codigo,
        tipo_expediente=dto.tipo_expediente.value,
        nombre=(dto.nombre or "").strip() or None,
        estado_cumplimiento="EN_REVISION",
        porcentaje_completitud=0.00,
    )
    db.add(nuevo_expediente)
    db.flush()

    ip = request.client.host if request.client else None
    bitacora.registrar(
        db,
        EVENTO_APERTURA_EXPEDIENTE,
        expediente_id=nuevo_expediente.id,
        usuario="OPERADOR",
        ip_origen=ip,
        detalle={
            "codigo_expediente": codigo,
            "tipo_expediente": nuevo_expediente.tipo_expediente,
            "nombre": nuevo_expediente.nombre,
            "titular_id": titular.id,
            "rfc_titular": titular.rfc,
        },
    )
    evaluacion = cumplimiento.reevaluar(db, nuevo_expediente, causa="APERTURA_EXPEDIENTE", ip_origen=ip)
    db.commit()
    db.refresh(nuevo_expediente)
    return _respuesta(nuevo_expediente, evaluacion)


@router.get(
    "",
    response_model=list[ExpedienteResponse],
    summary="Listar y buscar expedientes (por texto, tipo, fecha de apertura y estatus)",
)
def listar_expedientes(
    q: Optional[str] = Query(None, description="Folio, nombre del expediente, razón social o RFC"),
    tipo_expediente: Optional[str] = Query(None, description="JURIDICO, CORPORATIVO o REGULATORIO"),
    estado: Optional[str] = Query(None, description="CONFORME, EN_REVISION o NO_CONFORME"),
    desde: Optional[date] = Query(None, description="Apertura a partir de esta fecha (inclusive)"),
    hasta: Optional[date] = Query(None, description="Apertura hasta esta fecha (inclusive)"),
    db: Session = Depends(get_db),
):
    """
    Equivalente a @GetMapping (RF-05, HU-04).
    Retorna los expedientes con su titular y su semáforo consolidado. El
    estatus se filtra después de reevaluar, porque puede cambiar con la
    consulta (un documento que venció hoy, una regla pausada).
    """
    expedientes = consultar_expedientes(db, q=q, tipo_expediente=tipo_expediente, desde=desde, hasta=hasta)
    evaluados = evaluar_lista(db, expedientes, causa="CONSULTA_EXPEDIENTES")
    if estado:
        evaluados = [(exp, ev) for exp, ev in evaluados if exp.estado_cumplimiento == estado.strip().upper()]
    return [_respuesta(exp, evaluacion) for exp, evaluacion in evaluados]


@router.get(
    "/{expediente_id}",
    response_model=ExpedienteResponse,
    summary="Consultar un expediente con su estado consolidado de cumplimiento",
)
def obtener_expediente_por_id(expediente_id: str, db: Session = Depends(get_db)):
    """
    Retorna el expediente con el desglose del semáforo: documentos obligatorios
    y faltantes, anexos exigidos, estado y vigencia de cada documento, motivos
    del estado y alertas con su recomendación.
    """
    exp = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expediente con ID '{expediente_id}' no encontrado.",
        )
    evaluacion = cumplimiento.reevaluar(db, exp, causa="CONSULTA_EXPEDIENTE")
    db.commit()
    return _respuesta(exp, evaluacion)


@router.patch(
    "/{expediente_id}",
    response_model=ExpedienteResponse,
    summary="Renombrar un expediente (el tipo no se edita)",
)
def renombrar_expediente(expediente_id: str, dto: ExpedienteUpdate, request: Request, db: Session = Depends(get_db)):
    """
    Corrección del nombre descriptivo (RF-01, PRD §13.1). El cambio queda en la
    bitácora sellada con el nombre anterior y el nuevo (RF-27, RN-04) y aparece
    en el historial del expediente; si el nombre no cambia no hay evento.
    """
    exp = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Expediente con ID '{expediente_id}' no encontrado."
        )
    nombre = " ".join((dto.nombre or "").split()) or None
    if nombre != exp.nombre:
        anterior, exp.nombre = exp.nombre, nombre
        bitacora.registrar(
            db, EVENTO_ACTUALIZACION_EXPEDIENTE, expediente_id=exp.id, usuario="OPERADOR",
            ip_origen=request.client.host if request.client else None,
            detalle={"codigo_expediente": exp.codigo_expediente,
                     "cambios": {"nombre": {"anterior": anterior, "nuevo": nombre}}},
        )
        db.commit()
        db.refresh(exp)
    return _respuesta(exp, None)
