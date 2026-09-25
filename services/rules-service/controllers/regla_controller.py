"""
Controlador de Reglas de Validación.
Equivalente a @RestController @RequestMapping("/api/v1/reglas") en Spring Boot.
"""
from dataclasses import asdict
from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.regla import Regla
from motor import obligatorios, vigencia
from schemas.regla_schema import (
    DocumentoObligatorioResponse,
    EvaluacionVigenciaRequest,
    EvaluacionVigenciaResponse,
    ReglaCreate,
    ReglaResponse,
)

router = APIRouter(prefix="/api/v1/reglas", tags=["Reglas de Validación"])


@router.post(
    "/evaluar-vigencia",
    response_model=EvaluacionVigenciaResponse,
    summary="Evaluar la vigencia de un documento contra las reglas RCV activas (Nivel 2)",
)
def evaluar_vigencia(peticion: EvaluacionVigenciaRequest, db: Session = Depends(get_db)):
    """
    Aplica de forma determinista las reglas Cronológicas y de Vigencia activas:
    la vigencia mandatoria (RCV-01, días para el vencimiento) y la caducidad
    estricta por tipo de documento (p. ej. RCV-02: comprobante de domicilio con
    antigüedad máxima de 90 días naturales desde su emisión). Una regla pausada
    en el catálogo deja de aplicarse.
    """
    reglas = db.query(Regla).filter(Regla.familia_regla == "RCV", Regla.activo.is_(True)).all()
    resultado = vigencia.evaluar(
        reglas,
        tipo_documento=peticion.tipo_documento,
        fecha_emision=peticion.fecha_emision,
        fecha_vencimiento=peticion.fecha_vencimiento,
        fecha_referencia=peticion.fecha_referencia or date.today(),
    )
    return asdict(resultado)


@router.get(
    "/documentos-obligatorios",
    response_model=list[DocumentoObligatorioResponse],
    summary="Documentos que exige el expediente según las reglas RIE activas (HU-09)",
)
def listar_documentos_obligatorios(db: Session = Depends(get_db)):
    """
    Deriva el inventario obligatorio del expediente de las reglas activas de la
    familia RIE que declaran un tipo de documento obligatorio. El core-service
    lo consulta para calcular la completitud (RIE-01) en lugar de fijarla en
    su código.
    """
    reglas = db.query(Regla).filter(Regla.familia_regla == "RIE", Regla.activo.is_(True)).all()
    return [asdict(d) for d in obligatorios.documentos_obligatorios(reglas)]


@router.post(
    "",
    response_model=ReglaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta una nueva regla en el catálogo (RDS-01)",
)
def crear_regla(regla_dto: ReglaCreate, db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Valida que el código de la regla no exista y la guarda en reglas_validacion.
    """
    existente = db.query(Regla).filter(Regla.codigo_regla == regla_dto.codigo_regla.upper()).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Ya existe una regla registrada con el código '{regla_dto.codigo_regla.upper()}'.",
        )

    nueva_regla = Regla(
        codigo_regla=regla_dto.codigo_regla.upper(),
        nombre_regla=regla_dto.nombre_regla,
        familia_regla=regla_dto.familia_regla.upper(),
        descripcion=regla_dto.descripcion,
        severidad=regla_dto.severidad.upper(),
        accion=regla_dto.accion,
        tipo_documento=regla_dto.tipo_documento.upper() if regla_dto.tipo_documento else None,
        documento_obligatorio=regla_dto.documento_obligatorio,
        dias_maximos_vigencia=regla_dto.dias_maximos_vigencia,
        activo=regla_dto.activo,
    )

    db.add(nueva_regla)
    db.commit()
    db.refresh(nueva_regla)

    return nueva_regla


@router.get(
    "",
    response_model=list[ReglaResponse],
    summary="Listar reglas del catálogo, con filtros opcionales",
)
def listar_reglas(
    familia_regla: Optional[str] = None,
    activo: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """
    Equivalente a @GetMapping.
    Consulta reglas_validacion, permitiendo filtrar por familia (RIE, RCV,
    RSC, RDS) y por bandera de activación.
    """
    query = db.query(Regla)
    if familia_regla is not None:
        query = query.filter(Regla.familia_regla == familia_regla.upper())
    if activo is not None:
        query = query.filter(Regla.activo == activo)
    return query.order_by(Regla.codigo_regla.asc()).all()


@router.get(
    "/{regla_id}",
    response_model=ReglaResponse,
    summary="Consultar una regla del catálogo por su ID",
)
def obtener_regla_por_id(regla_id: str, db: Session = Depends(get_db)):
    """Retorna los datos de una regla específica del catálogo."""
    regla = db.query(Regla).filter(Regla.id == regla_id).first()
    if not regla:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regla con ID '{regla_id}' no encontrada.",
        )
    return regla


@router.patch(
    "/{regla_id}/activo",
    response_model=ReglaResponse,
    summary="Activar o desactivar una regla del catálogo",
)
def cambiar_estado_regla(regla_id: str, activo: bool, db: Session = Depends(get_db)):
    """
    Equivalente a @PatchMapping.
    Alterna la bandera de alta/baja lógica de una regla sin eliminarla (RN-04).
    """
    regla = db.query(Regla).filter(Regla.id == regla_id).first()
    if not regla:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Regla con ID '{regla_id}' no encontrada.",
        )

    regla.activo = activo
    db.commit()
    db.refresh(regla)

    return regla
