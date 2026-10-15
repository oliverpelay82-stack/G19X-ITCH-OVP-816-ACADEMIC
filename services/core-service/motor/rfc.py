"""
M1 (ESTADO_DEL_DESARROLLO §6.6) — RFC validado en el servidor.

El titular se identifica por su RFC (DOC-02). Hasta P6 el backend solo exigía
12 o 13 caracteres: un RFC con un dígito equivocado se aceptaba y después la
titularidad fallaba o, peor, coincidía con otra persona.

  * **Rechazo (422):** formato incorrecto, longitud que no corresponde al tipo
    de persona (12 moral, 13 física) o fecha AAMMDD imposible.
  * **Dígito verificador:** se calcula con el algoritmo público del SAT
    (módulo 11 sobre el diccionario de 39 caracteres; a la persona moral se le
    antepone un espacio para igualar las 12 posiciones de la física).

Resultado de la verificación (``rfc_verificacion`` en la respuesta):
``VERIFICADO`` (dígito correcto), ``GENERICO`` (RFC genéricos del SAT) o
``DIGITO_NO_COINCIDE``. Por decisión del residente, mientras se trabaja con RFC
de prueba este último se acepta con advertencia; ``RFC_DIGITO_ESTRICTO=true``
lo rechaza.
"""
from __future__ import annotations

import os
import re
from datetime import date

VERIFICADO = "VERIFICADO"
GENERICO = "GENERICO"
DIGITO_NO_COINCIDE = "DIGITO_NO_COINCIDE"

# RFC genéricos del SAT: público en general (nacional) y residentes en el extranjero.
GENERICOS = frozenset({"XAXX010101000", "XEXX010101000"})

# La homoclave se admite alfanumérica completa: un RFC de prueba cuyo último
# carácter no puede ser dígito verificador queda como DIGITO_NO_COINCIDE.
_PATRON = {"MORAL": re.compile(r"^[A-ZÑ&]{3}\d{6}[A-Z\d]{3}$"),
           "FISICA": re.compile(r"^[A-ZÑ&]{4}\d{6}[A-Z\d]{3}$")}
_LONGITUD = {"MORAL": 12, "FISICA": 13}
_NOMBRE = {"MORAL": "persona moral", "FISICA": "persona física"}

# Diccionario del SAT para el dígito verificador.
_VALOR = {
    **{str(d): d for d in range(10)},
    **{c: 10 + i for i, c in enumerate("ABCDEFGHIJKLMN")},
    "&": 24,
    **{c: 25 + i for i, c in enumerate("OPQRSTUVWXYZ")},
    " ": 37,
    "Ñ": 38,
}


class RfcInvalido(ValueError):
    """El RFC no puede registrarse; el mensaje está en lenguaje llano (RNF-08)."""


def digito_esperado(rfc: str) -> str:
    """Dígito verificador que corresponde a las primeras 11 (moral) o 12 (física) posiciones."""
    base = rfc[:-1].rjust(12)
    suma = sum(_VALOR[c] * (13 - i) for i, c in enumerate(base))
    resto = suma % 11
    if resto == 0:
        return "0"
    return "A" if 11 - resto == 10 else str(11 - resto)


def _fecha_posible(aammdd: str) -> bool:
    """La fecha embebida existe en algún siglo (00 → 1900 o 2000, por eso el 29/02/00 es válido)."""
    aa, mm, dd = int(aammdd[:2]), int(aammdd[2:4]), int(aammdd[4:])
    for siglo in (1900, 2000):
        try:
            date(siglo + aa, mm, dd)
            return True
        except ValueError:
            continue
    return False


def digito_estricto() -> bool:
    return os.getenv("RFC_DIGITO_ESTRICTO", "false").strip().lower() in ("true", "1", "si", "sí", "yes")


def verificar(rfc: str) -> str:
    """Resultado del dígito verificador de un RFC con formato ya válido."""
    if rfc in GENERICOS:
        return GENERICO
    return VERIFICADO if digito_esperado(rfc) == rfc[-1] else DIGITO_NO_COINCIDE


def validar(rfc: str, tipo_persona: str) -> str:
    """
    Normaliza y valida el RFC para su registro. Devuelve el RFC en mayúsculas;
    lanza ``RfcInvalido`` con el motivo si no puede registrarse.
    """
    valor = (rfc or "").strip().upper()
    tipo = (tipo_persona or "MORAL").strip().upper()
    if tipo not in _LONGITUD:
        raise RfcInvalido("El tipo de persona debe ser MORAL o FISICA.")
    if valor in GENERICOS:
        return valor
    if len(valor) != _LONGITUD[tipo]:
        raise RfcInvalido(f"Un RFC de {_NOMBRE[tipo]} tiene {_LONGITUD[tipo]} caracteres; «{valor}» tiene {len(valor)}.")
    if not _PATRON[tipo].match(valor):
        raise RfcInvalido("Formato de RFC incorrecto: letras iniciales, fecha AAMMDD y homoclave de 3 posiciones.")
    inicio = len(valor) - 9
    if not _fecha_posible(valor[inicio:inicio + 6]):
        raise RfcInvalido(f"La fecha embebida en el RFC ({valor[inicio:inicio + 6]}, AAMMDD) no existe.")
    if digito_estricto() and verificar(valor) == DIGITO_NO_COINCIDE:
        raise RfcInvalido(f"El dígito verificador del RFC no coincide (se esperaba «{digito_esperado(valor)}»): "
                          "revise que esté bien escrito.")
    return valor
