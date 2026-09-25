"""
Cliente del rules-service (:8002) para evaluar la vigencia de un documento.

El dictamen del Nivel 4 no decide por sí mismo cuánto tiempo es válido un
documento: consulta las reglas Cronológicas y de Vigencia activas del catálogo
(DOC-05), que son la fuente única de esos plazos. Así, pausar o ajustar una
regla desde la interfaz cambia el dictamen sin tocar el código del ai-service.
"""
from datetime import date
from typing import Any

import requests

from config import settings

# Sesión HTTP del proceso: reutiliza las conexiones TCP (keep-alive) hacia el
# rules-service. Sin estado propio, puede compartirse entre hilos.
_sesion = requests.Session()
# (conexión, lectura): un rules-service caído falla en segundos y el dictamen
# pasa a revisión humana en lugar de esperar el timeout completo.
TIMEOUT_SEGUNDOS = (3, 10)


class ReglasNoDisponiblesError(RuntimeError):
    """El rules-service no respondió o devolvió un error."""


def evaluar_vigencia(
    tipo_documento: str,
    fecha_emision: str | None,
    fecha_vencimiento: str | None,
    fecha_referencia: date,
) -> dict[str, Any]:
    """Devuelve el dictamen de vigencia del rules-service (resultado, días y reglas aplicadas)."""
    cuerpo = {
        "tipo_documento": tipo_documento,
        "fecha_emision": fecha_emision,
        "fecha_vencimiento": fecha_vencimiento,
        "fecha_referencia": fecha_referencia.isoformat(),
    }
    try:
        respuesta = _sesion.post(
            f"{settings.RULES_BASE_URL}/api/v1/reglas/evaluar-vigencia", json=cuerpo, timeout=TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        return respuesta.json()
    except requests.RequestException as exc:
        raise ReglasNoDisponiblesError(
            f"No fue posible consultar las reglas de vigencia en {settings.RULES_BASE_URL}: {exc}"
        ) from exc
