"""
Pruebas de T1, PLUS-08 (PRD §21.4): pasaje literal del documento, sin modelo,
para cláusulas nombradas y montos. Offline, con textos vectoriales del Gold
Standard.

  1. Montos y cláusulas con un pasaje claro: el renglón literal que responde,
     anclable como cita.
  2. Al modelo: preguntas interpretativas, seguimientos de un solo término,
     montos con varias respuestas (tres sumas aseguradas) y cláusulas cuyo
     tema no aparece en el texto.
  3. Por el endpoint: origen PASAJE_DEL_DOCUMENTO sin tokens, con citas
     verificadas; forzar_modelo lo omite.

Uso:  cd services/ai-service && python -m pytest tests/test_pasajes.py
"""
import os
import sys

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from config import settings  # noqa: E402
from pipelines import pasajes, repositorio_texto  # noqa: E402
from pipelines.verificacion_contenido import cita_literal  # noqa: E402

_DOCUMENTOS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "evaluacion", "gold_standard", "documentos")


def _texto(archivo: str) -> str:
    with fitz.open(os.path.join(_DOCUMENTOS, archivo)) as documento:
        return "\n".join(p.get_text() for p in documento)


def _citas(respuesta: str) -> list[str]:
    return [c.split("»")[0] for c in respuesta.split("«")[1:]]


@pytest.mark.parametrize("archivo,pregunta,dato", [
    ("gs-cont-ext.pdf", "¿Cuál es el monto mensual total de los servicios?", "$185,000.00"),
    ("gs-cont-01.pdf", "¿Cuál es el monto de la contraprestación?", "$185,000.00"),
    ("gs-acta-01.pdf", "¿Cuál es el capital social?", "$50,000.00"),
    ("gs-pol-01.pdf", "¿Cuál es la prima total?", "$48,930.00"),
    ("gs-pol-01.pdf", "¿Cuál es la suma asegurada de robo con violencia?", "$750,000.00"),
    ("gs-cont-ext.pdf", "¿Cuánto se paga por la mesa de ayuda?", "$38,500.00"),
    ("gs-cont-01.pdf", "¿Qué dice la cláusula de confidencialidad?", "no divulgar"),
    ("gs-cont-ext.pdf", "¿Qué dice la cláusula de subcontratación?", "no podrá subcontratar"),
])
def test_pasaje_literal(archivo, pregunta, dato):
    texto = _texto(archivo)
    respuesta, _ = pasajes.responder(pregunta, texto)
    citas = _citas(respuesta)
    assert citas and all(cita_literal(c, texto) for c in citas)
    assert any(dato in c for c in citas)
    assert respuesta.startswith("Pasaje del documento") and "sin interpretación" in respuesta


@pytest.mark.parametrize("archivo,pregunta", [
    ("gs-pol-01.pdf", "¿Cuál es la suma asegurada?"),                         # tres coberturas: varias respuestas
    ("gs-cont-01.pdf", "¿Puede el cliente terminar el contrato?"),            # interpretativa
    ("gs-cont-ext.pdf", "¿y cuánto se paga?"),                               # seguimiento de un solo término
    ("gs-cont-ext.pdf", "¿Cuál es el tiempo de respuesta de la mesa de ayuda?"),  # ni cláusula ni monto
    ("gs-cont-ext.pdf", "¿Qué establece el anexo D?"),                        # sin términos propios
])
def test_al_modelo(archivo, pregunta):
    assert pasajes.responder(pregunta, _texto(archivo)) is None


def test_pagina_del_pasaje():
    texto = _texto("gs-cont-ext.pdf")
    inicio = texto.find("Monto mensual total")
    paginas = [{"pagina": 1, "inicio": 0}, {"pagina": 17, "inicio": inicio - 10}]
    respuesta, pagina = pasajes.responder("¿Cuál es el monto mensual total de los servicios?", texto, paginas)
    assert pagina == 17 and "página 17" in respuesta


def test_por_el_endpoint(monkeypatch):
    llamadas = []
    texto = _texto("gs-acta-01.pdf")
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", lambda *a, **k: repositorio_texto.TextoDocumento(
        texto=texto, metadatos={"id": "doc-t1", "tipo_documento": "ACTA_CONSTITUTIVA", "nombre_archivo_original": "a.pdf"},
        traza={}, completo=True, sha256="1" * 64, fuente="memoria"))
    monkeypatch.setattr(core_client, "ultimo_dictamen", lambda documento_id: None)
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [])

    def conversar(mensajes, temperatura=None):
        llamadas.append(1)
        r = groq_client.RespuestaTexto("Respuesta del modelo.")
        r.uso = {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}
        return r

    monkeypatch.setattr(groq_client, "conversar", conversar)
    cliente = TestClient(main.app)
    r = cliente.post("/api/v1/ai/chat-documento", json={"documento_id": "doc-t1", "pregunta": "¿Cuál es el capital social?"})
    cuerpo = r.json()
    assert cuerpo["origen_respuesta"] == "PASAJE_DEL_DOCUMENTO" and not llamadas
    assert cuerpo["contexto_llm"]["estrategia_contexto"] == "pasaje_del_documento"
    assert cuerpo["contexto_llm"]["uso_tokens"]["total_tokens"] == 0
    assert cuerpo["citas"] and all(c["verificada"] and c["fuente"] == "documento" for c in cuerpo["citas"])
    r = cliente.post("/api/v1/ai/chat-documento",
                     json={"documento_id": "doc-t1", "pregunta": "¿Cuál es el capital social?", "forzar_modelo": True})
    assert r.json()["origen_respuesta"] == "MODELO" and llamadas == [1]
