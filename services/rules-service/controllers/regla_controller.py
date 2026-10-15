"""
Controlador de Reglas de Validación.
"""
import json
from dataclasses import asdict
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from config import seguridad, zona_horaria
from config.autorizacion import Actor, lectura_o_sistema, operacion, solo_admin
from config.database import get_db
from models.regla import Regla
from motor import obligatorios, version_catalogo, vigencia
from schemas.regla_schema import (
    DocumentoObligatorioResponse,
    EvaluacionVigenciaRequest,
    EvaluacionVigenciaResponse,
    ReglaCreate,
    ReglaResponse,
    TipoDocumentoDeclaradoResponse,
)

router = APIRouter(prefix="/api/v1/reglas", tags=["Reglas de Validación"])


@router.post(
    "/evaluar-vigencia",
    dependencies=[Depends(lectura_o_sistema)],
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
        fecha_referencia=peticion.fecha_referencia or zona_horaria.hoy(),
    )
    return asdict(resultado)


@router.get(
    "/documentos-obligatorios",
    dependencies=[Depends(lectura_o_sistema)],
    response_model=list[DocumentoObligatorioResponse],
    summary="Documentos y anexos que exige un tipo de expediente según las reglas RIE activas (HU-09, HU-10)",
)
def listar_documentos_obligatorios(
    response: Response,
    tipo_expediente: Optional[str] = Query(
        None, description="JURIDICO, CORPORATIVO o REGULATORIO; sin él se devuelven las reglas de todos los tipos"
    ),
    db: Session = Depends(get_db),
):
    """
    Deriva el inventario obligatorio del expediente de las reglas activas de la
    familia RIE que declaran un tipo de documento obligatorio. El core-service
    lo consulta para calcular la completitud (RIE-01) en lugar de fijarla en
    su código. Los registros con ``documento_principal`` son anexos (RIE-02):
    solo se exigen cuando el expediente contiene ese documento principal.
    """
    if tipo_expediente and tipo_expediente.strip().upper() not in obligatorios.TIPOS_EXPEDIENTE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Tipo de expediente no reconocido: '{tipo_expediente}'. "
                   f"Valores válidos: {', '.join(obligatorios.TIPOS_EXPEDIENTE)}.",
        )
    reglas = db.query(Regla).filter(Regla.familia_regla == "RIE", Regla.activo.is_(True)).all()
    # M6 y M7: el core recibe con el inventario la versión del catálogo y la de las
    # reglas de cada tipo de documento, sin otra consulta.
    todas = db.query(Regla).all()
    response.headers[version_catalogo.CABECERA] = version_catalogo.calcular(todas)
    response.headers[version_catalogo.CABECERA_POR_TIPO] = json.dumps(
        version_catalogo.por_tipo(todas), separators=(",", ":"))
    return [asdict(d) for d in obligatorios.documentos_obligatorios(reglas, tipo_expediente)]


@router.post(
    "",
    response_model=ReglaResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta una nueva regla en el catálogo (RDS-01)",
)
def crear_regla(regla_dto: ReglaCreate, actor: Actor = Depends(operacion), db: Session = Depends(get_db)):
    """
    Equivalente a @PostMapping.
    Valida que el código de la regla no exista y la guarda en reglas_validacion.

    Módulo 7 (PRD §5.1): el administrador da de alta reglas de cualquier familia;
    el validador, solo de la familia RDS (un tipo de documento nuevo con su
    criterio, RDS-01: «el administrador o validador»).
    """
    if actor.rol != seguridad.ADMIN and regla_dto.familia_regla.upper() != "RDS":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Su rol solo puede dar de alta tipos de documento nuevos (reglas dinámicas).",
        )
    principal = regla_dto.documento_principal.strip().upper() if regla_dto.documento_principal else None
    tipo_documento = regla_dto.tipo_documento.strip().upper() if regla_dto.tipo_documento else None
    if principal and not tipo_documento:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Una regla de anexo (RIE-02) debe indicar el tipo de documento del anexo.",
        )
    if principal and principal == tipo_documento:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Un documento no puede ser anexo de sí mismo.",
        )

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
        tipo_documento=tipo_documento,
        documento_obligatorio=regla_dto.documento_obligatorio,
        dias_maximos_vigencia=regla_dto.dias_maximos_vigencia,
        activo=regla_dto.activo,
        tipo_expediente=regla_dto.tipo_expediente,
        documento_principal=principal,
    )

    db.add(nueva_regla)
    db.commit()
    db.refresh(nueva_regla)

    return nueva_regla


@router.get(
    "",
    dependencies=[Depends(lectura_o_sistema)],
    response_model=list[ReglaResponse],
    summary="Listar reglas del catálogo, con filtros opcionales",
)
def listar_reglas(
    familia_regla: Optional[str] = None,
    activo: Optional[bool] = None,
    tipo_expediente: Optional[str] = Query(None, description="Reglas de ese tipo de expediente más las generales"),
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
    if tipo_expediente:
        query = query.filter(or_(Regla.tipo_expediente.is_(None), Regla.tipo_expediente == tipo_expediente.upper()))
    return query.order_by(Regla.codigo_regla.asc()).all()


@router.get(
    "/version",
    dependencies=[Depends(lectura_o_sistema)],
    summary="Versión del catálogo de reglas (huella de todas las reglas, activas y pausadas)",
)
def version_del_catalogo(
    tipo_documento: Optional[str] = Query(None, description="M7: también la versión de las reglas de ese tipo"),
    db: Session = Depends(get_db),
):
    """
    M6 (ESTADO_DEL_DESARROLLO §6.6): cada dictamen guarda esta versión para saber con qué
    catálogo se emitió aunque después se pause o cambie una regla. M7 (ESTADO_DEL_DESARROLLO §6.7):
    con ``tipo_documento``, también la de las reglas que deciden su dictamen.
    """
    reglas = db.query(Regla).all()
    respuesta = {
        "version_catalogo": version_catalogo.calcular(reglas),
        "reglas": len(reglas),
        "reglas_activas": sum(1 for r in reglas if r.activo),
    }
    if tipo_documento:
        respuesta["version_reglas_tipo"] = version_catalogo.de_tipo(reglas, tipo_documento)
    return respuesta


@router.get(
    "/tipos-documento",
    dependencies=[Depends(lectura_o_sistema)],
    response_model=list[TipoDocumentoDeclaradoResponse],
    summary="Tipos de documento declarados por reglas dinámicas (RF-09, RDS-01)",
)
def tipos_documento_declarados(db: Session = Depends(get_db)):
    """
    RF-09: un tipo de documento nuevo se declara con una regla RDS (RDS-01) cuyo
    nombre es el del tipo y cuya descripción es el criterio para la IA (RDS-02).
    Se listan todos los tipos que aparecen en reglas RDS, con el nombre de la más
    antigua; el core descarta los de su catálogo base y admite en la carga solo
    los activos.
    """
    reglas = db.query(Regla).filter(Regla.familia_regla == "RDS", Regla.tipo_documento.isnot(None)).all()
    return agrupar_tipos_declarados(reglas)


def agrupar_tipos_declarados(reglas) -> list[TipoDocumentoDeclaradoResponse]:
    """Un tipo por código: nombre y expediente de la regla RDS más antigua; activo si alguna lo está."""
    tipos: dict[str, TipoDocumentoDeclaradoResponse] = {}
    for r in sorted(reglas, key=lambda r: (str(r.creado_en), r.codigo_regla)):
        if r.familia_regla != "RDS" or not r.tipo_documento:
            continue
        clave = r.tipo_documento.strip().upper()
        if clave not in tipos:
            tipos[clave] = TipoDocumentoDeclaradoResponse(
                tipo_documento=clave, nombre=r.nombre_regla, activo=r.activo,
                tipo_expediente=r.tipo_expediente, codigo_regla=r.codigo_regla,
            )
        elif r.activo:
            tipos[clave].activo = True
    return list(tipos.values())


@router.get(
    "/{regla_id}",
    dependencies=[Depends(lectura_o_sistema)],
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
    dependencies=[Depends(solo_admin)],
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
