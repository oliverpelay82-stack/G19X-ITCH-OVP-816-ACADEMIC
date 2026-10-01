"""
Pruebas del entorno offline de la validación cuantitativa (evaluacion/entorno.py),
sin red: Groq se sustituye por una función falsa y el Gold Standard aporta los PDF.

  1. Reglas simuladas: criterios RSC del contrato y vigencia RCV con el motor
     puro del rules-service (RCV-03 y RCV-04 con la fecha de referencia fija).
  2. Reproducir sin la huella grabada no llama a Groq: la auditoría falla y la
     huella queda registrada como faltante.
  3. Grabar y reproducir: la misma auditoría da el mismo dictamen desde el
     casete, sin llamar a Groq, y el chat recibe el dictamen simulado con la
     forma del core.
  4. Al salir del entorno, los clientes y los ajustes originales se restauran.
  5. Un casete de respaldo (el del chat) ahorra las auditorías ya grabadas: se
     reproducen sin Groq y se copian al casete propio, que no lo modifica.
  6. Si Groq no responde, el aviso de procesamiento diferido queda en el core
     simulado y nunca llega al core real.

Uso:  cd services/ai-service && python -m pytest tests/test_entorno_evaluacion.py
"""
import json
import os
import sys
import time
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import core_client, groq_client  # noqa: E402
from config import settings  # noqa: E402
from evaluacion import entorno, gold_standard as gs  # noqa: E402

TITULAR = {"rfc_titular": gs.TITULAR["rfc"], "razon_social_titular": gs.TITULAR["razon_social"]}


def _casos(*ids):
    with open(gs.RUTA_ANOTACION, encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    return [c for c in casos if c["id"] in ids]


def _groq_falso(llamadas):
    def generar_json(prompt, system):
        llamadas.append("json")
        r = groq_client.RespuestaJSON({
            "tipo_documento_detectado": "CONSTANCIA_SITUACION_FISCAL", "rfc_detectado": "PLU180514AB3",
            "razon_social_detectada": "PLURIONE S.A. DE C.V.", "fecha_emision": "2026-09-10",
            "fecha_vencimiento": None, "nivel_confianza": 0.95, "observaciones": "Legible.",
        })
        r.uso = {"prompt_tokens": 1000, "completion_tokens": 100, "total_tokens": 1100}
        return r

    def conversar(mensajes, temperatura=None):
        llamadas.append("texto")
        r = groq_client.RespuestaTexto("El RFC es **PLU180514AB3**.")
        r.uso = {"prompt_tokens": 2000, "completion_tokens": 20, "total_tokens": 2020}
        return r

    return generar_json, conversar


def test_reglas_simuladas():
    reglas = entorno.ReglasSimuladas()
    codigos = {c["codigo_regla"] for c in reglas.criterios_contenido("CONTRATO_SERVICIOS")}
    assert codigos == {"RSC-01-CONT-OBJ", "RSC-01-CONT-VIG", "RSC-01-CONT-PEN", "RSC-01-CONT-CONF",
                       "RSC-01-CONT-FIRM", "RSC-02-CONT"}
    assert reglas.criterios_contenido("CSF_SAT") == []
    referencia = date(2026, 9, 30)
    assert reglas.evaluar_vigencia("CSF_SAT", "2026-05-04", None, referencia)["resultado"] == "VENCIDO"
    assert reglas.evaluar_vigencia("OPINION_CUMPLIMIENTO", "2026-09-18", None, referencia)["resultado"] == "VIGENTE"
    assert reglas.evaluar_vigencia("OPINION_CUMPLIMIENTO", "2026-07-20", None, referencia)["resultado"] == "VENCIDO"


def test_reproducir_sin_huella_no_llama_a_groq(tmp_path, monkeypatch):
    llamadas = []
    generar_json, conversar = _groq_falso(llamadas)
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    with entorno.Entorno(_casos("GS-CSF-01"), str(tmp_path / "vacio.json"), entorno.REPRODUCIR) as e:
        # El middleware errores_no_controlados convierte la excepción en un 500:
        # por eso el casete registra la huella faltante.
        r = e.cliente().post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR})
        assert r.status_code == 500
        assert len(e.casete.faltantes) == 1
    assert llamadas == []


def test_grabar_y_reproducir(tmp_path, monkeypatch):
    llamadas = []
    generar_json, conversar = _groq_falso(llamadas)
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    monkeypatch.setattr(groq_client, "conversar", conversar)
    ruta = str(tmp_path / "casete.json")
    ruta_original = settings.EXTRACCIONES_DB_PATH

    with entorno.Entorno(_casos("GS-CSF-01"), ruta, entorno.GRABAR) as e:
        cliente = e.cliente()
        grabada = cliente.post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR}).json()
        assert settings.EXTRACCIONES_DB_PATH != ruta_original
        chat = cliente.post("/api/v1/ai/chat-documento",
                            json={"documento_id": "GS-CSF-01", "pregunta": "¿Cuál es el RFC?",
                                           "forzar_modelo": True}).json()
        dictamen = core_client.ultimo_dictamen("GS-CSF-01")
    assert grabada["estatus_preliminar"] == "CONFORME"
    assert grabada["persistencia"]["guardado"] is True
    assert dictamen["reglas_aplicadas"][0]["codigo_regla"] == "RIE-03"
    assert any(r["codigo_regla"] == "RCV-03" and r["resultado"] == "VIGENTE" for r in dictamen["reglas_aplicadas"])
    assert chat["con_estado_del_sistema"] is True
    # Con forzar_modelo el chat consulta al modelo aunque la ficha de la auditoría pueda responder (PLUS-07).
    assert chat["origen_respuesta"] == "MODELO"
    assert llamadas == ["json", "texto"]
    assert os.path.exists(ruta)

    # Restaurado al salir.
    assert settings.EXTRACCIONES_DB_PATH == ruta_original
    assert groq_client.generar_json is generar_json

    with entorno.Entorno(_casos("GS-CSF-01"), ruta, entorno.REPRODUCIR) as e:
        cliente = e.cliente()
        repetida = cliente.post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR}).json()
        chat_repetido = cliente.post("/api/v1/ai/chat-documento",
                                     json={"documento_id": "GS-CSF-01", "pregunta": "¿Cuál es el RFC?",
                                           "forzar_modelo": True}).json()
        assert e.casete.faltantes == []
        assert [c["uso"]["total_tokens"] for c in e.casete.consultas] == [1100, 2020]
    assert llamadas == ["json", "texto"]   # ninguna llamada nueva
    assert repetida["estatus_preliminar"] == grabada["estatus_preliminar"]
    assert chat_repetido["respuesta"] == chat["respuesta"]
    assert chat_repetido["citas"] == chat["citas"]


def test_casete_de_respaldo_ahorra_lo_ya_grabado(tmp_path, monkeypatch):
    llamadas = []
    generar_json, _ = _groq_falso(llamadas)
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    respaldo, propio = str(tmp_path / "chat.json"), str(tmp_path / "precision.json")
    with entorno.Entorno(_casos("GS-CSF-01"), respaldo, entorno.GRABAR) as e:
        e.cliente().post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR})
    with open(respaldo, encoding="utf-8") as f:
        contenido_respaldo = f.read()
    assert llamadas == ["json"]

    with entorno.Entorno(_casos("GS-CSF-01"), propio, entorno.GRABAR, respaldos=(respaldo,)) as e:
        r = e.cliente().post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR})
        assert r.json()["estatus_preliminar"] == "CONFORME"
    assert llamadas == ["json"]   # ninguna llamada nueva
    with open(respaldo, encoding="utf-8") as f:
        assert f.read() == contenido_respaldo
    # El casete propio se reproduce sin el respaldo.
    with entorno.Entorno(_casos("GS-CSF-01"), propio, entorno.REPRODUCIR) as e:
        e.cliente().post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR})
        assert e.casete.faltantes == []


def test_groq_caido_no_avisa_al_core_real(tmp_path, monkeypatch):
    def caido(prompt, system):
        raise groq_client.GroqNoDisponibleError("sin cuota")

    def core_real(*_a, **_k):
        raise AssertionError("el entorno llamó al core real")

    monkeypatch.setattr(groq_client, "generar_json", caido)
    monkeypatch.setattr(core_client, "marcar_diferido", core_real)
    with entorno.Entorno(_casos("GS-CSF-01"), str(tmp_path / "c.json"), entorno.GRABAR) as e:
        r = e.cliente().post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR})
        assert r.status_code == 503
        assert [d["documento_id"] for d in e.core.diferidos] == ["GS-CSF-01"]


def test_sin_limite_de_tokens_el_grabador_no_espera():
    limitado = entorno.Casete("no-existe.json", entorno.GRABAR)
    libre = entorno.Casete("no-existe.json", entorno.GRABAR, limitar_tokens=False)
    for casete in (limitado, libre):
        casete._presupuesto.esperar(6000)
    inicio = time.monotonic()
    libre._presupuesto.esperar(6000)          # solo cabe en el mismo minuto sin el límite
    assert time.monotonic() - inicio < 0.5
    assert limitado._presupuesto.limite == entorno.TOKENS_POR_MINUTO
