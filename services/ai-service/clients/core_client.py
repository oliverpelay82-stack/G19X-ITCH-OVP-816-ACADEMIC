"""
Cliente del core-service (:8001): fichas, binarios verificados y dictámenes.

El ai-service no tiene acceso a la base de datos de Titulares/Expedientes: en la
arquitectura de microservicios desacoplados (DOC-08) cada servicio es dueño
exclusivo de su subconjunto de tablas. Por eso todo pasa por la API del
core-service, que además es quien garantiza la integridad de la bóveda:

  * ``obtener_metadatos`` — ficha de un documento (``GET /documentos/{id}``).
  * ``verificar_integridad`` — RIE-03 antes de usar un texto ya extraído: si el
    binario cambió desde la carga, el core lo bloquea y responde 409.
  * ``leer_binario`` — el binario, solo si su huella coincide (RIE-03).
  * ``registrar_dictamen`` — persiste el dictamen del Nivel 4.
"""
from typing import Any

import requests

from config import settings


class DocumentoNoEncontradoError(LookupError):
    """El identificador no existe en el catálogo o su binario no está disponible."""


class DocumentoAlteradoError(RuntimeError):
    """El core-service detectó que la huella del binario no coincide con la registrada (RIE-03)."""


class CoreNoDisponibleError(RuntimeError):
    """El core-service no respondió o devolvió un error inesperado."""


def _detalle(respuesta: requests.Response) -> str:
    try:
        return str(respuesta.json().get("detail") or respuesta.text)
    except ValueError:
        return respuesta.text


def _get(ruta: str, timeout: int = 15) -> requests.Response:
    url = f"{settings.CORE_BASE_URL}/api/v1{ruta}"
    try:
        respuesta = requests.get(url, timeout=timeout)
    except requests.RequestException as exc:
        raise CoreNoDisponibleError(f"No fue posible consultar el core-service en {settings.CORE_BASE_URL}: {exc}") from exc
    if respuesta.status_code == 404:
        raise DocumentoNoEncontradoError(_detalle(respuesta))
    if respuesta.status_code == 409:
        raise DocumentoAlteradoError(_detalle(respuesta))
    if not respuesta.ok:
        raise CoreNoDisponibleError(f"El core-service respondió HTTP {respuesta.status_code}: {_detalle(respuesta)}")
    return respuesta


def obtener_metadatos(documento_id: str) -> dict[str, Any]:
    """Recupera del core-service la ficha del documento solicitado."""
    return _get(f"/documentos/{documento_id}").json()


def verificar_integridad(documento_id: str) -> None:
    """RIE-03: lanza ``DocumentoAlteradoError`` si el binario ya no coincide con su huella."""
    _get(f"/documentos/{documento_id}/integridad", timeout=30)


def leer_binario(metadatos: dict[str, Any]) -> bytes:
    """Descarga el binario verificado (RIE-03) descrito por una ficha del catálogo."""
    return _get(f"/documentos/{metadatos.get('id', '')}/contenido", timeout=60).content


def registrar_dictamen(dictamen: dict[str, Any]) -> dict[str, Any]:
    """Persiste el dictamen del Nivel 4 en el core-service y devuelve el registro creado."""
    url = f"{settings.CORE_BASE_URL}/api/v1/dictamenes"
    try:
        respuesta = requests.post(url, json=dictamen, timeout=15)
    except requests.RequestException as exc:
        raise CoreNoDisponibleError(f"No fue posible registrar el dictamen en {settings.CORE_BASE_URL}: {exc}") from exc
    if respuesta.status_code == 409:
        raise DocumentoAlteradoError(_detalle(respuesta))
    if respuesta.status_code == 404:
        raise DocumentoNoEncontradoError(_detalle(respuesta))
    if not respuesta.ok:
        raise CoreNoDisponibleError(f"El core-service rechazó el dictamen (HTTP {respuesta.status_code}): {_detalle(respuesta)}")
    return respuesta.json()
