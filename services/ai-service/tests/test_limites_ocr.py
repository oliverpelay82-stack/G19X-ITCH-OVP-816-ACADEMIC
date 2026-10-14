"""
Topes defensivos del Nivel 3 (hallazgo 7 de la auditoría del 14/10/2026; HU-33,
RNF-02). Con Tesseract local y sin red.

  1. Una página que excede OCR_TIMEOUT_PAGINA_SEGUNDOS se corta: la extracción
     falla con TiempoOcrExcedidoError (400) y el pool de OCR sigue atendiendo,
     sin un hilo retenido por un Tesseract colgado.
  2. Una página PDF que a OCR_DPI excedería OCR_MAX_MEGAPIXELES_PAGINA se
     rasteriza a menos ppp, con su proporción; una de tamaño normal no cambia.
  3. Lo mismo para una imagen JPEG o PNG.
"""
import io
import os

import fitz
import pytest
from PIL import Image

from config import settings
from pipelines import extraccion_pipeline

ESCANEADA = os.path.join(os.path.dirname(__file__), "fixtures", "constancia_escaneada.pdf")


def _escaneada() -> bytes:
    with open(ESCANEADA, "rb") as archivo:
        return archivo.read()


def test_una_pagina_que_excede_el_tiempo_se_corta_y_el_pool_sigue_atendiendo(monkeypatch):
    monkeypatch.setattr(settings, "OCR_TIMEOUT_PAGINA_SEGUNDOS", 0.001)
    with pytest.raises(extraccion_pipeline.TiempoOcrExcedidoError, match="tardó más de"):
        extraccion_pipeline.extraer_texto(_escaneada(), forzar_ocr=True, texto_completo=True)

    monkeypatch.setattr(settings, "OCR_TIMEOUT_PAGINA_SEGUNDOS", 120)
    resultado = extraccion_pipeline.extraer_texto(_escaneada(), forzar_ocr=True, texto_completo=True)
    assert resultado.total_caracteres > 100, "Tras el corte, el pool de OCR reconoce con normalidad"


def _pagina(ancho_pt: float, alto_pt: float) -> "fitz.Page":
    documento = fitz.open()
    return documento.new_page(width=ancho_pt, height=alto_pt)


def test_una_pagina_enorme_se_rasteriza_dentro_del_tope(monkeypatch):
    monkeypatch.setattr(settings, "OCR_MAX_MEGAPIXELES_PAGINA", 1.0)
    imagen = extraccion_pipeline._rasterizar(_pagina(612, 1008))  # oficio: 10.7 MP a 300 ppp
    alto, ancho = imagen.shape
    assert ancho * alto <= 1_010_000, "MuPDF redondea hacia arriba cada lado: el tope admite ese píxel de más"
    assert abs(alto / ancho - 1008 / 612) < 0.01, "Conserva la proporción"


def test_una_pagina_normal_no_cambia():
    imagen = extraccion_pipeline._rasterizar(_pagina(612, 792))  # carta
    assert imagen.shape == (round(792 * settings.OCR_DPI / 72), round(612 * settings.OCR_DPI / 72))


@pytest.mark.parametrize("formato", ["JPEG", "PNG"])
def test_una_imagen_enorme_se_reduce_dentro_del_tope(monkeypatch, formato):
    monkeypatch.setattr(settings, "OCR_MAX_MEGAPIXELES_PAGINA", 0.04)
    salida = io.BytesIO()
    Image.new("RGB", (800, 400), "white").save(salida, formato)
    with extraccion_pipeline.abrir_imagen(salida.getvalue()) as imagen:
        assert imagen.width * imagen.height <= 40_000
        assert abs(imagen.width / imagen.height - 2) < 0.05
