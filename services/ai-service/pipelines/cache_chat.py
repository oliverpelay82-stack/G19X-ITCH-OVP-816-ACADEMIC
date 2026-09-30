"""
Caché de respuestas del chat documental — T3, PLUS-10 (PRD §21.4).

A temperatura 0.0 el modelo responde lo mismo ante la misma petición, así que
una respuesta ya obtenida se reutiliza sin consumir tokens. Dos claves:

  * **Exacta**: la petición completa (modelo, parámetros y mensajes, que
    incluyen el estado del sistema, los fragmentos y el historial). Cubre
    cualquier turno repetido tal cual.
  * **Por pregunta normalizada**, solo en el primer turno (sin historial): la
    huella del documento, la versión de su lectura, el estado del sistema y los
    términos de la pregunta según el mismo tokenizador de la búsqueda BM25 (sin
    acentos, mayúsculas, signos ni palabras vacías). «¿Cuándo vence?» y «cuando
    vence» comparten respuesta. Las negaciones se conservan en la clave: «¿quién
    firma?» y «¿quién no firma?» son preguntas distintas.

Como la clave incluye el estado del sistema (dictamen vigente, su ratificación y
las reglas evaluadas), una nueva auditoría o una ratificación produce otra clave:
el caché nunca necesita invalidarse a mano. Las respuestas se guardan en la tabla
``inferencias`` de la SQLite del servicio, con el prefijo ``chat:``.
"""
from __future__ import annotations

import hashlib
import json
import re
from typing import Iterable

from clients.groq_client import RespuestaTexto
from config import settings
from pipelines import extraccion_pipeline, fragmentos, persistencia_texto

_PREFIJO = "chat:"
_NEGACIONES = {"no", "sin", "ni", "nunca", "ningun", "ninguna", "excepto", "salvo"}
USO_DESDE_CACHE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "desde_cache": True}


def activo() -> bool:
    """Mismo criterio que el caché de la auditoría: solo a temperatura 0.0 y si está habilitado."""
    return settings.GROQ_CACHE_INFERENCIAS and settings.GROQ_TEMPERATURE == 0.0


def _huella(*partes: object) -> str:
    return _PREFIJO + hashlib.sha256(json.dumps(partes, ensure_ascii=False).encode("utf-8")).hexdigest()


def clave_exacta(mensajes: list[dict[str, str]], max_tokens: int) -> str:
    return _huella("exacta", settings.GROQ_MODEL, settings.GROQ_TEMPERATURE, max_tokens, mensajes)


def terminos_pregunta(pregunta: str) -> list[str]:
    palabras = set(re.findall(r"[a-z]+", fragmentos._normalizar(pregunta)))
    return sorted(set(fragmentos.tokenizar(pregunta)) | (palabras & _NEGACIONES))


def clave_pregunta(sha256: str | None, estado: str | None, pregunta: str) -> str | None:
    terminos = terminos_pregunta(pregunta)
    if not sha256 or not terminos:
        return None
    return _huella("pregunta", settings.GROQ_MODEL, settings.GROQ_TEMPERATURE, sha256,
                   extraccion_pipeline.version_lectura(), estado or "", terminos)


def leer(claves: Iterable[str | None]) -> RespuestaTexto | None:
    for clave in claves:
        if clave and (guardada := persistencia_texto.leer_inferencia(clave)) is not None:
            respuesta = RespuestaTexto(guardada["respuesta"])
            respuesta.uso = dict(USO_DESDE_CACHE)
            return respuesta
    return None


def guardar(claves: Iterable[str | None], respuesta: str) -> None:
    for clave in claves:
        if clave:
            persistencia_texto.guardar_inferencia(clave, {"respuesta": str(respuesta)})
