"""
Hora del negocio en reportes y folios (Q-a, ESTADO_DEL_DESARROLLO §6.6; RF-23, RF-24).

La base guarda los instantes en UTC sin zona; de las 18:00 a las 24:00 de
México en UTC ya es el día siguiente. Lo que se imprime o nombra va en la zona
del negocio, la misma de la hora de emisión del encabezado:

  1. Las fechas de los reportes (``_fecha``) y la «Verificada el» de la cadena
     (``_fecha_texto``) se convierten de UTC a la zona del negocio.
  2. Un expediente abierto a las 22:48 del 1 de noviembre en México: el folio,
     la «Fecha de apertura» del PDF y la del Excel dicen el 1 de noviembre.
  3. El nombre del archivo del reporte global lleva la hora de México.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
from datetime import date, datetime, timezone
from io import BytesIO

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

import pytest  # noqa: E402
from openpyxl import load_workbook  # noqa: E402
from pypdf import PdfReader  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import zona_horaria  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.expediente import Expediente  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import reportes  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)

# 22:48 del 1/11 en México (UTC-06:00) son las 04:48 del 2/11 en UTC.
APERTURA_UTC = datetime(2026, 11, 2, 4, 48)
APERTURA_LOCAL = datetime(2026, 11, 1, 22, 48, tzinfo=zona_horaria.ZONA)


@pytest.fixture
def noche_en_mexico(monkeypatch):
    monkeypatch.setattr(zona_horaria, "ahora", lambda: APERTURA_LOCAL)


def test_las_fechas_se_imprimen_en_la_zona_del_negocio():
    assert reportes._fecha(APERTURA_UTC) == "2026-11-01 22:48", "Sin zona es UTC"
    assert reportes._fecha(APERTURA_UTC.replace(tzinfo=timezone.utc)) == "2026-11-01 22:48"
    assert reportes._fecha(date(2026, 11, 2)) == "2026-11-02", "Una fecha sin hora no se mueve"
    assert reportes._fecha(None) == "—"
    assert reportes._fecha_texto("2026-11-02T04:50:12.123456") == "2026-11-01 22:50"
    assert reportes._fecha_texto(None) == "—"


def test_el_expediente_abierto_de_noche_lleva_la_fecha_de_mexico(noche_en_mexico):
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc="HLO011101AAA", razon_social="Hora Local S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    r = client.post("/api/v1/expedientes", json={"titular_id": titular_id})
    assert r.status_code == 201, r.text
    expediente = r.json()
    assert expediente["codigo_expediente"] == "EXP-HLO0-202611012248"

    db = SessionLocal()
    try:   # el instante de la apertura, como lo guarda la base
        db.query(Expediente).filter(Expediente.id == expediente["id"]).update({"creado_en": APERTURA_UTC})
        db.commit()
    finally:
        db.close()

    ruta = f"/api/v1/reportes/expedientes/{expediente['id']}"
    pdf = client.get(ruta, params={"formato": "pdf"})
    assert pdf.status_code == 200, pdf.text
    texto = "\n".join(p.extract_text() for p in PdfReader(BytesIO(pdf.content)).pages)
    assert "2026-11-01 22:48" in texto
    assert "2026-11-02 04:48" not in texto

    xlsx = client.get(ruta, params={"formato": "xlsx"})
    assert xlsx.status_code == 200, xlsx.text
    celdas = {str(v) for hoja in load_workbook(BytesIO(xlsx.content)).worksheets
              for fila in hoja.iter_rows(values_only=True) for v in fila if v is not None}
    assert "2026-11-01 22:48" in celdas
    assert "2026-11-02 04:48" not in celdas


def test_el_reporte_global_se_nombra_con_la_hora_de_mexico(noche_en_mexico):
    r = client.get("/api/v1/reportes/cumplimiento", params={"formato": "xlsx"})
    assert r.status_code == 200, r.text
    assert 'filename="reporte_cumplimiento_20261101_2248.xlsx"' in r.headers["content-disposition"]
