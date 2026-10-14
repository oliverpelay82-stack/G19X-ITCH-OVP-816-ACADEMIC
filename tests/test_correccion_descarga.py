"""
Descarga del archivo original y corrección de datos de captura (PRD §13.1;
docs/uml/ui-actividad-correccion-datos.puml).

  1. Descarga del original: llega con su nombre de carga (acentos incluidos,
     RFC 6266), verificada por RIE-03, y queda en la bitácora
     (DESCARGA_DOCUMENTO). La lectura sin `descarga` —la del ai-service— no se
     registra, y un archivo alterado no se descarga ni se registra.
  2. Corrección de datos: la razón social y la categoría de una empresa y el
     nombre de un expediente cambian con su valor anterior y el nuevo en la
     bitácora; sin cambios no hay evento; el RFC y el tipo no se aceptan.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import uuid
from urllib.parse import quote

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.boveda import ruta_en_boveda  # noqa: E402
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


def _rfc() -> str:
    return "DES" + "010101" + uuid.uuid4().hex[:3].upper()


def _titular(razon_social: str = "Descargas de Prueba S.A. de C.V.") -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=_rfc(), razon_social=razon_social, tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        return titular.id
    finally:
        db.close()


def _documento(nombre: str) -> tuple[dict, bytes]:
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": _titular()}).json()["id"]
    contenido = b"%PDF-1.4 " + os.urandom(16)
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": (nombre, contenido, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json(), contenido


def _descargas(documento_id: str) -> list[dict]:
    return client.get("/api/v1/bitacora", params={"documento_id": documento_id,
                                                  "evento": "DESCARGA_DOCUMENTO"}).json()


def test_la_descarga_entrega_el_original_con_su_nombre_y_queda_en_la_bitacora():
    nombre = "constancia situación fiscal.pdf"
    doc, contenido = _documento(nombre)

    r = client.get(f"/api/v1/documentos/{doc['id']}/contenido", params={"descarga": "true"})

    assert r.status_code == 200
    assert r.content == contenido
    disposicion = r.headers["content-disposition"]
    assert disposicion.startswith("attachment;")
    assert f"filename*=UTF-8''{quote(nombre)}" in disposicion
    assert 'filename="constancia situaci_n fiscal.pdf"' in disposicion   # respaldo ASCII
    eventos = _descargas(doc["id"])
    assert len(eventos) == 1
    assert eventos[0]["detalle"]["hash_sha256"] == doc["hash_sha256"]
    assert eventos[0]["expediente_id"] == doc["expediente_id"]


def test_la_lectura_del_ai_service_no_se_registra_como_descarga():
    doc, contenido = _documento("csf.pdf")

    r = client.get(f"/api/v1/documentos/{doc['id']}/contenido", headers=auth.sistema())

    assert r.status_code == 200 and r.content == contenido
    assert "content-disposition" not in r.headers
    assert _descargas(doc["id"]) == []


def test_un_archivo_alterado_no_se_descarga_ni_se_registra():
    doc, _ = _documento("csf_alterada.pdf")
    with open(ruta_en_boveda(doc["hash_sha256"], "csf_alterada.pdf"), "wb") as archivo:
        archivo.write(b"%PDF-1.4 contenido manipulado")

    r = client.get(f"/api/v1/documentos/{doc['id']}/contenido", params={"descarga": "true"})

    assert r.status_code == 409
    assert _descargas(doc["id"]) == []


def _eventos(evento: str) -> list[dict]:
    return client.get("/api/v1/bitacora", params={"evento": evento, "limite": 500}).json()


def test_corregir_la_razon_social_y_la_categoria_queda_en_la_bitacora():
    titular_id = _titular("Corrección Previa S.A. de C.V.")

    r = client.patch(f"/api/v1/titulares/{titular_id}",
                     json={"razon_social": "  Corrección   Nueva S.A. de C.V. ", "categoria": "cliente"})

    assert r.status_code == 200, r.text
    assert r.json()["razon_social"] == "Corrección Nueva S.A. de C.V."   # espacios normalizados
    assert r.json()["categoria"] == "CLIENTE"
    evento = next(e for e in _eventos("ACTUALIZACION_TITULAR") if e["detalle"]["titular_id"] == titular_id)
    assert evento["detalle"]["cambios"] == {
        "razon_social": {"anterior": "Corrección Previa S.A. de C.V.", "nuevo": "Corrección Nueva S.A. de C.V."},
        "categoria": {"anterior": "PROVEEDOR", "nuevo": "CLIENTE"},
    }


def test_sin_cambios_no_hay_evento_y_el_rfc_no_se_edita():
    titular_id = _titular("Sin Cambios S.A. de C.V.")
    antes = len(_eventos("ACTUALIZACION_TITULAR"))

    mismo = client.patch(f"/api/v1/titulares/{titular_id}", json={"razon_social": "Sin Cambios S.A. de C.V."})
    assert mismo.status_code == 200
    assert len(_eventos("ACTUALIZACION_TITULAR")) == antes
    assert client.patch(f"/api/v1/titulares/{titular_id}", json={"rfc": "XXX010101XXX"}).status_code == 422
    assert client.patch(f"/api/v1/titulares/{titular_id}", json={}).status_code == 422
    assert client.patch(f"/api/v1/titulares/{titular_id}", json={"razon_social": " ab "}).status_code == 422
    assert client.patch("/api/v1/titulares/no-existe", json={"categoria": "CLIENTE"}).status_code == 404


def test_renombrar_un_expediente_queda_en_su_historial():
    exp = client.post("/api/v1/expedientes", json={"titular_id": _titular(), "nombre": "Alta 2026"}).json()

    r = client.patch(f"/api/v1/expedientes/{exp['id']}", json={"nombre": "Proveedores 2026"})
    assert r.status_code == 200, r.text
    assert r.json()["nombre"] == "Proveedores 2026"
    filtro = {"expediente_id": exp["id"], "evento": "ACTUALIZACION_EXPEDIENTE"}
    historial = client.get("/api/v1/bitacora", params=filtro).json()
    assert [e["detalle"]["cambios"]["nombre"] for e in historial] == [
        {"anterior": "Alta 2026", "nuevo": "Proveedores 2026"}
    ]

    # Mismo nombre: sin evento. Vacío: quita el nombre. El tipo no se edita.
    client.patch(f"/api/v1/expedientes/{exp['id']}", json={"nombre": "Proveedores 2026"})
    assert client.patch(f"/api/v1/expedientes/{exp['id']}", json={"nombre": "  "}).json()["nombre"] is None
    assert len(client.get("/api/v1/bitacora", params=filtro).json()) == 2
    assert client.patch(f"/api/v1/expedientes/{exp['id']}", json={"tipo_expediente": "JURIDICO"}).status_code == 422


def test_la_ficha_del_documento_trae_el_titular_vigente():
    """
    Hallazgo 6 (auditoría del 14/10/2026): el ai-service toma de la ficha el RFC y
    la razón social del titular para la titularidad; tras una corrección, la nueva.
    """
    doc, _ = _documento("csf.pdf")
    expediente = client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()
    ficha = client.get(f"/api/v1/documentos/{doc['id']}").json()
    assert ficha["rfc_titular"] == expediente["titular"]["rfc"]
    assert ficha["razon_social_titular"] == "Descargas de Prueba S.A. de C.V."

    r = client.patch(f"/api/v1/titulares/{expediente['titular_id']}", json={"razon_social": "Razón Corregida S.A. de C.V."})
    assert r.status_code == 200, r.text
    assert client.get(f"/api/v1/documentos/{doc['id']}").json()["razon_social_titular"] == "Razón Corregida S.A. de C.V."

