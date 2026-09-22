"""
Controlador de Expedientes Documentales.
Equivalente a @RestController @RequestMapping("/api/v1/expedientes") en Spring Boot.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.titular import TitularExpediente
from models.expediente import Expediente
from schemas.expediente_schema import ExpedienteCreate, ExpedienteResponse
from schemas.titular_schema import TitularResponse

router = APIRouter(prefix="/api/v1/expedientes", tags=["Expedientes"])


@router.post(
    "",
    response_model=ExpedienteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Aperturar un nuevo expediente para un titular",
)
def crear_expediente(dto: ExpedienteCreate, db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Crea un expediente vinculado a un titular existente.
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
    db.commit()
    db.refresh(nuevo_expediente)

    return ExpedienteResponse(
        id=nuevo_expediente.id,
        titular_id=nuevo_expediente.titular_id,
        codigo_expediente=nuevo_expediente.codigo_expediente,
        estado_cumplimiento=nuevo_expediente.estado_cumplimiento,
        porcentaje_completitud=float(nuevo_expediente.porcentaje_completitud),
        actualizado_en=nuevo_expediente.actualizado_en,
        titular=TitularResponse.model_validate(titular),
    )


@router.get(
    "",
    response_model=list[ExpedienteResponse],
    summary="Listar todos los expedientes documentales",
)
def listar_expedientes(db: Session = Depends(get_db)):
    """
    Equivalente a @GetMapping.
    Retorna la lista de expedientes con su titular vinculado.
    """
    expedientes = db.query(Expediente).order_by(Expediente.actualizado_en.desc()).all()
    resultado = []
    for exp in expedientes:
        resultado.append(
            ExpedienteResponse(
                id=exp.id,
                titular_id=exp.titular_id,
                codigo_expediente=exp.codigo_expediente,
                estado_cumplimiento=exp.estado_cumplimiento,
                porcentaje_completitud=float(exp.porcentaje_completitud),
                actualizado_en=exp.actualizado_en,
                titular=TitularResponse.model_validate(exp.titular) if exp.titular else None,
            )
        )
    return resultado


@router.get(
    "/{expediente_id}",
    response_model=ExpedienteResponse,
    summary="Consultar un expediente documental por su ID",
)
def obtener_expediente_por_id(expediente_id: str, db: Session = Depends(get_db)):
    """Retorna los datos de un expediente específico, incluyendo titular y estado de cumplimiento."""
    exp = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not exp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Expediente con ID '{expediente_id}' no encontrado.",
        )
    return ExpedienteResponse(
        id=exp.id,
        titular_id=exp.titular_id,
        codigo_expediente=exp.codigo_expediente,
        estado_cumplimiento=exp.estado_cumplimiento,
        porcentaje_completitud=float(exp.porcentaje_completitud),
        actualizado_en=exp.actualizado_en,
        titular=TitularResponse.model_validate(exp.titular) if exp.titular else None,
    )
