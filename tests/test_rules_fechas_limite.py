"""
Q-a — Fechas límite de las reglas RCV en el rules-service (PRD §21.6; DOC-05).

Unitario, sin base de datos: mismos límites que el core (test_fechas_limite),
para que el dictamen del Nivel 4 y la evaluación diaria coincidan.
"""
import os
import sys
from datetime import date, datetime, timezone
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

import pytest  # noqa: E402

from config import zona_horaria  # noqa: E402
from motor import vigencia  # noqa: E402


def _regla(codigo, dias, tipo=None):
    return SimpleNamespace(codigo_regla=codigo, nombre_regla=codigo, severidad="ALTA", familia_regla="RCV",
                           dias_maximos_vigencia=dias, tipo_documento=tipo, activo=True)


CSF = _regla("RCV-03", 90, "CSF_SAT")
RCV01 = _regla("RCV-01", 30)


@pytest.mark.parametrize("emision,referencia,resultado", [
    (date(2023, 12, 1), date(2024, 2, 29), vigencia.VIGENTE),   # día 90, el 29 de febrero
    (date(2023, 12, 1), date(2024, 3, 1), vigencia.VENCIDO),    # día 91
    (date(2024, 2, 29), date(2024, 5, 29), vigencia.VIGENTE),
    (date(2024, 2, 29), date(2024, 5, 30), vigencia.VENCIDO),
    (date(2026, 11, 15), date(2027, 2, 13), vigencia.VIGENTE),  # cambio de año
    (date(2026, 11, 15), date(2027, 2, 14), vigencia.VENCIDO),
])
def test_caducidad_desde_la_emision(emision, referencia, resultado):
    assert vigencia.evaluar([CSF], "CSF_SAT", emision, None, referencia).resultado == resultado


@pytest.mark.parametrize("referencia,resultado", [
    (date(2026, 9, 14), vigencia.VIGENTE),
    (date(2026, 9, 15), vigencia.PROXIMO_A_VENCER),
    (date(2026, 10, 15), vigencia.PROXIMO_A_VENCER),   # el día del vencimiento
    (date(2026, 10, 16), vigencia.VENCIDO),
])
def test_fecha_de_vencimiento_declarada(referencia, resultado):
    assert vigencia.evaluar([RCV01], "CONTRATO_SERVICIOS", None, date(2026, 10, 15), referencia).resultado == resultado


def test_hoy_es_el_dia_de_mexico():
    assert zona_horaria.hoy(datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)) == date(2026, 10, 15)
