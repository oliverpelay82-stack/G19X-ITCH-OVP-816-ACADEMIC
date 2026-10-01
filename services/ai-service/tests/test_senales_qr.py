"""
P6 — QR del SAT (PLUS-17, HU-51) y tope de revisión por señales del archivo
(PLUS-16, PLUS-18). Sin red: Groq, el rules-service y el core se simulan; los
QR se generan con OpenCV dentro de un PDF de prueba.

  1. Un QR del SAT con el RFC del titular no cambia el estatus y deja el enlace
     oficial en las recomendaciones y en el dictamen.
  2. Un QR con otro RFC o ajeno al SAT deja la auditoría En revisión.
  3. Sin QR, el estatus no cambia; un acta no se revisa en busca de QR.
  4. Las señales del archivo que calculó el core (senales_revision) dejan la
     auditoría En revisión; un No conforme no cambia.
  5. Ninguna prueba llama al SAT: solo se lee el binario.
"""
import cv2
import fitz
import pytest
from fastapi.testclient import TestClient

import main
from clients import core_client, groq_client, rules_client
from controllers import analisis_controller
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import qr_sat, repositorio_texto

client = TestClient(main.app)
RFC = "BIM011108DJ5"
URL_SAT = "https://siat.sat.gob.mx/app/qr/faces/pages/mobile/validadorqr.jsf?D1=10&D2=1&D3=12345678901_{rfc}"
TEXTO = ("CONSTANCIA DE SITUACION FISCAL. RFC: BIM011108DJ5. Denominación: GRUPO BIMBO S.A.B. DE C.V. "
         "Lugar y fecha de emisión: CIUDAD DE MEXICO A 01 DE SEPTIEMBRE DE 2026. ") * 6


def pdf_con_qr(contenido: str | None) -> bytes:
    documento = fitz.open()
    pagina = documento.new_page()
    pagina.insert_text((72, 72), "CONSTANCIA DE SITUACION FISCAL")
    if contenido:
        imagen = cv2.QRCodeEncoder.create().encode(contenido)
        imagen = cv2.resize(imagen, None, fx=6, fy=6, interpolation=cv2.INTER_NEAREST)
        imagen = cv2.copyMakeBorder(imagen, 40, 40, 40, 40, cv2.BORDER_CONSTANT, value=255)
        pagina.insert_image(fitz.Rect(72, 100, 232, 260), stream=cv2.imencode(".png", imagen)[1].tobytes())
    return documento.tobytes()


@pytest.fixture
def entorno(monkeypatch):
    estado = {"binario": pdf_con_qr(None), "tipo": "CSF_SAT", "senales": [], "lecturas_binario": 0,
              "dictamenes": []}

    def obtener(documento_id, forzar_ocr=False, completar_en_fondo=True, texto_completo=False):
        return repositorio_texto.TextoDocumento(
            texto=TEXTO, traza={"confidence_score": 0.97, "total_paginas": 1}, completo=True, sha256="c" * 64,
            fuente="persistencia",
            metadatos={"id": documento_id, "tipo_documento": estado["tipo"], "mime_type": "application/pdf",
                       "nombre_archivo_original": "csf.pdf", "hash_sha256": "c" * 64,
                       "senales_revision": estado["senales"]},
        )

    def leer_binario(metadatos):
        estado["lecturas_binario"] += 1
        return estado["binario"]

    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", obtener)
    monkeypatch.setattr(core_client, "leer_binario", leer_binario)
    monkeypatch.setattr(groq_client, "generar_json", lambda prompt, system: {
        "tipo_documento_detectado": "CONSTANCIA_SITUACION_FISCAL", "rfc_detectado": RFC,
        "razon_social_detectada": "GRUPO BIMBO S.A.B. DE C.V.", "fecha_emision": "2026-09-01",
        "fecha_vencimiento": None, "nivel_confianza": 0.97, "observaciones": "Constancia legible."})
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [])
    monkeypatch.setattr(rules_client, "evaluar_vigencia",
                        lambda *a, **k: {"resultado": "VIGENTE", "evaluaciones": [], "dias_para_vencimiento": 60})
    monkeypatch.setattr(core_client, "registrar_dictamen",
                        lambda carga: estado["dictamenes"].append(carga) or {"id": "d-1", "estatus": carga["estatus"]})
    return estado


def _auditar():
    r = client.post("/api/v1/ai/analisis-semantico", json={
        "documento_id": "doc-qr", "rfc_titular": RFC, "razon_social_titular": "GRUPO BIMBO S.A.B. DE C.V."})
    assert r.status_code == 200, r.text
    return r.json()


def _revision_por(cuerpo: dict, fragmento: str) -> bool:
    return any(o.startswith("Dictamen EN_REVISION:") and fragmento in o for o in cuerpo["observaciones"])


def test_qr_del_sat_con_el_rfc_del_titular(entorno):
    entorno["binario"] = pdf_con_qr(URL_SAT.format(rfc=RFC))
    cuerpo = _auditar()

    qr = cuerpo["qr_sat"]
    assert qr["encontrado"] and qr["dominio_sat"] and qr["rfc_qr"] == RFC and qr["coincide_rfc"] is True
    assert not _revision_por(cuerpo, "código QR")
    assert any("portal del SAT" in r and qr["url"] in r for r in cuerpo["recomendaciones"])
    assert entorno["dictamenes"][0]["qr_sat"]["coincide_rfc"] is True, "El dictamen guarda la lectura del QR"


def test_qr_con_otro_rfc_queda_en_revision(entorno):
    entorno["binario"] = pdf_con_qr(URL_SAT.format(rfc="SAT970701NN3"))
    cuerpo = _auditar()
    assert cuerpo["estatus_preliminar"] == "EN_REVISION" and cuerpo["requiere_revision_humana"]
    assert _revision_por(cuerpo, "SAT970701NN3")


def test_qr_ajeno_al_sat_queda_en_revision(entorno):
    entorno["binario"] = pdf_con_qr(f"https://sat-validacion.example.com/qr?rfc={RFC}")
    cuerpo = _auditar()
    assert cuerpo["qr_sat"]["dominio_sat"] is False and cuerpo["qr_sat"]["url"] is None
    assert cuerpo["estatus_preliminar"] == "EN_REVISION" and _revision_por(cuerpo, "no lleva al portal del SAT")


def test_sin_qr_el_estatus_no_cambia(entorno):
    sin_qr = _auditar()
    entorno["binario"] = pdf_con_qr(URL_SAT.format(rfc=RFC))
    con_qr = _auditar()
    assert sin_qr["qr_sat"]["encontrado"] is False
    assert sin_qr["estatus_preliminar"] == con_qr["estatus_preliminar"], "Un QR ausente solo se informa"


def test_un_acta_no_se_revisa_en_busca_de_qr(entorno):
    entorno["tipo"] = "ACTA_CONSTITUTIVA"
    cuerpo = _auditar()
    assert cuerpo["qr_sat"] is None and entorno["lecturas_binario"] == 0


def test_las_senales_del_archivo_dejan_la_auditoria_en_revision(entorno):
    entorno["senales"] = ["Posible edición del archivo: el SAT emite este documento electrónicamente y el PDF "
                          "tiene 1 guardado posterior a su generación."]
    cuerpo = _auditar()
    assert cuerpo["estatus_preliminar"] == "EN_REVISION" and _revision_por(cuerpo, "posible edición del archivo")


def test_el_tope_no_cambia_un_no_conforme():
    resultado = pipeline_analisis.ResultadoAnalisis(
        tipo_documento_detectado="CSF_SAT", rfc_detectado=RFC, rfc_valido=True, match_titular=False,
        razon_social_detectada=None, fecha_emision=None, fecha_vencimiento=None, vigente=False,
        dias_para_vencimiento=None, nivel_confianza=0.9, estatus_preliminar="NO_CONFORME",
        requiere_revision_humana=False, observaciones=["Dictamen NO_CONFORME: RFC ajeno."], modelo_utilizado="x")
    analisis_controller._tope_revision(resultado, ["El PDF contiene JavaScript."], None)
    assert resultado.estatus_preliminar == "NO_CONFORME" and "El PDF contiene JavaScript." in resultado.observaciones


def test_motivos_del_qr():
    assert qr_sat.motivos(None) == [] and qr_sat.motivos({"encontrado": False}) == []
    assert qr_sat.motivos({"encontrado": True, "dominio_sat": True, "coincide_rfc": None}) == []


def test_el_dictamen_lleva_la_version_del_catalogo(entorno, monkeypatch):
    """M6 (HU-54): la versión del catálogo viaja con las de P5 y se guarda en el dictamen."""
    monkeypatch.setattr(rules_client, "version_catalogo", lambda: "cat-0123456789ab")
    cuerpo = _auditar()
    assert cuerpo["versiones"]["version_catalogo"] == "cat-0123456789ab"
    assert entorno["dictamenes"][-1]["version_catalogo"] == "cat-0123456789ab"


def test_sin_rules_service_la_version_queda_vacia_y_se_recuerda_la_falla(monkeypatch):
    import requests

    llamadas = []

    def caido(*a, **k):
        llamadas.append(1)
        raise requests.ConnectionError("rules-service caído")

    monkeypatch.setattr(rules_client, "_version_en_memoria", (float("-inf"), None))
    monkeypatch.setattr(rules_client._sesion, "get", caido)
    assert rules_client.version_catalogo() is None and rules_client.version_catalogo() is None
    assert len(llamadas) == 1, "La segunda auditoría no espera otra conexión rechazada"
