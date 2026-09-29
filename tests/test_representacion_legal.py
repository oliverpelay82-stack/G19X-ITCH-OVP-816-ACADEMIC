"""
P2 — Representación legal en el core-service (PRD §21.2: RSC-02, RN-03, HU-23,
HU-37, HU-38).

Persistencia
  1. El dictamen guarda los firmantes o apoderados del Nivel 4 solo con los
     roles y campos conocidos; un rol desconocido no se guarda.
  2. La columna representacion_legal es inmutable (trg_dictamen_protegido).

Cotejo determinista (RN-03, HU-38)
  3. Coincidencia de nombres sin acentos, títulos, partículas ni iniciales.
  4. ACREDITADO con un poder o un acta vigentes; la contraparte no se coteja.
  5. NO_ACREDITADO y PODER_VENCIDO alertan REPRESENTACION_NO_ACREDITADA (Alta)
     hasta que el analista ratifica el contrato (RN-05).
  6. Un poder de otro titular no acredita.
  7. Lo que falta (contrato, poder o acta sin auditar o auditados antes de P2,
     firmante sin cita) deja el cotejo PENDIENTE, sin alerta ni rechazo.

Aislamiento: base de datos de pruebas plurione_compliance_test y bóveda
temporal (tests/bd_pruebas.py).
"""
import os
import sys
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import representacion  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()

rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={t: {"codigo_regla": "RIE-01", "severidad": "CRITICA"}
                for t in ("CONTRATO_SERVICIOS", "ACUERDO_CONFIDENCIALIDAD", "PODER_NOTARIAL")},
    fuente=rules_client.FUENTE_CATALOGO,
)
client = TestClient(app)
RAZON = "Constructora Sierra Madre, S.A. de C.V."


def _expediente(rfc: str) -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=RAZON, tipo_persona="MORAL", categoria="PROVEEDOR")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    r = client.post("/api/v1/expedientes", json={"titular_id": titular_id, "tipo_expediente": "JURIDICO"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _subir(exp_id: str, tipo: str, nombre: str) -> str:
    r = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": tipo},
        files={"file": (nombre, b"%PDF-1.4 " + nombre.encode() + os.urandom(8), "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _dictaminar(doc_id: str, representacion: dict | None, estatus: str = "EN_REVISION", **extra) -> dict:
    r = client.post("/api/v1/dictamenes", json={
        "documento_id": doc_id, "estatus": estatus, "nivel_confianza": 0.95, "match_titular": True,
        "observaciones": ["Prueba automatizada."], "representacion": representacion, **extra,
    })
    assert r.status_code == 201, r.text
    return r.json()


def test_el_dictamen_guarda_la_representacion_depurada():
    exp_id = _expediente("REP010101AAA")
    doc_id = _subir(exp_id, "CONTRATO_SERVICIOS", "contrato.pdf")

    dictamen = _dictaminar(doc_id, {"rol": "FIRMANTES", "personas": [
        {"nombre": "  Juan   Pérez López ", "cargo": "Apoderado", "empresa": RAZON, "cita": "Juan Pérez López",
         "cita_verificada": True, "curp": "PELJ800101HGRRPN09"},     # campo no admitido
        {"cargo": "sin nombre"},
    ]})

    assert dictamen["representacion_legal"] == {"rol": "FIRMANTES", "personas": [
        {"nombre": "Juan Pérez López", "cargo": "Apoderado", "empresa": RAZON, "cita": "Juan Pérez López",
         "cita_verificada": True}]}
    otro = _dictaminar(_subir(exp_id, "ACUERDO_CONFIDENCIALIDAD", "nda.pdf"), {"rol": "TESTIGOS", "personas": []})
    assert otro["representacion_legal"] is None


def test_la_representacion_del_dictamen_es_inmutable():
    exp_id = _expediente("REP020202AAA")
    dictamen = _dictaminar(_subir(exp_id, "PODER_NOTARIAL", "poder.pdf"),
                           {"rol": "APODERADOS", "personas": [{"nombre": "Juan Pérez López", "cita": "x"}]})

    # La ratificación es la única escritura permitida; aprovecharla para cambiar
    # a los apoderados debe fallar igual que reescribir las reglas aplicadas.
    with pytest.raises(DBAPIError, match="RN-05"):
        with engine.begin() as conexion:
            conexion.execute(
                text("UPDATE dictamenes_auditoria SET revisado_por_humano = TRUE, estatus = 'CONFORME', "
                     "representacion_legal = CAST(:v AS JSON) WHERE id = :id"),
                {"v": '{"rol": "APODERADOS", "personas": []}', "id": dictamen["id"]},
            )


# ── Cotejo RN-03 (HU-38) ──────────────────────────────────────────────
HOY = date.today()
FIRMA_TITULAR = {"nombre": "Lic. Juan Pérez López", "cargo": "Apoderado legal", "empresa": RAZON,
                 "cita": "POR CONSTRUCTORA SIERRA MADRE: Lic. Juan Pérez López", "cita_verificada": True}
FIRMA_CONTRAPARTE = {"nombre": "Ana María Ruiz", "cargo": "Directora General",
                     "empresa": "Servicios del Pacífico, S.A. de C.V.", "cita": "Ana María Ruiz", "cita_verificada": True}


def _contrato(exp_id: str, firmantes: list[dict] | None = None, tipo: str = "CONTRATO_SERVICIOS") -> str:
    doc_id = _subir(exp_id, tipo, "contrato.pdf")
    _dictaminar(doc_id, {"rol": "FIRMANTES", "personas": firmantes or [FIRMA_TITULAR, FIRMA_CONTRAPARTE]})
    return doc_id


def _poder(exp_id: str, apoderado: str, vence_en: int = 200, tipo: str = "PODER_NOTARIAL", **extra) -> str:
    doc_id = _subir(exp_id, tipo, f"{tipo.lower()}.pdf")
    vencido = vence_en < 0
    _dictaminar(doc_id, {"rol": "APODERADOS", "personas": [
        {"nombre": apoderado, "cargo": "Apoderado general", "facultades": "Pleitos y cobranzas y actos de administración",
         "cita": f"a favor del señor {apoderado}", "cita_verificada": True}]},
        estatus="NO_CONFORME" if vencido else "CONFORME",
        fecha_vencimiento=(HOY + timedelta(days=vence_en)).isoformat(), **extra)
    return doc_id


def _evaluacion(exp_id: str) -> dict:
    return client.get(f"/api/v1/expedientes/{exp_id}").json()["evaluacion"]


def _cotejo(exp_id: str) -> dict:
    [cotejo] = [c for c in _evaluacion(exp_id)["representacion"] if c["tipo_documento"] == "CONTRATO_SERVICIOS"]
    return cotejo


def _alertas(exp_id: str) -> list[dict]:
    return [a for a in _evaluacion(exp_id)["alertas"] if a["codigo"] == "REPRESENTACION_NO_ACREDITADA"]


@pytest.mark.parametrize("a, b, esperado", [
    ("Lic. Juan Pérez López", "JUAN PEREZ LOPEZ", True),
    ("Juan Pérez", "Juan Pérez López", True),                    # contrato con un apellido, poder con dos
    ("María de la Luz Gómez", "MARIA LUZ GOMEZ", True),          # partículas
    ("Juan López", "Juan Pérez", False),
    ("Juan", "Juan Pérez", False),                               # una sola palabra no identifica a nadie
    ("C. P. Ana Ruiz", "Ana Ruiz Soto", True),                   # títulos e iniciales
])
def test_mismo_nombre(a, b, esperado):
    assert representacion.mismo_nombre(a, b) is esperado


def test_firmante_que_es_apoderado_de_un_poder_vigente_queda_acreditado():
    exp_id = _expediente("COT010101AAA")
    contrato = _contrato(exp_id)
    poder = _poder(exp_id, "JUAN PEREZ LOPEZ")

    cotejo = _cotejo(exp_id)

    assert cotejo["estado"] == "ACREDITADO", cotejo
    assert [f["nombre"] for f in cotejo["firmantes"]] == ["Lic. Juan Pérez López"], "La contraparte no se coteja"
    assert cotejo["coincidencias"][0]["documento_id"] == poder and cotejo["documento_id"] == contrato
    assert "JUAN PEREZ LOPEZ" in cotejo["coincidencias"][0]["cita"]
    assert not _alertas(exp_id)


def test_el_acta_constitutiva_tambien_acredita():
    exp_id = _expediente("COT020202AAA")
    _contrato(exp_id)
    _poder(exp_id, "Juan Pérez López", tipo="ACTA_CONSTITUTIVA")

    assert _cotejo(exp_id)["estado"] == "ACREDITADO"


def test_firmante_sin_facultades_alerta_hasta_que_el_analista_ratifica():
    exp_id = _expediente("COT030303AAA")
    contrato = _contrato(exp_id)
    _poder(exp_id, "María Gómez Ríos")

    cotejo = _cotejo(exp_id)
    [alerta] = _alertas(exp_id)
    assert cotejo["estado"] == "NO_ACREDITADO" and "Lic. Juan Pérez López" in cotejo["motivo"], cotejo
    assert alerta["severidad"] == "ALTA" and alerta["regla"] == "RSC-02" and alerta["documento_id"] == contrato
    assert any("RN-03" in m for m in _evaluacion(exp_id)["motivos"])

    dictamen = client.get("/api/v1/dictamenes", params={"documento_id": contrato}).json()[0]
    r = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "CONFORME", "justificacion": "El firmante acreditó sus facultades con poder en trámite."})
    assert r.status_code == 200, r.text

    assert _cotejo(exp_id)["ratificado"] and not _alertas(exp_id), "La decisión humana prevalece (RN-05)"


def test_firmante_con_poder_vencido():
    exp_id = _expediente("COT040404AAA")
    _contrato(exp_id)
    _poder(exp_id, "Juan Pérez López", vence_en=-10)

    cotejo = _cotejo(exp_id)

    assert cotejo["estado"] == "PODER_VENCIDO", cotejo
    assert len(_alertas(exp_id)) == 1


def test_poder_de_otro_titular_no_acredita():
    exp_id = _expediente("COT050505AAA")
    _contrato(exp_id)
    _poder(exp_id, "Juan Pérez López", match_titular=False)

    cotejo = _cotejo(exp_id)

    assert cotejo["estado"] == "NO_ACREDITADO" and "no pertenece al titular" in cotejo["motivo"], cotejo


@pytest.mark.parametrize("escenario, rfc", [
    ("poder_sin_auditar", "PEN010101AAA"), ("poder_previo_a_p2", "PEN020202AAA"),
    ("contrato_sin_auditar", "PEN030303AAA"), ("sin_poder", "PEN040404AAA"), ("firmante_sin_cita", "PEN050505AAA"),
])
def test_lo_que_falta_deja_el_cotejo_pendiente_sin_rechazar(escenario, rfc):
    exp_id = _expediente(rfc)
    if escenario == "contrato_sin_auditar":
        _subir(exp_id, "CONTRATO_SERVICIOS", "contrato.pdf")
        _poder(exp_id, "Juan Pérez López")
    elif escenario == "firmante_sin_cita":
        _contrato(exp_id, [{**FIRMA_TITULAR, "cita_verificada": False}])
        _poder(exp_id, "Juan Pérez López")
    else:
        _contrato(exp_id)
        if escenario == "poder_sin_auditar":
            _subir(exp_id, "PODER_NOTARIAL", "poder.pdf")
        elif escenario == "poder_previo_a_p2":
            _dictaminar(_subir(exp_id, "PODER_NOTARIAL", "poder.pdf"), None, estatus="CONFORME")

    cotejo = _cotejo(exp_id)

    assert cotejo["estado"] == "PENDIENTE" and cotejo["recomendacion"], cotejo
    assert not _alertas(exp_id)
