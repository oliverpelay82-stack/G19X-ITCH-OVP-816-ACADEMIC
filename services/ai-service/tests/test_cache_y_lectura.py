"""
Pruebas del caché de inferencias (Groq) y de la lectura completa bajo demanda,
sin red: el cliente de Groq, el core-service y el rules-service se simulan.

  1. Caché de inferencias: una petición idéntica no vuelve a llamar a Groq, ni
     siquiera tras una conexión nueva a SQLite; una petición distinta sí.
  2. Nunca se guarda un error ni un JSON inválido.
  3. El caché se desactiva con GROQ_CACHE_INFERENCIAS=false o con una
     temperatura distinta de 0.0.
  4. Lectura completa: el repositorio solo la programa si se pide y si la
     lectura es parcial.
  5. Por endpoint: la auditoría (preparar y análisis) lee todas las páginas
     antes de responder, una sola vez, y no programa nada en segundo plano; el
     chat responde con la lectura parcial y programa la completa.
  6. Métricas y límites: tokens consumidos (``uso``) en la llamada y en un
     acierto de caché, ``uso_tokens`` en el dictamen y en el chat, historial
     del chat acotado a 20 turnos y timeout (conexión, lectura) hacia el core.

Las simulaciones se instalan con ``monkeypatch`` de pytest y se deshacen al
terminar; la SQLite es un archivo temporal, nunca la de ``data/``.

Uso:  cd services/ai-service && python tests/test_cache_y_lectura.py
"""
import os
import sys
import tempfile
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402
from openai import APIConnectionError  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from config import settings  # noqa: E402
from pipelines import persistencia_texto, repositorio_texto  # noqa: E402
from pipelines.cache_extracciones import CacheExtracciones  # noqa: E402

client = TestClient(main.app)
RFC = "PLU180514AB3"
DOC_ID = "doc-cache-001"
_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


class GroqSimulado:
    """Imita ``OpenAI().chat.completions.create`` y cuenta las llamadas."""

    def __init__(self) -> None:
        self.llamadas = 0
        self.salida = '{"rfc_detectado": "PLU180514AB3"}'
        self.error: Exception | None = None
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **_):
        self.llamadas += 1
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content=self.salida))],
            usage=SimpleNamespace(prompt_tokens=3100, completion_tokens=120, total_tokens=3220),
        )


def prueba_cache_inferencias(mp: pytest.MonkeyPatch, groq: GroqSimulado) -> None:
    print("[1] Caché de inferencias")
    primera = groq_client.generar_json("texto del documento A", "sistema")
    segunda = groq_client.generar_json("texto del documento A", "sistema")
    verificar(groq.llamadas == 1 and primera == segunda, "Una petición idéntica se sirve sin llamar a Groq",
              f"{groq.llamadas} llamada(s)")
    verificar(groq_client.uso_de(primera) == {"prompt_tokens": 3100, "completion_tokens": 120,
                                              "total_tokens": 3220, "desde_cache": False},
              "La llamada al modelo informa sus tokens (usage)")
    verificar(groq_client.uso_de(segunda) == {"prompt_tokens": 0, "completion_tokens": 0,
                                              "total_tokens": 0, "desde_cache": True},
              "Un acierto de caché informa 0 tokens consumidos")
    verificar(persistencia_texto.leer_inferencia(groq_client._clave_inferencia("sistema", "texto del documento A"))
              == primera, "La respuesta queda en SQLite (sobrevive a una conexión nueva)")
    groq_client.generar_json("texto del documento A con otro titular", "sistema")
    verificar(groq.llamadas == 2, "Una petición distinta sí consulta al modelo")

    print("\n[2] Errores y JSON inválido no se guardan")
    groq.salida = "esto no es JSON"
    for _ in range(2):
        try:
            groq_client.generar_json("texto B", "sistema")
        except groq_client.GroqRespuestaInvalidaError:
            pass
    verificar(groq.llamadas == 4, "Un JSON inválido no se guarda: el reintento vuelve a consultar")
    groq.salida, groq.error = '{"ok": true}', APIConnectionError(request=None)
    try:
        groq_client.generar_json("texto C", "sistema")
        traducido = False
    except groq_client.GroqNoDisponibleError:
        traducido = True
    groq.error = None
    verificar(traducido and groq_client.generar_json("texto C", "sistema") == {"ok": True} and groq.llamadas == 6,
              "Tras un error de red, la siguiente petición consulta al modelo")

    print("\n[3] Interruptores")
    with pytest.MonkeyPatch.context() as local:
        local.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
        groq_client.generar_json("texto D", "sistema")
        groq_client.generar_json("texto D", "sistema")
    verificar(groq.llamadas == 8, "GROQ_CACHE_INFERENCIAS=false consulta siempre")
    with pytest.MonkeyPatch.context() as local:
        local.setattr(settings, "GROQ_TEMPERATURE", 0.3)
        groq_client.generar_json("texto E", "sistema")
        groq_client.generar_json("texto E", "sistema")
    verificar(groq.llamadas == 10, "Con temperatura distinta de 0.0 no se reutiliza la respuesta")


def preparar_repositorio(mp: pytest.MonkeyPatch, completo: bool, programadas: list) -> None:
    """Simula el core-service y una lectura ya persistida (parcial o completa)."""
    mp.setattr(repositorio_texto, "cache_texto", CacheExtracciones(4))
    mp.setattr(core_client, "verificar_integridad", lambda documento_id: None)
    mp.setattr(core_client, "obtener_metadatos", lambda documento_id: {
        "id": documento_id, "hash_sha256": "b" * 64, "tipo_documento": "ACTA_CONSTITUTIVA",
        "nombre_archivo_original": "acta.pdf"})
    mp.setattr(persistencia_texto, "leer", lambda sha256, forzar_ocr=False: persistencia_texto.ExtraccionPersistida(
        texto=f"ACTA CONSTITUTIVA ... RFC {RFC}", traza={"confidence_score": 0.97, "total_paginas": 26},
        completo=completo))
    mp.setattr(repositorio_texto, "_programar_lectura_completa",
               lambda documento_id, forzar_ocr, parcial: programadas.append(documento_id))


def prueba_lectura_completa(mp: pytest.MonkeyPatch) -> None:
    print("\n[4] Lectura completa bajo demanda (repositorio)")
    programadas: list[str] = []
    preparar_repositorio(mp, completo=False, programadas=programadas)
    repositorio_texto.obtener_por_documento(DOC_ID, completar_en_fondo=False)
    verificar(not programadas, "completar_en_fondo=False no programa la lectura completa")
    repositorio_texto.obtener_por_documento(DOC_ID)
    verificar(programadas == [DOC_ID], "Por defecto, una lectura parcial sí la programa")
    programadas.clear()
    preparar_repositorio(mp, completo=True, programadas=programadas)
    repositorio_texto.obtener_por_documento(DOC_ID)
    verificar(not programadas, "Una lectura ya completa no programa nada")

    print("\n[5] Lectura completa bajo demanda (endpoints)")
    programadas.clear()
    preparar_repositorio(mp, completo=False, programadas=programadas)
    mp.setattr(groq_client, "generar_json", lambda prompt, system: {
        "tipo_documento_detectado": "ACTA_CONSTITUTIVA", "rfc_detectado": RFC, "nivel_confianza": 0.95})
    mp.setattr(groq_client, "conversar", lambda mensajes, temperatura=None: "El capital social es de $50,000.00.")
    mp.setattr(rules_client, "evaluar_vigencia", lambda tipo, emision, vencimiento, referencia: {
        "resultado": "SIN_REGLAS", "evaluaciones": []})
    mp.setattr(core_client, "registrar_dictamen", lambda carga: {"id": "dictamen-cache", "estado_expediente": "EN_REVISION"})

    # La lectura completa de la auditoría se simula y se cuenta cuántas veces ocurre.
    lecturas: list[bool] = []

    def extraer(contenido, nombre, forzar_ocr, texto_completo, sha256):
        lecturas.append(texto_completo)
        return (f"ACTA CONSTITUTIVA ... RFC {RFC} ... 26 páginas completas",
                {"confidence_score": 0.97, "total_paginas": 26}, True)

    # En un contexto propio: la sección [6] verifica el leer_binario real.
    with pytest.MonkeyPatch.context() as local:
        local.setattr(core_client, "leer_binario", lambda metadatos: b"%PDF-1.4 acta")
        local.setattr(repositorio_texto, "_extraer", extraer)
        r = client.post(f"/api/v1/ai/documentos/{DOC_ID}/preparar")
        verificar(r.status_code == 200 and lecturas == [True] and not programadas
                  and r.json()["extraccion_nivel_3"]["lectura_completa"],
                  "Preparar (auditoría) lee todas las páginas antes de responder, sin tarea de fondo",
                  f"HTTP {r.status_code} · lecturas {lecturas}")
        r = client.post("/api/v1/ai/analisis-semantico", json={"documento_id": DOC_ID, "rfc_titular": RFC})
        verificar(r.status_code == 200 and lecturas == [True] and not programadas,
                  "El análisis reutiliza esa lectura completa: el OCR no se repite", f"HTTP {r.status_code}")

    # Un documento que nadie auditó: el chat no espera la lectura completa.
    preparar_repositorio(mp, completo=False, programadas=programadas)
    r = client.post("/api/v1/ai/chat-documento", json={"documento_id": DOC_ID, "pregunta": "¿Cuál es el capital social?"})
    verificar(r.status_code == 200 and programadas == [DOC_ID] and lecturas == [True],
              "El chat de un documento sin auditar responde con la lectura parcial y programa la completa",
              f"HTTP {r.status_code}")


def prueba_metricas_y_limites(mp: pytest.MonkeyPatch) -> None:
    print("\n[6] Métricas de tokens y límites")
    uso = {"prompt_tokens": 2900, "completion_tokens": 80, "total_tokens": 2980, "desde_cache": False}
    dictamen = groq_client.RespuestaJSON({"tipo_documento_detectado": "ACTA_CONSTITUTIVA", "rfc_detectado": RFC,
                                          "nivel_confianza": 0.95})
    dictamen.uso = uso
    respuesta_chat = groq_client.RespuestaTexto("El capital social es de $50,000.00.")
    respuesta_chat.uso = uso
    mp.setattr(groq_client, "generar_json", lambda prompt, system: dictamen)
    mp.setattr(groq_client, "conversar", lambda mensajes, temperatura=None: respuesta_chat)

    r = client.post("/api/v1/ai/analisis-semantico", json={"texto": f"ACTA ... RFC {RFC}", "rfc_titular": RFC})
    verificar(r.status_code == 200 and r.json()["contexto_llm"].get("uso_tokens") == uso,
              "El dictamen trae uso_tokens en contexto_llm", f"HTTP {r.status_code}")
    # forzar_modelo: la pregunta por un monto la respondería el pasaje literal (PLUS-08), sin modelo.
    r = client.post("/api/v1/ai/chat-documento", json={"texto": "ACTA ... capital social $50,000.00",
                                                        "pregunta": "¿Cuál es el capital social?",
                                                        "forzar_modelo": True})
    verificar(r.status_code == 200 and r.json()["contexto_llm"].get("uso_tokens") == uso,
              "El chat trae uso_tokens en contexto_llm", f"HTTP {r.status_code}")

    turnos = [{"rol": "usuario", "contenido": f"pregunta {i}"} for i in range(21)]
    r = client.post("/api/v1/ai/chat-documento", json={"texto": "ACTA", "pregunta": "¿Quién firma?", "historial": turnos})
    verificar(r.status_code == 422, "Un historial de 21 turnos se rechaza con 422", f"HTTP {r.status_code}")
    r = client.post("/api/v1/ai/chat-documento",
                    json={"texto": "ACTA", "pregunta": "¿Quién firma?", "historial": turnos[:20]})
    verificar(r.status_code == 200, "20 turnos se aceptan", f"HTTP {r.status_code}")

    peticiones = []
    mp.setattr(core_client._sesion, "get", lambda url, timeout: peticiones.append(timeout) or SimpleNamespace(
        status_code=200, ok=True, text="", content=b"%PDF-1.4"))
    # obtener_metadatos sigue simulado por la sección [4]; leer_binario llega a la sesión.
    core_client.leer_binario({"id": DOC_ID})
    verificar(peticiones == [(core_client.TIMEOUT_CONEXION_SEGUNDOS, 60)],
              "El core se consulta por la sesión compartida con timeout (conexión, lectura)", str(peticiones))


def main_pruebas(mp: pytest.MonkeyPatch) -> int:
    print("=== CACHÉ DE INFERENCIAS Y LECTURA COMPLETA BAJO DEMANDA ===\n")
    _resultados.clear()
    with tempfile.TemporaryDirectory() as tmp:
        with pytest.MonkeyPatch.context() as local:
            # SQLite temporal y cliente de Groq simulado; se restauran antes de borrar el directorio.
            local.setattr(settings, "EXTRACCIONES_DB_PATH", os.path.join(tmp, "extracciones.sqlite3"))
            local.setattr(settings, "GROQ_TEMPERATURE", 0.0)
            local.setattr(settings, "GROQ_CACHE_INFERENCIAS", True)
            groq = GroqSimulado()
            local.setattr(groq_client, "_client", lambda: groq)
            prueba_cache_inferencias(local, groq)
    prueba_lectura_completa(mp)
    prueba_metricas_y_limites(mp)

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_cache_y_lectura(monkeypatch):
    assert main_pruebas(monkeypatch) == 0, "Hay verificaciones de caché o lectura en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main_pruebas(mp))
