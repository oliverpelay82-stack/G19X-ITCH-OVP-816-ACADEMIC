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
import hashlib
import json
from functools import lru_cache
from typing import Any

from openai import OpenAI, APIError, APIConnectionError, RateLimitError

from config import settings
# El caché de inferencias vive en la misma SQLite que el texto extraído: es la
# única persistencia local del servicio (DOC-08).
from pipelines import persistencia_texto

# Tope del sondeo de salud: /health nunca debe esperar el timeout de inferencia.
_TIMEOUT_SONDEO_SEGUNDOS = 5


class GroqNoDisponibleError(RuntimeError):
    """La API de Groq no respondió o devolvió un error de transporte."""


class GroqRespuestaInvalidaError(RuntimeError):
    """El modelo respondió, pero su salida no es el JSON estricto solicitado."""


class RespuestaJSON(dict):
    """Objeto JSON del modelo; ``uso`` lleva los tokens consumidos por la llamada."""
    uso: dict[str, Any] | None = None


class RespuestaTexto(str):
    """Texto del modelo; ``uso`` lleva los tokens consumidos por la llamada."""
    uso: dict[str, Any] | None = None


def _uso(respuesta: Any) -> dict[str, Any] | None:
    """Métricas de tokens que Groq devuelve en ``usage`` (entran en el límite por minuto)."""
    usage = getattr(respuesta, "usage", None)
    if usage is None:
        return None
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
        "desde_cache": False,
    }


# Una respuesta servida por el caché no consume tokens del cupo de Groq.
_USO_DESDE_CACHE = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "desde_cache": True}


def uso_de(respuesta: Any) -> dict[str, Any] | None:
    """Tokens de una respuesta de ``generar_json``/``conversar``, o ``None`` si no se conocen."""
    return getattr(respuesta, "uso", None)


@lru_cache(maxsize=1)
def _client() -> OpenAI:
    """
    Cliente único del proceso.

    Crear un cliente por llamada abría una conexión HTTPS nueva (TCP + TLS) en
    cada inferencia: medido, ~490 ms por llamada frente a ~125 ms reutilizando
    las conexiones del pool (keep-alive). El cliente es seguro entre hilos.

    Los reintentos ante 429, 5xx y fallos de red los hace el SDK (backoff
    exponencial que respeta la cabecera Retry-After de Groq). Es la única capa
    de reintentos: un bucle propio encima multiplicaba las peticiones.
    """
    return OpenAI(
        base_url=settings.GROQ_BASE_URL,
        api_key=settings.GROQ_API_KEY,
        timeout=settings.GROQ_TIMEOUT,
        max_retries=settings.GROQ_MAX_RETRIES,
    )


def _traducir(exc: APIError) -> GroqNoDisponibleError:
    """Convierte el error del SDK, ya agotados sus reintentos, en el error del servicio."""
    if isinstance(exc, RateLimitError):
        return GroqNoDisponibleError(
            f"Groq rechazó la petición por límite de uso (429) tras {settings.GROQ_MAX_RETRIES} reintentos: {exc}"
        )
    if isinstance(exc, APIConnectionError):  # incluye APITimeoutError
        return GroqNoDisponibleError(f"No fue posible contactar a Groq ({settings.GROQ_BASE_URL}): {exc}")
    return GroqNoDisponibleError(f"Error de la API de Groq: {exc}")


def verificar_estado() -> dict[str, Any]:
    """
    Verifica conectividad con Groq y disponibilidad del modelo.

    Nunca lanza excepción: alimenta el health check, que debe responder 200
    incluso cuando el motor de inferencia no está disponible. Es un sondeo: no
    reintenta y usa un timeout corto.
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
        modelos = _client().with_options(timeout=_TIMEOUT_SONDEO_SEGUNDOS, max_retries=0).models.list()
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


def _clave_inferencia(system: str, prompt: str) -> str | None:
    """
    Huella de la petición exacta. Cualquier cambio de texto, titular, prompt,
    modelo o parámetros produce otra clave, así que el caché nunca sirve una
    respuesta a una pregunta distinta y no necesita invalidarse a mano.
    """
    if not settings.GROQ_CACHE_INFERENCIAS or settings.GROQ_TEMPERATURE != 0.0:
        return None
    material = json.dumps(
        [settings.GROQ_MODEL, settings.GROQ_TEMPERATURE, settings.GROQ_MAX_TOKENS, system, prompt],
        ensure_ascii=False,
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def generar_json(prompt: str, system: str) -> dict[str, Any]:
    """
    Inferencia de un turno exigiendo salida JSON estricta.

    ``response_format={"type": "json_object"}`` restringe la salida a un objeto
    JSON sintácticamente válido, lo que elimina el preámbulo conversacional que
    de otro modo rompería el parseo.

    A temperatura 0.0 la respuesta se guarda por huella de la petición: repetir
    la misma auditoría devuelve el mismo JSON sin volver a llamar a Groq. Solo
    se guarda una respuesta válida; los errores nunca se guardan.

    Devuelve un ``RespuestaJSON`` (un ``dict``) cuyo atributo ``uso`` informa
    de los tokens consumidos.
    """
    clave = _clave_inferencia(system, prompt)
    if clave and (previa := persistencia_texto.leer_inferencia(clave)) is not None:
        resultado = RespuestaJSON(previa)
        resultado.uso = dict(_USO_DESDE_CACHE)
        return resultado

    try:
        respuesta = _client().chat.completions.create(
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
    except APIError as exc:
        raise _traducir(exc) from exc

    crudo = respuesta.choices[0].message.content or ""
    try:
        objeto = json.loads(crudo)
    except json.JSONDecodeError as exc:
        raise GroqRespuestaInvalidaError(
            f"El modelo no devolvió JSON válido. Salida recibida: {crudo[:400]}"
        ) from exc
    if not isinstance(objeto, dict):
        raise GroqRespuestaInvalidaError(f"El modelo no devolvió un objeto JSON. Salida recibida: {crudo[:400]}")
    resultado = RespuestaJSON(objeto)
    if clave:
        persistencia_texto.guardar_inferencia(clave, resultado)
    resultado.uso = _uso(respuesta)
    return resultado


def conversar(mensajes: list[dict[str, str]], temperatura: float | None = None) -> str:
    """
    Turno de conversación multi-turno. Devuelve texto plano.

    Se usa en el endpoint de chat documental, donde la respuesta es para lectura
    humana y no debe forzarse a JSON. Devuelve un ``RespuestaTexto`` (un ``str``)
    cuyo atributo ``uso`` informa de los tokens consumidos.
    """
    try:
        respuesta = _client().chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=mensajes,
            max_tokens=settings.GROQ_MAX_TOKENS,
            temperature=settings.GROQ_TEMPERATURE if temperatura is None else temperatura,
            top_p=1.0,
        )
    except APIError as exc:
        raise _traducir(exc) from exc
    texto = RespuestaTexto((respuesta.choices[0].message.content or "").strip())
    texto.uso = _uso(respuesta)
    return texto
