"""
Redacción en lenguaje llano de lo que el motor muestra a personas (RNF-08).

Los motivos del semáforo, las alertas y los reportes los leen analistas y
auditores sin conocimientos técnicos. Aquí vive lo que comparten:

  * **Referencias a requisitos.** Las recomendaciones que vienen del catálogo
    de reglas o de un dictamen guardado pueden citar el requisito entre
    paréntesis («… (RN-03).»). El identificador de la regla ya viaja en su
    propio campo (`regla`), así que en el texto sobra. Los dictámenes y el
    catálogo no se reescriben: se limpia al redactar.
  * **Estados como código.** «Dictamen EN_REVISION: …» en las observaciones
    guardadas se lee «Dictamen en revisión: …».
  * **Fechas.** «29 de septiembre de 2026» en lugar de «2026-09-29».
"""
from __future__ import annotations

import re
from datetime import date

_MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

# «(RN-03)», «(RIE-02, RN-05)», «(RSC-02-CONT)», «(Nivel 5)», «(Nivel 5, RF-14)».
_REFERENCIA = re.compile(
    r"\s*\((?:(?:RIE|RCV|RSC|RDS|RN|RF|RNF|HU|PLUS)-[0-9A-Z-]+|Nivel(?:es)? [1-5](?: y [1-5])?)"
    r"(?:\s*,\s*(?:(?:RIE|RCV|RSC|RDS|RN|RF|RNF|HU|PLUS)-[0-9A-Z-]+|Nivel(?:es)? [1-5](?: y [1-5])?))*\)"
)


def sin_referencias(texto: str | None) -> str | None:
    """Quita las referencias a requisitos entre paréntesis; el resto no cambia."""
    if not texto:
        return texto
    return _REFERENCIA.sub("", texto).strip()


_ESTADOS = (("NO_CONFORME", "no conforme"), ("EN_REVISION", "en revisión"), ("CONFORME", "conforme"))


def texto_llano(texto: str | None) -> str | None:
    """
    sin_referencias() y, además, los estados del dictamen escritos como código
    («Dictamen EN_REVISION: …» en las observaciones que guarda el ai-service).
    """
    texto = sin_referencias(texto)
    if not texto:
        return texto
    for codigo, legible in _ESTADOS:
        texto = texto.replace(codigo, legible)
    return texto


def fecha_legible(valor: date | None) -> str:
    """«29 de septiembre de 2026»."""
    if valor is None:
        return "—"
    return f"{valor.day} de {_MESES[valor.month - 1]} de {valor.year}"


def dias(n: int) -> str:
    """«1 día», «12 días»."""
    return f"{n} día" if n == 1 else f"{n} días"
