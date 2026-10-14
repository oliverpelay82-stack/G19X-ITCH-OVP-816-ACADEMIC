"""
RF-09 — Carga de un tipo de documento nuevo declarado por una regla RDS
(RDS-01; docs/uml/rf09-actividad-tipo-documento-nuevo.puml).

  1. La carga admite un tipo declarado activo y lo nombra con el nombre de su
     regla en la bitácora y en las alertas del expediente; rechaza (422) un
     tipo desconocido, uno declarado pero pausado y un código mal formado.
  2. Un tipo declarado obligatorio (RIE-01 del rules-service) cuenta en la
     completitud como cualquier otro.
  3. Si el rules-service no responde, se conserva lo último conocido y los
     tipos del catálogo base se siguen admitiendo.

El rules-service se simula: la carga consulta GET /reglas/tipos-documento.
Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

import pytest  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import catalogo  # noqa: E402
from motor import tipos_documento  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)

NUEVO = "PERMISO_DE_IMPACTO_AMBIENTAL"
DECLARADOS = [
    {"tipo_documento": NUEVO, "nombre": "Permiso de Impacto Ambiental", "activo": True,
     "tipo_expediente": "REGULATORIO", "codigo_regla": f"RDS-{NUEVO}"},
    {"tipo_documento": "DICTAMEN_PROTECCION_CIVIL", "nombre": "Dictamen de Protección Civil", "activo": False,
     "tipo_expediente": None, "codigo_regla": "RDS-DICTAMEN_PROTECCION_CIVIL"},
]


@pytest.fixture(autouse=True)
def rules_simulado(monkeypatch):
    """Tipos declarados simulados, inventario con el tipo nuevo obligatorio y caché vacía."""
    respuestas = {"tipos": DECLARADOS}
    monkeypatch.setattr(rules_client, "tipos_documento_declarados", lambda: respuestas["tipos"])
    monkeypatch.setattr(rules_client, "obtener_documentos_obligatorios", lambda *_: rules_client.InventarioObligatorio(
        documentos={"LICENCIA_OPERACION": {"codigo_regla": "RIE-01-REG-LIC", "severidad": "CRITICA"},
                    NUEVO: {"codigo_regla": f"RIE-01-{NUEVO}", "severidad": "ALTA"}},
        fuente=rules_client.FUENTE_CATALOGO,
    ))
    monkeypatch.setattr(tipos_documento, "_consultado_en", None)
    monkeypatch.setattr(tipos_documento, "_declarados", {})
    yield respuestas


def _expediente() -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc="TDN" + "010101" + uuid.uuid4().hex[:3].upper(),
                                    razon_social="Tipos Nuevos S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    r = client.post("/api/v1/expedientes", json={"titular_id": titular_id, "tipo_expediente": "REGULATORIO"})
    return r.json()["id"]


def _subir(exp_id: str, tipo: str):
    return client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": tipo},
                       files={"file": ("permiso.pdf", b"%PDF-1.4 " + os.urandom(16), "application/pdf")})


def test_un_tipo_declarado_se_custodia_y_cuenta_en_la_completitud():
    exp_id = _expediente()
    faltantes_antes = client.get(f"/api/v1/expedientes/{exp_id}").json()["evaluacion"]["faltantes"]
    assert NUEVO in faltantes_antes

    r = _subir(exp_id, NUEVO.lower())   # el código se normaliza a mayúsculas

    assert r.status_code == 201, r.text
    assert r.json()["tipo_documento"] == NUEVO
    evaluacion = client.get(f"/api/v1/expedientes/{exp_id}").json()["evaluacion"]
    assert NUEVO not in evaluacion["faltantes"]
    assert any(o["tipo_documento"] == NUEVO and o["presente"] for o in evaluacion["obligatorios"])
    # La alerta del obligatorio que sigue faltando y la del tipo nuevo usan nombres legibles.
    titulos = [a["titulo"] for a in evaluacion["alertas"]]
    assert any("Licencia de Operación" in t for t in titulos)
    assert catalogo.etiqueta_documento(NUEVO) == "Permiso de Impacto Ambiental"
    # La ficha del documento trae el nombre legible: el ai-service lo usa para el motivo de una
    # discrepancia de tipo («Se esperaba el documento «Permiso de Impacto Ambiental»…»).
    ficha = client.get(f"/api/v1/documentos/{r.json()['id']}").json()
    assert ficha["nombre_tipo_documento"] == "Permiso de Impacto Ambiental"
    licencia = _subir(exp_id, "LICENCIA_OPERACION").json()
    assert licencia["nombre_tipo_documento"] == "Licencia de Operación"


@pytest.mark.parametrize("tipo", ["TIPO_INVENTADO", "DICTAMEN_PROTECCION_CIVIL", "tipo con espacios", "1X"])
def test_tipos_no_admitidos_se_rechazan(tipo):
    r = _subir(_expediente(), tipo)
    assert r.status_code == 422
    assert "no reconocido" in r.json()["detail"]


def test_sin_rules_service_se_conserva_lo_conocido(rules_simulado):
    exp_id = _expediente()
    assert _subir(exp_id, NUEVO).status_code == 201          # primera consulta: queda en caché
    rules_simulado["tipos"] = None                           # el rules-service deja de responder
    tipos_documento._consultado_en = None                    # y la caché venció
    assert catalogo.etiqueta_documento(NUEVO) == "Permiso de Impacto Ambiental"
    assert _subir(exp_id, "LICENCIA_OPERACION").status_code == 201, "El catálogo base no depende del rules-service"
