"""
M6 (ESTADO_DEL_DESARROLLO §6.6) — Versión del catálogo de reglas.

Huella SHA-256 abreviada (``cat-`` y 12 caracteres hexadecimales) de todo lo
que decide un dictamen: código, nombre, familia, descripción, severidad,
acción, alcance (tipo de documento y de expediente, documento principal),
obligatoriedad, días de vigencia y si la regla está activa. Pausar, editar o
agregar una regla cambia la versión; el identificador interno y la fecha de
alta no cuentan.

Cada dictamen guarda la versión con que se emitió y la evaluación del
expediente la informa (protocolo de auditoría del DOC-05): aunque después se
pause o cambie una regla, se sabe con qué catálogo se dictaminó.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable

CAMPOS = (
    "codigo_regla", "nombre_regla", "familia_regla", "descripcion", "severidad", "accion", "tipo_documento",
    "documento_obligatorio", "tipo_expediente", "documento_principal", "dias_maximos_vigencia", "activo",
)
CABECERA = "X-Version-Catalogo"


def calcular(reglas: Iterable[Any]) -> str:
    """Versión del catálogo completo (activas y pausadas), independiente del orden de consulta."""
    filas = sorted(({c: getattr(r, c, None) for c in CAMPOS} for r in reglas), key=lambda f: f["codigo_regla"] or "")
    canonico = json.dumps(filas, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)
    return "cat-" + hashlib.sha256(canonico.encode("utf-8")).hexdigest()[:12]


# M7 (ESTADO_DEL_DESARROLLO §6.7): versión de las reglas que deciden el dictamen de un tipo de
# documento: las de contenido (RSC, RDS) y de vigencia (RCV) de ese tipo, más
# las de vigencia generales (fecha de vencimiento declarada, RCV-01). Una regla
# de otro tipo no la cambia. La clave «*» es la de un tipo sin reglas propias.
CABECERA_POR_TIPO = "X-Version-Reglas-Tipo"
GENERAL = "*"
_FAMILIAS_DEL_DICTAMEN = ("RSC", "RDS", "RCV")


def _aplica(regla: Any, tipo: str | None) -> bool:
    familia = (getattr(regla, "familia_regla", "") or "").upper()
    propio = (getattr(regla, "tipo_documento", None) or "").upper() or None
    if familia not in _FAMILIAS_DEL_DICTAMEN:
        return False
    return propio == tipo if propio else familia == "RCV"


def por_tipo(reglas: Iterable[Any]) -> dict[str, str]:
    """{tipo de documento: versión de sus reglas}, más «*» para los tipos sin reglas propias."""
    reglas = list(reglas)
    tipos = {(r.tipo_documento or "").upper() for r in reglas if r.tipo_documento} - {""}
    versiones = {GENERAL: "tip-" + calcular([r for r in reglas if _aplica(r, None)])[4:]}
    for tipo in sorted(tipos):
        versiones[tipo] = "tip-" + calcular([r for r in reglas if _aplica(r, tipo)])[4:]
    return versiones


def de_tipo(reglas: Iterable[Any], tipo: str | None) -> str:
    versiones = por_tipo(reglas)
    return versiones.get((tipo or "").upper(), versiones[GENERAL])

