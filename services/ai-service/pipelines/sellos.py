"""
Sello Digital SAT (DOC-08: «presencia de Sello Digital SAT»), detectado en el
texto extraído: la cadena original o el sello digital que imprime el SAT.

La detección de sellos en tinta de color (zonas por croma y relectura de la
página con la tinta atenuada) se retiró el 02/10/2026: ningún DOC la pide,
estaba apagada por omisión y en el acta real medida no se activó en ninguna
página (docs/VALIDACION_CUANTITATIVA.md).
"""
from __future__ import annotations

import re

_SELLO_DIGITAL = re.compile(r"sello\s*digital|cadena\s*original", re.IGNORECASE)


def tiene_sello_digital(texto: str) -> bool:
    """El texto incluye el Sello Digital SAT (cadena original o sello digital)."""
    return bool(_SELLO_DIGITAL.search(texto or ""))
