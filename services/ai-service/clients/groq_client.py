"""
Cliente de Groq Cloud (GroqCloud).

Groq ejecuta modelos de lenguaje sobre su LPU (Language Processing Unit), un
procesador diseñado específicamente para inferencia. La API es
OpenAI-compatible: se usa la librería estándar openai con base_url apuntando a
https://api.groq.com/openai/v1.

Minimización de datos: ningún documento fiscal abandona el perímetro de la
organización; solo viaja el texto que ya extrajo el Nivel 3 (OCR/PyMuPDF),
cifrado en tránsito (TLS). Por defecto Groq no retiene las entradas ni las
salidas de inferencia y no las usa para entrenar modelos; puede registrarlas
temporalmente (hasta 30 días) solo para diagnosticar fallas o investigar abuso,
salvo que la organización active Zero Data Retention en Data Controls.
"""
import json
from typing import Any

from openai import OpenAI, APIError, APIConnectionError, APITimeoutError

from config import settings


class GroqNoDisponibleError(RuntimeError):
    """La API de Groq no respondió o devolvió un error de transporte."""


class GroqRespuestaInvalidaError(RuntimeError):
    """El modelo respondió, pero su salida no es el JSON estricto solicitado."""


def _client() -> OpenAI:
    return OpenAI(
        base_url=settings.GROQ_BASE_URL,
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT,
    )


def verificar_estado() -> dict[str, Any]:
    """
    Verifica conectividad con Groq y disponibilidad del modelo.

    Nunca lanza excepción: alimenta el health check, que debe responder 200
    incluso cuando el motor de inferencia no está disponible.
    """
    if not settings.GROQ_API_KEY:
        return {
            "disponible": False,
            "modelos_instalados": [],
            "modelo_requerido": settings.GROQ_MODEL,
            "modelo_disponible": False,
            "detalle": "GROQ_API_KEY no está configurada.",
        }
    try:
        client = _client()
        modelos = client.models.list()
        nombres = [m.id for m in modelos.data]
        requerido = settings.GROQ_MODEL
        disponible = requerido in nombres
        return {
            "disponible": True,
            "modelos_instalados": nombres,
            "modelo_requerido": requerido,
            "modelo_disponible": disponible,
            "detalle": "Groq Cloud API operativa." if disponible
                       else f"La API responde pero el modelo '{requerido}' no está disponible.",
        }
    except Exception as exc:
        return {
            "disponible": False,
            "modelos_instalados": [],
            "modelo_requerido": settings.GROQ_MODEL,
            "modelo_disponible": False,
            "detalle": f"Sin respuesta de Groq: {exc}",
        }


def generar_json(prompt: str, system: str) -> dict[str, Any]:
    """
    Inferencia de un turno exigiendo salida JSON estricta.

    ``response_format={"type": "json_object"}`` restringe la salida a un objeto
    JSON sintácticamente válido, lo que elimina el preámbulo conversacional que
    de otro modo rompería el parseo.
    """
    try:
        client = _client()
        respuesta = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            response_format={"type": "json_object"},
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=settings.GROQ_TEMPERATURE,
            top_p=1.0,
            seed=42,
        )
        crudo = respuesta.choices[0].message.content or ""
    except (APIConnectionError, APITimeoutError) as exc:
        raise GroqNoDisponibleError(
            f"No fue posible contactar a Groq ({settings.GROQ_BASE_URL}): {exc}"
        ) from exc
    except APIError as exc:
        raise GroqNoDisponibleError(
            f"Error de la API de Groq: {exc}"
        ) from exc

    try:
        return json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise GroqRespuestaInvalidaError(
            f"El modelo no devolvió JSON válido. Salida recibida: {crudo[:400]}"
        ) from exc


def conversar(mensajes: list[dict[str, str]], temperatura: float | None = None) -> str:
    """
    Turno de conversación multi-turno. Devuelve texto plano.

    Se usa en el endpoint de chat documental, donde la respuesta es para lectura
    humana y no debe forzarse a JSON.
    """
    try:
        client = _client()
        respuesta = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=mensajes,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=settings.GROQ_TEMPERATURE if temperatura is None else temperatura,
            top_p=1.0,
        )
        return (respuesta.choices[0].message.content or "").strip()
    except (APIConnectionError, APITimeoutError, APIError) as exc:
        raise GroqNoDisponibleError(
            f"No fue posible contactar a Groq ({settings.GROQ_BASE_URL}): {exc}"
        ) from exc
