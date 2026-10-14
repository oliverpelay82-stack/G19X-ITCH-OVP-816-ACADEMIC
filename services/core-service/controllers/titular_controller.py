"""
Controlador de Titulares de Expediente.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.autorizacion import Actor, lectura, operacion
from config.database import get_db
from models.bitacora import EVENTO_ACTUALIZACION_TITULAR
from models.titular import TitularExpediente
from motor import bitacora
from schemas.titular_schema import TitularCreate, TitularResponse, TitularUpdate

router = APIRouter(prefix="/api/v1/titulares", tags=["Titulares"])


@router.post(
    "",
    response_model=TitularResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo titular",
)
def registrar_titular(titular_dto: TitularCreate, _: Actor = Depends(operacion), db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Valida si el RFC ya existe y guarda en la tabla titulares_expediente.
    """
    # 1. Verificar si ya existe el RFC
    existente = db.query(TitularExpediente).filter(TitularExpediente.rfc == titular_dto.rfc.upper()).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe un titular registrado con el RFC '{titular_dto.rfc.upper()}'.",
        )

    # 2. Crear la entidad (Modelo)
    nuevo_titular = TitularExpediente(
        rfc=titular_dto.rfc.upper(),
        razon_social=titular_dto.razon_social,
        tipo_persona=titular_dto.tipo_persona.upper(),
        categoria=titular_dto.categoria.upper(),
    )

    # 3. Guardar en base de datos
    db.add(nuevo_titular)
    db.commit()
    db.refresh(nuevo_titular)

    return nuevo_titular


@router.get(
    "",
    response_model=list[TitularResponse],
    summary="Listar todos los titulares",
)
def listar_titulares(_: Actor = Depends(lectura), db: Session = Depends(get_db)):
    """
    Equivalente a @GetMapping.
    Consulta todos los registros de la tabla titulares_expediente.
    """
    return db.query(TitularExpediente).order_by(TitularExpediente.creado_en.desc()).all()


@router.patch(
    "/{titular_id}",
    response_model=TitularResponse,
    summary="Corregir la razón social o la categoría de un titular (el RFC no se edita)",
)
def corregir_titular(titular_id: str, dto: TitularUpdate, actor: Actor = Depends(operacion),
                     db: Session = Depends(get_db)):
    """
    Corrección de datos de captura (PRD §13.1). Solo los campos que cambian
    quedan en la bitácora sellada, con su valor anterior y el nuevo (RF-27,
    RN-04); si nada cambia no hay evento. Los dictámenes emitidos no cambian
    (RN-05): el cotejo RN-03 y las auditorías nuevas usan la razón social corregida.
    """
    titular = db.query(TitularExpediente).filter(TitularExpediente.id == titular_id).first()
    if not titular:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=f"Titular con ID '{titular_id}' no encontrado."
        )
    cambios = {
        campo: {"anterior": getattr(titular, campo), "nuevo": valor}
        for campo, valor in dto.model_dump(exclude_none=True).items()
        if getattr(titular, campo) != valor
    }
    if not cambios:
        return titular
    for campo, valores in cambios.items():
        setattr(titular, campo, valores["nuevo"])
    bitacora.registrar(
        db, EVENTO_ACTUALIZACION_TITULAR, usuario=actor.email, ip_origen=actor.ip,
        detalle={"titular_id": titular.id, "rfc": titular.rfc, "cambios": cambios},
    )
    db.commit()
    db.refresh(titular)
    return titular
