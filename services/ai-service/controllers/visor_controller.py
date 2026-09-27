"""
Visor de evidencia (HU-20, RF-13): páginas del documento y ubicación de citas.

  * ``GET  /api/v1/ai/documentos/{id}/visor`` — páginas y cómo se lee cada una.
  * ``GET  /api/v1/ai/documentos/{id}/paginas/{n}?ancho=`` — la página en JPEG.
  * ``POST /api/v1/ai/documentos/{id}/localizar`` — página y recuadros de una cita.

Todas leen el binario a través del core-service, que verifica su huella (RIE-03).
"""
from fastapi import APIRouter, HTTPException, Query, Response, status
from pydantic import BaseModel, Field

from clients.core_client import CoreNoDisponibleError, DocumentoAlteradoError, DocumentoNoEncontradoError
from pipelines import repositorio_texto, visor_documento
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError

router = APIRouter(prefix="/api/v1/ai/documentos", tags=["Visor de evidencia"])


class LocalizarCitaRequest(BaseModel):
    cita: str = Field(..., min_length=6, max_length=1000, description="Cita literal a ubicar en el documento.")


def _traducir(exc: Exception) -> HTTPException:
    if isinstance(exc, (DocumentoNoEncontradoError, IndexError)):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, DocumentoAlteradoError):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, FormatoNoSoportadoError):
        return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"[Nivel 3] {exc}")
    if isinstance(exc, (CoreNoDisponibleError, MotorOcrNoDisponibleError)):
        return HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc))
    raise exc


_ERRORES = (DocumentoNoEncontradoError, DocumentoAlteradoError, CoreNoDisponibleError,
            FormatoNoSoportadoError, MotorOcrNoDisponibleError, IndexError)


@router.get("/{documento_id}/visor", summary="Páginas del documento para el visor de evidencia")
def info_visor(documento_id: str):
    try:
        return visor_documento.info(documento_id)
    except _ERRORES as exc:
        raise _traducir(exc) from exc


@router.get(
    "/{documento_id}/paginas/{numero}",
    summary="Página del documento renderizada en JPEG",
    response_class=Response,
    responses={200: {"content": {"image/jpeg": {}}}},
)
def pagina(documento_id: str, numero: int, ancho: int = Query(1000, ge=100, le=4000)):
    try:
        imagen = visor_documento.pagina_jpeg(documento_id, numero, ancho)
    except _ERRORES as exc:
        raise _traducir(exc) from exc
    # El binario es inmutable (NOM-151): la misma página no cambia mientras el documento exista.
    return Response(content=imagen, media_type="image/jpeg", headers={"Cache-Control": "private, max-age=3600"})


@router.post("/{documento_id}/localizar", summary="Ubicar una cita literal en las páginas del documento")
def localizar_cita(documento_id: str, peticion: LocalizarCitaRequest):
    """
    Devuelve la página y los recuadros (normalizados a [0, 1], uno por renglón)
    donde aparece la cita. Si la cita no está literalmente en el documento,
    ``encontrada`` es falso y no se resalta nada.
    """
    try:
        # El texto ya extraído (memoria o disco) y la posición de cada página en
        # él llevan la búsqueda directo a la página donde está la cita.
        documento = repositorio_texto.obtener_por_documento(documento_id, completar_en_fondo=False)
        paginas = documento.traza.get("detalle_paginas") or []
        return visor_documento.localizar(documento_id, peticion.cita, documento.texto, paginas).a_dict()
    except _ERRORES as exc:
        raise _traducir(exc) from exc
