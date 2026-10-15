"""
Configuración de operación desde la interfaz (HU-14, RF-17;
docs/uml/hu14-actividad-umbrales-vencimiento.puml).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config.autorizacion import Actor, lectura, solo_admin
from config.database import get_db
from motor import umbrales
from schemas.configuracion_schema import UmbralesResponse, UmbralesUpdate

router = APIRouter(prefix="/api/v1/configuracion", tags=["Configuración"])


@router.get(
    "/umbrales-vencimiento",
    response_model=UmbralesResponse,
    summary="Días de anticipación de las alertas de vencimiento (por omisión 30, 15 y 5)",
)
def obtener_umbrales(_: Actor = Depends(lectura), db: Session = Depends(get_db)):
    return umbrales.estado(db)


@router.put(
    "/umbrales-vencimiento",
    response_model=UmbralesResponse,
    summary="Cambiar los días de anticipación de las alertas de vencimiento (solo el administrador)",
)
def cambiar_umbrales(dto: UmbralesUpdate, actor: Actor = Depends(solo_admin), db: Session = Depends(get_db)):
    """
    Tres enteros de 1 a 365, de mayor a menor y distintos. El cambio queda en la
    bitácora sellada con el valor anterior y el nuevo (RF-27); si no cambia nada,
    no hay evento. Surte efecto en la siguiente evaluación de cada expediente.
    """
    motivo = umbrales.problema(dto.umbrales)
    if motivo:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=motivo)
    if umbrales.guardar(db, dto.umbrales, usuario=actor.email, ip_origen=actor.ip):
        db.commit()
    return umbrales.estado(db)
