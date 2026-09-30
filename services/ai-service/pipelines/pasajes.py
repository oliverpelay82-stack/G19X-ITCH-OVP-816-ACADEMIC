"""
Pasaje literal del documento, sin modelo — T1, PLUS-08 (PRD §21.4).

Para una pregunta que pide el texto de una cláusula («¿qué dice la cláusula de
confidencialidad?») o un monto («¿cuál es el monto de la contraprestación?»), el
chat devuelve el renglón del documento que lo contiene, con su página, rotulado
como pasaje. No interpreta: la lectura la hace el analista.

Salvaguardas:
  * Solo si un tramo gana con claridad: su puntaje supera en ``VENTAJA_MINIMA``
    al del siguiente tramo, o es el único. Siete páginas que repiten el mismo
    texto no se resuelven aquí: las resuelve el modelo con su contexto.
  * En un monto, el pasaje debe contener una cantidad en pesos.
  * El pasaje es un recorte literal (se ancla como cita y abre el visor).
  * Las preguntas interpretativas van al modelo, igual que en T0, y también las que
    preguntan por un monto con menos de dos términos propios (un seguimiento breve).
  * En un monto, si varias cantidades empatan (tres sumas aseguradas), la pregunta
    tiene varias respuestas y va al modelo.
"""
from __future__ import annotations

import re
from typing import Any

from pipelines import fragmentos
from pipelines.respuestas_directas import _INTERPRETATIVA, _normalizar

VENTAJA_MINIMA = 1.3
# Términos propios que debe traer una pregunta por un monto: «¿y cuánto se paga?»
# depende de la conversación y con un solo término no ubica un pasaje. Una pregunta
# que nombra la cláusula («¿qué dice la cláusula de confidencialidad?») basta con su tema.
MIN_TERMINOS = {"monto": 2, "clausula": 1}
_MAX_PASAJE = 420
_RENGLONES_EXTRA = 2

_PIDE_TEXTO = re.compile(r"\b(que dice|que establece|que senala|que estipula|muestrame|transcribe|texto de|cita)\b")
_SECCION = re.compile(r"\b(clausula|articulo|anexo|apartado|seccion|inciso)\b")
_PIDE_MONTO = re.compile(r"\b(monto|importe|precio|cuanto (cuesta|se paga|paga|pagara)|contraprestacion|"
                         r"suma asegurada|capital social|prima total)\b")
_CANTIDAD = re.compile(r"\$\s?\d[\d,. ]*")


def intencion(pregunta: str) -> str | None:
    texto = _normalizar(pregunta)
    if _INTERPRETATIVA.search(texto):
        return None
    if _PIDE_MONTO.search(texto):
        return "monto"
    if _PIDE_TEXTO.search(texto) and _SECCION.search(texto):
        return "clausula"
    return None


def _renglones_con(tramo: str, base: set[str], requiere_cantidad: bool) -> str | None:
    """
    El renglón del tramo que más términos reúne y los siguientes. En un monto, solo
    cuentan los renglones con una cantidad en ellos o en los dos siguientes («la
    cantidad mensual de / $185,000.00»): «del monto mensual de la contraprestación»,
    en la cláusula de la pena, reúne más términos pero no dice el monto.
    """
    renglones = [r for r in tramo.splitlines() if r.strip()]
    if not renglones:
        return None
    alcance = {i: next((j for j in range(i, min(len(renglones), i + _RENGLONES_EXTRA + 1))
                        if _CANTIDAD.search(renglones[j])), None) for i in range(len(renglones))}
    puntaje = [len(set(fragmentos.tokenizar(r)) & base) if not requiere_cantidad or alcance[i] is not None else 0
               for i, r in enumerate(renglones)]
    if max(puntaje) == 0:
        return None
    if requiere_cantidad and puntaje.count(max(puntaje)) > 1 and len({alcance[i] for i, p in enumerate(puntaje)
                                                                     if p == max(puntaje)}) > 1:
        # Varias cantidades empatan («Suma asegurada» de tres coberturas): la pregunta tiene
        # varias respuestas y un solo renglón la contestaría a medias.
        return None
    inicio = puntaje.index(max(puntaje))
    fin = alcance[inicio] if requiere_cantidad else min(len(renglones) - 1, inicio + _RENGLONES_EXTRA)
    pasaje = "\n".join(r.strip() for r in renglones[inicio:fin + 1])
    return pasaje if len(pasaje) <= _MAX_PASAJE else None


def _distintos(tramos: list) -> list:
    """Tramos que no se traslapan entre sí (las ventanas de BM25 se traslapan un 20 %)."""
    elegidos = []
    for t, p in tramos:
        if not any(fragmentos._repite(t, [e]) or fragmentos._repite(e, [t]) for e, _ in elegidos):
            elegidos.append((t, p))
    return elegidos


def _pasaje_de_clausula(tramos: list, base: set[str]) -> str | None:
    """El tramo ganador, si supera en VENTAJA_MINIMA al mejor tramo distinto."""
    distintos = _distintos(tramos)
    (mejor, puntaje), siguiente = distintos[0], (distintos[1][1] if len(distintos) > 1 else 0.0)
    if siguiente and puntaje < VENTAJA_MINIMA * siguiente:
        return None
    return _renglones_con(mejor.texto, base, requiere_cantidad=False)


def _pasaje_de_monto(tramos: list, base: set[str]) -> str | None:
    """
    En un monto compiten solo los renglones que dicen una cantidad: gana el que
    reúne más términos de la pregunta, si ningún renglón de otro tramo lo empata.
    «Monto mensual total» también aparece en las deductivas y en la pena, pero
    sin una cantidad en pesos.
    """
    candidatos, vistos = [], set()
    # Todos los tramos: uno traslapado con otro puede contener un renglón distinto.
    for tramo, _ in tramos[:6]:
        pasaje = _renglones_con(tramo.texto, base, requiere_cantidad=True)
        if pasaje and pasaje not in vistos:          # el mismo renglón visto desde otra ventana no compite
            vistos.add(pasaje)
            candidatos.append((len(set(fragmentos.tokenizar(pasaje.splitlines()[0])) & base), pasaje))
    candidatos.sort(key=lambda c: c[0], reverse=True)
    if not candidatos or (len(candidatos) > 1 and candidatos[1][0] >= candidatos[0][0]):
        return None
    return candidatos[0][1]


def responder(pregunta: str, texto: str, paginas: list[dict[str, Any]] | None = None) -> tuple[str, int | None] | None:
    """(respuesta, página) con el pasaje literal, o ``None`` si la pregunta debe ir al modelo."""
    nombre = intencion(pregunta)
    if nombre is None:
        return None
    # Las palabras de la petición («qué dice la cláusula de…») no distinguen ningún tramo.
    tema = _SECCION.sub(" ", _PIDE_TEXTO.sub(" ", _normalizar(pregunta)))
    base = set(fragmentos.tokenizar(tema))
    if len(base) < MIN_TERMINOS[nombre]:
        return None
    tramos = fragmentos.tramos_relevantes(texto, tema)
    if not tramos:
        return None
    pasaje = _pasaje_de_monto(tramos, base) if nombre == "monto" else _pasaje_de_clausula(tramos, base)
    if not pasaje:
        return None
    # Cada renglón se cita por separado: el visor ubica cada cita en su renglón.
    citas = " ".join(f"«{r}»" for r in pasaje.splitlines())
    inicio = texto.strip().find(pasaje.splitlines()[0])
    pagina = fragmentos.pagina_de(inicio, paginas) if inicio >= 0 else None
    donde = f", página {pagina}" if pagina else ""
    return (f"Pasaje del documento{donde}:\n{citas}\n"
            "Es el texto literal del documento, sin interpretación; la lectura corresponde al analista."), pagina
