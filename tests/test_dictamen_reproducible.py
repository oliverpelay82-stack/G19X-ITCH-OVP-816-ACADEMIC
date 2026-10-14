"""
P5 — Dictamen reproducible (PRD §21.5; protocolo de auditoría del DOC-05; HU-46).

  1. El dictamen guarda la versión de la lectura del Nivel 3 y la huella de las
     instrucciones al modelo, las devuelve y las sella en su evento DICTAMEN_IA.
  2. Un dictamen sin ellas (anterior a P5 o emitido sin la IA) las deja vacías.
  3. El trigger de RN-05 impide cambiarlas, también dentro de una ratificación.
     Tampoco los datos que extrajo la auditoría (RFC, coincidencia con el titular,
     fechas, vigencia, tipo detectado, modelo y si requería revisión humana).
  4. El Excel del expediente muestra con qué lectura e instrucciones se dictaminó.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from io import BytesIO  # noqa: E402

import pytest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)

LECTURA = "n3-3.3|tesseract-5.4.0|spa|300dpi|sin-sellos"
INSTRUCCIONES = "inst-0123456789ab"


def _documento(rfc: str) -> dict:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Reproducible {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": ("csf.pdf", b"%PDF-1.4 reproducible " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _dictaminar(doc: dict, **extra) -> dict:
    r = client.post("/api/v1/dictamenes", headers=auth.sistema(), json={"documento_id": doc["id"], "estatus": "EN_REVISION",
                                                 "nivel_confianza": 0.8, "observaciones": ["Prueba P5."], **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_dictamen_guarda_y_sella_sus_versiones():
    doc = _documento("RPD010101AAA")
    dictamen = _dictaminar(doc, version_lectura=LECTURA, version_instrucciones=INSTRUCCIONES)

    guardado = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    assert guardado["id"] == dictamen["id"]
    assert guardado["version_lectura"] == LECTURA and guardado["version_instrucciones"] == INSTRUCCIONES
    [evento] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "DICTAMEN_IA"}).json()
    assert evento["detalle"]["version_lectura"] == LECTURA and evento["hash_evento"], "Sellado en la bitácora"


def test_un_dictamen_sin_versiones_las_deja_vacias():
    doc = _documento("RPD020202AAA")
    _dictaminar(doc)
    guardado = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    assert guardado["version_lectura"] is None and guardado["version_instrucciones"] is None


def test_la_ratificacion_no_puede_cambiar_las_versiones():
    doc = _documento("RPD030303AAA")
    dictamen = _dictaminar(doc, version_lectura=LECTURA, version_instrucciones=INSTRUCCIONES)

    with pytest.raises(DBAPIError, match="RN-05"):
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE dictamenes_auditoria SET revisado_por_humano = true, estatus = 'CONFORME', "
                "justificacion_humana = 'Ratificación que intenta cambiar la lectura.', revisado_por = 'prueba', "
                "version_lectura = 'otra-lectura' WHERE id = :id"), {"id": dictamen["id"]})

    # La ratificación legítima sí procede y conserva las versiones.
    r = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "CONFORME", "justificacion": "Constancia cotejada en el portal del SAT.", "usuario": "p5"})
    assert r.status_code == 200, r.text
    guardado = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    assert guardado["version_lectura"] == LECTURA and guardado["revisado_por_humano"]



# Hallazgo 5 (auditoría del 14/10/2026): datos de origen que el trigger no comparaba.
_DATOS_EXTRAIDOS = {
    "requiere_revision_humana": "true",
    "vigencia_resultado": "'VENCIDO'",
    "tipo_documento_detectado": "'OTRO'",
    "rfc_detectado": "'XAXX010101000'",
    "match_titular": "true",
    "fecha_emision_extraida": "DATE '2020-01-01'",
    "fecha_vencimiento_extraida": "DATE '2020-01-01'",
    "modelo_utilizado": "'otro-modelo'",
}


@pytest.mark.parametrize("n,columna", list(enumerate(_DATOS_EXTRAIDOS, start=1)))
def test_la_ratificacion_no_puede_cambiar_los_datos_extraidos(n, columna):
    dictamen = _dictaminar(_documento(f"RPE01010{n}AAA"))
    with pytest.raises(DBAPIError, match="RN-05"):
        with engine.begin() as conn:
            conn.execute(text(
                "UPDATE dictamenes_auditoria SET revisado_por_humano = true, estatus = 'CONFORME', "
                "justificacion_humana = 'Ratificación que intenta reescribir lo extraído.', revisado_por = 'prueba', "
                f"{columna} = {_DATOS_EXTRAIDOS[columna]} WHERE id = :id"), {"id": dictamen["id"]})


def test_el_excel_del_expediente_muestra_las_versiones():
    doc = _documento("RPD040404AAA")
    _dictaminar(doc, version_lectura=LECTURA, version_instrucciones=INSTRUCCIONES)

    r = client.get(f"/api/v1/reportes/expedientes/{doc['expediente_id']}", params={"formato": "xlsx"})

    assert r.status_code == 200
    hoja = load_workbook(BytesIO(r.content))["Evidencia"]
    cabecera = [c.value for c in hoja[1]]
    fila = dict(zip(cabecera, [c.value for c in hoja[2]]))
    assert fila["Versión de la lectura"] == LECTURA and fila["Instrucciones al modelo"] == INSTRUCCIONES
