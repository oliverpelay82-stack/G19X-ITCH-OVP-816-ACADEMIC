"""
Pruebas de T2, PLUS-09 (ESTADO_DEL_DESARROLLO §6.4), por el endpoint del chat. Sin red.

  1. Una pregunta puntual recibe el contexto enfocado (≤ CHAT_PRESUPUESTO_PUNTUAL)
     y el estado breve (sin reglas evaluadas ni elementos exigidos).
  2. Una pregunta general conserva el contexto amplio y el estado completo.
  3. El historial se acota a los últimos mensajes y las respuestas previas del
     asistente se recortan.
  4. La respuesta del chat usa su propio tope, CHAT_MAX_TOKENS.

Uso:  cd services/ai-service && python -m pytest tests/test_contexto_chat.py
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sesion  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from config import settings  # noqa: E402
from controllers import analisis_controller  # noqa: E402
from pipelines import repositorio_texto  # noqa: E402

TEXTO = "CONTRATO DE PRESTACIÓN DE SERVICIOS\n" + "\n".join(
    f"CLÁUSULA {n}. Obligación número {n} del prestador sobre el servicio {n}: entregar el reporte {n} "
    f"dentro de {n} días naturales, con la evidencia de cumplimiento correspondiente al periodo {n}."
    for n in range(1, 61))


@pytest.fixture
def chat(monkeypatch):
    enviados = []
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
    monkeypatch.setattr(settings, "GROQ_TOKENS_POR_MINUTO", 0)
    monkeypatch.setattr(analisis_controller, "_criterios_en_memoria", {})
    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", lambda *a, **k: repositorio_texto.TextoDocumento(
        texto=TEXTO, metadatos={"id": "doc-t2", "tipo_documento": "CONTRATO_SERVICIOS", "nombre_archivo_original": "c.pdf"},
        traza={}, completo=True, sha256="f" * 64, fuente="memoria"))
    monkeypatch.setattr(core_client, "ultimo_dictamen", lambda documento_id: {
        "estatus": "EN_REVISION", "estatus_preliminar": "EN_REVISION", "revisado_por_humano": False,
        "reglas_aplicadas": [{"codigo_regla": "RSC-01-CONT-PEN", "nombre_regla": "Penalización",
                              "resultado": "NO_LOCALIZADO", "recomendacion": "Revisar"}], "observaciones": []})
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [
        {"codigo_regla": "RSC-01-CONT-PEN", "nombre_regla": "Penalización", "criterio": "Pena convencional",
         "recomendacion": "Revisar", "familia_regla": "RSC", "severidad": "MEDIA_ALTA"}])

    def conversar(mensajes, temperatura=None):
        enviados.append(mensajes)
        r = groq_client.RespuestaTexto("Respuesta.")
        r.uso = {"prompt_tokens": 100, "completion_tokens": 5, "total_tokens": 105}
        return r

    monkeypatch.setattr(groq_client, "conversar", conversar)
    return sesion.cliente(main.app), enviados


def _preguntar(cliente, pregunta, historial=None):
    r = cliente.post("/api/v1/ai/chat-documento",
                     json={"documento_id": "doc-t2", "pregunta": pregunta, "historial": historial or []})
    assert r.status_code == 200, r.text
    return r.json()


def _sistema(mensajes):
    return "\n".join(m["content"] for m in mensajes if m["role"] == "system")


def test_pregunta_puntual_con_contexto_enfocado_y_estado_breve(chat):
    cliente, enviados = chat
    respuesta = _preguntar(cliente, "¿Qué plazo fija la cláusula 37?")
    assert respuesta["caracteres_de_contexto"] <= settings.CHAT_PRESUPUESTO_PUNTUAL
    assert "CLÁUSULA 37." in _sistema(enviados[-1])
    assert "Dictamen vigente del motor" in _sistema(enviados[-1])
    assert "Reglas evaluadas" not in _sistema(enviados[-1])
    assert "Elementos que el catálogo exige" not in _sistema(enviados[-1])


def test_pregunta_general_con_contexto_amplio_y_estado_completo(chat):
    cliente, enviados = chat
    puntual = _preguntar(cliente, "¿Qué plazo fija la cláusula 37?")
    general = _preguntar(cliente, "¿El contrato cumple con la penalización?")
    assert general["caracteres_de_contexto"] > puntual["caracteres_de_contexto"]
    assert "Reglas evaluadas" in _sistema(enviados[-1])
    assert "Elementos que el catálogo exige" in _sistema(enviados[-1])


def test_historial_acotado(chat):
    cliente, enviados = chat
    historial = []
    for n in range(4):
        historial += [{"rol": "usuario", "contenido": f"Pregunta {n}"},
                      {"rol": "asistente", "contenido": f"Respuesta {n}. " + "detalle " * 200}]
    _preguntar(cliente, "¿Qué plazo fija la cláusula 37?", historial)
    turnos = [m for m in enviados[-1] if m["role"] in ("user", "assistant")][:-1]
    assert len(turnos) == settings.CHAT_MENSAJES_HISTORIAL
    assert turnos[0]["content"] == "Pregunta 2"
    asistente = [m["content"] for m in turnos if m["role"] == "assistant"]
    assert all(len(c) <= settings.CHAT_CARACTERES_TURNO_ASISTENTE + 1 for c in asistente)


def test_el_chat_usa_su_propio_tope_de_respuesta(monkeypatch):
    recibido = {}
    respuesta = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content="texto"))],
                                usage=SimpleNamespace(prompt_tokens=10, completion_tokens=2, total_tokens=12))

    def crear(**kwargs):
        recibido.update(kwargs)
        return respuesta

    monkeypatch.setattr(groq_client, "_client",
                        lambda: SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=crear))))
    groq_client.conversar([{"role": "user", "content": "hola"}])
    assert recibido["max_tokens"] == settings.CHAT_MAX_TOKENS == 600
