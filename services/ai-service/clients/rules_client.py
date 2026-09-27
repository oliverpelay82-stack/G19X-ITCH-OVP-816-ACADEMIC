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


# Familias cuyas reglas describen, en lenguaje natural, qué debe contener un
# documento de cierto tipo: RSC (semánticas y contractuales, DOC-05) y RDS
# (dinámicas, dadas de alta por el usuario con su criterio para la IA, RDS-02).
FAMILIAS_CONTENIDO = ("RSC", "RDS")


def criterios_contenido(tipo_documento: str | None) -> list[dict[str, Any]]:
    """
    Reglas activas de las familias RSC y RDS ligadas al tipo de documento. Cada
    una es un elemento que el Nivel 4 debe localizar en el texto; su
    ``descripcion`` es el criterio y su ``accion``, la recomendación si falta.
    """
    if not tipo_documento:
        return []
    try:
        respuesta = _sesion.get(
            f"{settings.RULES_BASE_URL}/api/v1/reglas", params={"activo": "true"}, timeout=TIMEOUT_SEGUNDOS
        )
        respuesta.raise_for_status()
        reglas = respuesta.json()
    except (requests.RequestException, ValueError) as exc:
        raise ReglasNoDisponiblesError(
            f"No fue posible consultar los criterios de contenido en {settings.RULES_BASE_URL}: {exc}"
        ) from exc
    tipo = tipo_documento.strip().upper()
    return [
        {
            "codigo_regla": r["codigo_regla"],
            "nombre_regla": r["nombre_regla"],
            "familia_regla": r["familia_regla"],
            "criterio": r["descripcion"],
            "recomendacion": r["accion"],
            "severidad": r["severidad"],
        }
        for r in reglas
        if r.get("familia_regla") in FAMILIAS_CONTENIDO and (r.get("tipo_documento") or "").upper() == tipo
    ]
