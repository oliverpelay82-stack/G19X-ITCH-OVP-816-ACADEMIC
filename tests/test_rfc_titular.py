"""
M1 — RFC validado en el servidor (PRD §21.6; DOC-02; HU-49).

  1. Formato, longitud por tipo de persona y fecha AAMMDD imposible → 422 con
     el motivo en lenguaje llano.
  2. Dígito verificador del SAT: un RFC real queda VERIFICADO, los genéricos
     del SAT GENERICO y uno de prueba DIGITO_NO_COINCIDE, que por decisión del
     residente se acepta con advertencia.
  3. Con RFC_DIGITO_ESTRICTO=true, el dígito que no coincide responde 422.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import rfc  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
client = TestClient(app)

# RFC reales y públicos de personas morales (dígito verificador correcto).
RFC_REALES = ["BIM011108DJ5", "SAT970701NN3"]


@pytest.fixture(autouse=True)
def _sin_titulares_de_prueba():
    yield
    db = SessionLocal()
    try:
        db.query(TitularExpediente).filter(TitularExpediente.razon_social.like("M1 PRUEBA%")).delete(
            synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _alta(valor: str, tipo: str = "MORAL"):
    return client.post("/api/v1/titulares", json={
        "rfc": valor, "razon_social": f"M1 PRUEBA {uuid.uuid4().hex[:6]}", "tipo_persona": tipo})


# ── Algoritmo ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("valor", RFC_REALES)
def test_digito_de_rfc_reales(valor):
    assert rfc.digito_esperado(valor) == valor[-1]
    assert rfc.verificar(valor) == rfc.VERIFICADO


def test_genericos_y_de_prueba():
    assert rfc.verificar("XAXX010101000") == rfc.GENERICO
    assert rfc.verificar("XEXX010101000") == rfc.GENERICO
    assert rfc.verificar("BIM980101XYZ") == rfc.DIGITO_NO_COINCIDE


def test_fecha_del_29_de_febrero_segun_el_siglo():
    rfc.validar("ABC000229AB1", "MORAL")              # 2000 fue bisiesto
    with pytest.raises(rfc.RfcInvalido):
        rfc.validar("ABC010229AB1", "MORAL")          # ni 1901 ni 2001 lo son


# ── API ───────────────────────────────────────────────────────────────


def test_rfc_real_se_registra_verificado():
    r = _alta("bim011108dj5")
    assert r.status_code == 201, r.text
    assert r.json()["rfc"] == "BIM011108DJ5" and r.json()["rfc_verificacion"] == "VERIFICADO"


def test_rfc_de_prueba_se_acepta_con_advertencia():
    r = _alta("PRU980101XYZ")
    assert r.status_code == 201, r.text
    assert r.json()["rfc_verificacion"] == "DIGITO_NO_COINCIDE"


def test_rfc_generico_del_sat():
    r = _alta("XEXX010101000")
    assert r.status_code == 201 and r.json()["rfc_verificacion"] == "GENERICO"


@pytest.mark.parametrize("valor,tipo,fragmento", [
    ("ABC991399AB1", "MORAL", "no existe"),                  # mes 13
    ("ABC990230AB1", "MORAL", "no existe"),                  # 30 de febrero
    ("PEPJ850101H23", "MORAL", "12 caracteres"),             # física declarada como moral
    ("ABC850101H23", "FISICA", "13 caracteres"),             # moral declarada como física
    ("AB1850101H23", "MORAL", "Formato de RFC incorrecto"),
])
def test_rfc_invalido_responde_422(valor, tipo, fragmento):
    r = _alta(valor, tipo)
    assert r.status_code == 422
    assert fragmento in str(r.json()["detail"])


def test_modo_estricto_rechaza_el_digito(monkeypatch):
    monkeypatch.setenv("RFC_DIGITO_ESTRICTO", "true")
    r = _alta("PRU980101XYZ")
    assert r.status_code == 422 and "dígito verificador" in str(r.json()["detail"])
    assert _alta("SAT970701NN3").status_code == 201, "Un RFC real pasa también en modo estricto"


def test_titular_existente_informa_su_verificacion():
    _alta("PRU980101XYZ")
    titulares = client.get("/api/v1/titulares").json()
    assert all("rfc_verificacion" in t for t in titulares)
