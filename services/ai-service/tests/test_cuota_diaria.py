"""
PLUS-19 — Cuota diaria del proveedor de IA visible (PRD §21.6; HU-55). Sin red.

  1. Los tokens de las llamadas reales se suman por día (UTC); las del caché
     no cuentan y un día nuevo empieza en cero.
  2. Un 429 por cuota diaria marca la cuota agotada hasta el tiempo que indica
     Groq, corrige el uso con el que informa y responde en lenguaje llano; un
     429 por minuto no la marca.
  3. /health informa la cuota en motor_inferencia.cuota_diaria.
  4. Con la cuota agotada, el ciclo de procesamiento diferido no gasta intentos.
"""
import time
from datetime import datetime, timedelta, timezone

import httpx

import sesion
from openai import RateLimitError

import main
from clients import groq_client
from config import settings
from controllers import analisis_controller, health_controller
from pipelines import cuota_diaria, diferidos

MENSAJE_TPD = ("Rate limit reached for model `qwen/qwen3.8-27b` in organization `org_x` service tier `on_demand` on "
               "tokens per day (TPD): Limit 200000, Used 199500, Requested 1200. Please try again in 5m30s.")
MENSAJE_TPM = ("Rate limit reached for model `qwen/qwen3.8-27b` on tokens per minute (TPM): Limit 8000, Used 7900, "
               "Requested 900. Please try again in 6.5s.")


def _limite(mensaje: str) -> RateLimitError:
    respuesta = httpx.Response(429, request=httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions"))
    return RateLimitError(mensaje, response=respuesta, body=None)


def test_los_tokens_se_suman_por_dia_utc():
    hoy = datetime(2026, 10, 1, 23, 50, tzinfo=timezone.utc)
    cuota_diaria.registrar(1200, ahora=hoy)
    cuota_diaria.registrar(800, ahora=hoy)
    cuota_diaria.registrar(None, ahora=hoy)
    assert cuota_diaria.estado(ahora=hoy)["usados"] == 2000
    manana = hoy + timedelta(minutes=20)
    assert cuota_diaria.estado(ahora=manana)["usados"] == 0, "Un día nuevo (UTC) empieza en cero"


def test_una_llamada_real_cuenta_y_una_del_cache_no():
    groq_client._registrar({"total_tokens": 1500, "desde_cache": False})
    groq_client._registrar(dict(groq_client._USO_DESDE_CACHE))
    estado = cuota_diaria.estado()
    assert estado["usados"] == 1500 and estado["restantes"] == settings.GROQ_TOKENS_POR_DIA - 1500


def test_un_429_por_cuota_diaria_la_marca_agotada():
    antes = datetime.now(timezone.utc)
    error = groq_client._traducir(_limite(MENSAJE_TPD))

    assert "cuota diaria" in str(error) and "429" not in str(error), "Lenguaje llano"
    estado = cuota_diaria.estado()
    assert estado["agotada"] and estado["usados"] == 199500, "Groq corrige la estimación"
    liberacion = datetime.fromisoformat(estado["disponible_desde"])
    assert timedelta(minutes=5) < liberacion - antes < timedelta(minutes=6)
    assert not cuota_diaria.agotada(ahora=liberacion + timedelta(seconds=1))


def test_un_429_por_minuto_no_agota_la_cuota_diaria():
    groq_client._traducir(_limite(MENSAJE_TPM))
    assert not cuota_diaria.estado()["agotada"]


def test_health_informa_la_cuota():
    ahora = time.monotonic()
    health_controller._cache["groq"] = (ahora, {"disponible": True, "modelos_instalados": [], "modelo_disponible": True,
                                                "modelo_requerido": settings.GROQ_MODEL, "detalle": "simulado"})
    health_controller._cache["ocr"] = (ahora, {"disponible": True})
    try:
        cuota_diaria.registrar(3000)
        cuerpo = sesion.cliente(main.app).get("/api/v1/health").json()
    finally:
        health_controller._cache.clear()
    cuota = cuerpo["motor_inferencia"]["cuota_diaria"]
    assert cuota["usados"] == 3000 and cuota["limite"] == settings.GROQ_TOKENS_POR_DIA and cuota["agotada"] is False


def test_con_la_cuota_agotada_el_ciclo_diferido_espera(monkeypatch):
    diferidos.registrar_fallo({"documento_id": "doc-cuota", "usuario": "p6"}, "Groq no respondió.")
    cuota_diaria.registrar_agotada(MENSAJE_TPD)
    llamadas = []
    monkeypatch.setattr(diferidos, "procesar_vencidas", lambda *a, **k: llamadas.append(1))

    resumen = analisis_controller.procesar_diferidos()

    assert llamadas == [] and not any(resumen.values())
    assert diferidos.obtener("doc-cuota").intentos == 1, "No se gastó un intento"
