"""
P5 — Excepciones del DOC-05, Tabla 1, en el core (PRD §10.4 y ESTADO_DEL_DESARROLLO §6.5; HU-33,
HU-47, HU-48).

  1. Documento ilegible: un dictamen de origen NIVEL_3_ILEGIBLE deja el
     documento «ilegible», con su motivo y la alerta DOCUMENTO_ILEGIBLE en
     lugar de «Pendiente de ratificación»; no puede ratificarse como conforme
     (sí como no conforme).
  2. Procesamiento diferido: el aviso del ai-service marca el documento,
     sella PROCESAMIENTO_DIFERIDO y muestra la alerta en lugar de «Sin
     auditar»; con los reintentos agotados la alerta pide relanzarla; al
     guardarse el dictamen la marca y la alerta desaparecen.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

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


def _documento(rfc: str) -> dict:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Excepciones {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": ("csf.pdf", b"%PDF-1.4 excepciones " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _evaluacion(doc: dict) -> dict:
    return client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()["evaluacion"]


def _estado_documento(evaluacion: dict, doc: dict) -> dict:
    return next(d for d in evaluacion["documentos"] if d["documento_id"] == doc["id"])


def _codigos(evaluacion: dict) -> set[str]:
    return {a["codigo"] for a in evaluacion["alertas"]}


# ── Documento ilegible ────────────────────────────────────────────────


def _dictamen_ilegible(doc: dict) -> dict:
    r = client.post("/api/v1/dictamenes", headers=auth.sistema(), json={
        "documento_id": doc["id"], "estatus": "EN_REVISION", "nivel_confianza": 0.12,
        "requiere_revision_humana": True, "origen": "NIVEL_3_ILEGIBLE",
        "observaciones": ["Documento ilegible, se requiere recarga: la lectura no obtuvo texto suficiente."]})
    assert r.status_code == 201, r.text
    return r.json()


def test_un_documento_ilegible_lleva_su_alerta_y_su_motivo():
    doc = _documento("EXC010101AAA")
    _dictamen_ilegible(doc)

    evaluacion = _evaluacion(doc)
    assert _estado_documento(evaluacion, doc)["ilegible"] is True
    assert evaluacion["estado"] == "EN_REVISION"
    assert "DOCUMENTO_ILEGIBLE" in _codigos(evaluacion)
    assert "PENDIENTE_RATIFICACION" not in _codigos(evaluacion), "No se confunde con la revisión por contenido"
    assert any("documento ilegible, se requiere recarga" in m for m in evaluacion["motivos"])
    alerta = next(a for a in evaluacion["alertas"] if a["codigo"] == "DOCUMENTO_ILEGIBLE")
    assert "mejor resolución" in alerta["recomendacion"]


def test_un_documento_ilegible_no_se_ratifica_como_conforme():
    doc = _documento("EXC020202AAA")
    dictamen = _dictamen_ilegible(doc)

    conforme = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "CONFORME", "justificacion": "Se leyó a mano y parece correcto.", "usuario": "p5"})
    assert conforme.status_code == 409 and "ilegible" in conforme.json()["detail"]

    no_conforme = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "NO_CONFORME", "justificacion": "Ilegible: se solicitó al titular la recarga.", "usuario": "p5"})
    assert no_conforme.status_code == 200, no_conforme.text
    assert _estado_documento(_evaluacion(doc), doc)["ilegible"] is False, "Ratificado, deja de contarse como ilegible"


# ── Procesamiento diferido ────────────────────────────────────────────


def _diferir(doc: dict, **extra) -> dict:
    r = client.post(f"/api/v1/documentos/{doc['id']}/procesamiento-diferido", headers=auth.sistema(), json={
        "motivo": "El servicio de IA no respondió tras 3 intentos.", "intentos": 1, "max_intentos": 6,
        "proximo_intento": "2026-10-01T10:15:00+00:00", **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_una_auditoria_diferida_se_marca_y_alerta_en_lugar_de_sin_auditar():
    doc = _documento("EXC030303AAA")
    _diferir(doc)

    evaluacion = _evaluacion(doc)
    estado = _estado_documento(evaluacion, doc)
    assert estado["procesamiento_diferido"]["intentos"] == 1 and estado["procesamiento_diferido"]["desde"]
    assert "PROCESAMIENTO_DIFERIDO" in _codigos(evaluacion) and "PENDIENTE_AUDITORIA" not in _codigos(evaluacion)
    assert any("se reintentará sola" in m for m in evaluacion["motivos"])
    [evento] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"],
                                                      "evento": "PROCESAMIENTO_DIFERIDO"}).json()
    assert evento["hash_evento"] and evento["detalle"]["max_intentos"] == 6


def test_con_los_reintentos_agotados_la_alerta_pide_relanzar():
    doc = _documento("EXC040404AAA")
    _diferir(doc)
    _diferir(doc, intentos=6, agotado=True)

    evaluacion = _evaluacion(doc)
    alerta = next(a for a in evaluacion["alertas"] if a["codigo"] == "PROCESAMIENTO_DIFERIDO")
    assert alerta["severidad"] == "MEDIA_ALTA" and "Relanzar" in alerta["recomendacion"]
    assert any("se agotaron los reintentos" in m for m in evaluacion["motivos"])
    eventos = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "PROCESAMIENTO_DIFERIDO"})
    primero, segundo = sorted(eventos.json(), key=lambda e: e["secuencia"])
    assert primero["detalle"]["desde"] == segundo["detalle"]["desde"], "Conserva desde cuándo está diferido"


def test_al_guardarse_el_dictamen_la_marca_y_la_alerta_desaparecen():
    doc = _documento("EXC050505AAA")
    _diferir(doc)

    r = client.post("/api/v1/dictamenes", headers=auth.sistema(), json={"documento_id": doc["id"], "estatus": "EN_REVISION",
                                                 "nivel_confianza": 0.8, "observaciones": ["Reintento exitoso."]})
    assert r.status_code == 201, r.text

    evaluacion = _evaluacion(doc)
    assert _estado_documento(evaluacion, doc)["procesamiento_diferido"] is None
    assert "PROCESAMIENTO_DIFERIDO" not in _codigos(evaluacion)


def test_diferir_un_documento_inexistente():
    r = client.post("/api/v1/documentos/no-existe/procesamiento-diferido", headers=auth.sistema(),
                    json={"motivo": "x", "intentos": 1, "max_intentos": 6})
    assert r.status_code == 404
