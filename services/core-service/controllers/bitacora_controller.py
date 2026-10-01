"""
Controlador de la Bitácora de Auditoría (RF-27, HU-30).

Solo expone lectura: la bitácora se escribe como efecto de las operaciones del
sistema y un trigger de PostgreSQL rechaza cualquier modificación o borrado.
Cada evento va sellado en cadena (P3) y ``/verificar-cadena`` la recalcula.
P7 (PLUS-22): ``/sello-tiempo`` pide a demanda un sello RFC 3161 del último
eslabón y ``/sellos-tiempo`` los lista y entrega su token para openssl.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from config.database import get_db
from models.bitacora import BitacoraAuditoria
from models.sello_tiempo import SelloTiempo
from motor import bitacora, sello_tiempo
from schemas.dictamen_schema import (
    BitacoraResponse, SelloTiempoResponse, SolicitudSelloTiempoResponse, VerificacionCadenaResponse,
)

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


@router.post(
    "/sello-tiempo",
    response_model=SolicitudSelloTiempoResponse,
    summary="Pedir a una autoridad RFC 3161 el sello de tiempo del último eslabón (P7, PLUS-22)",
    responses={409: {"description": "El sello de tiempo está apagado (SELLO_TIEMPO_URL vacía)."},
               502: {"description": "La autoridad no respondió o su respuesta no es un sello válido."}},
)
def pedir_sello_tiempo(db: Session = Depends(get_db)):
    """
    Solo viaja la huella del último eslabón. Si ese eslabón ya es un
    SELLO_TIEMPO, no hay nada nuevo que sellar y se devuelve el vigente
    (``nuevo: false``).
    """
    try:
        registro, nuevo = sello_tiempo.sellar(db, sello_tiempo.ORIGEN_A_DEMANDA)
    except sello_tiempo.SelloTiempoApagado as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except sello_tiempo.SelloTiempoError as exc:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc)) from exc
    return {"nuevo": nuevo, "sello": sello_tiempo.resumen(registro, coincide=True)}


@router.get("/sellos-tiempo", response_model=list[SelloTiempoResponse],
            summary="Sellos de tiempo de la bitácora, del más reciente al más antiguo (P7, PLUS-22)")
def listar_sellos_tiempo(limite: int = Query(30, ge=1, le=500), db: Session = Depends(get_db)):
    sellos = db.query(SelloTiempo).order_by(SelloTiempo.secuencia.desc(), SelloTiempo.creado_en.desc()).limit(limite).all()
    eventos = {e.id: e for e in db.query(BitacoraAuditoria).filter(
        BitacoraAuditoria.id.in_([s.evento_id for s in sellos])).all()} if sellos else {}
    return [sello_tiempo.resumen(s, coincide=s.evento_id in eventos and eventos[s.evento_id].hash_evento == s.hash_evento)
            for s in sellos]


@router.get(
    "/sellos-tiempo/{sello_id}/token",
    response_class=Response,
    summary="Token DER del sello, para verificarlo con openssl ts -verify -token_in (P7, PLUS-22)",
    responses={200: {"content": {"application/octet-stream": {}}}},
)
def token_sello_tiempo(sello_id: str, db: Session = Depends(get_db)):
    s = db.get(SelloTiempo, sello_id)
    if not s:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Sello de tiempo '{sello_id}' no encontrado.")
    return Response(
        content=s.token_der, media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="sello_tiempo_{s.secuencia}.tst"'},
    )
