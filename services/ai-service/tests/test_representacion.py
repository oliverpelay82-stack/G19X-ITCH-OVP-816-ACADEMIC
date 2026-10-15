"""
Pruebas offline de los datos de representación legal del Nivel 4 (P2, ESTADO_DEL_DESARROLLO §6.2: RSC-02, HU-23, HU-37). Groq, el rules-service y el core se simulan.

  1. Cada persona trae su cita anclada en el texto y la cita debe contener el
     nombre; si no, queda «no verificada». Sin duplicados.
  2. Contrato con RSC-02 activa: los firmantes vienen en la MISMA llamada de
     extracción (RSC-02 no se envía a la verificación de contenido) y el
     dictamen queda EN_REVISION por RSC-02.
  3. Poder notarial: la extracción devuelve los apoderados; el dictamen sigue
     sus reglas de siempre.
  4. Los demás tipos no cambian su prompt (el caché de inferencias se conserva).
  5. El dictamen que se persiste en el core lleva la representación.

Uso:  cd services/ai-service && python tests/test_representacion.py
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import core_client, groq_client, rules_client  # noqa: E402
from controllers import analisis_controller  # noqa: E402
from pipelines import analisis_semantico, representacion, verificacion_contenido  # noqa: E402

HOY = date(2026, 9, 29)
RFC = "CSM150310QK4"
RAZON = "CONSTRUCTORA SIERRA MADRE, S.A. DE C.V."
CONTRATO = (
    "CONTRATO DE PRESTACION DE SERVICIOS que celebran por una parte CONSTRUCTORA SIERRA MADRE, S.A. DE C.V., "
    "representada en este acto por el Lic. Juan Pérez López en su carácter de apoderado legal, y por la otra "
    "SERVICIOS DEL PACIFICO, S.A. DE C.V., representada por la C. Ana María Ruiz.\n"
    "PRIMERA. OBJETO. El prestador realizará los servicios de mantenimiento descritos en el anexo A.\n"
    "FIRMAS\nPOR CONSTRUCTORA SIERRA MADRE: Juan Pérez López, Apoderado legal\n"
    "POR SERVICIOS DEL PACIFICO: Ana María Ruiz, Directora General\n"
)
PODER = (
    "ESCRITURA PUBLICA NUMERO 9,812. Ante mí, Notario Público número 3 de Chilpancingo, CONSTRUCTORA SIERRA "
    "MADRE, S.A. DE C.V. otorga PODER GENERAL PARA PLEITOS Y COBRANZAS Y ACTOS DE ADMINISTRACION a favor del "
    "señor JUAN PEREZ LOPEZ, quien acepta el cargo.\n"
)
RSC_02 = {"codigo_regla": "RSC-02-CONT", "nombre_regla": "Datos del firmante y representación legal",
          "familia_regla": "RSC", "criterio": "Datos del firmante.", "severidad": "ALTA",
          "recomendacion": "Confirmar la representación contra el poder o el acta (RN-03)."}
RSC_OBJ = {"codigo_regla": "RSC-01-CONT-OBJ", "nombre_regla": "Objeto del contrato", "familia_regla": "RSC",
           "criterio": "El contrato define su objeto.", "severidad": "MEDIA_ALTA",
           "recomendacion": "Solicitar el contrato con su objeto."}


def _vigencia_sin_reglas(monkeypatch):
    monkeypatch.setattr(rules_client, "evaluar_vigencia", lambda tipo, emision, venc, ref: {
        "tipo_documento": tipo, "fecha_referencia": ref.isoformat(), "resultado": "SIN_REGLAS",
        "es_vigente": None, "dias_calculados": None, "evaluaciones": []})


def _groq(monkeypatch, extraccion: dict, verificaciones: list | None = None) -> list[tuple[str, str]]:
    llamadas: list[tuple[str, str]] = []

    def generar_json(prompt, system):
        llamadas.append((system, prompt))
        if system == verificacion_contenido.SYSTEM_PROMPT:
            return {"verificaciones": verificaciones or []}
        return extraccion
    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    return llamadas


def _extraccion(tipo: str, **extra) -> dict:
    return {"tipo_documento_detectado": tipo, "rfc_detectado": RFC, "razon_social_detectada": RAZON,
            "fecha_emision": "2026-01-15", "fecha_vencimiento": None, "nivel_confianza": 0.95,
            "observaciones": "Texto legible.", **extra}


# ── 1. Personas con cita anclada ────────────────────────────────────
def test_cada_persona_trae_su_cita_anclada_y_con_su_nombre():
    datos = representacion.procesar(representacion.FIRMANTES, {"firmantes": [
        {"nombre": "Juan Pérez López", "cargo": "Apoderado legal", "empresa": RAZON,
         "cita": "POR CONSTRUCTORA SIERRA MADRE: Juan Pérez López, Apoderado legal"},
        {"nombre": "Ana María Ruiz", "cargo": "Directora General", "empresa": "Servicios del Pacífico",
         "cita": "firmado por Ana María Ruiz en Acapulco"},                     # la cita no está en el texto
        {"nombre": "Pedro Gómez Salas", "cita": "POR SERVICIOS DEL PACIFICO: Ana María Ruiz, Directora General"},
        {"nombre": "juan perez lopez", "cita": "Juan Pérez López"},              # duplicado
        {"nombre": "X", "cita": "x"},                                           # nombre inválido
    ]}, CONTRATO)

    assert datos["rol"] == representacion.FIRMANTES
    personas = {p["nombre"]: p for p in datos["personas"]}
    assert list(personas) == ["Juan Pérez López", "Ana María Ruiz", "Pedro Gómez Salas"]
    assert personas["Juan Pérez López"]["cita_verificada"] and personas["Juan Pérez López"]["empresa"] == RAZON
    assert not personas["Ana María Ruiz"]["cita_verificada"], "Cita inexistente en el texto"
    assert not personas["Pedro Gómez Salas"]["cita_verificada"], "La cita existe pero no contiene su nombre"


def test_el_apoderado_nombrado_solo_por_su_poder_recibe_el_cargo():
    acta = PODER + "Se otorga a María Elena Ruiz Soto poder general para actos de administración.\n"
    datos = representacion.procesar(representacion.APODERADOS, {"apoderados": [
        {"nombre": "María Elena Ruiz Soto", "cargo": None,
         "cita": "Se otorga a María Elena Ruiz Soto poder general para actos de administración."},
        {"nombre": "Juan Pérez López", "cargo": "Administrador único",                 # el del modelo se respeta
         "cita": "a favor del señor JUAN PEREZ LOPEZ, quien acepta el cargo."},
        {"nombre": "Pedro Gómez Salas", "cargo": None,                                   # cita sin verificar
         "cita": "Se otorga a Pedro Gómez Salas poder especial."},
    ]}, acta)

    cargos = {p["nombre"]: p["cargo"] for p in datos["personas"]}
    assert cargos == {"María Elena Ruiz Soto": "Apoderado", "Juan Pérez López": "Administrador único",
                      "Pedro Gómez Salas": None}
    # Un firmante sin cargo no lo recibe: en un contrato, «poder» no lo hace apoderado de nadie.
    firmante = representacion.procesar(representacion.FIRMANTES, {"firmantes": [
        {"nombre": "Ana María Ruiz", "cargo": None, "cita": "representada por la C. Ana María Ruiz."}]}, CONTRATO)
    assert firmante["personas"][0]["cargo"] is None


def test_la_regla_rsc_02_resume_a_los_firmantes_verificados():
    datos = {"rol": "FIRMANTES", "personas": [
        {"nombre": "Juan Pérez López", "cargo": "Apoderado legal", "empresa": RAZON, "cita": "Juan Pérez López",
         "cita_verificada": True}]}
    v = representacion.verificacion(RSC_02, datos)
    assert v["resultado"] == verificacion_contenido.CUMPLE and "Juan Pérez López (Apoderado legal" in v["observacion"]
    assert representacion.verificacion(RSC_02, {"rol": "FIRMANTES", "personas": []})["resultado"] == "NO_LOCALIZADO"


# ── 2. Contrato ─────────────────────────────────────────────────────
def test_contrato_extrae_firmantes_en_la_misma_llamada_y_queda_en_revision(monkeypatch):
    _vigencia_sin_reglas(monkeypatch)
    llamadas = _groq(monkeypatch, _extraccion("CONTRATO", firmantes=[
        {"nombre": "Juan Pérez López", "cargo": "Apoderado legal", "empresa": RAZON,
         "cita": "POR CONSTRUCTORA SIERRA MADRE: Juan Pérez López, Apoderado legal"}]),
        verificaciones=[{"codigo_regla": "RSC-01-CONT-OBJ", "cumple": True,
                         "cita": "El prestador realizará los servicios de mantenimiento", "observacion": "Sí."}])

    resultado = analisis_semantico.analizar(
        CONTRATO, rfc_titular=RFC, razon_social_titular=RAZON, fecha_referencia=HOY,
        tipo_documento_registrado="CONTRATO_SERVICIOS", criterios_contenido=[RSC_02, RSC_OBJ])

    extraccion = [p for s, p in llamadas if s == analisis_semantico.SYSTEM_PROMPT]
    verificacion = [p for s, p in llamadas if s == verificacion_contenido.SYSTEM_PROMPT]
    assert len(extraccion) == 1 and '"firmantes"' in extraccion[0], "Los firmantes van en la misma extracción"
    assert len(verificacion) == 1 and "RSC-02-CONT" not in verificacion[0], "RSC-02 no es un elemento a verificar"
    assert resultado.representacion["personas"][0]["cita_verificada"]
    rsc02 = next(v for v in resultado.verificaciones if v["codigo_regla"] == "RSC-02-CONT")
    assert rsc02["resultado"] == "CUMPLE" and "Juan Pérez López" in rsc02["cita"]
    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_EN_REVISION
    assert any("RSC-02" in o for o in resultado.observaciones), resultado.observaciones


def test_contrato_sin_firmante_identificado_queda_pendiente(monkeypatch):
    _vigencia_sin_reglas(monkeypatch)
    _groq(monkeypatch, _extraccion("CONTRATO", firmantes=[]))

    resultado = analisis_semantico.analizar(
        CONTRATO, rfc_titular=RFC, razon_social_titular=RAZON, fecha_referencia=HOY,
        tipo_documento_registrado="CONTRATO_SERVICIOS", criterios_contenido=[RSC_02])

    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_EN_REVISION
    assert resultado.verificaciones[0]["resultado"] == "NO_LOCALIZADO"
    assert RSC_02["recomendacion"] in resultado.recomendaciones


# ── 3. Poder notarial ───────────────────────────────────────────────
def test_poder_extrae_apoderados_sin_cambiar_su_dictamen(monkeypatch):
    _vigencia_sin_reglas(monkeypatch)
    llamadas = _groq(monkeypatch, _extraccion("PODER_NOTARIAL", apoderados=[
        {"nombre": "Juan Pérez López", "cargo": "Apoderado general",
         "facultades": "Pleitos y cobranzas y actos de administración",
         "cita": "a favor del señor JUAN PEREZ LOPEZ, quien acepta el cargo"}]))

    resultado = analisis_semantico.analizar(
        PODER, rfc_titular=RFC, razon_social_titular=RAZON, fecha_referencia=HOY,
        tipo_documento_registrado="PODER_NOTARIAL", criterios_contenido=[])

    assert '"apoderados"' in llamadas[0][1] and '"firmantes"' not in llamadas[0][1]
    [apoderado] = resultado.representacion["personas"]
    assert resultado.representacion["rol"] == representacion.APODERADOS
    assert apoderado["cita_verificada"] and "JUAN PEREZ LOPEZ" in apoderado["cita"]
    assert apoderado["facultades"].startswith("Pleitos")
    assert resultado.estatus_preliminar == analisis_semantico.ESTATUS_CONFORME, resultado.observaciones


# ── 4. Los demás tipos no cambian ───────────────────────────────────
def test_otros_tipos_no_piden_datos_de_representacion(monkeypatch):
    _vigencia_sin_reglas(monkeypatch)
    llamadas = _groq(monkeypatch, _extraccion("CONSTANCIA_SITUACION_FISCAL"))

    resultado = analisis_semantico.analizar(
        "CONSTANCIA DE SITUACION FISCAL RFC CSM150310QK4", rfc_titular=RFC, fecha_referencia=HOY,
        tipo_documento_registrado="CSF_SAT", criterios_contenido=[])

    prompt = llamadas[0][1]
    assert '"firmantes"' not in prompt and '"apoderados"' not in prompt and "Identifica también" not in prompt
    assert resultado.representacion is None


# ── 5. Persistencia ─────────────────────────────────────────────────
def test_el_dictamen_persistido_lleva_la_representacion(monkeypatch):
    enviado = {}
    monkeypatch.setattr(core_client, "registrar_dictamen", lambda carga: enviado.update(carga) or {"id": "d-1"})
    resultado = analisis_semantico.ResultadoAnalisis(
        tipo_documento_detectado="CONTRATO", rfc_detectado=RFC, rfc_valido=True, match_titular=True,
        razon_social_detectada=RAZON, fecha_emision=None, fecha_vencimiento=None, vigente=None,
        dias_para_vencimiento=None, nivel_confianza=0.9, estatus_preliminar="EN_REVISION",
        requiere_revision_humana=True, observaciones=[], modelo_utilizado="qwen/qwen3.8-27b",
        representacion={"rol": "FIRMANTES", "personas": []},
    )

    respuesta = analisis_controller._persistir_dictamen("doc-1", resultado, "analista")

    assert respuesta["guardado"] and enviado["representacion"] == {"rol": "FIRMANTES", "personas": []}


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
