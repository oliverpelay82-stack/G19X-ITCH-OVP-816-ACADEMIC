"""
Titularidad contra el titular del expediente (hallazgo 6 de la auditoría del
14/10/2026; RN-03, HU-21). Sin red: el texto, Groq, el rules-service y el core
se simulan.

  1. Con un documento de la bóveda, el RFC y la razón social salen de la ficha
     del core (GET /documentos/{id}), no de la petición: un cliente que omite el
     RFC o envía otro ya no cambia el dictamen. Si envió otro, una observación
     lo dice.
  2. La ficha se vuelve a pedir al core: la razón social corregida después de
     leer el documento es la que cuenta.
  3. Sin esos campos en la ficha (un core anterior) se usan los de la petición.
"""
import pytest
from fastapi.testclient import TestClient

import main
from clients import core_client, groq_client, rules_client
from pipelines import repositorio_texto

client = TestClient(main.app)
DOC_ID = "doc-titular-001"
RFC = "PLU180514AB3"
RAZON = "PLURIONE S.A. DE C.V."
TEXTO = "CONSTANCIA DE SITUACION FISCAL ... RFC PLU180514AB3 ... " + "Datos de identificación. " * 30


@pytest.fixture
def entorno(monkeypatch):
    estado = {"ficha": {"rfc_titular": RFC, "razon_social_titular": RAZON}, "ficha_core": None,
              "extraido": {"rfc_detectado": RFC, "razon_social_detectada": RAZON}, "dictamenes": []}

    def obtener(documento_id, forzar_ocr=False, completar_en_fondo=True, texto_completo=False):
        return repositorio_texto.TextoDocumento(
            texto=TEXTO, traza={"confidence_score": 0.97, "total_paginas": 1}, completo=True, sha256="c" * 64,
            fuente="persistencia",
            metadatos={"id": documento_id, "tipo_documento": "CSF_SAT", "nombre_archivo_original": "csf.pdf",
                       "hash_sha256": "c" * 64, **estado["ficha"]},
        )

    def generar_json(prompt, system):
        return {"tipo_documento_detectado": "CSF_SAT", "fecha_emision": None, "fecha_vencimiento": None,
                "nivel_confianza": 0.95, "observaciones": "Texto legible.", **estado["extraido"]}

    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", obtener)
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [])
    monkeypatch.setattr(rules_client, "evaluar_vigencia", lambda *a, **k: {"resultado": "SIN_REGLAS", "evaluaciones": []})
    monkeypatch.setattr(core_client, "obtener_metadatos", lambda _id: estado["ficha_core"] or estado["ficha"])
    monkeypatch.setattr(core_client, "registrar_dictamen",
                        lambda carga: estado["dictamenes"].append(carga) or {"id": "d-1", "estatus": carga["estatus"]})
    return estado


def _auditar(**peticion):
    r = client.post("/api/v1/ai/analisis-semantico", json={"documento_id": DOC_ID, **peticion})
    assert r.status_code == 200, r.text
    return r.json()


def test_sin_rfc_en_la_peticion_coteja_con_el_del_expediente(entorno):
    cuerpo = _auditar()
    assert cuerpo["match_titular"] is True
    assert not any("No se proporcionó el RFC" in o for o in cuerpo["observaciones"])


def test_un_rfc_ajeno_en_la_peticion_no_cambia_el_dictamen(entorno):
    cuerpo = _auditar(rfc_titular="OTR010101AAA", razon_social_titular="Otra S.A. de C.V.")
    assert cuerpo["match_titular"] is True and cuerpo["estatus_preliminar"] != "NO_CONFORME"
    assert any("no es el del expediente" in o for o in cuerpo["observaciones"])


def test_cuenta_la_razon_social_corregida(entorno):
    # El documento no trae RFC: la titularidad se decide por la razón social, que
    # se corrigió en el core después de leerlo.
    entorno["extraido"] = {"rfc_detectado": None, "razon_social_detectada": "PLURIONE MEXICO S.A. DE C.V."}
    entorno["ficha_core"] = {"rfc_titular": RFC, "razon_social_titular": "PLURIONE MEXICO S.A. DE C.V."}
    assert _auditar()["match_titular"] is True


def test_un_core_sin_los_campos_usa_los_de_la_peticion(entorno):
    entorno["ficha"] = {}
    assert _auditar(rfc_titular=RFC)["match_titular"] is True
    assert _auditar()["match_titular"] is False
