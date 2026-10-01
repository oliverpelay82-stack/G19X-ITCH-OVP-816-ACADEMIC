"""
M6 — Versión del catálogo de reglas en el core (PRD §21.6; protocolo de
auditoría del DOC-05; HU-54).

  1. El cliente del rules-service toma la versión de la cabecera
     X-Version-Catalogo del inventario y la evaluación del expediente la informa.
  2. El dictamen guarda version_catalogo, la sella en su evento y el trigger de
     RN-05 impide cambiarla; un dictamen sin ella la deja vacía.
  3. El Excel del expediente la muestra en el resumen y en la hoja «Evidencia».

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from io import BytesIO  # noqa: E402
from types import SimpleNamespace  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
VERSION = "cat-0123456789ab"
_obtener_real = rules_client.obtener_documentos_obligatorios
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO, version_catalogo=VERSION,
)
client = TestClient(app)


def _documento(rfc: str) -> dict:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Catálogo {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": ("csf.pdf", b"%PDF-1.4 catalogo " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _dictaminar(doc: dict, **extra) -> dict:
    r = client.post("/api/v1/dictamenes", json={"documento_id": doc["id"], "estatus": "EN_REVISION",
                                                 "nivel_confianza": 0.8, "observaciones": ["M6."], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_cliente_toma_la_version_de_la_cabecera(monkeypatch):
    import requests

    respuesta = SimpleNamespace(
        json=lambda: [{"tipo_documento": "CSF_SAT", "codigo_regla": "RIE-01-CSF", "severidad": "CRITICA"}],
        headers={"X-Version-Catalogo": VERSION}, raise_for_status=lambda: None)
    monkeypatch.setattr(requests, "get", lambda *a, **k: respuesta)
    assert _obtener_real("CORPORATIVO").version_catalogo == VERSION


def test_la_evaluacion_informa_la_version():
    doc = _documento("VCT010101AAA")
    evaluacion = client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()["evaluacion"]
    assert evaluacion["version_catalogo"] == VERSION


def test_el_dictamen_guarda_y_protege_la_version():
    doc = _documento("VCT020202AAA")
    dictamen = _dictaminar(doc, version_catalogo=VERSION)

    guardado = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    assert guardado["version_catalogo"] == VERSION
    [evento] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "DICTAMEN_IA"}).json()
    assert evento["detalle"]["version_catalogo"] == VERSION
    with pytest.raises(DBAPIError), engine.begin() as conexion:
        conexion.execute(text("UPDATE dictamenes_auditoria SET version_catalogo = 'cat-otro' WHERE id = :id"),
                         {"id": dictamen["id"]})

    sin_version = _documento("VCT030303AAA")
    _dictaminar(sin_version)
    assert client.get("/api/v1/dictamenes", params={"documento_id": sin_version["id"]}).json()[0]["version_catalogo"] is None


def test_el_excel_muestra_la_version():
    doc = _documento("VCT040404AAA")
    _dictaminar(doc, version_catalogo=VERSION)

    r = client.get(f"/api/v1/reportes/expedientes/{doc['expediente_id']}", params={"formato": "xlsx"})

    assert r.status_code == 200
    libro = load_workbook(BytesIO(r.content))
    evidencia = libro["Evidencia"]
    fila = dict(zip([c.value for c in evidencia[1]], [c.value for c in evidencia[2]]))
    assert fila["Catálogo de reglas"] == VERSION
    valores = {c.value for hoja in libro.worksheets for fila in hoja.iter_rows() for c in fila}
    assert "Versión del catálogo de reglas" in valores
