"""
Pruebas del contexto enfocado del chat — T2, PLUS-09 (PRD §21.4). Offline, con
el texto vectorial del contrato de 20 páginas del Gold Standard.

  1. Para cada pregunta puntual de la batería extensa, el contexto enfocado
     contiene la respuesta y cabe en el presupuesto puntual.
  2. En la pregunta de la mesa de ayuda, el tramo elegido es el del servicio
     A.1 (su encabezado reordena a los demás servicios con el mismo texto).
  3. Cada tramo es un recorte literal del documento (las citas siguen
     anclándose) y un documento corto se envía completo.
  4. En un acta cuyas reglas de aumento repiten «capital social» en muchas
     páginas, la pregunta por el capital llega al rubro «CAPITAL SOCIAL» que fija
     el monto, también con el contexto reducido de T4 (10/10/2026).

Uso:  cd services/ai-service && python -m pytest tests/test_contexto_enfocado.py
"""
import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipelines import fragmentos  # noqa: E402

_CONTRATO = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                         "evaluacion", "gold_standard", "documentos", "gs-cont-ext.pdf")
PRESUPUESTO = 3000


@pytest.fixture(scope="module")
def texto():
    with fitz.open(_CONTRATO) as documento:
        return "\n".join(p.get_text() for p in documento).strip()


@pytest.mark.parametrize("pregunta,respuesta", [
    ("¿Cuál es el monto mensual total de los servicios?", "185,000.00"),
    ("¿Qué deductiva se aplica si la disponibilidad de los servidores baja del 99.5 %?", "99.0 %: cinco por ciento"),
    ("¿Puede el prestador subcontratar los servicios?", "autorización"),
    ("¿Cuál es el tiempo de respuesta de la mesa de ayuda para un incidente de prioridad crítica?", "15 minutos"),
    ("¿Hasta cuándo está vigente el contrato?", "1 de marzo de 2027"),
    ("¿Cuál es la pena convencional?", "diez por ciento del monto mensual"),
])
def test_el_contexto_enfocado_contiene_la_respuesta(texto, pregunta, respuesta):
    seleccion = fragmentos.seleccionar_enfocado(texto, pregunta, presupuesto=PRESUPUESTO, max_fragmentos=3)
    assert respuesta in seleccion.texto
    assert len(seleccion.texto) <= PRESUPUESTO
    general = fragmentos.seleccionar(texto, pregunta, max_fragmentos=4)
    assert len(seleccion.texto) < len(general.texto)


def test_la_mesa_de_ayuda_elige_su_propio_servicio(texto):
    seleccion = fragmentos.seleccionar_enfocado(
        texto, "¿Cuál es el tiempo de respuesta de la mesa de ayuda para un incidente de prioridad crítica?",
        presupuesto=PRESUPUESTO, max_fragmentos=3)
    tramo = next(p for p in seleccion.texto.split(fragmentos._SEPARADOR) if "MESA DE AYUDA" in p)
    assert "15 minutos" in tramo


def test_los_tramos_son_literales(texto):
    seleccion = fragmentos.seleccionar_enfocado(texto, "¿Cuál es la pena convencional?",
                                                presupuesto=PRESUPUESTO, max_fragmentos=3)
    assert seleccion.estrategia == "fragmentos" and seleccion.fragmentos
    for parte in seleccion.texto.split(fragmentos._SEPARADOR):
        assert parte.strip() in texto


def _acta_con_reglas_de_capital() -> str:
    """Estatutos donde «capital social» aparece en un tercio de las ventanas, casi
    siempre en las reglas para aumentarlo; el monto solo está bajo su rubro."""
    clausulas = []
    for n in range(1, 61):
        # Como en el OCR del acta, el rubro y el cuerpo de cada artículo van en el mismo renglón.
        if n == 6:
            c = ("ARTÍCULO SEXTO. - CAPITAL SOCIAL. El capital social es variable. La parte mínima fija sin derecho a "
                 "retiro es de $55,000.00 (cincuenta y cinco mil pesos Moneda Nacional), dividida en cincuenta y cinco "
                 "acciones.")
        elif n % 10 == 0:
            c = (f"ARTÍCULO {n}. - AUMENTOS. Cualquier aumento del capital social en su parte fija requiere asamblea; "
                 "el aumento del capital social se inscribe en el libro de variaciones del capital social.")
        elif n % 3 == 0:
            c = f"ARTÍCULO {n}. - ASAMBLEAS. Las resoluciones se toman por las acciones que integran el capital social."
        else:
            c = (f"ARTÍCULO {n}. - ADMINISTRACIÓN. El consejo sesiona con la mayoría de sus miembros y lleva su libro "
                 "de actas.")
        clausulas.append(c + "\n" + "Texto de relleno del instrumento notarial sin términos de la consulta. " * 10)
    return "ACTA CONSTITUTIVA DE DESARROLLOS DEMOSTRATIVOS, S.A. DE C.V.\n" + "\n".join(clausulas)


@pytest.mark.parametrize("presupuesto,fragmentos_max", [(PRESUPUESTO, 3), (6500 // 3, 2)])
def test_el_capital_social_llega_a_su_rubro(presupuesto, fragmentos_max):
    seleccion = fragmentos.seleccionar_enfocado(_acta_con_reglas_de_capital(), "¿Cuál es el capital social?",
                                                presupuesto=presupuesto, max_fragmentos=fragmentos_max)
    assert "$55,000.00" in seleccion.texto
    assert seleccion.fragmentos[0]["titulo"].startswith("ARTÍCULO SEXTO. - CAPITAL SOCIAL")


def test_un_documento_corto_va_completo():
    corto = "CONSTANCIA DE SITUACION FISCAL\nRFC: PLU180514AB3"
    seleccion = fragmentos.seleccionar_enfocado(corto, "¿Cuál es el RFC?", presupuesto=PRESUPUESTO, max_fragmentos=3)
    assert seleccion.estrategia == "completo" and seleccion.texto == corto
