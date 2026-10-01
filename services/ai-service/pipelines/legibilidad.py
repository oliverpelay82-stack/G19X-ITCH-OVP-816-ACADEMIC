"""
Excepción «Documento ilegible, se requiere recarga» (DOC-05, Tabla 1; P5).

La extracción del Nivel 3 puede terminar sin texto suficiente para verificar
nada: un escaneo de muy baja calidad o una imagen borrosa. En ese caso no tiene
sentido llamar al modelo (no hay qué analizar y se gastaría cuota): la auditoría
emite directamente un dictamen En revisión de origen NIVEL_3_ILEGIBLE.

Criterio conservador, para marcar solo lo claramente ilegible:
  * no se recuperó texto, o
  * hay menos de ``LEGIBILIDAD_MIN_CARACTERES`` caracteres útiles (letras y
    dígitos) por página **y** la confianza del OCR es menor que
    ``LEGIBILIDAD_MIN_CONFIANZA``.
Un documento breve pero nítido (una sola línea de capa vectorial, confianza
alta) no es ilegible. Los umbrales se calibran con el Gold Standard escaneado.
"""
from __future__ import annotations

import re
from typing import Any

from config import settings

_UTIL = re.compile(r"[\W_]+", re.UNICODE)


def caracteres_utiles(texto: str | None) -> int:
    """Letras y dígitos del texto (sin espacios, puntuación ni guiones de relleno)."""
    return len(_UTIL.sub("", texto or ""))


def motivo_ilegible(texto: str | None, traza: dict[str, Any] | None) -> str | None:
    """Motivo en lenguaje llano si la lectura no obtuvo texto suficiente; None si el documento es legible."""
    traza = traza or {}
    utiles = caracteres_utiles(texto)
    if utiles == 0:
        return "La lectura no recuperó texto: el archivo puede estar en blanco o ser una imagen sin contenido legible."
    paginas = max(int(traza.get("total_paginas") or 1), 1)
    por_pagina = utiles / paginas
    confianza = traza.get("confidence_score")
    confianza_baja = confianza is None or float(confianza) < settings.LEGIBILIDAD_MIN_CONFIANZA
    if por_pagina < settings.LEGIBILIDAD_MIN_CARACTERES and confianza_baja:
        detalle_confianza = f" y una confianza de lectura de {float(confianza):.0%}" if confianza is not None else ""
        return (
            f"La lectura obtuvo apenas {por_pagina:.0f} caracteres por página{detalle_confianza}: "
            "el escaneo es de muy baja calidad o la imagen está borrosa."
        )
    return None
