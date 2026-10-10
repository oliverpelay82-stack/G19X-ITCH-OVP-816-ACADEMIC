"""
Métricas de la validación cuantitativa (docs/VALIDACION_CUANTITATIVA.md §4 y §6.3).

Funciones puras, sin dependencias del servicio, para que cada cifra del reporte
pueda recalcularse a mano:

  * ``Conteo`` y ``comparar_campo``: VP, FP, FN y VN de un campo extraído, con la
    convención de *slot filling* (un valor equivocado es FP y FN a la vez).
  * ``wilson``: intervalo de confianza de una proporción.
  * ``matriz_confusion``, ``exactitud``, ``f1_macro`` y ``kappa_cohen``: decisiones
    de los Niveles 4 y 5 (CONFORME, EN_REVISION, NO_CONFORME).
  * ``bootstrap_f1``: intervalo del F1 micro remuestreando casos.
  * ``percentil``: latencias p50 y p95.
  * ``distancia_edicion`` y ``cer``: tasa de error de caracteres del OCR.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Any, Callable, Iterable, Sequence


@dataclass
class Conteo:
    vp: int = 0
    fp: int = 0
    fn: int = 0
    vn: int = 0

    def __add__(self, otro: "Conteo") -> "Conteo":
        return Conteo(self.vp + otro.vp, self.fp + otro.fp, self.fn + otro.fn, self.vn + otro.vn)

    @property
    def precision(self) -> float | None:
        """VP / (VP + FP); ``None`` si el sistema no afirmó nada (indefinida, no cero)."""
        return self.vp / (self.vp + self.fp) if self.vp + self.fp else None

    @property
    def exhaustividad(self) -> float | None:
        """VP / (VP + FN); ``None`` si no había nada que encontrar."""
        return self.vp / (self.vp + self.fn) if self.vp + self.fn else None

    @property
    def f1(self) -> float | None:
        p, r = self.precision, self.exhaustividad
        if p is None or r is None:
            return None
        return 2 * p * r / (p + r) if p + r else 0.0

    def a_dict(self) -> dict[str, Any]:
        return {"vp": self.vp, "fp": self.fp, "fn": self.fn, "vn": self.vn,
                "precision": self.precision, "exhaustividad": self.exhaustividad, "f1": self.f1}


def comparar_campo(esperado: Any, extraido: Any, iguales: Callable[[Any, Any], bool] | None = None) -> Conteo:
    """
    Clasifica la extracción de un campo contra su valor esperado.

    ``None`` representa «el documento no trae el dato» (en lo esperado) y «el
    sistema no extrajo nada» (en lo extraído). Un valor extraído distinto del
    esperado cuenta como FP (afirmó algo falso) y como FN (omitió lo verdadero).
    """
    iguales = iguales or (lambda a, b: a == b)
    if esperado is None:
        return Conteo(vn=1) if extraido is None else Conteo(fp=1)
    if extraido is None:
        return Conteo(fn=1)
    return Conteo(vp=1) if iguales(esperado, extraido) else Conteo(fp=1, fn=1)


def sumar(conteos: Iterable[Conteo]) -> Conteo:
    total = Conteo()
    for c in conteos:
        total = total + c
    return total


def wilson(exitos: int, total: int, z: float = 1.96) -> tuple[float, float] | None:
    """Intervalo de Wilson al 95 % (z = 1.96). A diferencia del de Wald, no colapsa en 0 % ni en 100 %."""
    if total <= 0:
        return None
    p = exitos / total
    denominador = 1 + z * z / total
    centro = (p + z * z / (2 * total)) / denominador
    margen = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominador
    return max(0.0, centro - margen), min(1.0, centro + margen)


def matriz_confusion(pares: Iterable[tuple[str, str]], clases: Sequence[str]) -> dict[str, dict[str, int]]:
    """Filas: clase esperada; columnas: clase dictaminada."""
    matriz = {e: {p: 0 for p in clases} for e in clases}
    for esperado, predicho in pares:
        if esperado not in matriz or predicho not in matriz:
            raise ValueError(f"Clase fuera del catálogo: esperado={esperado!r}, dictaminado={predicho!r}")
        matriz[esperado][predicho] += 1
    return matriz


def _total(matriz: dict[str, dict[str, int]]) -> int:
    return sum(sum(fila.values()) for fila in matriz.values())


def exactitud(matriz: dict[str, dict[str, int]]) -> float | None:
    n = _total(matriz)
    return sum(matriz[c][c] for c in matriz) / n if n else None


def f1_por_clase(matriz: dict[str, dict[str, int]]) -> dict[str, Conteo]:
    clases = list(matriz)
    return {
        c: Conteo(
            vp=matriz[c][c],
            fp=sum(matriz[o][c] for o in clases if o != c),
            fn=sum(matriz[c][o] for o in clases if o != c),
        )
        for c in clases
    }


def f1_macro(matriz: dict[str, dict[str, int]]) -> float | None:
    """Promedio del F1 de las clases que tienen al menos un caso esperado o dictaminado."""
    valores = [c.f1 for c in f1_por_clase(matriz).values() if c.vp + c.fp + c.fn]
    valores = [0.0 if v is None else v for v in valores]
    return sum(valores) / len(valores) if valores else None


def kappa_cohen(matriz: dict[str, dict[str, int]]) -> float | None:
    """κ = (p_o − p_e) / (1 − p_e): acuerdo entre el motor y la anotación corregido por azar."""
    n = _total(matriz)
    if not n:
        return None
    clases = list(matriz)
    p_o = sum(matriz[c][c] for c in clases) / n
    p_e = sum(
        (sum(matriz[c].values()) / n) * (sum(matriz[o][c] for o in clases) / n)
        for c in clases
    )
    return 1.0 if p_e == 1 else (p_o - p_e) / (1 - p_e)


def bootstrap_f1(
    conteos_por_caso: Sequence[Conteo], repeticiones: int = 1000, semilla: int = 20260930
) -> tuple[float, float] | None:
    """
    Intervalo al 95 % del F1 micro por *bootstrap* de casos: remuestrea los
    casos con reemplazo (las unidades de un mismo documento no son
    independientes) y toma los percentiles 2.5 y 97.5. Semilla fija para que
    el reporte sea reproducible.
    """
    if not conteos_por_caso:
        return None
    azar = random.Random(semilla)
    n = len(conteos_por_caso)
    valores = []
    for _ in range(repeticiones):
        f1 = sumar(conteos_por_caso[azar.randrange(n)] for _ in range(n)).f1
        if f1 is not None:
            valores.append(f1)
    if not valores:
        return None
    return percentil(valores, 2.5), percentil(valores, 97.5)


def percentil(valores: Sequence[float], p: float) -> float | None:
    """Percentil con interpolación lineal entre rangos (el método por defecto de NumPy)."""
    if not valores:
        return None
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    abajo, arriba = math.floor(posicion), math.ceil(posicion)
    if abajo == arriba:
        return float(ordenados[abajo])
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def distancia_edicion(a: str, b: str) -> int:
    """Distancia de Levenshtein (inserciones, eliminaciones y sustituciones de un carácter)."""
    if len(a) < len(b):
        a, b = b, a
    anterior = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        actual = [i]
        for j, cb in enumerate(b, start=1):
            actual.append(min(anterior[j] + 1, actual[j - 1] + 1, anterior[j - 1] + (ca != cb)))
        anterior = actual
    return anterior[-1]


def cer(referencia: str, reconocido: str) -> float | None:
    """
    Tasa de error de caracteres: distancia de edición / longitud de la referencia.

    Antes de comparar se colapsan los espacios y saltos de línea en uno solo: el
    OCR no reproduce la maquetación y eso no es un error de lectura. Puede pasar
    de 1 si el OCR inventa más texto del que hay.
    """
    ref = " ".join(referencia.split())
    rec = " ".join(reconocido.split())
    return distancia_edicion(ref, rec) / len(ref) if ref else None
