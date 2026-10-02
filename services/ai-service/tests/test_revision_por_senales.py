"""
P6 — Tope de revisión por el contenido activo del PDF (PLUS-18) y versiones
del dictamen (M6, M7). Sin red: Groq, el rules-service y el core se simulan.

  1. Los motivos que calculó el core (senales_revision) dejan la auditoría En
     revisión; un No conforme no cambia.
  2. La auditoría ya no lee el binario en busca del QR del SAT (PLUS-17 se
     retiró el 02/10/2026) ni devuelve «qr_sat».
  3. El dictamen lleva la versión del catálogo y la de las reglas de su tipo.
"""
import pytest
from fastapi.testclient import TestClient

import main
from clients import core_client, groq_client, rules_client
from controllers import analisis_controller
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import repositorio_texto

client = TestClient(main.app)
RFC = "BIM011108DJ5"
TEXTO = ("CONSTANCIA DE SITUACION FISCAL. RFC: BIM011108DJ5. Denominación: GRUPO BIMBO S.A.B. DE C.V. "
         "Lugar y fecha de emisión: CIUDAD DE MEXICO A 01 DE SEPTIEMBRE DE 2026. ") * 6


@pytest.fixture
def entorno(monkeypatch):
    estado = {"tipo": "CSF_SAT", "senales": [], "lecturas_binario": 0, "dictamenes": []}

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
        return b"%PDF-1.4"

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


def test_la_auditoria_no_busca_el_qr_del_sat(entorno):
    cuerpo = _auditar()
    assert "qr_sat" not in cuerpo and "qr_sat" not in entorno["dictamenes"][0]
    assert entorno["lecturas_binario"] == 0, "Ya no se lee el binario para buscar el QR"


def test_las_senales_del_archivo_dejan_la_auditoria_en_revision(entorno):
    entorno["senales"] = ["El PDF contiene JavaScript: se recomienda pedir una versión sin contenido activo."]
    cuerpo = _auditar()
    assert cuerpo["estatus_preliminar"] == "EN_REVISION" and _revision_por(cuerpo, "JavaScript")


def test_el_tope_no_cambia_un_no_conforme():
    resultado = pipeline_analisis.ResultadoAnalisis(
        tipo_documento_detectado="CSF_SAT", rfc_detectado=RFC, rfc_valido=True, match_titular=False,
        razon_social_detectada=None, fecha_emision=None, fecha_vencimiento=None, vigente=False,
        dias_para_vencimiento=None, nivel_confianza=0.9, estatus_preliminar="NO_CONFORME",
        requiere_revision_humana=False, observaciones=["Dictamen NO_CONFORME: RFC ajeno."], modelo_utilizado="x")
    analisis_controller._tope_revision(resultado, ["El PDF contiene JavaScript."])
    assert resultado.estatus_preliminar == "NO_CONFORME" and "El PDF contiene JavaScript." in resultado.observaciones


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


def test_el_dictamen_lleva_la_version_de_las_reglas_del_tipo(entorno, monkeypatch):
    """M7 (HU-59): la versión de las reglas del tipo registrado viaja con el dictamen."""
    pedidas = []
    monkeypatch.setattr(rules_client, "version_reglas_tipo", lambda tipo: pedidas.append(tipo) or "tip-0123456789ab")
    _auditar()
    assert pedidas == ["CSF_SAT"] and entorno["dictamenes"][-1]["version_reglas_tipo"] == "tip-0123456789ab"
