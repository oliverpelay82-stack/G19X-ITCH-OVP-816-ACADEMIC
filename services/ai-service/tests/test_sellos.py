"""
Sello Digital SAT (DOC-08: «presencia de Sello Digital SAT»), detectado en el
texto extraído.

  1. Se detecta la cadena original o el sello digital; un sello notarial
     mencionado en el texto no lo es.
  2. El dictamen lo menciona como observación informativa.

La detección de sellos en tinta de color se retiró el 02/10/2026 (estaba
apagada y ningún DOC la pide): una página a color se lee como siempre y no
reporta sellos.
"""
import os
import sys
from types import SimpleNamespace

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from controllers import analisis_controller as controlador  # noqa: E402
from pipelines import extraccion_pipeline, sellos  # noqa: E402


def test_se_detecta_el_sello_digital_sat_en_el_texto():
    assert sellos.tiene_sello_digital("Cadena Original Sello: ||1.1|ABC||  Sello Digital: aZx9...")
    assert not sellos.tiene_sello_digital("El sello de autorizar del notario.")
    assert not sellos.tiene_sello_digital("")


def test_el_dictamen_menciona_el_sello_digital_sat():
    con_sello = SimpleNamespace(traza={"sello_digital_sat": True})
    [observacion] = controlador._observaciones_de_sellos(con_sello)
    assert "Sello Digital del SAT" in observacion
    assert controlador._observaciones_de_sellos(SimpleNamespace(traza={})) == []
    assert controlador._observaciones_de_sellos(None) == []


def test_una_pagina_a_color_no_reporta_sellos_y_la_lectura_conserva_su_version():
    blanca = np.full((400, 600, 3), 255, dtype=np.uint8)
    *_, encontrados = extraccion_pipeline._ocr_sobre_imagen(blanca)
    assert encontrados == []
    assert extraccion_pipeline.version_lectura().endswith("|sin-sellos"), "Las extracciones guardadas siguen válidas"
