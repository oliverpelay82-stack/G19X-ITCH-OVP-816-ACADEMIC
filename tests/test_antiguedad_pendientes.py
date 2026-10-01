"""
PLUS-20 — Antigüedad de lo pendiente (PRD §21.6; HU-56).

  1. Un documento En revisión sin ratificar informa los días que su dictamen
     lleva esperando, y la alerta «Pendiente de ratificación» los dice.
  2. Un dictamen ratificado, conforme o recién emitido no acumula espera.
  3. La bandeja ordena por antigüedad dentro de la misma severidad.
  4. La fecha del dictamen (UTC sin zona) se cuenta en la zona del servidor.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from datetime import date, datetime, timedelta, timezone  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.dictamen import DictamenAuditoria  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import cumplimiento  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
client = TestClient(app)


def _documento(rfc: str) -> dict:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Antigüedad {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": ("csf.pdf", b"%PDF-1.4 antiguedad " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _dictamen_de_hace(doc: dict, dias: int, estatus: str = "EN_REVISION") -> None:
    """Un dictamen emitido hace `dias` días (el trigger de RN-05 impide cambiar la fecha de uno existente)."""
    db = SessionLocal()
    try:
        db.add(DictamenAuditoria(
            documento_id=doc["id"], expediente_id=doc["expediente_id"], estatus=estatus, estatus_preliminar=estatus,
            nivel_confianza=0.75, observaciones=["Dictamen EN_REVISION: confianza baja."], reglas_aplicadas=[],
            hash_sha256=doc["hash_sha256"],
            creado_en=(datetime.now(timezone.utc) - timedelta(days=dias)).replace(tzinfo=None)))
        db.commit()
    finally:
        db.close()


def _evaluacion(doc: dict) -> dict:
    return client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()["evaluacion"]


def test_un_pendiente_informa_sus_dias_en_espera():
    doc = _documento("ANT010101AAA")
    _dictamen_de_hace(doc, 12)

    evaluacion = _evaluacion(doc)
    [estado] = [d for d in evaluacion["documentos"] if d["documento_id"] == doc["id"]]
    assert estado["dias_en_espera"] == 12
    [alerta] = [a for a in evaluacion["alertas"] if a["codigo"] == "PENDIENTE_RATIFICACION"]
    assert alerta["dias_en_espera"] == 12 and "Lleva 12 días esperando ratificación." in alerta["detalle"]


def test_sin_espera_no_se_informa():
    hoy_mismo, conforme = _documento("ANT020202AAA"), _documento("ANT030303AAA")
    _dictamen_de_hace(hoy_mismo, 0)
    _dictamen_de_hace(conforme, 30, estatus="CONFORME")

    pendiente = _evaluacion(hoy_mismo)
    [alerta] = [a for a in pendiente["alertas"] if a["codigo"] == "PENDIENTE_RATIFICACION"]
    assert alerta["dias_en_espera"] == 0 and "esperando" not in alerta["detalle"]
    assert all(d["dias_en_espera"] is None for d in _evaluacion(conforme)["documentos"])


def test_la_ratificacion_detiene_la_cuenta():
    doc = _documento("ANT040404AAA")
    _dictamen_de_hace(doc, 5)
    dictamen = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    r = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "NO_CONFORME", "justificacion": "La constancia no corresponde al titular.", "usuario": "p6"})
    assert r.status_code == 200, r.text
    assert all(d["dias_en_espera"] is None for d in _evaluacion(doc)["documentos"])


def test_la_bandeja_ordena_por_antiguedad_dentro_de_la_severidad():
    reciente, antiguo = _documento("ANT050505AAA"), _documento("ANT060606AAA")
    _dictamen_de_hace(reciente, 2)
    _dictamen_de_hace(antiguo, 40)

    bandeja = client.get("/api/v1/alertas", params={"codigo": "PENDIENTE_RATIFICACION"}).json()
    posiciones = {a["documento_id"]: i for i, a in enumerate(bandeja)}
    assert posiciones[antiguo["id"]] < posiciones[reciente["id"]]
    dias = [a["dias_en_espera"] or 0 for a in bandeja]
    assert dias == sorted(dias, reverse=True)


def test_la_fecha_utc_se_cuenta_en_la_zona_del_servidor():
    # 02:00 UTC del día 2 es todavía el día 1 en México (UTC-6): no es un día de espera más.
    creado = datetime(2026, 10, 2, 2, 0)
    local = creado.replace(tzinfo=timezone.utc).astimezone().date()
    dictamen = SimpleNamespace(revisado_por_humano=False, creado_en=creado)
    assert cumplimiento._dias_en_espera(dictamen, local) == 0
    assert cumplimiento._dias_en_espera(dictamen, local + timedelta(days=3)) == 3
    assert cumplimiento._dias_en_espera(dictamen, date(2000, 1, 1)) == 0, "Nunca negativo"
