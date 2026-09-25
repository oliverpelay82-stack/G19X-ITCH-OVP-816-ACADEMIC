"""
Controlador de la Bitácora de Auditoría (RF-27, HU-30).

Solo expone lectura: la bitácora se escribe como efecto de las operaciones del
sistema y un trigger de PostgreSQL rechaza cualquier modificación o borrado.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from models.bitacora import BitacoraAuditoria
from schemas.dictamen_schema import BitacoraResponse

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
    return query.order_by(BitacoraAuditoria.creado_en.desc()).limit(limite).all()
