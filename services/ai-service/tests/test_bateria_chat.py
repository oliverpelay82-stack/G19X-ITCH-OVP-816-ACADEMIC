"""
Pruebas de la batería del chat documental (evaluacion/bateria_chat.py): su
composición (§6.2) y la regla con que se califica cada respuesta. Offline.

Uso:  cd services/ai-service && python -m pytest tests/test_bateria_chat.py
"""
import json
import os
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluacion import bateria_chat as b  # noqa: E402
from evaluacion import gold_standard as gs  # noqa: E402


def test_composicion():
    assert len(b.PREGUNTAS) == 30
    assert Counter(p.documento for p in b.PREGUNTAS) == {d: 5 for d in b.DOCUMENTOS}
    assert Counter(p.categoria for p in b.PREGUNTAS) == {
        b.SUGERIDA: 8, b.FACTUAL: 10, b.LOCALIZACION: 6, b.INTERPRETATIVA: 4, b.AUSENTE: 2}
    assert [len(c) for c in b.CONVERSACIONES] == [4, 4]
    assert b.total_turnos() == 38


def test_los_documentos_son_casos_del_gold_standard():
    with open(gs.RUTA_ANOTACION, encoding="utf-8") as f:
        ids = {c["id"] for c in json.load(f)["casos"]}
    assert set(b.DOCUMENTOS) <= ids


def test_bateria_extensa():
    from evaluacion import documento_extenso
    with open(documento_extenso.RUTA_ANOTACION, encoding="utf-8") as f:
        ids = {c["id"] for c in json.load(f)["casos"]}
    assert set(b.DOCUMENTOS_EXTENSOS) <= ids
    assert len(b.PREGUNTAS_EXTENSAS) == 8
    assert {p.documento for p in b.PREGUNTAS_EXTENSAS} == set(b.DOCUMENTOS_EXTENSOS)


def test_cada_pregunta_tiene_como_calificarse():
    for p in b.PREGUNTAS + b.PREGUNTAS_EXTENSAS + [q for c in b.CONVERSACIONES for q in c]:
        assert p.ausente or (p.contiene and all(p.contiene)), p.pregunta


def test_acierta_sin_acentos_ni_negritas_y_con_fechas_en_palabras():
    p = next(q for q in b.PREGUNTAS if q.documento == "GS-CONT-03" and "vence" in q.pregunta)
    assert b.acierta("El contrato vence el **1 de marzo de 2027**.", p)
    assert b.acierta("Vigente hasta 01/03/2027.", p)
    assert not b.acierta("Vence el 1 de marzo de 2026.", p)
    firmantes = next(q for q in b.PREGUNTAS if q.pregunta == "¿Quiénes firman el contrato?")
    assert b.acierta("Firman **María Elena Ruiz Soto** y **Jorge Alberto Treviño Garza**.", firmantes)
    assert not b.acierta("Firma María Elena Ruiz Soto.", firmantes)   # falta el segundo grupo


def test_ausencia():
    p = next(q for q in b.PREGUNTAS if q.categoria == b.AUSENTE)
    assert b.acierta("No aparece en el texto disponible.", p)
    assert b.acierta("El contrato no incluye una pena convencional.", p)
    assert not b.acierta("La pena convencional es del 10 %.", p)
