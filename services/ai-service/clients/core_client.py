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

from config import observabilidad, settings

# Sesión HTTP del proceso: reutiliza las conexiones TCP (keep-alive) hacia el
# core-service en lugar de abrir una por petición. Sin estado propio (no hay
# cookies ni autenticación), así que puede compartirse entre los hilos del pool.
_sesion = requests.Session()
# Tope para establecer la conexión: un core-service caído o inalcanzable falla
# en segundos; el segundo valor de cada timeout es el de lectura de la respuesta.
TIMEOUT_CONEXION_SEGUNDOS = 3


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
        respuesta = _sesion.get(url, timeout=(TIMEOUT_CONEXION_SEGUNDOS, timeout),
                                headers=observabilidad.cabeceras())
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
        respuesta = _sesion.post(url, json=dictamen, timeout=(TIMEOUT_CONEXION_SEGUNDOS, 15),
                                 headers=observabilidad.cabeceras())
    except requests.RequestException as exc:
        raise CoreNoDisponibleError(f"No fue posible registrar el dictamen en {settings.CORE_BASE_URL}: {exc}") from exc
    if respuesta.status_code == 409:
        raise DocumentoAlteradoError(_detalle(respuesta))
    if respuesta.status_code == 404:
        raise DocumentoNoEncontradoError(_detalle(respuesta))
    if not respuesta.ok:
        raise CoreNoDisponibleError(f"El core-service rechazó el dictamen (HTTP {respuesta.status_code}): {_detalle(respuesta)}")
    return respuesta.json()


def ultimo_dictamen(documento_id: str) -> dict[str, Any] | None:
    """
    Dictamen vigente del documento (el más reciente), para dar contexto al chat.
    Es información de apoyo: si el core-service no responde, el chat sigue sin él.
    """
    try:
        respuesta = _sesion.get(
            f"{settings.CORE_BASE_URL}/api/v1/dictamenes",
            params={"documento_id": documento_id, "limite": 1},
            timeout=(TIMEOUT_CONEXION_SEGUNDOS, 10),
            headers=observabilidad.cabeceras(),
        )
        respuesta.raise_for_status()
        dictamenes = respuesta.json()
    except (requests.RequestException, ValueError):
        return None
    return dictamenes[0] if dictamenes else None


def marcar_diferido(documento_id: str, aviso: dict[str, Any]) -> bool:
    """
    P5 (DOC-05, Tabla 1): avisa al core que la auditoría del documento quedó
    diferida (o que se agotaron sus reintentos). Es un aviso: si el core no
    responde, la cola del ai-service sigue igual y lo repite en el siguiente fallo.
    """
    try:
        respuesta = _sesion.post(
            f"{settings.CORE_BASE_URL}/api/v1/documentos/{documento_id}/procesamiento-diferido",
            json=aviso, timeout=(TIMEOUT_CONEXION_SEGUNDOS, 10),
            headers=observabilidad.cabeceras(),
        )
        return respuesta.ok
    except requests.RequestException:
        return False

