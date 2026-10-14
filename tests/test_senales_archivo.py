"""
P6 — Contenido activo del PDF (PRD §21.6: PLUS-18, HU-52).

  1. Un PDF sin contenido activo no genera señales.
  2. Una constancia fiscal hecha con un procesador de texto y guardada de
     nuevo no va a revisión: las señales de edición (PLUS-16) se retiraron el
     02/10/2026 porque dejaban en revisión los documentos de prueba.
  3. Un PDF con JavaScript se custodia, la carga advierte, el evento de ingesta
     sellado lo registra y aparece la alerta alta; sigue aunque se ratifique.
  4. El barrido programado calcula las señales de lo custodiado antes de P6.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from pypdf import PdfWriter  # noqa: E402
from pypdf.generic import ArrayObject, DictionaryObject, NameObject, TextStringObject  # noqa: E402
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
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)


def _pdf(semilla: str, *, incremental=False, modificado=None, javascript=False, productor="Generador del SAT") -> bytes:
    escritor = PdfWriter()
    escritor.add_blank_page(612, 792)
    meta = {"/Producer": productor, "/Title": semilla, "/CreationDate": "D:20260901100000-06'00'"}
    if modificado:
        meta["/ModDate"] = modificado
    escritor.add_metadata(meta)
    if javascript:
        # Lo mismo que hacía PdfWriter.add_js (obsoleta en pypdf 7): JavaScript de documento en /Names.
        accion = DictionaryObject({NameObject("/Type"): NameObject("/Action"), NameObject("/S"): NameObject("/JavaScript"),
                                   NameObject("/JS"): TextStringObject("app.alert('P6');")})
        escritor._root_object[NameObject("/Names")] = DictionaryObject({NameObject("/JavaScript"): DictionaryObject(
            {NameObject("/Names"): ArrayObject([TextStringObject("p6"), accion])})})
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


def test_un_pdf_sin_contenido_activo_no_genera_senales():
    doc = _subir(_expediente("SEN010101AAA"), _pdf("limpia"))
    assert doc["senales_pdf"]["contenido_activo"] == [] and "edicion" not in doc["senales_pdf"]
    assert doc["senales_revision"] == [] and doc["advertencia_nivel_1"] is None


def test_una_constancia_hecha_en_un_procesador_de_texto_no_va_a_revision():
    """Regresión: con PLUS-16, una constancia de prueba hecha en Word y guardada de nuevo quedaba «Posible edición»."""
    doc = _subir(_expediente("SEN020202AAA"), _pdf("de-prueba", incremental=True, productor="Microsoft® Word 2019",
                                                  modificado="D:20260915120000-06'00'"))
    assert doc["senales_revision"] == []
    evaluacion = client.get(f"/api/v1/expedientes/{doc['expediente_id']}").json()["evaluacion"]
    assert not [a for a in evaluacion["alertas"] if a["documento_id"] == doc["id"] and a["codigo"] == "POSIBLE_EDICION"]


def test_pdf_con_javascript_se_custodia_y_se_advierte():
    doc = _subir(_expediente("SEN050505AAA"), _pdf("activo", javascript=True), tipo="ACTA_CONSTITUTIVA")

    assert doc["senales_pdf"]["contenido_activo"] == ["JAVASCRIPT"]
    assert "JavaScript" in doc["advertencia_nivel_1"] and "custodiado" in doc["advertencia_nivel_1"]
    assert any("JavaScript" in m for m in doc["senales_revision"])
    [alerta] = _alertas(doc, "CONTENIDO_ACTIVO")
    assert alerta["severidad"] == "ALTA"
    [ingesta] = client.get("/api/v1/bitacora", params={"documento_id": doc["id"], "evento": "INGESTA_DOCUMENTO"}).json()
    assert ingesta["detalle"]["contenido_activo"] == ["JAVASCRIPT"] and ingesta["hash_evento"]


def test_el_contenido_activo_sigue_aunque_se_ratifique():
    activo = _subir(_expediente("SEN060606AAA"), _pdf("activo-ratificado", javascript=True), tipo="ACTA_CONSTITUTIVA")
    dictamen = client.post("/api/v1/dictamenes", headers=auth.sistema(), json={"documento_id": activo["id"], "estatus": "EN_REVISION",
                                                       "nivel_confianza": 0.8, "observaciones": ["P6."]}).json()
    r = client.post(f"/api/v1/dictamenes/{dictamen['id']}/ratificar", json={
        "nuevo_estatus": "CONFORME", "justificacion": "Revisado contra el original.", "usuario": "p6"})
    assert r.status_code == 200, r.text
    assert _alertas(activo, "CONTENIDO_ACTIVO"), "El archivo sigue teniendo JavaScript"


def test_el_barrido_calcula_las_senales_de_lo_custodiado_antes():
    doc = _subir(_expediente("SEN070707AAA"), _pdf("anterior", javascript=True), tipo="ACTA_CONSTITUTIVA")
    db = SessionLocal()
    try:
        db.get(Documento, doc["id"]).senales_pdf = None   # como un documento custodiado antes de P6
        db.commit()
        integridad.barrer(db)
    finally:
        db.close()

    consultado = client.get(f"/api/v1/documentos/{doc['id']}").json()
    assert consultado["senales_pdf"]["contenido_activo"] == ["JAVASCRIPT"]
    constancias = client.get("/api/v1/bitacora", params={"evento": "VERIFICACION_INTEGRIDAD"}).json()
    constancia = max(constancias, key=lambda e: e["secuencia"])
    assert constancia["detalle"].get("senales_calculadas", 0) >= 1


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

