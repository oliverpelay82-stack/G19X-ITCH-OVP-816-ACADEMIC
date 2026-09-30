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

Uso:  cd services/ai-service && python -m pytest tests/test_entorno_evaluacion.py
"""
import json
import os
import sys
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
                            json={"documento_id": "GS-CSF-01", "pregunta": "¿Cuál es el RFC?"}).json()
        dictamen = core_client.ultimo_dictamen("GS-CSF-01")
    assert grabada["estatus_preliminar"] == "CONFORME"
    assert grabada["persistencia"]["guardado"] is True
    assert dictamen["reglas_aplicadas"][0]["codigo_regla"] == "RIE-03"
    assert any(r["codigo_regla"] == "RCV-03" and r["resultado"] == "VIGENTE" for r in dictamen["reglas_aplicadas"])
    assert chat["con_estado_del_sistema"] is True
    assert llamadas == ["json", "texto"]
    assert os.path.exists(ruta)

    # Restaurado al salir.
    assert settings.EXTRACCIONES_DB_PATH == ruta_original
    assert groq_client.generar_json is generar_json

    with entorno.Entorno(_casos("GS-CSF-01"), ruta, entorno.REPRODUCIR) as e:
        cliente = e.cliente()
        repetida = cliente.post("/api/v1/ai/analisis-semantico", json={"documento_id": "GS-CSF-01", **TITULAR}).json()
        chat_repetido = cliente.post("/api/v1/ai/chat-documento",
                                     json={"documento_id": "GS-CSF-01", "pregunta": "¿Cuál es el RFC?"}).json()
        assert e.casete.faltantes == []
        assert [c["uso"]["total_tokens"] for c in e.casete.consultas] == [1100, 2020]
    assert llamadas == ["json", "texto"]   # ninguna llamada nueva
    assert repetida["estatus_preliminar"] == grabada["estatus_preliminar"]
    assert chat_repetido["respuesta"] == chat["respuesta"]
    assert chat_repetido["citas"] == chat["citas"]
