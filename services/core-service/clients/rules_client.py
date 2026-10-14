"""
Cliente del rules-service (:8002) para conocer los documentos obligatorios.

La completitud del expediente (RIE-01) se calcula contra el inventario que
declaran las reglas RIE activas del catálogo (HU-09) para el tipo del
expediente (RF-06), no contra una lista fija en el código. Las reglas de anexo
(RIE-02, RF-07) llegan aparte: solo se exigen si el expediente contiene su
documento principal. Si el rules-service no responde, o su catálogo no declara
ningún documento obligatorio para ese tipo, se aplica el inventario base del
DOC-02 y la respuesta lo indica, para que la interfaz y la bitácora sepan con
qué criterio se evaluó.
"""
from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any

import requests

from config import observabilidad, seguridad
from config.catalogo import TIPO_EXPEDIENTE_PREDETERMINADO, etiqueta_expediente

logger = logging.getLogger("core-service.rules_client")

RULES_BASE_URL = os.getenv("RULES_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
TIMEOUT_SEGUNDOS = float(os.getenv("RULES_TIMEOUT", "2"))


def _cabeceras() -> dict[str, str]:
    """Folio de la petición (PLUS-21) y token SISTEMA del core (Módulo 7, DOC-08)."""
    return {**observabilidad.cabeceras(), **seguridad.cabeceras_sistema("core-service")}


FUENTE_CATALOGO = "rules-service"
FUENTE_RESPALDO = "respaldo-doc02"

# Inventario base por tipo de expediente (DOC-02, documentos marcados como
# obligatorios en las Tablas 3 a 5). Solo se usa como respaldo; replica el
# seed del rules-service.
OBLIGATORIOS_RESPALDO: dict[str, dict[str, dict[str, str]]] = {
    "CORPORATIVO": {
        "CSF_SAT": {"codigo_regla": "RIE-01-CSF", "severidad": "CRITICA"},
        "COMP_DOMICILIO": {"codigo_regla": "RIE-01-DOM", "severidad": "CRITICA"},
        "ACTA_CONSTITUTIVA": {"codigo_regla": "RIE-01-ACTA", "severidad": "CRITICA"},
    },
    "JURIDICO": {
        "CONTRATO_SERVICIOS": {"codigo_regla": "RIE-01-JUR-CONT", "severidad": "CRITICA"},
        "ACUERDO_CONFIDENCIALIDAD": {"codigo_regla": "RIE-01-JUR-NDA", "severidad": "CRITICA"},
        "PODER_NOTARIAL": {"codigo_regla": "RIE-01-JUR-PODER", "severidad": "CRITICA"},
    },
    "REGULATORIO": {
        "LICENCIA_OPERACION": {"codigo_regla": "RIE-01-REG-LIC", "severidad": "CRITICA"},
        "PERMISO_SECTORIAL": {"codigo_regla": "RIE-01-REG-PERM", "severidad": "CRITICA"},
        "POLIZA_SEGURO": {"codigo_regla": "RIE-01-REG-POL", "severidad": "CRITICA"},
        "REGISTRO_SECTORIAL": {"codigo_regla": "RIE-01-REG-REGS", "severidad": "CRITICA"},
    },
}
ANEXOS_RESPALDO: list[dict[str, str]] = [
    {"tipo_documento": "ANEXO_CONTRATO", "documento_principal": "CONTRATO_SERVICIOS",
     "codigo_regla": "RIE-02-CONT-ANX", "severidad": "ALTA"},
]


@dataclass
class InventarioObligatorio:
    """
    Tipos de documento exigidos: {tipo: {codigo_regla, severidad}}, más los
    anexos vinculados: [{tipo_documento, documento_principal, codigo_regla, severidad}].
    """
    documentos: dict[str, dict[str, str]]
    fuente: str
    advertencia: str | None = None
    anexos: list[dict[str, str]] = field(default_factory=list)
    # M6: versión del catálogo con que se calculó (cabecera X-Version-Catalogo del rules-service).
    version_catalogo: str | None = None
    # M7: versión de las reglas de cada tipo de documento («*»: tipos sin reglas propias).
    versiones_por_tipo: dict[str, str] = field(default_factory=dict)

    def version_de_tipo(self, tipo: str) -> str | None:
        return self.versiones_por_tipo.get(tipo.upper(), self.versiones_por_tipo.get("*"))


def _respaldo(tipo_expediente: str, motivo: str) -> InventarioObligatorio:
    logger.warning("Documentos obligatorios (%s) desde el respaldo DOC-02: %s", tipo_expediente, motivo)
    base = OBLIGATORIOS_RESPALDO.get(tipo_expediente, OBLIGATORIOS_RESPALDO[TIPO_EXPEDIENTE_PREDETERMINADO])
    return InventarioObligatorio(
        documentos={tipo: dict(datos) for tipo, datos in base.items()},
        fuente=FUENTE_RESPALDO,
        advertencia=(
            f"{motivo} Se aplicó el inventario base del DOC-02 para el expediente "
            f"{etiqueta_expediente(tipo_expediente).lower()}."
        ),
        anexos=[dict(a) for a in ANEXOS_RESPALDO],
    )


def _versiones_por_tipo(cabecera: str | None) -> dict[str, str]:
    """M7: la cabecera X-Version-Reglas-Tipo; vacía o ilegible, sin aviso de nueva auditoría."""
    try:
        valor = json.loads(cabecera) if cabecera else {}
    except ValueError:
        return {}
    return {str(k).upper() if k != "*" else "*": str(v) for k, v in valor.items()} if isinstance(valor, dict) else {}


def obtener_documentos_obligatorios(tipo_expediente: str = TIPO_EXPEDIENTE_PREDETERMINADO) -> InventarioObligatorio:
    """Consulta el inventario obligatorio de un tipo de expediente, con respaldo controlado."""
    tipo_expediente = (tipo_expediente or TIPO_EXPEDIENTE_PREDETERMINADO).upper()
    url = f"{RULES_BASE_URL}/api/v1/reglas/documentos-obligatorios"
    try:
        respuesta = requests.get(url, params={"tipo_expediente": tipo_expediente}, timeout=TIMEOUT_SEGUNDOS,
                                 headers=_cabeceras())
        respuesta.raise_for_status()
        registros = respuesta.json()
        version = respuesta.headers.get("X-Version-Catalogo")
        versiones_por_tipo = _versiones_por_tipo(respuesta.headers.get("X-Version-Reglas-Tipo"))
    except (requests.RequestException, ValueError) as exc:
        return _respaldo(tipo_expediente, f"El rules-service ({RULES_BASE_URL}) no respondió: {exc.__class__.__name__}.")

    documentos: dict[str, dict[str, str]] = {}
    anexos: list[dict[str, str]] = []
    for r in registros:
        if not r.get("tipo_documento"):
            continue
        datos = {"codigo_regla": r["codigo_regla"], "severidad": (r.get("severidad") or "").upper()}
        if r.get("documento_principal"):
            anexos.append({"tipo_documento": r["tipo_documento"].upper(),
                           "documento_principal": r["documento_principal"].upper(), **datos})
        else:
            documentos[r["tipo_documento"].upper()] = datos
    if not documentos:
        return _respaldo(
            tipo_expediente,
            "El catálogo de reglas no declara ningún documento obligatorio activo (familia RIE) "
            f"para el expediente {etiqueta_expediente(tipo_expediente).lower()}.",
        )
    return InventarioObligatorio(documentos=documentos, fuente=FUENTE_CATALOGO, anexos=anexos, version_catalogo=version,
                                 versiones_por_tipo=versiones_por_tipo)


def tipos_documento_declarados() -> list[dict[str, Any]] | None:
    """
    RF-09: tipos de documento declarados por reglas dinámicas (RDS-01), con su
    nombre y si siguen activos. ``None`` si el rules-service no responde: quien
    llama conserva lo que ya sabía.
    """
    try:
        respuesta = requests.get(f"{RULES_BASE_URL}/api/v1/reglas/tipos-documento", timeout=TIMEOUT_SEGUNDOS,
                                 headers=_cabeceras())
        respuesta.raise_for_status()
        return [t for t in respuesta.json() if isinstance(t, dict) and t.get("tipo_documento")]
    except (requests.RequestException, ValueError):
        return None
