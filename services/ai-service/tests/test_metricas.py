"""
Pruebas de las métricas de la validación cuantitativa (evaluacion/metricas.py),
con valores calculados a mano. Offline y sin dependencias del servicio.

Uso:  cd services/ai-service && python -m pytest tests/test_metricas.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluacion import metricas as m  # noqa: E402

CLASES = ("CONFORME", "EN_REVISION", "NO_CONFORME")


def test_comparar_campo_cubre_los_cuatro_casos():
    assert m.comparar_campo("PLU180514AB3", "PLU180514AB3") == m.Conteo(vp=1)
    assert m.comparar_campo(None, None) == m.Conteo(vn=1)
    # Alucinación: el documento no trae el dato y el sistema afirma uno.
    assert m.comparar_campo(None, "PLU180514AB3") == m.Conteo(fp=1)
    assert m.comparar_campo("PLU180514AB3", None) == m.Conteo(fn=1)
    # Valor equivocado: afirmó algo falso y omitió lo verdadero.
    assert m.comparar_campo("PLU180514AB3", "PLU180514AB8") == m.Conteo(fp=1, fn=1)


def test_comparar_campo_con_igualdad_propia():
    iguales = lambda a, b: a.upper() == b.upper()  # noqa: E731
    assert m.comparar_campo("plu180514ab3", "PLU180514AB3", iguales) == m.Conteo(vp=1)


def test_precision_exhaustividad_y_f1():
    # VP=8, FP=2, FN=4 → P = 8/10 = 0.8; R = 8/12 = 0.6667; F1 = 2·0.8·0.6667/1.4667 = 0.7273
    c = m.Conteo(vp=8, fp=2, fn=4)
    assert c.precision == pytest.approx(0.8)
    assert c.exhaustividad == pytest.approx(2 / 3)
    assert c.f1 == pytest.approx(16 / 22)


def test_metricas_indefinidas_no_son_cero():
    assert m.Conteo(fn=3).precision is None
    assert m.Conteo(fp=3).exhaustividad is None
    assert m.Conteo(vn=5).f1 is None
    assert m.Conteo(vp=0, fp=1, fn=1).f1 == 0.0


def test_wilson_contra_valores_de_referencia():
    # 8 de 10, z = 1.96: centro = (0.8 + 0.19208) / 1.38416 = 0.71675;
    # margen = 1.96·√(0.016 + 0.009604) / 1.38416 = 0.22657 → [0.4902, 0.9433].
    bajo, alto = m.wilson(8, 10)
    assert bajo == pytest.approx(0.4902, abs=1e-4)
    assert alto == pytest.approx(0.9433, abs=1e-4)
    # 10 de 10 no colapsa en [1, 1]: [0.7225, 1.0]
    bajo, alto = m.wilson(10, 10)
    assert bajo == pytest.approx(0.7225, abs=1e-4) and alto == 1.0
    assert m.wilson(0, 0) is None


def test_matriz_exactitud_f1_macro_y_kappa():
    # Esperado → dictaminado, 10 casos:
    #   CONFORME:    3 bien, 1 a EN_REVISION
    #   EN_REVISION: 4 bien
    #   NO_CONFORME: 1 bien, 1 a EN_REVISION
    pares = ([("CONFORME", "CONFORME")] * 3 + [("CONFORME", "EN_REVISION")]
             + [("EN_REVISION", "EN_REVISION")] * 4
             + [("NO_CONFORME", "NO_CONFORME"), ("NO_CONFORME", "EN_REVISION")])
    matriz = m.matriz_confusion(pares, CLASES)
    assert matriz["CONFORME"]["EN_REVISION"] == 1
    assert m.exactitud(matriz) == pytest.approx(0.8)
    # F1: CONFORME P=1 R=0.75 → 0.8571; EN_REVISION P=4/6 R=1 → 0.8; NO_CONFORME P=1 R=0.5 → 0.6667
    assert m.f1_macro(matriz) == pytest.approx((6 / 7 + 0.8 + 2 / 3) / 3)
    # p_o = 0.8; p_e = 0.4·0.3 + 0.4·0.6 + 0.2·0.1 = 0.38; κ = 0.42 / 0.62 = 0.6774
    assert m.kappa_cohen(matriz) == pytest.approx(0.42 / 0.62)


def test_matriz_rechaza_una_clase_desconocida():
    with pytest.raises(ValueError):
        m.matriz_confusion([("CONFORME", "APROBADO")], CLASES)


def test_percentil_con_interpolacion_lineal():
    valores = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
    assert m.percentil(valores, 50) == pytest.approx(5.5)
    assert m.percentil(valores, 95) == pytest.approx(9.55)
    assert m.percentil([], 50) is None


def test_bootstrap_es_reproducible_y_contiene_el_f1_observado():
    casos = [m.Conteo(vp=1), m.Conteo(vp=1), m.Conteo(fp=1, fn=1), m.Conteo(vp=2, fn=1)] * 5
    observado = m.sumar(casos).f1
    a = m.bootstrap_f1(casos, repeticiones=300)
    b = m.bootstrap_f1(casos, repeticiones=300)
    assert a == b
    assert a[0] <= observado <= a[1]


def test_distancia_de_edicion_contra_valores_conocidos():
    assert m.distancia_edicion("kitten", "sitting") == 3      # k→s, e→i, +g
    assert m.distancia_edicion("", "abc") == 3
    assert m.distancia_edicion("RFC", "RFC") == 0
    assert m.distancia_edicion("abc", "ab") == m.distancia_edicion("ab", "abc") == 1


def test_cer_ignora_la_maquetacion_y_cuenta_sobre_la_referencia():
    # 1 error (0→O) en 10 caracteres de referencia; el doble espacio y el salto final no cuentan.
    assert m.cer("RFC PLU180", "RFC  PLU18O\n") == pytest.approx(0.1)
    assert m.cer("ab\ncd", "ab cd") == 0.0
    assert m.cer("", "algo") is None
    assert m.cer("ab", "abxyz") == pytest.approx(1.5)   # el texto inventado también cuenta
