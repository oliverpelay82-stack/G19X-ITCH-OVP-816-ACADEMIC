"""
Catálogo de documentos obligatorios por expediente (RIE-01, HU-09 y HU-12).

La completitud de un expediente no se decide en el código del core-service:
se deriva de las reglas activas de la familia RIE que declaran un tipo de
documento con ``documento_obligatorio = True``. Pausar o dar de alta una de
esas reglas desde la interfaz cambia qué documentos exige el expediente sin
tocar una línea de código (RF-06).

Las reglas generales (sin tipo de documento, como RIE-01 o RIE-03) no aportan
un tipo: describen el criterio, no el inventario.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

# De la más grave a la menos grave: si dos reglas exigen el mismo tipo de
# documento, prevalece la severidad más alta.
ORDEN_SEVERIDAD = ["CRITICA", "ALTA", "MEDIA_ALTA", "MEDIA", "BAJA"]


class ReglaObligatoriedad(Protocol):
    codigo_regla: str
    familia_regla: str
    severidad: str
    tipo_documento: str | None
    documento_obligatorio: bool
    activo: bool


@dataclass
class DocumentoObligatorio:
    tipo_documento: str
    codigo_regla: str
    severidad: str


def _rango(severidad: str) -> int:
    valor = (severidad or "").upper()
    return ORDEN_SEVERIDAD.index(valor) if valor in ORDEN_SEVERIDAD else len(ORDEN_SEVERIDAD)


def documentos_obligatorios(reglas: Iterable[ReglaObligatoriedad]) -> list[DocumentoObligatorio]:
    """Un registro por tipo de documento exigido, con la regla más severa que lo exige."""
    por_tipo: dict[str, DocumentoObligatorio] = {}
    for regla in reglas:
        if not regla.activo or regla.familia_regla != "RIE" or not regla.documento_obligatorio:
            continue
        if not regla.tipo_documento:
            continue
        tipo = regla.tipo_documento.strip().upper()
        candidato = DocumentoObligatorio(tipo, regla.codigo_regla, (regla.severidad or "").upper())
        actual = por_tipo.get(tipo)
        if actual is None or _rango(candidato.severidad) < _rango(actual.severidad):
            por_tipo[tipo] = candidato
    return sorted(por_tipo.values(), key=lambda d: d.tipo_documento)
