"""
Asignación de usuarios a expedientes (HU-31, RF-20; PRD §5.2).

El administrador decide quién es responsable de cada expediente: el usuario de
consulta solo ve el semáforo de los suyos (``GET /expedientes/asignados``) y el
correo del RF-20 avisa a los validadores asignados. Cada cambio queda en la
bitácora sellada con la lista anterior y la nueva (RF-27).

Este router se registra antes que el de expedientes: ``/expedientes/asignados``
no debe confundirse con ``/expedientes/{expediente_id}``.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.autorizacion import Actor, cualquier_usuario, solo_admin
from config.database import get_db
from models.bitacora import EVENTO_ASIGNACION_EXPEDIENTE
from models.expediente import Expediente
from models.usuario import ExpedienteAsignacion, Usuario
from motor import bitacora, cumplimiento
from schemas.usuario_schema import AsignacionesUpdate, ExpedienteAsignadoResponse, UsuarioResumen

router = APIRouter(prefix="/api/v1/expedientes", tags=["Asignaciones"])


def _expediente_o_404(db: Session, expediente_id: str) -> Expediente:
    exp = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expediente con ID '{expediente_id}' no encontrado.")
    return exp


def _asignados(db: Session, expediente_id: str) -> list[Usuario]:
    return (
        db.query(Usuario)
        .join(ExpedienteAsignacion, ExpedienteAsignacion.usuario_id == Usuario.id)
        .filter(ExpedienteAsignacion.expediente_id == expediente_id)
        .order_by(Usuario.nombre_completo)
        .all()
    )


@router.get(
    "/asignados",
    response_model=list[ExpedienteAsignadoResponse],
    summary="Semáforo de los expedientes asignados al usuario en sesión",
)
def mis_expedientes(actor: Actor = Depends(cualquier_usuario), db: Session = Depends(get_db)):
    """
    HU-31: folio, nombre, empresa y semáforo, sin documentos, dictámenes ni reglas.
    El semáforo se recalcula como en el resto de las consultas (RN-02: un
    documento que venció hoy se refleja al consultar).
    """
    expedientes = (
        db.query(Expediente)
        .join(ExpedienteAsignacion, ExpedienteAsignacion.expediente_id == Expediente.id)
        .filter(ExpedienteAsignacion.usuario_id == actor.usuario.id)
        .order_by(Expediente.actualizado_en.desc())
        .all()
    )
    cache = cumplimiento.CacheInventarios()
    for exp in expedientes:
        cumplimiento.reevaluar(db, exp, causa="CONSULTA_EXPEDIENTES", inventario=cache.para(exp))
    db.commit()
    return [
        ExpedienteAsignadoResponse(
            id=exp.id,
            codigo_expediente=exp.codigo_expediente,
            nombre=exp.nombre,
            tipo_expediente=exp.tipo_expediente,
            razon_social=exp.titular.razon_social,
            rfc=exp.titular.rfc,
            estado_cumplimiento=exp.estado_cumplimiento,
            actualizado_en=exp.actualizado_en,
        )
        for exp in expedientes
    ]


@router.get(
    "/{expediente_id}/asignaciones",
    response_model=list[UsuarioResumen],
    summary="Usuarios asignados a un expediente",
)
def listar_asignaciones(expediente_id: str, _: Actor = Depends(solo_admin), db: Session = Depends(get_db)):
    _expediente_o_404(db, expediente_id)
    return _asignados(db, expediente_id)


@router.put(
    "/{expediente_id}/asignaciones",
    response_model=list[UsuarioResumen],
    summary="Reemplazar la lista de usuarios asignados a un expediente",
)
def asignar_usuarios(expediente_id: str, dto: AsignacionesUpdate, actor: Actor = Depends(solo_admin),
                     db: Session = Depends(get_db)):
    exp = _expediente_o_404(db, expediente_id)
    ids = list(dict.fromkeys(dto.usuario_ids))
    nuevos = db.query(Usuario).filter(Usuario.id.in_(ids)).all() if ids else []
    faltantes = set(ids) - {u.id for u in nuevos}
    if faltantes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Usuarios no encontrados: {', '.join(sorted(faltantes))}.",
        )

    anteriores = _asignados(db, expediente_id)
    antes, despues = {u.id for u in anteriores}, {u.id for u in nuevos}
    if antes == despues:
        return anteriores

    db.query(ExpedienteAsignacion).filter(
        ExpedienteAsignacion.expediente_id == expediente_id, ExpedienteAsignacion.usuario_id.in_(antes - despues)
    ).delete(synchronize_session=False)
    for usuario_id in despues - antes:
        db.add(ExpedienteAsignacion(expediente_id=expediente_id, usuario_id=usuario_id, asignado_por=actor.email))
    bitacora.registrar(
        db, EVENTO_ASIGNACION_EXPEDIENTE, expediente_id=expediente_id, usuario=actor.email, ip_origen=actor.ip,
        detalle={"codigo_expediente": exp.codigo_expediente,
                 "anteriores": sorted(u.email for u in anteriores),
                 "nuevos": sorted(u.email for u in nuevos)},
    )
    db.commit()
    return _asignados(db, expediente_id)
