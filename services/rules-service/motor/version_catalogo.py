"""
M6 (PRD §21.6) — Versión del catálogo de reglas.

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
