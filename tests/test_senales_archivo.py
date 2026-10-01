"""
P6 — Señales del archivo PDF (PRD §21.6: PLUS-16, HU-50; PLUS-18, HU-52).

  1. Una constancia fiscal sin tocar no genera señales; guardada de nuevo
     (guardado incremental o modificación posterior) queda con la alerta
     «Posible edición del archivo» y con el motivo de revisión en el documento.
  2. Un acta con las mismas señales solo las informa: procesar un escaneo es
     lo normal.
  3. Un PDF con JavaScript se custodia, la carga advierte, el evento de ingesta
     sellado lo registra y aparece la alerta alta; sigue aunque se ratifique.
  4. La ratificación resuelve la alerta de posible edición.
  5. El barrido programado calcula las señales de lo custodiado antes de P6.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from pypdf import PdfWriter  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.documento import Documento  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import integridad  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
client = TestClient(app)


def _pdf(semilla: str, *, incremental=False, modificado=None, javascript=False, productor="Generador del SAT") -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(612, 792)
    meta = {"/Producer": productor, "/Title": semilla, "/CreationDate": "D:20260901100000-06'00'"}
    if modificado:
        meta["/ModDate"] = modificado
    escritor.add_metadata(meta)
    if javascript:
        escritor.add_js("app.alert('P6');")
    salida = io.BytesIO()
    escritor.write(salida)
    datos = salida.getvalue()
    if incremental:
        retoque = PdfWriter(io.BytesIO(datos), incremental=True)
        retoque.add_metadata({"/Subject": "retocado"})
        salida = io.BytesIO()
        retoque.write(salida)
        datos = salida.getvalue()
    return datos


def _expediente(rfc: str) -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Señales {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    return client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]


def _subir(exp_id: str, contenido: bytes, tipo: str = "CSF_SAT") -> dict:
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": tipo},
                    files={"file": ("archivo.pdf", contenido, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _alertas(doc: dict, codigo: str) -> list[dict]:
    evaluacion = client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()["evaluacion"]
    return [a for a in evaluacion["alertas"] if a["codigo"] == codigo and a["documento_id"] == doc["id"]]


def test_constancia_sin_tocar_no_genera_senales():
    doc = _subir(_expediente("SEN010101AAA"), _pdf("limpia"))
    assert doc["senales_pdf"]["edicion"] == [] and doc["senales_pdf"]["contenido_activo"] == []
    assert doc["senales_revision"] == [] and doc["advertencia_nivel_1"] is None
    assert not _alertas(doc, "POSIBLE_EDICION")


def test_constancia_retocada_queda_con_posible_edicion():
    doc = _subir(_expediente("SEN020202AAA"), _pdf("retocada", incremental=True))

    assert [e["codigo"] for e in doc["senales_pdf"]["edicion"]] == ["GUARDADO_INCREMENTAL"]
    assert doc["senales_revision"][0].startswith("Posible edición del archivo")
    [alerta] = _alertas(doc, "POSIBLE_EDICION")
    assert alerta["severidad"] == "MEDIA_ALTA" and "guardado posterior" in alerta["detalle"]
    consultado = client.get(f"/api/v1/documentos/{doc['id']}").json()
    assert consultado["senales_revision"] == doc["senales_revision"], "El ai-service lo recibe al consultar"


def test_modificacion_posterior_a_la_emision():
    doc = _subir(_expediente("SEN030303AAA"), _pdf("modificada", modificado="D:20260915120000-06'00'"))
    assert [e["codigo"] for e in doc["senales_pdf"]["edicion"]] == ["MODIFICADO_DESPUES_DE_EMISION"]
    assert _alertas(doc, "POSIBLE_EDICION")


def test_un_acta_con_senales_solo_las_informa():
    doc = _subir(_expediente("SEN040404AAA"), _pdf("acta", incremental=True, productor="iLovePDF"),
                 tipo="ACTA_CONSTITUTIVA")
    assert len(doc["senales_pdf"]["edicion"]) == 2, "Se guardan para el registro"
    assert doc["senales_revision"] == [] and not _alertas(doc, "POSIBLE_EDICION")


def test_pdf_con_javascript_se_custodia_y_se_advierte():
    doc = _subir(_expediente("SEN050505AAA"), _pdf("activo", javascript=True), tipo="ACTA_CONSTITUTIVA")

    assert doc["senales_pdf"]["contenido_activo"] == ["JAVASCRIPT"]
    assert "JavaScript" in doc["advertencia_nivel_1"] and "custodiado" in doc["advertencia_nivel_1"]
    assert any("JavaScript" in m for m in doc["senales_revision"])
    [alerta] = _alertas(doc, "CONTENIDO_ACTIVO")
    assert alerta["severidad"] == "ALTA"
    [ingesta] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "INGESTA_DOCUMENTO"}).json()
    assert ingesta["detalle"]["contenido_activo"] == ["JAVASCRIPT"] and ingesta["hash_evento"]


def test_la_ratificacion_resuelve_la_posible_edicion_pero_no_el_contenido_activo():
    exp_id = _expediente("SEN060606AAA")
    retocada = _subir(exp_id, _pdf("ratificada", incremental=True))
    activo = _subir(exp_id, _pdf("activo-ratificado", javascript=True), tipo="ACTA_CONSTITUTIVA")
    for doc in (retocada, activo):
        dictamen = client.post("/api/v1/dictamenes", json={"documento_id": doc["id"], "estatus": "EN_REVISION",
                                                           "nivel_confianza": 0.8, "observaciones": ["P6."]}).json()
        r = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
            "nuevo_estatus": "CONFORME", "justificacion": "Validado en el portal del SAT.", "usuario": "p6"})
        assert r.status_code == 200, r.text

    assert not _alertas(retocada, "POSIBLE_EDICION")
    assert _alertas(activo, "CONTENIDO_ACTIVO"), "El archivo sigue teniendo JavaScript"


def test_el_barrido_calcula_las_senales_de_lo_custodiado_antes():
    doc = _subir(_expediente("SEN070707AAA"), _pdf("anterior", incremental=True))
    db = SessionLocal()
    try:
        db.get(Documento, doc["id"]).senales_pdf = None   # como un documento custodiado antes de P6
        db.commit()
        integridad.barrer(db)
    finally:
        db.close()

    consultado = client.get(f"/api/v1/documentos/{doc['id']}").json()
    assert [e["codigo"] for e in consultado["senales_pdf"]["edicion"]] == ["GUARDADO_INCREMENTAL"]
    constancias = client.get("/api/v1/bitacora", params={"evento": "VERIFICACION_INTEGRIDAD"}).json()
    constancia = max(constancias, key=lambda e: e["secuencia"])
    assert constancia["detalle"].get("senales_calculadas", 0) >= 1


def test_el_dictamen_guarda_el_qr_y_el_trigger_lo_protege():
    import pytest
    from sqlalchemy import text
    from sqlalchemy.exc import DBAPIError

    doc = _subir(_expediente("SEN080808AAA"), _pdf("qr"))
    qr = {"encontrado": True, "dominio_sat": True, "rfc_qr": "SEN080808AAA", "coincide_rfc": True,
          "url": "https://siat.sat.gob.mx/app/qr/faces/pages/mobile/validadorqr.jsf?D3=1_SEN080808AAA"}
    dictamen = client.post("/api/v1/dictamenes", json={"documento_id": doc["id"], "estatus": "EN_REVISION",
                                                       "nivel_confianza": 0.8, "observaciones": ["P6."],
                                                       "qr_sat": qr}).json()
    guardado = client.get("/api/v1/dictamenes", params={"documento_id": doc["id"]}).json()[0]
    assert guardado["qr_sat"]["url"] == qr["url"]
    [evento] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "DICTAMEN_IA"}).json()
    assert evento["detalle"]["qr_sat"]["coincide_rfc"] is True and "url" not in evento["detalle"]["qr_sat"]
    with pytest.raises(DBAPIError), engine.begin() as conexion:
        conexion.execute(text("UPDATE dictamenes_auditoria SET qr_sat = NULL WHERE id = :id"), {"id": dictamen["id"]})


# ── M5: el mismo archivo en el expediente de otro titular ─────────────


def test_el_mismo_archivo_en_otro_titular_genera_alerta():
    contenido = _pdf("compartido")
    primero = _subir(_expediente("SEN090909AAA"), contenido)
    segundo = _subir(_expediente("SEN101010AAA"), contenido)

    [alerta] = _alertas(segundo, "ARCHIVO_DE_OTRO_TITULAR")
    folio = client.get(f"/api/v1/expedientes/{primero['expediente_id']}").json()["codigo_expediente"]
    assert alerta["severidad"] == "MEDIA_ALTA" and folio in alerta["detalle"]
    assert _alertas(primero, "ARCHIVO_DE_OTRO_TITULAR"), "Las dos partes lo ven"


def test_un_contrato_compartido_es_de_severidad_media():
    contenido = _pdf("contrato")
    _subir(_expediente("SEN111111AAA"), contenido, tipo="CONTRATO_SERVICIOS")
    doc = _subir(_expediente("SEN121212AAA"), contenido, tipo="CONTRATO_SERVICIOS")
    [alerta] = _alertas(doc, "ARCHIVO_DE_OTRO_TITULAR")
    assert alerta["severidad"] == "MEDIA" and "dos partes" in alerta["detalle"]


def test_el_mismo_titular_en_dos_expedientes_no_genera_alerta():
    exp_corporativo = _expediente("SEN131313AAA")
    titular_id = client.get(f"/api/v1/expedientes/{exp_corporativo}").json()["titular_id"]
    exp_juridico = client.post("/api/v1/expedientes", json={"titular_id": titular_id,
                                                           "tipo_expediente": "JURIDICO"}).json()["id"]
    contenido = _pdf("mismo-titular")
    _subir(exp_corporativo, contenido, tipo="ACTA_CONSTITUTIVA")
    doc = _subir(exp_juridico, contenido, tipo="ACTA_CONSTITUTIVA")
    assert not _alertas(doc, "ARCHIVO_DE_OTRO_TITULAR")

