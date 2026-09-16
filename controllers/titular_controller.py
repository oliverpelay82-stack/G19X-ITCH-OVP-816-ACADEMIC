"""
Controlador de Titulares de Expediente.
Equivalente a @RestController @RequestMapping("/api/v1/titulares") en Spring Boot.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.titular import TitularExpediente
from schemas.titular_schema import TitularCreate, TitularResponse

router = APIRouter(prefix="/api/v1/titulares", tags=["Titulares"])


@router.post(
    "",
    response_model=TitularResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo titular en MySQL",
)
def registrar_titular(titular_dto: TitularCreate, db: Session = Depends(get_db)):
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
    summary="Listar todos los titulares desde MySQL",
)
def listar_titulares(db: Session = Depends(get_db)):
    """
    Equivalente a @GetMapping.
    Consulta todos los registros de la tabla titulares_expediente.
    """
    return db.query(TitularExpediente).order_by(TitularExpediente.creado_en.desc()).all()
