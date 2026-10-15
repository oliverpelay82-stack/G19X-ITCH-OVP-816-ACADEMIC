"""
P5 — Excepciones del DOC-05, Tabla 1, en el ai-service (ESTADO_DEL_DESARROLLO §6.5; HU-33,
HU-47, HU-48). Sin red: Groq, el rules-service y el core se simulan.

  1. Documento ilegible: sin texto útil, o con muy pocos caracteres por página
     y confianza de OCR baja, la auditoría no llama al modelo y persiste un
     dictamen En revisión de origen NIVEL_3_ILEGIBLE. Un documento breve pero
     nítido no es ilegible.
  2. Procesamiento diferido: si Groq no responde, la auditoría entra en la
     cola, el core recibe el aviso y la respuesta es 503 con la explicación.
  3. El ciclo de reintentos repite la auditoría vencida y la saca de la cola
     al tener éxito; si Groq sigue sin responder, la reprograma con espera
     creciente y, al agotar los intentos, avisa «agotado» y la retira; un
     documento que ya no existe se descarta.
  4. Archivo dañado (HU-33): una imagen JPEG o PNG con la firma correcta pero
     truncada, o mayor que el límite de píxeles de PIL, se rechaza con 400
     (FormatoNoSoportadoError), como un PDF corrupto, y no con un error 500,
     en la extracción y en el visor.
"""
import io
from datetime import datetime, timedelta, timezone

import pytest

import sesion

import main
from clients import core_client, groq_client, rules_client
from clients.core_client import DocumentoNoEncontradoError
from clients.groq_client import GroqNoDisponibleError
from config import settings
from controllers import analisis_controller
from PIL import Image

from pipelines import diferidos, extraccion_pipeline, legibilidad, repositorio_texto, visor_documento

client = sesion.cliente(main.app)
GENERAR_JSON_REAL = groq_client.generar_json
DOC_ID = "doc-p5-001"
TEXTO_LEGIBLE = "ACTA CONSTITUTIVA ... RFC PLU180514AB3 ... " + "Cláusula primera. " * 40


@pytest.fixture
def entorno(monkeypatch):
    """Simula el texto del documento, Groq, el rules-service y el core; registra lo que llega al core."""
    estado = {"texto": TEXTO_LEGIBLE, "traza": {"confidence_score": 0.97, "total_paginas": 1},
              "groq": "ok", "llamadas_groq": 0, "dictamenes": [], "avisos": [], "documento_existe": True}

    def obtener(documento_id, forzar_ocr=False, completar_en_fondo=True, texto_completo=False):
        if not estado["documento_existe"]:
            raise DocumentoNoEncontradoError(f"Documento con ID '{documento_id}' no encontrado.")
        return repositorio_texto.TextoDocumento(
            texto=estado["texto"], traza=dict(estado["traza"]), completo=True, sha256="b" * 64, fuente="persistencia",
            metadatos={"id": documento_id, "tipo_documento": "ACTA_CONSTITUTIVA",
                       "nombre_archivo_original": "acta.pdf", "hash_sha256": "b" * 64},
        )

    def generar_json(prompt, system):
        estado["llamadas_groq"] += 1
        if estado["groq"] == "caido":
            raise GroqNoDisponibleError("Groq no respondió (simulado).")
        return {"tipo_documento_detectado": "ACTA_CONSTITUTIVA", "rfc_detectado": "PLU180514AB3",
                "razon_social_detectada": "PLURIONE S.A. DE C.V.", "fecha_emision": "2019-04-13",
                "fecha_vencimiento": None, "nivel_confianza": 0.95, "observaciones": "Texto legible."}

    def registrar(carga):
        estado["dictamenes"].append(carga)
        return {"id": f"dictamen-{len(estado['dictamenes'])}", "estatus": carga["estatus"]}

    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", obtener)
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [])
    monkeypatch.setattr(rules_client, "evaluar_vigencia", lambda *a, **k: {"resultado": "SIN_REGLAS", "evaluaciones": []})
    monkeypatch.setattr(core_client, "registrar_dictamen", registrar)
    monkeypatch.setattr(core_client, "marcar_diferido", lambda doc, aviso: estado["avisos"].append((doc, aviso)) or True)
    return estado


def _auditar():
    return client.post("/api/v1/ai/analisis-semantico", json={
        "documento_id": DOC_ID, "rfc_titular": "PLU180514AB3", "razon_social_titular": "PLURIONE S.A. DE C.V.",
        "usuario": "analista.p5"})


# ── Documento ilegible ────────────────────────────────────────────────


def test_sin_texto_util_la_auditoria_es_ilegible_y_no_llama_al_modelo(entorno):
    entorno["texto"], entorno["traza"] = "··· —— ~~", {"confidence_score": 0.1, "total_paginas": 3}

    r = _auditar()

    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["ilegible"] is True and cuerpo["estatus_preliminar"] == "EN_REVISION"
    assert entorno["llamadas_groq"] == 0, "No se gasta cuota en un documento sin texto"
    [carga] = entorno["dictamenes"]
    assert carga["origen"] == "NIVEL_3_ILEGIBLE" and carga["match_titular"] is None
    assert carga["observaciones"][0].startswith("Documento ilegible, se requiere recarga")
    assert carga["version_lectura"].startswith("n3-") and cuerpo["persistencia"]["guardado"] is True


def test_pocos_caracteres_con_confianza_baja_es_ilegible(entorno):
    entorno["texto"], entorno["traza"] = "AB 12 xx", {"confidence_score": 0.22, "total_paginas": 2}
    assert _auditar().json().get("ilegible") is True and entorno["llamadas_groq"] == 0


def test_un_documento_breve_pero_nitido_no_es_ilegible(entorno):
    entorno["texto"], entorno["traza"] = "RFC PLU180514AB3 PLURIONE", {"confidence_score": 0.98, "total_paginas": 1}
    r = _auditar()
    assert r.status_code == 200 and not r.json().get("ilegible") and entorno["llamadas_groq"] >= 1
    assert "origen" not in entorno["dictamenes"][0], "Un dictamen del Nivel 4 conserva su origen por omisión"


def test_criterio_de_legibilidad():
    assert legibilidad.motivo_ilegible("", {}) is not None
    assert legibilidad.motivo_ilegible("x" * 40, {"confidence_score": 0.3, "total_paginas": 1}) is not None
    assert legibilidad.motivo_ilegible("x" * 40, {"confidence_score": 0.95, "total_paginas": 1}) is None
    assert legibilidad.motivo_ilegible("x" * 400, {"confidence_score": 0.2, "total_paginas": 2}) is None


# ── Procesamiento diferido ────────────────────────────────────────────


def test_si_groq_no_responde_la_auditoria_queda_diferida(entorno, monkeypatch):
    entorno["groq"] = "caido"
    monkeypatch.setattr(settings, "GROQ_MAX_RETRIES", 4)

    r = _auditar()

    assert r.status_code == 503 and "procesamiento diferido" in r.json()["detail"]
    assert "tras 5 intentos" in r.json()["detail"], "El primero más GROQ_MAX_RETRIES, no un 3 fijo"
    diferida = diferidos.obtener(DOC_ID)
    assert diferida.intentos == 1 and diferida.peticion["usuario"] == "analista.p5"
    assert diferida.proximo_intento - datetime.now(timezone.utc) > timedelta(minutes=14)
    [(documento, aviso)] = entorno["avisos"]
    assert documento == DOC_ID and aviso["agotado"] is False and aviso["max_intentos"] == settings.DIFERIDOS_MAX_INTENTOS


def test_sin_clave_de_ia_responde_503_claro_y_no_encola(entorno, monkeypatch):
    """Sin la clave del proveedor, el SDK lanzaba un error no controlado (500); no es una caída que se reintente."""
    monkeypatch.setattr(groq_client, "generar_json", GENERAR_JSON_REAL)
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    groq_client._client.cache_clear()

    r = _auditar()

    assert r.status_code == 503 and "no está configurado" in r.json()["detail"]
    assert diferidos.obtener(DOC_ID) is None and entorno["avisos"] == []


def test_el_ciclo_completa_la_auditoria_cuando_groq_vuelve(entorno):
    entorno["groq"] = "caido"
    _auditar()
    entorno["groq"] = "ok"

    resumen = diferidos.procesar_vencidas(
        analisis_controller._auditar_diferida, core_client.marcar_diferido, analisis_controller._ReintentarDespues,
        (analisis_controller._SinReintento,), ahora=datetime.now(timezone.utc) + timedelta(hours=1))

    assert resumen["auditadas"] == 1 and diferidos.obtener(DOC_ID) is None
    assert entorno["dictamenes"][-1]["usuario"] == "analista.p5", "El reintento conserva quién pidió la auditoría"


def test_el_ciclo_reprograma_y_al_agotarse_avisa_y_retira(entorno, monkeypatch):
    monkeypatch.setattr(settings, "DIFERIDOS_MAX_INTENTOS", 3)
    entorno["groq"] = "caido"
    _auditar()
    lejano = datetime.now(timezone.utc) + timedelta(days=3)
    argumentos = (analisis_controller._auditar_diferida, core_client.marcar_diferido,
                  analisis_controller._ReintentarDespues, (analisis_controller._SinReintento,))

    segundo = diferidos.procesar_vencidas(*argumentos, ahora=lejano)
    assert segundo["reprogramadas"] == 1 and diferidos.obtener(DOC_ID).intentos == 2
    tercero = diferidos.procesar_vencidas(*argumentos, ahora=lejano)

    assert tercero["agotadas"] == 1 and diferidos.obtener(DOC_ID) is None
    ultimo_aviso = entorno["avisos"][-1][1]
    assert ultimo_aviso["agotado"] is True and ultimo_aviso["proximo_intento"] is None


def test_un_documento_que_ya_no_existe_se_descarta(entorno):
    entorno["groq"] = "caido"
    _auditar()
    entorno["documento_existe"] = False

    resumen = diferidos.procesar_vencidas(
        analisis_controller._auditar_diferida, core_client.marcar_diferido, analisis_controller._ReintentarDespues,
        (analisis_controller._SinReintento,), ahora=datetime.now(timezone.utc) + timedelta(hours=1))

    assert resumen["descartadas"] == 1 and diferidos.obtener(DOC_ID) is None


def test_la_espera_crece_hasta_un_dia():
    assert [diferidos.espera(n) for n in (1, 2, 3)] == [timedelta(minutes=15), timedelta(minutes=30), timedelta(hours=1)]
    assert diferidos.espera(20) == timedelta(hours=24)
    # Q-c: muchos fallos seguidos (auditorías manuales con Groq caído) no desbordan la duración.
    assert diferidos.espera(40) == diferidos.espera(10_000) == timedelta(hours=24)


def _imagen(formato: str, lado: int = 64) -> bytes:
    salida = io.BytesIO()
    Image.new("RGB", (lado, lado), "white").save(salida, formato)
    return salida.getvalue()


@pytest.mark.parametrize("formato,corte", [("JPEG", 200), ("PNG", 60)])
def test_una_imagen_truncada_se_rechaza_como_formato_no_soportado(formato, corte):
    truncada = _imagen(formato)[:corte]
    with pytest.raises(extraccion_pipeline.FormatoNoSoportadoError, match="truncada o dañada"):
        extraccion_pipeline.extraer_texto(truncada, texto_completo=True)


def test_una_bomba_de_descompresion_se_rechaza(monkeypatch):
    # PIL rechaza una imagen de más del doble de MAX_IMAGE_PIXELS; se baja el límite
    # para no generar en la prueba una imagen de 180 millones de píxeles.
    monkeypatch.setattr(Image, "MAX_IMAGE_PIXELS", 1_000)
    with pytest.raises(extraccion_pipeline.FormatoNoSoportadoError, match="tamaño máximo"):
        extraccion_pipeline.extraer_texto(_imagen("PNG", 100), texto_completo=True)


def test_la_imagen_truncada_responde_400_y_no_500():
    respuesta = client.post(
        "/api/v1/ai/extraer-texto",
        files={"file": ("truncada.png", _imagen("PNG")[:60], "image/png")},
        data={"usar_cache": "false"},
    )
    assert respuesta.status_code == 400
    assert "truncada o dañada" in respuesta.json()["detail"]


def test_el_visor_de_una_imagen_truncada_responde_400(monkeypatch):
    truncada = _imagen("JPEG")[:200]
    monkeypatch.setattr(visor_documento, "_documento", lambda _id: visor_documento.Documento("0" * 64, truncada, False))
    for ruta in ("/api/v1/ai/documentos/x/visor", "/api/v1/ai/documentos/x/paginas/1?ancho=800"):
        respuesta = client.get(ruta)
        assert respuesta.status_code == 400, ruta
        assert "truncada o dañada" in respuesta.json()["detail"]
