"""
Pruebas de la normalización de la iluminación del Nivel 3 (VERSION_PIPELINE 3.3).

  1. En la página del contrato escaneado del Gold Standard donde se detectó la
     falla (Anexo A.1, bordes oscuros), el encabezado de la esquina superior
     izquierda se lee: antes, el corte de Otsu lo pintaba de negro.
  2. Sobre papel parejo el paso no altera la página: el fondo queda blanco y la
     tinta, oscura.
  3. Una imagen diminuta se devuelve sin cambios.

Usa Tesseract.  Uso:  cd services/ai-service && python -m pytest tests/test_iluminacion.py
"""
import os
import sys

import cv2
import fitz
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from pipelines import extraccion_pipeline as ep  # noqa: E402


_CONTRATO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "evaluacion", "gold_standard", "documentos", "gs-cont-ext-esc.pdf")


def test_el_texto_de_la_esquina_se_conserva():
    # Página 10 del contrato escaneado del Gold Standard (Anexo A.1): con el corte de
    # Otsu sin normalizar, el 22.8 % de la página quedaba en negro y se perdían el
    # título del anexo, «A.1 MESA DE AYUDA» y su descripción.
    with fitz.open(_CONTRATO) as documento:
        imagen = ep._rasterizar(documento[9])
    texto, _, _, _ = ep.reconocer_pagina(imagen)
    normal = texto.upper()
    assert "MESA DE AYUDA" in normal, texto[:300]
    assert "CATÁLOGO DE SERVICIOS" in normal and "15 MINUTOS" in normal, texto[:300]


def test_papel_parejo_no_cambia():
    gris = np.full((800, 600), 235, np.uint8)
    cv2.putText(gris, "TEXTO", (100, 400), cv2.FONT_HERSHEY_SIMPLEX, 3, 30, 8)
    normalizada = ep._normalizar_iluminacion(gris)
    assert normalizada[50:150, 50:150].mean() > 250          # el fondo queda blanco
    tinta = gris < 100
    assert normalizada[tinta].mean() < 60                    # la tinta sigue oscura


def test_imagen_diminuta_sin_cambios():
    gris = np.full((40, 40), 120, np.uint8)
    assert ep._normalizar_iluminacion(gris) is gris


def test_version_del_nivel_3():
    assert ep.VERSION_PIPELINE == "3.3" and "n3-3.3" in ep.version_lectura()
