"""
Controlador de Salud (Health Check) del AI Service.

A diferencia de los otros microservicios, aquí el health check no solo declara
que el proceso está vivo: verifica las dos dependencias externas de las que
depende el análisis —Groq Cloud con su modelo disponible y el motor OCR
Tesseract— para que el frontend pueda avisar al operador *antes* de que intente
analizar un expediente y se encuentre con un error a mitad del flujo.

El endpoint responde siempre 200: un 5xx haría que Docker Compose reiniciara el
contenedor en ciclo cuando el único problema es que falta configurar la API key.

El frontend lo sondea cada 15 s. Consultar Groq (una petición a internet) y
Tesseract (dos procesos externos) en cada sondeo costaba de 0.5 a 1.8 s por
llamada, así que el estado de ambas dependencias se reutiliza durante un TTL:
una caída de Groq se refleja en, a lo sumo, 60 s.
"""
import time
from threading import Lock
from typing import Any, Callable

from fastapi import APIRouter

from clients import groq_client
from config import settings
from pipelines import extraccion_pipeline
from pipelines import repositorio_texto

router = APIRouter(prefix="/api/v1", tags=["Salud"])

_TTL_SEGUNDOS = {"groq": 60, "ocr": 300}
_cache: dict[str, tuple[float, dict[str, Any]]] = {}
_candado = Lock()


def _cacheado(clave: str, calcular: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    """Devuelve el último estado de la dependencia si aún está dentro de su TTL."""
    with _candado:
        guardado = _cache.get(clave)
        if guardado and time.monotonic() - guardado[0] < _TTL_SEGUNDOS[clave]:
            return guardado[1]
    valor = calcular()
    with _candado:
        _cache[clave] = (time.monotonic(), valor)
    return valor


def precargar() -> tuple[dict[str, Any], dict[str, Any]]:
    """
    Arranque del servicio: consulta Groq y Tesseract una vez y deja ambos
    estados en el caché, para que ni el primer sondeo de /health pague la
    latencia en frío. De paso abre la conexión HTTPS del cliente compartido de
    Groq, que la primera inferencia reutiliza. Devuelve (estado_groq, estado_ocr).
    """
    return _cacheado("groq", groq_client.verificar_estado), _cacheado("ocr", extraccion_pipeline.diagnostico_ocr)


@router.get("/health", summary="Estado de salud del ai-service, de Groq y del motor OCR")
def health_check():
    estado_groq = _cacheado("groq", groq_client.verificar_estado)
    estado_ocr = _cacheado("ocr", extraccion_pipeline.diagnostico_ocr)

    operativo = estado_groq["modelo_disponible"] and estado_ocr["disponible"]

    return {
        "status": "online",
        "servicio": "ai-service",
        "puerto": 8003,
        "version": "1.0.0",
        "modo_despliegue": "cloud-groq",
        "capacidades_operativas": operativo,
        "motor_inferencia": {
            "proveedor": "Groq Cloud",
            "endpoint": settings.GROQ_BASE_URL,
            "temperatura_auditoria": settings.GROQ_TEMPERATURE,
            **estado_groq,
        },
        "motor_ocr": {
            "proveedor": "Tesseract",
            **estado_ocr,
        },
        "bandas_confianza": {
            "conforme_desde": settings.UMBRAL_CONFIANZA_CONFORME,
            "revision_humana_desde": settings.UMBRAL_CONFIANZA_HITL,
        },
        "umbral_confianza_hitl": settings.UMBRAL_CONFIANZA_HITL,
        "cache_extracciones": repositorio_texto.estadisticas(),
    }
