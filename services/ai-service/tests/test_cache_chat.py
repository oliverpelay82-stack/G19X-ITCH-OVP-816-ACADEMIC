"""
Pruebas del caché de respuestas del chat documental — T3, PLUS-10 (PRD §21.4).
Sin red: Groq, el core y el rules-service se simulan; la SQLite es temporal.

  1. La misma pregunta sobre el mismo documento no vuelve a llamar al modelo:
     la respuesta sale del caché con origen CACHE, cero tokens y sus citas
     marcadas como en la primera.
  2. Una variante sin acentos, mayúsculas ni signos comparte respuesta (clave
     por pregunta normalizada); una negación no.
  3. Con historial solo aplica la clave exacta.
  4. Un cambio del estado del sistema (una ratificación) invalida la respuesta.
  5. forzar_modelo omite el caché; con GROQ_CACHE_INFERENCIAS apagado no se
     guarda nada.

Uso:  cd services/ai-service && python -m pytest tests/test_cache_chat.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from config import settings  # noqa: E402
from pipelines import cache_chat, repositorio_texto  # noqa: E402

TEXTO = ("CONSTANCIA DE SITUACION FISCAL\nRFC: PLU180514AB3\nDenominación o Razón Social: PLURIONE S.A. DE C.V.\n"
         "Lugar y fecha de emisión: CHIHUAHUA, a 10 de septiembre de 2026")
DOC_ID = "doc-cache-chat"


@pytest.fixture
def entorno(tmp_path, monkeypatch):
    llamadas = []
    dictamen = {"estatus": "CONFORME", "estatus_preliminar": "CONFORME", "nivel_confianza": 0.95,
                "revisado_por_humano": False, "reglas_aplicadas": [], "observaciones": [],
                "fecha_emision_extraida": "2026-09-10"}
    monkeypatch.setattr(settings, "EXTRACCIONES_DB_PATH", str(tmp_path / "e.sqlite3"))
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", True)
    monkeypatch.setattr(settings, "GROQ_TEMPERATURE", 0.0)
    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", lambda *a, **k: repositorio_texto.TextoDocumento(
        texto=TEXTO, metadatos={"id": DOC_ID, "tipo_documento": "CSF_SAT", "nombre_archivo_original": "csf.pdf"},
        traza={}, completo=True, sha256="b" * 64, fuente="memoria"))
    monkeypatch.setattr(core_client, "ultimo_dictamen", lambda documento_id: dict(dictamen))
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [])

    def conversar(mensajes, temperatura=None):
        llamadas.append(mensajes[-1]["content"])
        r = groq_client.RespuestaTexto("El RFC es **PLU180514AB3**: «RFC: PLU180514AB3».")
        r.uso = {"prompt_tokens": 900, "completion_tokens": 30, "total_tokens": 930}
        return r

    monkeypatch.setattr(groq_client, "conversar", conversar)
    return TestClient(main.app), llamadas, dictamen


def _preguntar(cliente, pregunta, **extra):
    r = cliente.post("/api/v1/ai/chat-documento", json={"documento_id": DOC_ID, "pregunta": pregunta, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_la_misma_pregunta_sale_del_cache(entorno):
    cliente, llamadas, _ = entorno
    primera = _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    segunda = _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    assert len(llamadas) == 1
    assert primera["origen_respuesta"] == "MODELO" and segunda["origen_respuesta"] == "CACHE"
    assert segunda["respuesta"] == primera["respuesta"]
    assert segunda["contexto_llm"]["uso_tokens"]["total_tokens"] == 0
    assert segunda["contexto_llm"]["uso_tokens"]["desde_cache"] is True
    assert segunda["citas"] == primera["citas"] and segunda["citas"][0]["verificada"] is True


def test_variante_normalizada_si_y_negacion_no(entorno):
    cliente, llamadas, _ = entorno
    _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    assert _preguntar(cliente, "cual es el rfc del contribuyente")["origen_respuesta"] == "CACHE"
    assert len(llamadas) == 1
    assert _preguntar(cliente, "¿Cuál no es el RFC del contribuyente?")["origen_respuesta"] == "MODELO"
    assert len(llamadas) == 2


def test_con_historial_solo_la_clave_exacta(entorno):
    cliente, llamadas, _ = entorno
    _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    historial = [{"rol": "usuario", "contenido": "¿De qué trata?"}, {"rol": "asistente", "contenido": "Una CSF."}]
    assert _preguntar(cliente, "¿Cuál es el RFC del contribuyente?", historial=historial)["origen_respuesta"] == "MODELO"
    assert _preguntar(cliente, "¿Cuál es el RFC del contribuyente?", historial=historial)["origen_respuesta"] == "CACHE"
    assert len(llamadas) == 2


def test_una_ratificacion_invalida_la_respuesta(entorno):
    cliente, llamadas, dictamen = entorno
    _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    dictamen.update(revisado_por_humano=True, revisado_por="ana.lopez")
    assert _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")["origen_respuesta"] == "MODELO"
    assert len(llamadas) == 2


def test_forzar_modelo_y_cache_apagado(entorno, monkeypatch):
    cliente, llamadas, _ = entorno
    _preguntar(cliente, "¿Cuál es el RFC del contribuyente?")
    assert _preguntar(cliente, "¿Cuál es el RFC del contribuyente?", forzar_modelo=True)["origen_respuesta"] == "MODELO"
    assert len(llamadas) == 2
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
    assert not cache_chat.activo()
    _preguntar(cliente, "¿Quién emite la constancia?")
    _preguntar(cliente, "¿Quién emite la constancia?")
    assert len(llamadas) == 4


def test_terminos_de_la_clave():
    assert cache_chat.terminos_pregunta("¿Cuándo VENCE este documento?") == cache_chat.terminos_pregunta(
        "cuando vence este documento")
    assert "no" in cache_chat.terminos_pregunta("¿Quién no firma?")
    assert cache_chat.clave_pregunta(None, "estado", "¿Quién firma?") is None
