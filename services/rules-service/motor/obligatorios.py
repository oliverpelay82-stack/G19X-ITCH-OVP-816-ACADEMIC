"""
Catálogo de documentos obligatorios por expediente (RIE-01, RIE-02; HU-09, HU-10 y HU-12).

La completitud de un expediente no se decide en el código del core-service:
se deriva de las reglas activas de la familia RIE que declaran un tipo de
documento con ``documento_obligatorio = True``. Pausar o dar de alta una de
esas reglas desde la interfaz cambia qué documentos exige el expediente sin
tocar una línea de código (RF-06).

  * **Por tipo de expediente (RF-06).** Una regla con ``tipo_expediente`` solo
    aplica a ese tipo (jurídico, corporativo o regulatorio); sin él, a todos.
  * **Anexos vinculados (RIE-02, RF-07).** Una regla con ``documento_principal``
    exige su ``tipo_documento`` como anexo solo cuando el expediente contiene
    el documento principal. El core-service decide si el principal está
    presente; aquí solo se declara el vínculo.

Las reglas generales (sin tipo de documento, como RIE-01 o RIE-03) no aportan
un tipo: describen el criterio, no el inventario.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol

# De la más grave a la menos grave: si dos reglas exigen el mismo tipo de
# documento, prevalece la severidad más alta.
ORDEN_SEVERIDAD = ["CRITICA", "ALTA", "MEDIA_ALTA", "MEDIA", "BAJA"]

TIPOS_EXPEDIENTE = ("JURIDICO", "CORPORATIVO", "REGULATORIO")


class ReglaObligatoriedad(Protocol):
    codigo_regla: str
    familia_regla: str
    severidad: str
    tipo_documento: str | None
    documento_obligatorio: bool
    activo: bool
    tipo_expediente: str | None
    documento_principal: str | None


@dataclass
class DocumentoObligatorio:
    tipo_documento: str
    codigo_regla: str
    severidad: str
    # Solo en los anexos (RIE-02): documento cuya presencia los vuelve exigibles.
    documento_principal: str | None = None
    tipo_expediente: str | None = None


def _rango(severidad: str) -> int:
    valor = (severidad or "").upper()
    return ORDEN_SEVERIDAD.index(valor) if valor in ORDEN_SEVERIDAD else len(ORDEN_SEVERIDAD)


def _normalizar(valor: str | None) -> str | None:
    return valor.strip().upper() if valor and valor.strip() else None


def documentos_obligatorios(
    reglas: Iterable[ReglaObligatoriedad], tipo_expediente: str | None = None
) -> list[DocumentoObligatorio]:
    """
    Un registro por documento exigido (y por vínculo de anexo), con la regla
    más severa que lo exige. Con ``tipo_expediente`` se descartan las reglas de
    otros tipos; sin él se devuelven todas, como antes de RF-06.
    """
    tipo_exp = _normalizar(tipo_expediente)
    por_clave: dict[tuple[str, str | None], DocumentoObligatorio] = {}
    for regla in reglas:
        if not regla.activo or regla.familia_regla != "RIE" or not regla.documento_obligatorio:
            continue
        tipo = _normalizar(regla.tipo_documento)
        if not tipo:
            continue
        alcance = _normalizar(getattr(regla, "tipo_expediente", None))
        if tipo_exp and alcance and alcance != tipo_exp:
            continue
        principal = _normalizar(getattr(regla, "documento_principal", None))
        candidato = DocumentoObligatorio(tipo, regla.codigo_regla, (regla.severidad or "").upper(), principal, alcance)
        clave = (tipo, principal)
        actual = por_clave.get(clave)
        if actual is None or _rango(candidato.severidad) < _rango(actual.severidad):
            por_clave[clave] = candidato
    return sorted(por_clave.values(), key=lambda d: (d.documento_principal or "", d.tipo_documento))
