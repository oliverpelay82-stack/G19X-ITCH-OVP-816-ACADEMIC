"""
Sellos y marcas en tinta de color (Nivel 3).

En actas, poderes y documentos registrales, los sellos son evidencia: el del
notario, el del Registro Público (la inscripción de un acta puede constar solo
en un sello) o el de recepción de una autoridad. El DOC-08 pide además detectar
la presencia del Sello Digital SAT. Por eso los sellos no se borran: se leen.

El problema es que un sello estampado sobre el texto impreso lo tapa, y la
lectura en escala de grises convierte su tinta en ruido. Este módulo separa la
tinta de color del papel y del texto negro para que el Nivel 3:

  * registre cada sello como evidencia de su presencia: página y recuadro, que
    el visor resalta y el dictamen menciona;
  * detecte cuándo un sello denso hizo que la lectura perdiera el texto impreso
    (``cobertura_tinta_negra``) y, solo entonces, relea la página con la tinta
    de los sellos atenuada (``atenuar_sellos``). Atenuar siempre no conviene:
    medido sobre el acta de prueba, en páginas sin pérdida cambiaba renglones
    que la lectura normal ya reconocía bien.

El texto propio de un sello no se transcribe: medido sobre un acta real,
Tesseract no lee el texto curvo de los sellos circulares ni la tinta pálida
cruzada por firmas, y lo que devolvía era ruido que empeoraba el análisis.
Lo impreso en tinta negra —como el sello de inscripción del Registro Público
del acta de prueba— ya queda en la lectura normal.

La imagen original nunca se modifica: el visor y la huella SHA-256 siempre
corresponden al archivo custodiado. Lo que no es de color (un sello en tinta
negra, una firma) se queda en la lectura normal, como antes.

La detección usa el croma (máximo menos mínimo de los canales RGB), no la
saturación: las tintas de sello son pálidas y un umbral de saturación las
pierde. El papel de un escaneo es prácticamente neutro (croma < 5).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import cv2
import numpy as np

# Croma mínimo para considerar un píxel como tinta de color, y brillo máximo
# (lo más claro es papel aunque tenga un tinte leve).
CROMA_MIN = 28
BRILLO_MAX = 245
# Si más de esta fracción de la página es «de color», es el papel o la
# iluminación (una foto amarillenta), no sellos: la página se lee como siempre.
MAX_FRACCION_COLOR = 0.25
# Tinta mínima de una zona, en píxeles a ~75 ppp, para tomarla en cuenta.
MIN_TINTA = 100
# La detección trabaja a una cuarta parte de la resolución del OCR (~75 ppp):
# basta para ubicar un sello y cuesta la dieciseisava parte.
_ESCALA = 4
# Una zona con más tinta que esta proporción de su recuadro es un gráfico
# (holograma, escudo relleno): no tiene texto que leer.
MAX_DENSIDAD_TEXTO = 0.33
# Al atenuar un sello solo se borra su tinta clara. Donde una letra negra
# cruza la tinta del sello el píxel queda de color pero oscuro: es la letra y se
# conserva (medido: con este umbral se recuperan 9 de 9 palabras bajo un sello
# denso; borrando toda la tinta de color, 0 de 9). Una tinta de color oscura
# —texto en azul marino, una firma en tinta oscura— tampoco se borra.
BRILLO_MIN_TINTA_SELLO = 140
# Proporción ancho/alto a partir de la cual una zona es un renglón de texto
# impreso en color (un título en verde), no un sello.
MIN_PROPORCION_RENGLON = 4.0

_SELLO_DIGITAL = re.compile(r"sello\s*digital|cadena\s*original", re.IGNORECASE)


@dataclass(frozen=True)
class Zona:
    """Zona con tinta de color, en píxeles de la imagen recibida."""
    x0: int
    y0: int
    x1: int
    y1: int
    densidad: float

    @property
    def es_grafico(self) -> bool:
        return self.densidad > MAX_DENSIDAD_TEXTO

    @property
    def es_renglon(self) -> bool:
        return (self.x1 - self.x0) >= MIN_PROPORCION_RENGLON * max(self.y1 - self.y0, 1)

    @property
    def tipo(self) -> str | None:
        """SELLO (sello o marca estampada), o None si es texto impreso en color."""
        return None if self.es_renglon else "SELLO"


def mascara_color(bgr: np.ndarray) -> np.ndarray:
    """True donde hay tinta de color (croma alto y no es papel)."""
    canales = bgr.astype(np.int16)
    maximo = canales.max(axis=2)
    croma = maximo - canales.min(axis=2)
    return (croma > CROMA_MIN) & (maximo < BRILLO_MAX)


def zonas_de_color(bgr: np.ndarray) -> list[Zona]:
    """
    Zonas con tinta de color de una página (BGR), en píxeles de la imagen
    recibida. Devuelve [] si la página no es a color o si el color es el papel.
    """
    if bgr.ndim != 3:
        return []
    escala = _ESCALA
    reducida = cv2.resize(bgr, (bgr.shape[1] // escala, bgr.shape[0] // escala), interpolation=cv2.INTER_AREA)
    mascara = mascara_color(reducida).astype(np.uint8)
    if mascara.mean() > MAX_FRACCION_COLOR:
        return []
    nucleo = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7))
    agrupada = cv2.dilate(cv2.morphologyEx(mascara, cv2.MORPH_CLOSE, nucleo), nucleo)
    n, _, estadisticas, _ = cv2.connectedComponentsWithStats(agrupada)
    alto, ancho = bgr.shape[:2]
    zonas: list[Zona] = []
    for i in range(1, n):
        x, y, w, h, _ = estadisticas[i]
        tinta = int(mascara[y:y + h, x:x + w].sum())
        if tinta < MIN_TINTA:
            continue
        margen = 3
        zonas.append(Zona(
            max(0, (x - margen) * escala), max(0, (y - margen) * escala),
            min(ancho, (x + w + margen) * escala), min(alto, (y + h + margen) * escala),
            round(tinta / max(w * h, 1), 3),
        ))
    return _unir(zonas)


def _unir(zonas: list[Zona]) -> list[Zona]:
    """Une zonas que se traslapan (un sello partido en dos componentes)."""
    unidas = sorted(zonas, key=lambda z: (z.y0, z.x0))
    cambio = True
    while cambio:
        cambio = False
        for i in range(len(unidas)):
            for j in range(i + 1, len(unidas)):
                a, b = unidas[i], unidas[j]
                if a.x0 < b.x1 and b.x0 < a.x1 and a.y0 < b.y1 and b.y0 < a.y1:
                    area_a = (a.x1 - a.x0) * (a.y1 - a.y0)
                    area_b = (b.x1 - b.x0) * (b.y1 - b.y0)
                    unidas[i] = Zona(min(a.x0, b.x0), min(a.y0, b.y0), max(a.x1, b.x1), max(a.y1, b.y1),
                                     round((a.densidad * area_a + b.densidad * area_b) / (area_a + area_b), 3))
                    del unidas[j]
                    cambio = True
                    break
            if cambio:
                break
    return unidas


def atenuar_sellos(bgr: np.ndarray, zonas: list[Zona]) -> np.ndarray:
    """
    Copia de la página con la tinta clara de los sellos convertida en papel,
    solo dentro de las zonas de sello: deja el texto impreso que había debajo.
    Los renglones impresos en color no son zonas de sello y se conservan.
    """
    limpia = bgr.copy()
    for zona in zonas:
        recorte = limpia[zona.y0:zona.y1, zona.x0:zona.x1]
        recorte[mascara_color(recorte) & (recorte.max(axis=2) > BRILLO_MIN_TINTA_SELLO)] = 255
    return limpia


def cobertura_tinta_negra(bgr: np.ndarray, palabras: list[list]) -> float:
    """
    Fracción de la tinta negra de la página (texto impreso, sin la tinta de
    color) que cae dentro de alguna palabra leída. Una lectura que descartó un
    bloque de texto deja mucha tinta sin cubrir.
    """
    reducida = cv2.resize(bgr, (bgr.shape[1] // _ESCALA, bgr.shape[0] // _ESCALA), interpolation=cv2.INTER_AREA)
    negra = (cv2.cvtColor(reducida, cv2.COLOR_BGR2GRAY) < 110) & ~mascara_color(reducida)
    total = int(negra.sum())
    if total == 0:
        return 1.0
    alto, ancho = negra.shape
    cubierta = np.zeros_like(negra)
    for p in palabras:
        x0, y0 = max(0, int(p[0] * ancho) - 1), max(0, int(p[1] * alto) - 1)
        cubierta[y0:int(p[3] * alto) + 2, x0:int(p[2] * ancho) + 2] = True
    return float((negra & cubierta).sum()) / total


def tiene_sello_digital(texto: str) -> bool:
    """El texto incluye el Sello Digital SAT o su cadena original (DOC-08)."""
    return bool(_SELLO_DIGITAL.search(texto or ""))
