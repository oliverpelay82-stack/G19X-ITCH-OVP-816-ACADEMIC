"""
Pruebas de T4, PLUS-11 (ESTADO_DEL_DESARROLLO §6.4): presupuesto local de tokens por minuto,
criterios del catálogo en memoria y dictamen en vivo en el chat. Sin red.

  1. La ventana de 60 s suma los tokens del último minuto y olvida los viejos;
     con GROQ_TOKENS_POR_MINUTO=0 queda desactivada.
  2. Cada llamada real a Groq (auditoría o chat) entra en la cuenta; una
     respuesta desde un caché no.
  3. Si una auditoría acaba de gastar la cuota, el chat acota su contexto en
     lugar de esperar, lo declara en contexto_llm.presupuesto_tokens y no
     guarda esa respuesta bajo las claves del contexto completo.
  4. Los criterios se consultan una vez por tipo mientras no venzan; el
     dictamen se lee en cada turno (una ratificación se ve de inmediato).

Uso:  cd services/ai-service && python -m pytest tests/test_presupuesto_tokens.py
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
from pipelines import presupuesto_tokens, repositorio_texto  # noqa: E402

DOC_ID = "doc-presupuesto"
# Documento largo: 60 cláusulas distintas, muy por encima del contexto máximo del chat.
TEXTO = "CONTRATO DE PRESTACIÓN DE SERVICIOS\n" + "\n".join(
    f"CLÁUSULA {n}. Obligación número {n} del prestador sobre el servicio {n}: entregar el reporte {n} "
    f"dentro de {n} días naturales, con la evidencia de cumplimiento correspondiente al periodo {n}."
    for n in range(1, 61))


class Reloj:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


@pytest.fixture
def chat(monkeypatch):
    llamadas = {"conversar": 0, "dictamen": 0, "criterios": 0}
    monkeypatch.setattr(settings, "GROQ_TOKENS_POR_MINUTO", 8000)
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", True)
    monkeypatch.setattr(presupuesto_tokens, "presupuesto", presupuesto_tokens.Presupuesto())
    monkeypatch.setattr(analisis_controller, "_criterios_en_memoria", {})
    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", lambda *a, **k: repositorio_texto.TextoDocumento(
        texto=TEXTO, metadatos={"id": DOC_ID, "tipo_documento": "CONTRATO_SERVICIOS", "nombre_archivo_original": "c.pdf"},
        traza={}, completo=True, sha256="c" * 64, fuente="memoria"))

    def dictamen(documento_id):
        llamadas["dictamen"] += 1
        return {"estatus": "EN_REVISION", "estatus_preliminar": "EN_REVISION", "revisado_por_humano": False,
                "reglas_aplicadas": [], "observaciones": []}

    def criterios(tipo):
        llamadas["criterios"] += 1
        return [{"codigo_regla": "RSC-01-CONT-PEN", "nombre_regla": "Penalización", "criterio": "Pena convencional",
                 "recomendacion": "Revisar", "familia_regla": "RSC", "severidad": "MEDIA_ALTA"}]

    def conversar(mensajes, temperatura=None):
        llamadas["conversar"] += 1
        r = groq_client.RespuestaTexto("La cláusula 7 fija **7 días naturales**.")
        r.uso = {"prompt_tokens": 1500, "completion_tokens": 20, "total_tokens": 1520}
        return r

    monkeypatch.setattr(core_client, "ultimo_dictamen", dictamen)
    monkeypatch.setattr(rules_client, "criterios_contenido", criterios)
    monkeypatch.setattr(groq_client, "conversar", conversar)
    return sesion.cliente(main.app), llamadas


def _preguntar(cliente, pregunta="¿Qué plazo fija la cláusula 7?"):
    r = cliente.post("/api/v1/ai/chat-documento", json={"documento_id": DOC_ID, "pregunta": pregunta})
    assert r.status_code == 200, r.text
    return r.json()


def test_ventana_de_un_minuto(monkeypatch):
    reloj = Reloj()
    p = presupuesto_tokens.Presupuesto(reloj)
    monkeypatch.setattr(settings, "GROQ_TOKENS_POR_MINUTO", 8000)
    p.registrar(5000)
    reloj.t += 30
    p.registrar(2000)
    assert p.usados() == 7000 and p.limite == 7600
    assert p.cabe(600) and not p.cabe(601)
    reloj.t += 31                       # el primer consumo ya tiene 61 s
    assert p.usados() == 2000
    monkeypatch.setattr(settings, "GROQ_TOKENS_POR_MINUTO", 0)
    assert not p.activo() and p.cabe(10 ** 6)


def test_estimacion():
    mensajes = [{"role": "system", "content": "x" * 3300}, {"role": "user", "content": ""}]
    assert presupuesto_tokens.estimar(mensajes) == 1000 + presupuesto_tokens.RESERVA_RESPUESTA


def test_las_llamadas_reales_entran_en_la_cuenta(monkeypatch):
    monkeypatch.setattr(presupuesto_tokens, "presupuesto", presupuesto_tokens.Presupuesto())
    monkeypatch.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
    respuesta = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))],
        usage=SimpleNamespace(prompt_tokens=6000, completion_tokens=900, total_tokens=6900))
    cliente = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **k: respuesta)))
    monkeypatch.setattr(groq_client, "_client", lambda: cliente)
    groq_client.generar_json("prompt", "system")
    assert presupuesto_tokens.presupuesto.usados() == 6900
    respuesta.choices[0].message.content = "texto"
    respuesta.usage.total_tokens = 1100
    groq_client.conversar([{"role": "user", "content": "hola"}])
    assert presupuesto_tokens.presupuesto.usados() == 8000


def test_el_chat_acota_su_contexto_si_la_cuota_se_agoto(chat):
    cliente, llamadas = chat
    normal = _preguntar(cliente)
    assert "presupuesto_tokens" in normal["contexto_llm"]
    assert normal["contexto_llm"]["presupuesto_tokens"]["reducido"] is False

    presupuesto_tokens.presupuesto.registrar(6995)          # una auditoría de 20 páginas acaba de terminar
    acotada = _preguntar(cliente, "¿Qué plazo fija la cláusula 9?")
    datos = acotada["contexto_llm"]["presupuesto_tokens"]
    assert datos["reducido"] is True and datos["usados_ultimo_minuto"] >= 6995
    assert datos["estimado_reducido"] < datos["estimado"]
    assert acotada["caracteres_de_contexto"] < normal["caracteres_de_contexto"]
    assert acotada["caracteres_de_contexto"] <= settings.MAX_CARACTERES_CONTEXTO // 3
    assert acotada["origen_respuesta"] == "MODELO"

    # Con la cuota libre, la misma pregunta no reutiliza la respuesta de contexto acotado.
    presupuesto_tokens.presupuesto.vaciar()
    completa = _preguntar(cliente, "¿Qué plazo fija la cláusula 9?")
    assert completa["origen_respuesta"] == "MODELO"
    assert completa["contexto_llm"]["presupuesto_tokens"]["reducido"] is False
    assert llamadas["conversar"] == 3


def test_sin_presupuesto_no_se_acota(chat, monkeypatch):
    cliente, _ = chat
    monkeypatch.setattr(settings, "GROQ_TOKENS_POR_MINUTO", 0)
    presupuesto_tokens.presupuesto.registrar(7999)
    respuesta = _preguntar(cliente)
    assert "presupuesto_tokens" not in respuesta["contexto_llm"]


def test_criterios_en_memoria_y_dictamen_en_vivo(chat, monkeypatch):
    cliente, llamadas = chat
    _preguntar(cliente, "¿Qué plazo fija la cláusula 3?")
    _preguntar(cliente, "¿Qué plazo fija la cláusula 4?")
    assert llamadas["criterios"] == 1
    assert llamadas["dictamen"] == 2
    monkeypatch.setattr(settings, "CHAT_TTL_CRITERIOS_SEGUNDOS", 0)
    _preguntar(cliente, "¿Qué plazo fija la cláusula 5?")
    assert llamadas["criterios"] == 2


def test_un_fallo_del_rules_service_no_se_guarda(chat, monkeypatch):
    cliente, llamadas = chat

    def caido(tipo):
        llamadas["criterios"] += 1
        raise rules_client.ReglasNoDisponiblesError("sin conexión")

    monkeypatch.setattr(rules_client, "criterios_contenido", caido)
    _preguntar(cliente, "¿Qué plazo fija la cláusula 3?")
    _preguntar(cliente, "¿Qué plazo fija la cláusula 4?")
    assert llamadas["criterios"] == 2
