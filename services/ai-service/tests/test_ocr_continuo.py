"""
Pruebas de la lectura completa en flujo continuo del Nivel 3 (RNF-02).

La auditoría (``texto_completo=True``) ya no reconoce las páginas escaneadas
por tandas de ``OCR_WORKERS`` que esperan a la más lenta: cada página entra al
pool en cuanto se rasteriza, con un tope de páginas en vuelo.

  1. El resultado es idéntico al de las tandas: mismo texto, mismas posiciones
     de página y mismas palabras con recuadro (no hace falta subir
     VERSION_PIPELINE ni releer lo persistido).
  2. El rasterizado no se adelanta sin límite: nunca hay más de
     ``_EN_VUELO_POR_TRABAJADOR × OCR_WORKERS`` páginas rasterizadas sin
     reconocer (cada una ocupa ≈ 8 MB a 300 ppp).
  3. Un fallo de Tesseract a media lectura se propaga como
     ``MotorOcrNoDisponibleError`` y el pool sigue disponible.

La prueba 1 usa Tesseract.  Uso:  cd services/ai-service && python -m pytest tests/test_ocr_continuo.py
"""
import os
import sys
import threading
import time

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import settings  # noqa: E402
from pipelines import extraccion_pipeline as ep  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _pdf_escaneado(paginas: int) -> bytes:
    with fitz.open(os.path.join(FIXTURES, "constancia_escaneada.pdf")) as fuente, fitz.open() as destino:
        for _ in range(paginas):
            destino.insert_pdf(fuente)
        return destino.tobytes()


def _huella(resultado: ep.ResultadoExtraccion) -> tuple:
    return (resultado.texto, resultado.confidence_score, resultado.paginas_omitidas,
            [(p.numero, p.metodo, p.inicio, p.caracteres, p.confianza, p.palabras) for p in resultado.detalle_paginas])


def test_flujo_continuo_igual_a_las_tandas(monkeypatch):
    contenido = _pdf_escaneado(3)
    continuo = ep.extraer_texto(contenido, texto_completo=True)
    # Sin corte temprano posible, la lectura parcial recorre todas las páginas por tandas.
    monkeypatch.setattr(settings, "MAX_PAGINAS_OCR", 99)
    monkeypatch.setattr(settings, "MAX_CARACTERES_CONTEXTO", 10**9)
    monkeypatch.setattr(settings, "OCR_WORKERS", 2)
    tandas = ep.extraer_texto(contenido, texto_completo=False)
    assert continuo.paginas_ocr == tandas.paginas_ocr == 3
    assert _huella(continuo) == _huella(tandas)


def test_el_rasterizado_no_se_adelanta_sin_limite(monkeypatch):
    monkeypatch.setattr(settings, "OCR_WORKERS", 2)
    tope = ep._EN_VUELO_POR_TRABAJADOR * 2
    candado = threading.Lock()
    conteo = {"rasterizadas": 0, "reconocidas": 0, "max_pendientes": 0}
    rasterizar = ep._rasterizar

    def rasterizar_contando(pagina):
        with candado:
            conteo["max_pendientes"] = max(conteo["max_pendientes"], conteo["rasterizadas"] - conteo["reconocidas"])
            conteo["rasterizadas"] += 1
        return rasterizar(pagina)

    # Cada reconocimiento tarda mucho más que un rasterizado: sin el tope, todo el
    # documento quedaría rasterizado en memoria antes de que termine la primera página.
    def ocr_lento(imagen):
        time.sleep(0.6)
        with candado:
            conteo["reconocidas"] += 1
        return "texto de la página", 0.9, [], []

    monkeypatch.setattr(ep, "_rasterizar", rasterizar_contando)
    monkeypatch.setattr(ep, "_ocr_sobre_imagen", ocr_lento)
    resultado = ep.extraer_texto(_pdf_escaneado(12), texto_completo=True)
    assert resultado.paginas_ocr == 12
    assert [p.numero for p in resultado.detalle_paginas] == list(range(1, 13))
    assert conteo["max_pendientes"] <= tope, conteo


def test_un_fallo_de_tesseract_se_propaga(monkeypatch):
    llamadas = []

    def ocr_que_falla(imagen):
        llamadas.append(1)
        if len(llamadas) == 3:
            raise ep.MotorOcrNoDisponibleError("Tesseract no es ejecutable")
        time.sleep(0.02)
        return "texto", 0.9, [], []

    monkeypatch.setattr(ep, "_ocr_sobre_imagen", ocr_que_falla)
    with pytest.raises(ep.MotorOcrNoDisponibleError):
        ep.extraer_texto(_pdf_escaneado(10), texto_completo=True)
    # El pool compartido sigue atendiendo después del fallo.
    assert ep._POOL_OCR.submit(lambda: "listo").result(timeout=10) == "listo"
