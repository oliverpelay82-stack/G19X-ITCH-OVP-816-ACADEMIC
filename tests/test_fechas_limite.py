"""
Q-a — Fechas límite de la vigencia en el core (ESTADO_DEL_DESARROLLO §6.6; RN-02; DOC-05, RCV).

Sin base de datos ni red: la vigencia se calcula con las fechas del dictamen.

  1. Umbrales de anticipación de 30, 15 y 5 días exactos, y el día anterior a cada uno.
  2. Fecha de vencimiento declarada (RCV-01): el día del vencimiento todavía es
     vigente (próximo a vencer) y el siguiente ya está vencido.
  3. Caducidad desde la emisión (RCV-02/03, 90 días): el día 90 es vigente y
     el 91 vencido, también cruzando un 29 de febrero, con emisión el 29 de
     febrero y con cambio de año; RCV-04 (opinión 32-D, 30 días).
  4. Con varias caducidades prevalece la que vence antes.
  5. «Hoy» es el día de México aunque en UTC ya sea el siguiente.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()

from datetime import date, datetime, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402

from config import zona_horaria  # noqa: E402
from motor import cumplimiento  # noqa: E402
from motor.cumplimiento import PROXIMO_A_VENCER, VENCIDO, VIGENTE  # noqa: E402


def _dictamen(emision=None, vencimiento=None, reglas=()):
    return SimpleNamespace(fecha_emision_extraida=emision, fecha_vencimiento_extraida=vencimiento,
                           reglas_aplicadas=list(reglas))


def _antiguedad(codigo: str, limite: int) -> dict:
    return {"codigo_regla": codigo, "limite_dias": limite, "criterio": cumplimiento.CRITERIO_ANTIGUEDAD}


RCV01 = {"codigo_regla": "RCV-01", "limite_dias": 30, "criterio": cumplimiento.CRITERIO_VENCIMIENTO}


@pytest.mark.parametrize("dias,severidad", [
    (31, None), (30, "MEDIA"), (16, "MEDIA"), (15, "MEDIA_ALTA"), (6, "MEDIA_ALTA"), (5, "ALTA"), (1, "ALTA"),
    (0, "ALTA"),
])
def test_umbrales_de_anticipacion(dias, severidad):
    assert cumplimiento._severidad_por_anticipacion(dias) == severidad


@pytest.mark.parametrize("hoy,estado,dias", [
    (date(2026, 9, 14), VIGENTE, 31),
    (date(2026, 9, 15), PROXIMO_A_VENCER, 30),        # entra en la ventana de RCV-01 justo a 30 días
    (date(2026, 10, 15), PROXIMO_A_VENCER, 0),        # el día del vencimiento todavía es vigente
    (date(2026, 10, 16), VENCIDO, -1),
])
def test_fecha_de_vencimiento_declarada(hoy, estado, dias):
    vigencia = cumplimiento.vigencia_actual(_dictamen(vencimiento=date(2026, 10, 15), reglas=[RCV01]), hoy)
    assert (vigencia.estado, vigencia.dias) == (estado, dias)


@pytest.mark.parametrize("emision,dia_90", [
    (date(2026, 7, 1), date(2026, 9, 29)),
    (date(2023, 12, 1), date(2024, 2, 29)),   # el día 90 cae en 29 de febrero
    (date(2024, 2, 29), date(2024, 5, 29)),   # emisión el 29 de febrero
    (date(2026, 11, 15), date(2027, 2, 13)),  # cambio de año
])
def test_caducidad_de_90_dias_desde_la_emision(emision, dia_90):
    dictamen = _dictamen(emision=emision, reglas=[_antiguedad("RCV-03", 90)])
    assert cumplimiento.vigencia_actual(dictamen, dia_90).estado == VIGENTE
    siguiente = cumplimiento.vigencia_actual(dictamen, date.fromordinal(dia_90.toordinal() + 1))
    assert (siguiente.estado, siguiente.dias) == (VENCIDO, -1)


def test_la_caducidad_por_antiguedad_no_tiene_ventana_de_proximo_a_vencer():
    dictamen = _dictamen(emision=date(2026, 9, 1), reglas=[_antiguedad("RCV-04", 30)])
    assert cumplimiento.vigencia_actual(dictamen, date(2026, 9, 30)).estado == VIGENTE   # día 29
    assert cumplimiento.vigencia_actual(dictamen, date(2026, 10, 1)).estado == VIGENTE   # día 30
    assert cumplimiento.vigencia_actual(dictamen, date(2026, 10, 2)).estado == VENCIDO   # día 31


def test_prevalece_la_caducidad_mas_cercana():
    dictamen = _dictamen(emision=date(2026, 9, 1), vencimiento=date(2027, 9, 1),
                         reglas=[RCV01, _antiguedad("RCV-02", 90)])
    vigencia = cumplimiento.vigencia_actual(dictamen, date(2026, 11, 30))
    assert (vigencia.estado, vigencia.regla, vigencia.fecha_caducidad) == (VIGENTE, "RCV-02", date(2026, 11, 30))
    assert cumplimiento.vigencia_actual(dictamen, date(2026, 12, 1)).estado == VENCIDO


def test_sin_fechas_no_hay_vigencia():
    assert cumplimiento.vigencia_actual(_dictamen(reglas=[_antiguedad("RCV-02", 90)]), date(2026, 9, 30)) is None


def test_hoy_es_el_dia_de_mexico_aunque_en_utc_sea_el_siguiente():
    # 22:30 del 15/10 en México son las 04:30 del 16/10 en UTC (un contenedor corre en UTC).
    instante = datetime(2026, 10, 16, 4, 30, tzinfo=timezone.utc)
    assert zona_horaria.hoy(instante) == date(2026, 10, 15)
    assert zona_horaria.fecha_local(datetime(2026, 10, 16, 4, 30)) == date(2026, 10, 15), "Sin zona es UTC"
    vigencia = cumplimiento.vigencia_actual(_dictamen(vencimiento=date(2026, 10, 15), reglas=[RCV01]),
                                            zona_horaria.hoy(instante))
    assert vigencia.estado == PROXIMO_A_VENCER, "Esa noche el documento todavía no vence"
