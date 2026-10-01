"""
Controlador de Reportes de Auditoría (Módulo 6: RF-22, RF-23, RF-24; HU-28, HU-29).

  * ``GET /api/v1/reportes/expedientes/{id}?formato=pdf|xlsx`` — dictamen formal
    de cumplimiento de un expediente.
  * ``GET /api/v1/reportes/cumplimiento?formato=pdf|xlsx`` — reporte global.
  * ``GET /api/v1/reportes/documentos/{id}/custodia?formato=pdf|xlsx`` — ficha
    de custodia de un documento para una auditoría externa (P3, PLUS-06).

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
from models.dictamen import DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora, cumplimiento, integridad, reportes

router = APIRouter(prefix="/api/v1/reportes", tags=["Reportes de Auditoría"])

Formato = Literal["pdf", "xlsx"]


def _archivo(contenido: bytes, formato: str, nombre: str) -> Response:
    return Response(
        content=contenido,
        media_type=reportes.FORMATOS[formato],
        headers={"Content-Disposition": f'attachment; filename="{nombre}.{formato}"'},
    )


def _registrar(
    db: Session, request: Request, detalle: dict, expediente_id: str | None = None, documento_id: str | None = None
) -> None:
    bitacora.registrar(
        db, EVENTO_EXPORTACION_REPORTE, expediente_id=expediente_id, documento_id=documento_id, usuario="OPERADOR",
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
    # PLUS-15: el último eslabón antes de esta exportación queda impreso como ancla externa.
    datos = reportes.DatosExpediente(exp, evaluacion, dictamenes, eventos, cadena=bitacora.verificar_cadena(db))
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
    cadena = bitacora.verificar_cadena(db)  # PLUS-15: ancla del último eslabón antes de exportar
    contenido = reportes.global_pdf(evaluados, cadena) if formato == "pdf" else reportes.global_xlsx(evaluados, cadena)
    _registrar(db, request, {"reporte": "CUMPLIMIENTO_GLOBAL", "formato": formato,
                             "tipo_expediente": tipo_expediente, "expedientes": len(evaluados)})
    return _archivo(contenido, formato, f"reporte_cumplimiento_{datetime.now().strftime('%Y%m%d_%H%M')}")


@router.get(
    "/documentos/{documento_id}/custodia",
    summary="Ficha de custodia de un documento, en PDF o Excel (P3, PLUS-06)",
    response_class=Response,
    responses={200: {"content": {v: {} for v in reportes.FORMATOS.values()}}},
)
def ficha_custodia(
    documento_id: str,
    request: Request,
    formato: Formato = Query("pdf"),
    db: Session = Depends(get_db),
):
    """
    Historia completa de un documento para una auditoría externa: huella de la
    carga y su recálculo a la fecha (RIE-03), versiones del mismo tipo en el
    expediente (RF-04), dictámenes con la huella evaluada, ratificaciones,
    eventos de la bitácora con su sello y la verificación de la cadena.
    """
    documento = db.query(Documento).filter(Documento.id == documento_id).first()
    if not documento:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Documento con ID '{documento_id}' no encontrado.")
    ip = request.client.host if request.client else None

    # La ficha recalcula la huella: si el binario cambió, RIE-03 lo bloquea y la ficha lo reporta.
    try:
        integridad.leer_verificado(db, documento, usuario="OPERADOR", ip_origen=ip)
        integro, hash_actual = True, documento.hash_sha256
    except integridad.DocumentoAlteradoError:
        db.refresh(documento)
        integro, hash_actual = False, integridad.huella_actual(documento)

    versiones = (
        db.query(Documento)
        .filter(Documento.expediente_id == documento.expediente_id, Documento.tipo_documento == documento.tipo_documento)
        .order_by(Documento.creado_en)
        .all()
    )
    dictamenes = (
        db.query(DictamenAuditoria)
        .filter(DictamenAuditoria.documento_id == documento.id)
        .order_by(DictamenAuditoria.creado_en)
        .all()
    )
    eventos = (
        db.query(BitacoraAuditoria)
        .filter(BitacoraAuditoria.documento_id == documento.id)
        .order_by(BitacoraAuditoria.creado_en, BitacoraAuditoria.secuencia)
        .all()
    )
    cadena = bitacora.verificar_cadena(db)
    datos = reportes.DatosCustodia(
        documento=documento, expediente=documento.expediente, integro=integro, hash_actual=hash_actual,
        versiones=versiones, dictamenes=dictamenes, eventos=eventos, cadena=cadena,
    )
    contenido = reportes.ficha_custodia_pdf(datos) if formato == "pdf" else reportes.ficha_custodia_xlsx(datos)
    _registrar(db, request, {"reporte": "FICHA_CUSTODIA", "formato": formato,
                             "nombre_archivo_original": documento.nombre_archivo_original,
                             "hash_sha256": documento.hash_sha256, "integro": integro,
                             "cadena_integra": cadena.get("integra")},
               documento.expediente_id, documento.id)
    return _archivo(contenido, formato, f"custodia_{documento.hash_sha256[:12]}")
