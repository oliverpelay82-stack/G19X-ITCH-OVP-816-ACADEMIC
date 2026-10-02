"""
Controlador de la Bitácora de Auditoría (RF-27, HU-30).

Solo expone lectura: la bitácora se escribe como efecto de las operaciones del
sistema y un trigger de PostgreSQL rechaza cualquier modificación o borrado.
Cada evento va sellado en cadena (P3) y ``/verificar-cadena`` la recalcula.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from models.bitacora import BitacoraAuditoria
from motor import bitacora
from schemas.dictamen_schema import BitacoraResponse, VerificacionCadenaResponse

router = APIRouter(prefix="/api/v1/bitacora", tags=["Bitácora de Auditoría"])


@router.get("", response_model=list[BitacoraResponse], summary="Consultar la bitácora, del evento más reciente al más antiguo")
def consultar_bitacora(
    expediente_id: Optional[str] = None,
    documento_id: Optional[str] = None,
    evento: Optional[str] = None,
    limite: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
):
    query = db.query(BitacoraAuditoria)
    if expediente_id:
        query = query.filter(BitacoraAuditoria.expediente_id == expediente_id)
    if documento_id:
        query = query.filter(BitacoraAuditoria.documento_id == documento_id)
    if evento:
        query = query.filter(BitacoraAuditoria.evento == evento.upper())
    return (
        query.order_by(BitacoraAuditoria.creado_en.desc(), BitacoraAuditoria.secuencia.desc().nulls_last())
        .limit(limite)
        .all()
    )


@router.get(
    "/verificar-cadena",
    response_model=VerificacionCadenaResponse,
    summary="Recalcular la cadena sellada de la bitácora (P3, PLUS-05)",
)
def verificar_cadena(db: Session = Depends(get_db)):
    """
    Recalcula el hash y el enlace de cada evento sellado, la huella del
    historial previo contra la del génesis y detecta eventos sin sellar
    insertados después. No escribe nada.
    """
    return bitacora.verificar_cadena(db)
