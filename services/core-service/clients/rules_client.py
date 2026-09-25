"""
Cliente del rules-service (:8002) para conocer los documentos obligatorios.

La completitud del expediente (RIE-01) se calcula contra el inventario que
declaran las reglas RIE activas del catálogo (HU-09), no contra una lista fija
en el código. Si el rules-service no responde, o su catálogo no declara ningún
documento obligatorio, se aplica el inventario base del DOC-02 y la respuesta
lo indica, para que la interfaz y la bitácora sepan con qué criterio se evaluó.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import requests

logger = logging.getLogger("core-service.rules_client")

RULES_BASE_URL = os.getenv("RULES_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
TIMEOUT_SEGUNDOS = float(os.getenv("RULES_TIMEOUT", "2"))

FUENTE_CATALOGO = "rules-service"
FUENTE_RESPALDO = "respaldo-doc02"

# Inventario base del expediente B2B (DOC-02). Solo se usa como respaldo.
OBLIGATORIOS_RESPALDO: dict[str, dict[str, str]] = {
    "CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"},
    "COMP_DOMICILIO": {"codigo_regla": "RIE-01", "severidad": "CRITICA"},
    "ACTA_CONSTITUTIVA": {"codigo_regla": "RIE-01", "severidad": "CRITICA"},
}


@dataclass
class InventarioObligatorio:
    """Tipos de documento exigidos: {tipo: {codigo_regla, severidad}}."""
    documentos: dict[str, dict[str, str]]
    fuente: str
    advertencia: str | None = None


def _respaldo(motivo: str) -> InventarioObligatorio:
    logger.warning("Documentos obligatorios desde el respaldo DOC-02: %s", motivo)
    return InventarioObligatorio(
        documentos={tipo: dict(datos) for tipo, datos in OBLIGATORIOS_RESPALDO.items()},
        fuente=FUENTE_RESPALDO,
        advertencia=f"{motivo} Se aplicó el inventario base del DOC-02 (CSF, comprobante de domicilio y acta).",
    )


def obtener_documentos_obligatorios() -> InventarioObligatorio:
    """Consulta el inventario obligatorio al rules-service, con respaldo controlado."""
    url = f"{RULES_BASE_URL}/api/v1/reglas/documentos-obligatorios"
    try:
        respuesta = requests.get(url, timeout=TIMEOUT_SEGUNDOS)
        respuesta.raise_for_status()
        registros = respuesta.json()
    except (requests.RequestException, ValueError) as exc:
        return _respaldo(f"El rules-service ({RULES_BASE_URL}) no respondió: {exc.__class__.__name__}.")

    documentos = {
        r["tipo_documento"].upper(): {"codigo_regla": r["codigo_regla"], "severidad": (r.get("severidad") or "").upper()}
        for r in registros
        if r.get("tipo_documento")
    }
    if not documentos:
        return _respaldo("El catálogo de reglas no declara ningún documento obligatorio activo (familia RIE).")
    return InventarioObligatorio(documentos=documentos, fuente=FUENTE_CATALOGO)
