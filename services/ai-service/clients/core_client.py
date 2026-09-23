"""
Cliente del core-service (:8001) para resolver documentos por identificador.

El ai-service no tiene acceso a la base de datos de Titulares/Expedientes: en la
arquitectura de microservicios desacoplados (DOC-08) cada servicio es dueño
exclusivo de su subconjunto de tablas. Por eso, cuando el frontend pide analizar
un documento ya cargado en la bóveda, este módulo consulta el catálogo por HTTP
al core-service y recupera el binario de ``storage_vault`` usando la convención
de nombrado que el propio core-service aplica al guardarlo
(``<12 primeros caracteres del SHA-256>_<nombre original>``).
"""
import os
from typing import Any

import requests

from config import settings


class DocumentoNoEncontradoError(LookupError):
    """El identificador no existe en el catálogo o su binario no está en la bóveda."""


def obtener_metadatos(documento_id: str) -> dict[str, Any]:
    """Recupera del core-service la ficha del documento solicitado."""
    try:
        respuesta = requests.get(f"{settings.CORE_BASE_URL}/api/v1/documentos", timeout=15)
        respuesta.raise_for_status()
        catalogo = respuesta.json()
    except requests.RequestException as exc:
        raise DocumentoNoEncontradoError(
            f"No fue posible consultar el catálogo del core-service en "
            f"{settings.CORE_BASE_URL}: {exc}"
        ) from exc

    for documento in catalogo:
        if documento.get("id") == documento_id:
            return documento

    raise DocumentoNoEncontradoError(
        f"El documento '{documento_id}' no existe en el catálogo del core-service."
    )


def obtener_binario(documento_id: str) -> tuple[bytes, dict[str, Any]]:
    """Devuelve el contenido binario del documento junto con sus metadatos."""
    metadatos = obtener_metadatos(documento_id)
    return leer_binario(metadatos), metadatos


def leer_binario(metadatos: dict[str, Any]) -> bytes:
    """Lee de la bóveda el binario descrito por una ficha del catálogo."""
    documento_id = metadatos.get("id", "")
    hash_sha256 = metadatos.get("hash_sha256", "")
    nombre_original = metadatos.get("nombre_archivo_original", "")

    nombre_en_boveda = f"{hash_sha256[:12]}_{nombre_original}"
    ruta = os.path.join(settings.STORAGE_VAULT_PATH, nombre_en_boveda)

    if not os.path.isfile(ruta):
        raise DocumentoNoEncontradoError(
            f"El documento '{documento_id}' está catalogado pero su binario no se "
            f"encuentra en la bóveda ({ruta})."
        )

    with open(ruta, "rb") as archivo:
        return archivo.read()
