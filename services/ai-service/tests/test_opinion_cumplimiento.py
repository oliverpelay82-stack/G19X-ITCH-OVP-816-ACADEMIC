"""
Pruebas offline de la opinión de cumplimiento 32-D (PLUS-03, ESTADO_DEL_DESARROLLO §6.1): la
regla RSC-OPIN-SENT se lee del texto sin el modelo y un sentido negativo deja
el dictamen NO_CONFORME. Groq y el rules-service se simulan.

  1. Lectura del sentido: positivo, negativo, sin obligaciones, no inscrito;
     tolerancia a acentos y a errores de OCR; menciones condicionales
     descartadas; dos sentidos distintos → AMBIGUO; sin declaración → None.
  2. Verificación: la regla determinista no se envía al modelo; si es la única
     del tipo, no hay llamada a Groq; si Groq falla, su resultado se conserva.
  3. Dictamen: negativo → NO_CONFORME con la cita y la recomendación de la
     regla; positivo → CONFORME; sin declaración → EN_REVISION.

Uso:  cd services/ai-service && python tests/test_opinion_cumplimiento.py
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import groq_client, rules_client  # noqa: E402
from clients.groq_client import GroqNoDisponibleError  # noqa: E402
from pipelines import analisis_semantico, opinion_cumplimiento, verificacion_contenido  # noqa: E402
from pipelines.opinion_cumplimiento import leer_sentido  # noqa: E402

HOY = date(2026, 9, 29)
RFC = "CSM150310QK4"
ENCABEZADO = (
    "SERVICIO DE ADMINISTRACION TRIBUTARIA\nOpinión del cumplimiento de obligaciones fiscales\n"
    "Folio 26NA1234567 Clave en el RFC CSM150310QK4 Nombre CONSTRUCTORA SIERRA MADRE SA DE CV\n"
)
LEYENDA_CONDICIONAL = (
    "En caso de que la opinión sea en sentido negativo, el contribuyente podrá aclarar su situación "
    "ante el SAT.\n"
)
OPINION_POSITIVA = ENCABEZADO + "Sentido: Positivo\n" + LEYENDA_CONDICIONAL
OPINION_NEGATIVA = ENCABEZADO + (
    "En atención a su consulta, se le informa que se emite opinión del cumplimiento en sentido NEGATIVO.\n"
    "Obligaciones omitidas: declaración anual 2025.\n"
)
CRITERIO_SENTIDO = {
    "codigo_regla": "RSC-OPIN-SENT", "nombre_regla": "Sentido positivo de la opinión de cumplimiento",
    "familia_regla": "RSC", "criterio": "La opinión declara expresamente su sentido.", "severidad": "ALTA",
    "recomendacion": "Solicitar una opinión en sentido positivo emitida en los últimos 30 días.",
}
CRITERIO_FOLIO = {
    "codigo_regla": "RSC-OPIN-FOLIO", "nombre_regla": "Folio de la opinión", "familia_regla": "RDS",
    "criterio": "La opinión indica su folio.", "severidad": "MEDIA", "recomendacion": "Solicitar la opinión completa.",
}


# ── 1. Lectura del sentido ──────────────────────────────────────────
@pytest.mark.parametrize("texto, esperado", [
    ("Sentido: Positivo", opinion_cumplimiento.POSITIVO),
    ("SENTIDO DE LA OPINIÓN: NEGATIVO", opinion_cumplimiento.NEGATIVO),
    ("se emite opinión Positiva", opinion_cumplimiento.POSITIVO),
    ("se emite la opinión en sentido negativo", opinion_cumplimiento.NEGATIVO),
    ("Opinión: POSITIVA", opinion_cumplimiento.POSITIVO),
    ("Sentido: Inscrito sin obligaciones", opinion_cumplimiento.SIN_OBLIGACIONES),
    ("Sentido: No inscrito", opinion_cumplimiento.NO_INSCRITO),
    ("Sentido : NEGAT1VO", opinion_cumplimiento.NEGATIVO),       # OCR: 1 por i
    ("sentido p0sitivo", opinion_cumplimiento.POSITIVO),          # OCR: 0 por o
    ("Sentido de la opinion:\nPositivo", opinion_cumplimiento.POSITIVO),
])
def test_lee_el_sentido_declarado(texto, esperado):
    assert leer_sentido(texto).valor == esperado


def test_la_mencion_condicional_no_es_una_declaracion():
    assert leer_sentido(LEYENDA_CONDICIONAL).valor is None
    sentido = leer_sentido(OPINION_POSITIVA)
    assert sentido.valor == opinion_cumplimiento.POSITIVO and sentido.cita == "Sentido: Positivo"


def test_dos_sentidos_distintos_son_ambiguos():
    assert leer_sentido("Sentido: Positivo\nSe emite opinión en sentido negativo.").valor == opinion_cumplimiento.AMBIGUO


def test_sin_declaracion_no_hay_sentido():
    sentido = leer_sentido(ENCABEZADO)
    assert sentido.valor is None and sentido.cita is None


def test_la_cita_es_el_renglon_tal_como_esta_escrito():
    sentido = leer_sentido(OPINION_NEGATIVA)
    assert sentido.cita.startswith("En atención a su consulta") and "NEGATIVO" in sentido.cita
    assert verificacion_contenido.cita_literal(sentido.cita, OPINION_NEGATIVA) is not None


# ── 2. Verificación sin el modelo ───────────────────────────────────
def test_la_regla_determinista_no_consulta_al_modelo(monkeypatch):
    def prohibido(**_):
        raise AssertionError("RSC-OPIN-SENT no debe enviarse a Groq")
    monkeypatch.setattr(groq_client, "generar_json", prohibido)

    resultado = verificacion_contenido.verificar(OPINION_NEGATIVA, [CRITERIO_SENTIDO])

    assert resultado.disponible and resultado.uso_tokens is None
    [v] = resultado.verificaciones
    assert v["resultado"] == verificacion_contenido.NO_CUMPLE and "NEGATIVO" in v["cita"]
    assert v["recomendacion"] == CRITERIO_SENTIDO["recomendacion"]
    assert resultado.incumplidos == [v] and resultado.pendientes == []


def test_con_otras_reglas_solo_esas_van_al_modelo(monkeypatch):
    enviados = []

    def generar_json(prompt, system):
        enviados.append(prompt)
        return {"verificaciones": [{"codigo_regla": "RSC-OPIN-FOLIO", "cumple": True,
                                    "cita": "Folio 26NA1234567", "observacion": "Folio visible."}]}
    monkeypatch.setattr(groq_client, "generar_json", generar_json)

    resultado = verificacion_contenido.verificar(OPINION_POSITIVA, [CRITERIO_SENTIDO, CRITERIO_FOLIO])

    assert len(enviados) == 1 and "RSC-OPIN-FOLIO" in enviados[0] and "RSC-OPIN-SENT" not in enviados[0]
    assert [v["codigo_regla"] for v in resultado.verificaciones] == ["RSC-OPIN-SENT", "RSC-OPIN-FOLIO"]
    assert all(v["resultado"] == verificacion_contenido.CUMPLE for v in resultado.verificaciones)


def test_si_groq_falla_el_sentido_leido_se_conserva(monkeypatch):
    def falla(**_):
        raise GroqNoDisponibleError("429 Too Many Requests")
    monkeypatch.setattr(groq_client, "generar_json", falla)

    resultado = verificacion_contenido.verificar(OPINION_NEGATIVA, [CRITERIO_SENTIDO, CRITERIO_FOLIO])

    assert not resultado.disponible and resultado.nota
    assert [v["codigo_regla"] for v in resultado.incumplidos] == ["RSC-OPIN-SENT"]


# ── 3. Dictamen ─────────────────────────────────────────────────────
def _auditar(monkeypatch, texto: str):
    monkeypatch.setattr(groq_client, "generar_json", lambda prompt, system: {
        "tipo_documento_detectado": "OPINION_CUMPLIMIENTO", "rfc_detectado": RFC,
        "razon_social_detectada": "CONSTRUCTORA SIERRA MADRE SA DE CV", "fecha_emision": "2026-09-20",
        "fecha_vencimiento": None, "nivel_confianza": 0.95, "observaciones": "Texto legible."})
    monkeypatch.setattr(rules_client, "evaluar_vigencia", lambda tipo, emision, venc, ref: {
        "tipo_documento": tipo, "fecha_referencia": ref.isoformat(), "resultado": "VIGENTE", "es_vigente": True,
        "dias_calculados": 9, "evaluaciones": [{"codigo_regla": "RCV-04", "resultado": "VIGENTE",
                                               "limite_dias": 30, "dias_calculados": 9, "detalle": "9 días."}]})
    return analisis_semantico.analizar(
        texto, rfc_titular=RFC, fecha_referencia=HOY, tipo_documento_registrado="OPINION_CUMPLIMIENTO",
        criterios_contenido=[CRITERIO_SENTIDO],
    )


def test_opinion_negativa_vigente_es_no_conforme(monkeypatch):
    resultado = _auditar(monkeypatch, OPINION_NEGATIVA)

    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_NO_CONFORME
    assert not resultado.requiere_revision_humana
    assert any("RSC-OPIN-SENT" in o and "NEGATIVO" in o for o in resultado.observaciones), resultado.observaciones
    assert CRITERIO_SENTIDO["recomendacion"] in resultado.recomendaciones


def test_opinion_positiva_vigente_es_conforme(monkeypatch):
    resultado = _auditar(monkeypatch, OPINION_POSITIVA)

    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_CONFORME, resultado.observaciones
    assert resultado.verificaciones[0]["cita"] == "Sentido: Positivo"


def test_opinion_sin_sentido_legible_pasa_a_revision(monkeypatch):
    resultado = _auditar(monkeypatch, ENCABEZADO)

    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_EN_REVISION
    assert resultado.requiere_revision_humana


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
