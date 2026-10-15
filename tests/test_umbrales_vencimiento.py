"""
Umbrales de anticipación de las alertas de vencimiento desde la interfaz (HU-14, RF-17;
docs/uml/hu14-actividad-umbrales-vencimiento.puml).

  1. Sin configuración rigen los de UMBRALES_ALERTA_VENCIMIENTO (30, 15 y 5).
  2. Solo se aceptan tres enteros de 1 a 365, de mayor a menor y distintos (422 con el motivo).
  3. Un cambio válido queda guardado y en la bitácora con el valor anterior y el nuevo;
     repetir los mismos valores no deja otro evento.
  4. La evaluación de un expediente usa los umbrales guardados, no los del arranque.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py). Al
terminar se borra el parámetro, para que las demás suites evalúen con los de omisión.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

import pytest  # noqa: E402

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.expediente import Expediente  # noqa: E402
from models.parametro import ParametroSistema  # noqa: E402
from motor import cumplimiento, umbrales  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
admin = auth.cliente(app)
RUTA = "/api/v1/configuracion/umbrales-vencimiento"


def _borrar_parametro() -> None:
    db = SessionLocal()
    try:
        db.query(ParametroSistema).filter(ParametroSistema.clave == umbrales.CLAVE).delete()
        db.commit()
    finally:
        db.close()


@pytest.fixture(autouse=True)
def sin_parametro():
    _borrar_parametro()
    yield
    _borrar_parametro()


def _eventos() -> list[dict]:
    return admin.get("/api/v1/bitacora", params={"evento": "ACTUALIZACION_PARAMETRO", "limite": 500}).json()


def test_sin_configuracion_rigen_los_de_omision():
    r = admin.get(RUTA)
    assert r.status_code == 200, r.text
    assert r.json() == {"umbrales": [30, 15, 5], "configurado": False, "actualizado_en": None,
                        "actualizado_por": None}


@pytest.mark.parametrize("valores, motivo", [
    ([30, 15], "exactamente 3"),
    ([30, 15, 5, 1], "exactamente 3"),
    ([30, 15, 0], "entre 1 y 365"),
    ([400, 15, 5], "entre 1 y 365"),
    ([5, 15, 30], "de mayor a menor"),
    ([30, 15, 15], "de mayor a menor"),
])
def test_valores_no_validos_se_rechazan_con_el_motivo(valores, motivo):
    antes = len(_eventos())
    r = admin.put(RUTA, json={"umbrales": valores})
    assert r.status_code == 422, r.text
    assert motivo in r.json()["detail"]
    assert admin.get(RUTA).json()["configurado"] is False
    assert len(_eventos()) == antes, "Un valor rechazado no deja evento"


def test_el_cambio_se_guarda_y_queda_en_la_bitacora():
    antes = len(_eventos())
    r = admin.put(RUTA, json={"umbrales": [45, 20, 7]})
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["umbrales"] == [45, 20, 7] and cuerpo["configurado"] is True
    assert cuerpo["actualizado_por"] == bd_pruebas.Autenticacion.correo("ADMIN")
    eventos = _eventos()
    assert len(eventos) == antes + 1
    detalle = eventos[0]["detalle"]
    assert detalle["anterior"] == [30, 15, 5] and detalle["nuevo"] == [45, 20, 7]
    assert eventos[0]["usuario"] == bd_pruebas.Autenticacion.correo("ADMIN")

    assert admin.put(RUTA, json={"umbrales": [45, 20, 7]}).status_code == 200
    assert len(_eventos()) == antes + 1, "Los mismos valores no dejan otro evento"


def test_la_evaluacion_usa_los_umbrales_guardados(monkeypatch):
    assert admin.put(RUTA, json={"umbrales": [60, 25, 10]}).status_code == 200
    rfc = bd_pruebas.rfc_ficticio("UMB")
    titular = admin.post("/api/v1/titulares", json={"rfc": rfc, "razon_social": f"Umbrales {rfc}",
                                                     "tipo_persona": "MORAL", "categoria": "PROVEEDOR"}).json()
    exp = admin.post("/api/v1/expedientes", json={"titular_id": titular["id"], "nombre": "Umbrales",
                                                  "tipo_expediente": "CORPORATIVO"}).json()
    recibidos = []
    original = cumplimiento._alertas

    def espia(*args, **kwargs):
        recibidos.append(args[7] if len(args) > 7 else kwargs.get("umbrales_vigentes"))
        return original(*args, **kwargs)

    monkeypatch.setattr(cumplimiento, "_alertas", espia)
    db = SessionLocal()
    try:
        cumplimiento.evaluar(db, db.get(Expediente, exp["id"]))
    finally:
        db.close()
    assert recibidos == [(60, 25, 10)]
    # Con esos umbrales, a 40 días ya hay alerta (Media) y a 8 días es Alta.
    assert cumplimiento._severidad_por_anticipacion(40, (60, 25, 10)) == "MEDIA"
    assert cumplimiento._severidad_por_anticipacion(8, (60, 25, 10)) == "ALTA"
    assert cumplimiento._severidad_por_anticipacion(40) is None, "Con los de omisión, a 40 días todavía no"
