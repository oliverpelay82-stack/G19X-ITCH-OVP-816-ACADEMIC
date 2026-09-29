"""
Sentido de la opinión de cumplimiento de obligaciones fiscales (Art. 32-D del
CFF) — regla RSC-OPIN-SENT, extensión PLUS-03 (PRD §21.1).

El SAT declara el sentido en un formato fijo («Sentido: Positivo», «se emite
opinión en sentido negativo»), así que se lee del texto con reglas
deterministas y no se consulta al modelo: el resultado es reproducible, no
consume tokens de Groq y no depende de que el modelo interprete bien una
leyenda. La lectura es deliberadamente conservadora:

  * Solo cuenta una declaración explícita del sentido. Una mención condicional
    («en caso de que la opinión sea en sentido negativo…») no es una
    declaración y se descarta.
  * Si el texto declara dos sentidos distintos, el resultado es AMBIGUO: un
    analista decide. Nunca se rechaza un documento por una lectura dudosa.
  * La comparación tolera acentos perdidos y las confusiones habituales del
    OCR entre cifras y letras (NEGAT1VO, P0SITIVO).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

CODIGO_REGLA = "RSC-OPIN-SENT"

POSITIVO = "POSITIVO"
NEGATIVO = "NEGATIVO"
SIN_OBLIGACIONES = "SIN_OBLIGACIONES"
NO_INSCRITO = "NO_INSCRITO"
AMBIGUO = "AMBIGUO"

# Longitud máxima de la cita: la del renglón que contiene la declaración.
MAX_CITA = 200

# Cifras que el OCR confunde con letras. La sustitución es de un carácter por
# otro, así que las posiciones del texto normalizado siguen siendo las del original.
_CIFRAS_COMO_LETRAS = str.maketrans("0158", "oisb")

_VALOR = r"(positiv[oa]|negativ[oa]|inscrito\s+sin\s+obligaciones|sin\s+obligaciones|no\s+inscrito)"
_DECLARACIONES = [
    # «Sentido: Positivo», «Sentido de la opinión: NEGATIVO», «en sentido positivo»
    re.compile(r"sentido\s*(?:de\s+la\s+opinion)?\s*[:\-]?\s*(?:es\s+)?" + _VALOR),
    # «se emite opinión Positiva», «se emite la opinión en sentido negativo»
    re.compile(r"se\s+emite\s+(?:la\s+)?opinion\s+(?:del\s+cumplimiento\s+)?(?:en\s+sentido\s+)?" + _VALOR),
    # «Opinión: POSITIVA»
    re.compile(r"opinion\s*:\s*" + _VALOR),
]
# Palabras que, justo antes de la declaración, la vuelven hipotética.
_CONDICIONAL = re.compile(r"(en\s+caso\s+de|si\s+la|si\s+el|si\s+se|cuando|de\s+ser|de\s+resultar)[^.]{0,60}$")


@dataclass
class Sentido:
    valor: str | None       # POSITIVO, NEGATIVO, SIN_OBLIGACIONES, NO_INSCRITO, AMBIGUO o None
    cita: str | None        # renglón del documento con la declaración, tal como está escrito


def _normalizar(texto: str) -> str:
    """Minúsculas sin acentos y con cifras como letras; un carácter por cada carácter del original."""
    salida = []
    for c in texto:
        # [:1]: algunas minúsculas y descomposiciones ocupan dos caracteres.
        minuscula = c.lower()[:1] or c
        salida.append(unicodedata.normalize("NFKD", minuscula)[:1] or minuscula)
    return "".join(salida).translate(_CIFRAS_COMO_LETRAS)


def _clasificar(valor: str) -> str:
    valor = " ".join(valor.split())
    if valor.startswith("positiv"):
        return POSITIVO
    if valor.startswith("negativ"):
        return NEGATIVO
    if valor == "no inscrito":
        return NO_INSCRITO
    return SIN_OBLIGACIONES


def _renglon(texto: str, inicio: int, fin: int) -> str:
    """El renglón (o renglones) del original que contienen la declaración, acotado a MAX_CITA."""
    ini = texto.rfind("\n", 0, inicio) + 1
    fin_renglon = texto.find("\n", fin)
    renglon = " ".join(texto[ini:fin_renglon if fin_renglon >= 0 else len(texto)].split())
    if len(renglon) <= MAX_CITA:
        return renglon
    # Renglón muy largo (capa vectorial sin saltos): ventana centrada en la declaración.
    centro = " ".join(texto[max(ini, inicio - 80):fin + 40].split())
    return centro[:MAX_CITA]


def leer_sentido(texto: str) -> Sentido:
    """Sentido declarado en el texto de una opinión de cumplimiento, con su cita."""
    normalizado = _normalizar(texto)
    hallazgos: dict[str, tuple[int, int]] = {}
    for patron in _DECLARACIONES:
        for m in patron.finditer(normalizado):
            if _CONDICIONAL.search(normalizado[max(0, m.start() - 70):m.start()]):
                continue
            hallazgos.setdefault(_clasificar(m.group(1)), (m.start(), m.end()))
    if not hallazgos:
        return Sentido(None, None)
    if len(hallazgos) > 1:
        inicio, fin = min(hallazgos.values())
        return Sentido(AMBIGUO, _renglon(texto, inicio, fin))
    valor, (inicio, fin) = next(iter(hallazgos.items()))
    return Sentido(valor, _renglon(texto, inicio, fin))
