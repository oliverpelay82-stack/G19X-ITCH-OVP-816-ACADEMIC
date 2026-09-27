"""
Controlador de Reportes de Auditoría (Módulo 6: RF-22, RF-23, RF-24; HU-28, HU-29).

  * ``GET /api/v1/reportes/expedientes/{id}?formato=pdf|xlsx`` — dictamen formal
    de cumplimiento de un expediente.
  * ``GET /api/v1/reportes/cumplimiento?formato=pdf|xlsx`` — reporte global.

Cada exportación queda en la bitácora (EXPORTACION_REPORTE): qué se exportó,
en qué formato y desde qué IP.
"""
from datetime import datetime
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session

from config.database import get_db
from controllers.expediente_controller import consultar_expedientes, evaluar_lista
from models.bitacora import EVENTO_EXPORTACION_REPORTE, BitacoraAuditoria
from models.expediente import Expediente
from motor import bitacora, cumplimiento, reportes

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes de Auditoría"])

Formato = Literal["pdf", "xlsx"]


def _archivo(contenido: bytes, formato: str, nombre: str) -> Response:
    return Response(
        content=contenido,
        media_type=reportes.FORMATOS[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}.{formato}"'},
    )


def _registrar(db: Session, request: Request, detalle: dict, expediente_id: str | None = None) -> None:
    bitacora.registrar(
        db, EVENTO_EXPORTACION_REPORTE, expediente_id=expediente_id, usuario="OPERADOR",
        ip_origen=request.client.host if request.client else None, detalle=detalle,
    )
    db.commit()


@router.get(
    "/expedientes/{expediente_id}",
    summary="Dictamen formal de cumplimiento de un expediente, en PDF o Excel (RF-23, RF-24)",
    response_class=Response,
    responses={200: {"content": {v: {} for v in reportes.FORMATOS.values()}}},
)
def reporte_expediente(
    expediente_id: str,
    request: Request,
    formato: Formato = Query("pdf"),
    db: Session = Depends(get_db),
):
    exp = db.query(Expediente).filter(Expediente.id == expediente_id).first()
    if not exp:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Expediente con ID '{expediente_id}' no encontrado.")
    evaluacion = cumplimiento.reevaluar(db, exp, causa="REPORTE_EXPEDIENTE")
    dictamenes = cumplimiento.ultimos_dictamenes(db, [d.documento_id for d in evaluacion.documentos])
    eventos = (
        db.query(BitacoraAuditoria)
        .filter(BitacoraAuditoria.expediente_id == exp.id)
        .order_by(BitacoraAuditoria.creado_en.desc())
        .limit(200)
        .all()
    )
    datos = reportes.DatosExpediente(exp, evaluacion, dictamenes, eventos)
    contenido = reportes.expediente_pdf(datos) if formato == "pdf" else reportes.expediente_xlsx(datos)
    _registrar(db, request, {"reporte": "DICTAMEN_EXPEDIENTE", "formato": formato,
                             "codigo_expediente": exp.codigo_expediente, "estado": evaluacion.estado}, exp.id)
    return _archivo(contenido, formato, f"dictamen_{exp.codigo_expediente}")


@router.get(
    "/cumplimiento",
    summary="Reporte global de cumplimiento, en PDF o Excel (RF-22, RF-24)",
    response_class=Response,
    responses={200: {"content": {v: {} for v in reportes.FORMATOS.values()}}},
)
def reporte_global(
    request: Request,
    formato: Formato = Query("xlsx"),
    tipo_expediente: Optional[str] = Query(None, description="JURIDICO, CORPORATIVO o REGULATORIO"),
    db: Session = Depends(get_db),
):
    evaluados = evaluar_lista(db, consultar_expedientes(db, tipo_expediente=tipo_expediente), causa="REPORTE_GLOBAL")
    contenido = reportes.global_pdf(evaluados) if formato == "pdf" else reportes.global_xlsx(evaluados)
    _registrar(db, request, {"reporte": "CUMPLIMIENTO_GLOBAL", "formato": formato,
                             "tipo_expediente": tipo_expediente, "expedientes": len(evaluados)})
    return _archivo(contenido, formato, f"reporte_cumplimiento_{datetime.now().strftime('%Y%m%d_%H%M')}")
