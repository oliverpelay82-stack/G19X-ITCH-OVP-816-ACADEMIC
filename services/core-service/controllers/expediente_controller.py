"""
Controlador de Expedientes Documentales.
Equivalente a @RestController @RequestMapping("/api/v1/expedientes") en Spring Boot.

El estado de cumplimiento que devuelven estas rutas es el consolidado del
semáforo (``motor/cumplimiento.py``): se recalcula en cada consulta contra el
catálogo de reglas vigente y los dictámenes persistidos, de modo que pausar una
regla o ratificar un dictamen se refleja de inmediato.
"""
from datetime import datetime
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from clients import rules_client
from config.database import get_db
from models.bitacora import EVENTO_APERTURA_EXPEDIENTE
from models.titular import TitularExpediente
from models.expediente import Expediente
from motor import bitacora, cumplimiento
from schemas.expediente_schema import EvaluacionExpedienteResponse, ExpedienteCreate, ExpedienteResponse
from schemas.titular_schema import TitularResponse

router = APIRouter(prefix="/api/v1/expedientes", tags=["Expedientes"])


def _respuesta(exp: Expediente, evaluacion: cumplimiento.EvaluacionExpediente | None) -> ExpedienteResponse:
    return ExpedienteResponse(
        id=exp.id,
        titular_id=exp.titular_id,
        codigo_expediente=exp.codigo_expediente,
        estado_cumplimiento=exp.estado_cumplimiento,
        porcentaje_completitud=float(exp.porcentaje_completitud),
        actualizado_en=exp.actualizado_en,
        titular=TitularResponse.model_validate(exp.titular) if exp.titular else None,
        evaluacion=EvaluacionExpedienteResponse.model_validate(asdict(evaluacion)) if evaluacion else None,
    )


@router.post(
    "",
    response_model=ExpedienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aperturar un nuevo expediente para un titular",
)
def crear_expediente(dto: ExpedienteCreate, request: Request, db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Crea un expediente vinculado a un titular existente. Nace sin documentos,
    así que su semáforo inicial refleja los obligatorios faltantes (RIE-01).
    """
    # 1. Validar que el titular exista
    titular = db.query(TitularExpediente).filter(TitularExpediente.id == dto.titular_id).first()
    if not titular:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Titular con ID '{dto.titular_id}' no encontrado en el sistema.",
        )

    # 2. Generar código legible de expediente (ej. EXP-PLU-202609131745)
    prefijo_rfc = titular.rfc[:4]
    estampa_tiempo = datetime.now().strftime("%Y%m%d%H%M")
    codigo = f"EXP-{prefijo_rfc}-{estampa_tiempo}"

    # 3. Crear el modelo
    nuevo_expediente = Expediente(
        titular_id=titular.id,
        codigo_expediente=codigo,
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
        detalle={"codigo_expediente": codigo, "titular_id": titular.id, "rfc_titular": titular.rfc},
    )
    evaluacion = cumplimiento.reevaluar(db, nuevo_expediente, causa="APERTURA_EXPEDIENTE", ip_origen=ip)
    db.commit()
    db.refresh(nuevo_expediente)
    return _respuesta(nuevo_expediente, evaluacion)


@router.get(
    "",
    response_model=list[ExpedienteResponse],
    summary="Listar todos los expedientes documentales",
)
def listar_expedientes(db: Session = Depends(get_db)):
    """
    Equivalente a @GetMapping.
    Retorna la lista de expedientes con su titular y su semáforo consolidado.
    El catálogo de obligatorios se consulta una sola vez para toda la lista.
    """
    expedientes = db.query(Expediente).order_by(Expediente.actualizado_en.desc()).all()
    inventario = rules_client.obtener_documentos_obligatorios() if expedientes else None
    resultado = []
    for exp in expedientes:
        evaluacion = cumplimiento.reevaluar(db, exp, causa="CONSULTA_EXPEDIENTES", inventario=inventario)
        resultado.append((exp, evaluacion))
    db.commit()
    return [_respuesta(exp, evaluacion) for exp, evaluacion in resultado]


@router.get(
    "/{expediente_id}",
    response_model=ExpedienteResponse,
    summary="Consultar un expediente con su estado consolidado de cumplimiento",
)
def obtener_expediente_por_id(expediente_id: str, db: Session = Depends(get_db)):
    """
    Retorna el expediente con el desglose del semáforo: documentos obligatorios
    y faltantes, estado de cada documento vigente y los motivos del estado.
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
