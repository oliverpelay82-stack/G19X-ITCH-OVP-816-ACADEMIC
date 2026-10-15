"""
Pruebas de T0, PLUS-07 (ESTADO_DEL_DESARROLLO §6.4): respuestas del chat desde los datos del
dictamen, sin modelo. Sin red.

  1. Ruta de cada pregunta: factuales y sugeridas → datos del dictamen;
     interpretativas, por otra parte del contrato o sin intención → modelo.
  2. Cada respuesta lleva el dato en negritas y una cita copiada del documento.
  3. Nunca afirma una ausencia: sin el dato o sin cita literal, responde el modelo.
  4. Por los endpoints: la auditoría guarda la ficha; el chat la usa solo si es
     la del dictamen vigente de ese binario; forzar_modelo la omite.

Uso:  cd services/ai-service && python -m pytest tests/test_respuestas_directas.py
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sesion  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from pipelines import repositorio_texto  # noqa: E402
from pipelines import respuestas_directas as rd  # noqa: E402
from pipelines.verificacion_contenido import cita_literal  # noqa: E402

TEXTO = """CONTRATO DE PRESTACIÓN DE SERVICIOS
Contrato que celebran PLURIONE S.A. DE C.V., con RFC PLU180514AB3, en lo sucesivo EL CLIENTE,
y SERVICIOS INTEGRALES DEL NORTE S.A. DE C.V., con RFC SIN150302KL7, en lo sucesivo EL PRESTADOR.
TERCERA. VIGENCIA. El presente contrato estará vigente del 2 de marzo de 2026 al 1 de marzo de 2027.
Chihuahua, Chihuahua, el 2 de marzo de 2026.
María Elena Ruiz Soto, Apoderada legal
Jorge Alberto Treviño Garza, Representante legal"""

FICHA = {
    "tipo_documento_detectado": "CONTRATO", "tipo_registrado": "CONTRATO_SERVICIOS", "rfc": "PLU180514AB3",
    "razon_social": "PLURIONE S.A. DE C.V.", "fecha_emision": "2026-03-02", "fecha_vencimiento": "2027-03-01",
    "titularidad": "RFC", "sello_digital_sat": False,
    "representacion": {"rol": "FIRMANTES", "personas": [
        {"nombre": "María Elena Ruiz Soto", "cargo": "Apoderada legal", "empresa": "PLURIONE S.A. DE C.V.",
         "cita": "María Elena Ruiz Soto, Apoderada legal", "cita_verificada": True},
        {"nombre": "Jorge Alberto Treviño Garza", "cargo": "Representante legal", "empresa": None,
         "cita": "Jorge Alberto Treviño Garza, Representante legal", "cita_verificada": True}]},
    "verificaciones": [
        {"codigo_regla": "RSC-01-CONT-VIG", "nombre_regla": "Vigencia y terminación anticipada", "resultado": "CUMPLE",
         "cita": "El presente contrato estará vigente del 2 de marzo de 2026 al 1 de marzo de 2027."},
        {"codigo_regla": "RSC-01-CONT-PEN", "nombre_regla": "Penalización por incumplimiento",
         "resultado": "NO_LOCALIZADO", "cita": None, "recomendacion": "Revisar las penas convencionales."}],
    "vigencia": {"resultado": "VIGENTE", "evaluaciones": [
        {"codigo_regla": "RCV-01", "nombre_regla": "Vigencia Mandatoria", "criterio": "DIAS_PARA_VENCIMIENTO",
         "limite_dias": 30, "resultado": "VIGENTE"}]},
}
DICTAMEN = {"id": "dic-1", "hash_sha256": "d" * 64, "estatus": "EN_REVISION", "requiere_revision_humana": True,
            "revisado_por_humano": False, "reglas_aplicadas": [
                {"codigo_regla": "RSC-01-CONT-PEN", "nombre_regla": "Penalización por incumplimiento",
                 "resultado": "NO_LOCALIZADO", "recomendacion": "Revisar las penas convencionales."}]}


@pytest.mark.parametrize("pregunta,esperada", [
    ("¿Qué le falta a este documento?", "faltantes"),
    ("¿Qué recomiendas corregir?", "faltantes"),
    ("Resume los datos clave de este archivo", "resumen"),
    ("¿Cuándo vence este documento?", "vencimiento"),
    ("¿hasta cuándo está vigente el contrato?", "vencimiento"),
    ("¿Cuál es la fecha de emisión?", "emision"),
    ("¿Cuál es el RFC del contribuyente?", "rfc"),
    ("¿Cuál es la razón social?", "razon_social"),
    ("¿Quiénes firman el contrato?", "personas"),
    ("¿y quién lo firma?", "personas"),
    ("¿Quién es el administrador único?", "personas"),
    ("¿Cuál es el sentido de la opinión?", "sentido"),
    # Al modelo:
    ("¿Cuál es el RFC del prestador?", None),
    ("¿El apoderado puede vender inmuebles de la empresa?", None),
    ("¿Ante qué notario se otorgó el poder?", None),
    ("¿Quién es el comisario?", None),
    ("¿Qué pasa si hay falta de pago?", None),
    ("¿Cuál es el monto de la contraprestación?", None),
    ("¿con qué cargo?", None),
])
def test_ruta_de_cada_pregunta(pregunta, esperada):
    assert rd.intencion(pregunta) == esperada


def test_respuestas_con_dato_en_negritas_y_cita_literal():
    rfc = rd.responder("¿Cuál es el RFC del contribuyente?", TEXTO, FICHA, DICTAMEN)
    assert "**PLU180514AB3**" in rfc
    cita = rfc.split("«")[1].split("»")[0]
    assert cita_literal(cita, TEXTO)
    vence = rd.responder("¿Cuándo vence este documento?", TEXTO, FICHA, DICTAMEN)
    assert "**1 de marzo de 2027**" in vence and "«" in vence
    firmantes = rd.responder("¿Quiénes firman el contrato?", TEXTO, FICHA, DICTAMEN)
    assert "María Elena Ruiz Soto" in firmantes and "Jorge Alberto Treviño Garza" in firmantes


def test_faltantes_desde_el_dictamen_vigente():
    respuesta = rd.responder("¿Qué le falta a este documento?", TEXTO, FICHA, DICTAMEN)
    assert "**en revisión** (pendiente de ratificación)" in respuesta
    assert "**Penalización por incumplimiento**" in respuesta and "Revisar las penas convencionales." in respuesta
    assert "firmante" in respuesta and "apoderado" in respuesta
    ratificado = dict(DICTAMEN, revisado_por_humano=True, revisado_por="ana.lopez")
    assert "ratificado por ana.lopez" in rd.responder("¿Qué le falta?", TEXTO, FICHA, ratificado)


def test_vigencia_por_caducidad_desde_la_emision():
    ficha = dict(FICHA, fecha_vencimiento=None, vigencia={"evaluaciones": [
        {"nombre_regla": "Caducidad Estricta de la Constancia", "criterio": "ANTIGUEDAD_DESDE_EMISION",
         "limite_dias": 90}]})
    respuesta = rd.responder("¿Cuándo vence este documento?", TEXTO, ficha, DICTAMEN)
    assert "**31 de mayo de 2026**" in respuesta and "90 días" in respuesta   # 2 de marzo + 90 días
    # El nombre de la regla no va entre «…»: esas comillas son solo para citas del documento.
    assert "«Caducidad" not in respuesta
    citas = [c.split("»")[0] for c in respuesta.split("«")[1:]]
    assert citas and all(cita_literal(c, TEXTO) for c in citas)


def test_el_resumen_de_un_contrato_nombra_a_las_partes():
    personas = [dict(p, empresa=e) for p, e in zip(FICHA["representacion"]["personas"],
                                                    ("PLURIONE S.A. DE C.V.", "SERVICIOS INTEGRALES DEL NORTE S.A. DE C.V."))]
    ficha = dict(FICHA, representacion={"rol": "FIRMANTES", "personas": personas})
    resumen = rd.responder("Resume los datos clave de este archivo", TEXTO, ficha, DICTAMEN)
    assert "SERVICIOS INTEGRALES DEL NORTE" in resumen and "Apoderada legal, PLURIONE" in resumen
    citas = [c.split("»")[0] for c in resumen.split("«")[1:]]
    assert all(cita_literal(c, TEXTO) for c in citas)


def test_nunca_afirma_una_ausencia():
    sin_vencimiento = dict(FICHA, fecha_vencimiento=None, vigencia={"evaluaciones": []})
    assert rd.responder("¿Cuándo vence este documento?", TEXTO, sin_vencimiento, DICTAMEN) is None
    assert rd.responder("¿Cuál es el RFC?", TEXTO, dict(FICHA, rfc=None), DICTAMEN) is None
    # El dato está en la ficha pero no hay un renglón del documento que lo respalde.
    assert rd.responder("¿Cuál es el RFC?", TEXTO, dict(FICHA, rfc="XAXX010101000"), DICTAMEN) is None
    # Una persona cuya cita no quedó anclada no se presenta.
    no_ancladas = {"rol": "FIRMANTES", "personas": [dict(p, cita_verificada=False)
                                                   for p in FICHA["representacion"]["personas"]]}
    assert rd.responder("¿Quiénes firman?", TEXTO, dict(FICHA, representacion=no_ancladas), DICTAMEN) is None
    # Un poder con apoderados no responde «quién firma».
    apoderados = {"rol": "APODERADOS", "personas": FICHA["representacion"]["personas"]}
    assert rd.responder("¿Quién firma?", TEXTO, dict(FICHA, representacion=apoderados), DICTAMEN) is None
    assert rd.responder("¿Quién es el director?", TEXTO, dict(FICHA, representacion=apoderados), DICTAMEN) is None


# ── Por los endpoints ────────────────────────────────────────────────

@pytest.fixture
def servicio(monkeypatch):
    estado = {"dictamen": None, "conversar": 0, "sha": "d" * 64}
    monkeypatch.setattr(repositorio_texto, "obtener_por_documento", lambda *a, **k: repositorio_texto.TextoDocumento(
        texto=TEXTO, metadatos={"id": "doc-t0", "tipo_documento": "CONTRATO_SERVICIOS",
                                "nombre_archivo_original": "contrato.pdf", "hash_sha256": estado["sha"]},
        traza={"confidence_score": 0.99}, completo=True, sha256=estado["sha"], fuente="memoria"))

    def generar_json(prompt, system):
        if "firmantes" in prompt:
            datos = {"tipo_documento_detectado": "CONTRATO", "rfc_detectado": "PLU180514AB3",
                     "razon_social_detectada": "PLURIONE S.A. DE C.V.", "fecha_emision": "2026-03-02",
                     "fecha_vencimiento": "2027-03-01", "nivel_confianza": 0.95, "observaciones": "Legible.",
                     "firmantes": [{"nombre": "María Elena Ruiz Soto", "cargo": "Apoderada legal",
                                    "empresa": "PLURIONE S.A. DE C.V.",
                                    "cita": "María Elena Ruiz Soto, Apoderada legal"}]}
        else:
            datos = {"verificaciones": []}
        r = groq_client.RespuestaJSON(datos)
        r.uso = {"total_tokens": 100}
        return r

    def conversar(mensajes, temperatura=None):
        estado["conversar"] += 1
        r = groq_client.RespuestaTexto("Respuesta del modelo.")
        r.uso = {"prompt_tokens": 1000, "completion_tokens": 10, "total_tokens": 1010}
        return r

    def registrar(carga):
        estado["dictamen"] = {"id": "dic-100", "hash_sha256": estado["sha"], "estatus": carga["estatus"],
                              "requiere_revision_humana": True, "revisado_por_humano": False, "reglas_aplicadas": []}
        return {"id": "dic-100", "estatus": carga["estatus"]}

    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    monkeypatch.setattr(groq_client, "conversar", conversar)
    monkeypatch.setattr(core_client, "registrar_dictamen", registrar)
    monkeypatch.setattr(core_client, "ultimo_dictamen", lambda documento_id: estado["dictamen"])
    monkeypatch.setattr(rules_client, "criterios_contenido", lambda tipo: [
        {"codigo_regla": "RSC-02-CONT", "nombre_regla": "Datos del firmante", "criterio": "Firmantes",
         "recomendacion": "Confirmar", "familia_regla": "RSC", "severidad": "ALTA"}])
    monkeypatch.setattr(rules_client, "evaluar_vigencia", lambda *a: {"resultado": "VIGENTE", "evaluaciones": []})
    return sesion.cliente(main.app), estado


def _chat(cliente, pregunta, **extra):
    r = cliente.post("/api/v1/ai/chat-documento", json={"documento_id": "doc-t0", "pregunta": pregunta, **extra})
    assert r.status_code == 200, r.text
    return r.json()


def test_la_auditoria_deja_la_ficha_y_el_chat_responde_sin_modelo(servicio):
    cliente, estado = servicio
    # Antes de auditar no hay ficha: responde el modelo.
    estado["dictamen"] = None
    assert _chat(cliente, "¿Cuál es el RFC del contribuyente?")["origen_respuesta"] == "MODELO"
    r = cliente.post("/api/v1/ai/analisis-semantico", json={"documento_id": "doc-t0", "rfc_titular": "PLU180514AB3",
                                                            "razon_social_titular": "PLURIONE S.A. DE C.V."})
    assert r.status_code == 200 and r.json()["persistencia"]["guardado"] is True
    llamadas = estado["conversar"]
    respuesta = _chat(cliente, "¿Cuál es el RFC del contribuyente?")
    assert respuesta["origen_respuesta"] == "DATOS_DEL_DICTAMEN"
    assert respuesta["modelo_utilizado"] is None and respuesta["contexto_llm"]["uso_tokens"]["total_tokens"] == 0
    assert respuesta["contexto_llm"]["estrategia_contexto"] == "datos_del_dictamen"
    assert respuesta["citas"] and all(c["verificada"] and c["fuente"] == "documento" for c in respuesta["citas"])
    assert "extraccion_nivel_3" in respuesta and respuesta["documento"]["id"] == "doc-t0"
    firmantes = _chat(cliente, "¿Quiénes firman el contrato?")
    assert firmantes["origen_respuesta"] == "DATOS_DEL_DICTAMEN" and "María Elena Ruiz Soto" in firmantes["respuesta"]
    assert estado["conversar"] == llamadas
    # Interpretativa y forzar_modelo: al modelo.
    assert _chat(cliente, "¿Puede la apoderada firmar solo?")["origen_respuesta"] == "MODELO"
    assert _chat(cliente, "¿Cuál es el RFC del contribuyente?", forzar_modelo=True)["origen_respuesta"] == "MODELO"


def test_la_ficha_solo_vale_para_su_dictamen_y_su_binario(servicio):
    cliente, estado = servicio
    cliente.post("/api/v1/ai/analisis-semantico", json={"documento_id": "doc-t0", "rfc_titular": "PLU180514AB3"})
    assert _chat(cliente, "¿Cuál es el RFC del contribuyente?")["origen_respuesta"] == "DATOS_DEL_DICTAMEN"
    # Otro dictamen vigente (una auditoría hecha por otra instancia): la ficha ya no es la suya.
    estado["dictamen"] = dict(estado["dictamen"], id="dic-200")
    assert _chat(cliente, "¿Cuál es el RFC del contribuyente?")["origen_respuesta"] == "MODELO"
    # Un dictamen de otro binario.
    estado["dictamen"] = dict(estado["dictamen"], id="dic-100", hash_sha256="e" * 64)
    # (Puede salir del caché del modelo, T3: el estado del sistema es el mismo que en la pregunta anterior.)
    assert _chat(cliente, "¿Cuál es el RFC del contribuyente?")["origen_respuesta"] != "DATOS_DEL_DICTAMEN"
