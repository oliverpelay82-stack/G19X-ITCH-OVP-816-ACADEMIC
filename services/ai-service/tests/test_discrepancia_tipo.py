"""
Discrepancia de tipo documental (DOC-01, Cap. I: la IA confirma «que el documento
sea del tipo que el usuario seleccionó»), sin red.

Caso que se corrige: un archivo de otro tipo (una INE o un contrato) registrado
como Poder notarial. Antes, el motivo del dictamen hablaba de la titularidad
(«el documento no incluye RFC…») como si fuera un poder fallido, y se aplicaban
al archivo la vigencia y los elementos RSC del tipo esperado.

  1. La discrepancia decide el dictamen: En revisión, con un motivo que nombra
     el tipo esperado y el detectado; ni la titularidad ni la vigencia ni el
     contenido del tipo esperado se convierten en motivos.
  2. No se aplican al archivo las reglas del tipo esperado: ni la vigencia RCV
     ni los elementos RSC; tampoco se extraen apoderados para el cotejo (RN-03).
  3. Un RFC ajeno en un archivo de otro tipo no lo vuelve No conforme: la
     discrepancia la decide un analista (la clasificación es del modelo).
  4. La respuesta trae tipo_esperado, tipo_detectado y descripcion_coherente.
  5. El dictamen que se persiste no lleva las fechas ni la representación del
     archivo equivocado, para que el core no recalcule la vigencia del tipo
     esperado con ellas.
  6. Sin discrepancia, el dictamen no cambia y descripcion_coherente es su motivo.

Uso:  cd services/ai-service && python -m pytest tests/test_discrepancia_tipo.py
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import core_client, groq_client, rules_client  # noqa: E402
from controllers import analisis_controller  # noqa: E402
from pipelines import analisis_semantico, verificacion_contenido  # noqa: E402

HOY = date(2026, 10, 3)
RFC = "CSM150310QK4"
RAZON = "CONSTRUCTORA SIERRA MADRE, S.A. DE C.V."
TEXTO_INE = ("INSTITUTO NACIONAL ELECTORAL\nCREDENCIAL PARA VOTAR\nNOMBRE PEREZ LOPEZ JUAN\n"
             "CLAVE DE ELECTOR PRLPJN80010112H400\nVIGENCIA 2030")
RSC_PODER = [{"codigo_regla": "RSC-PODER-FAC", "nombre_regla": "Facultades del apoderado", "familia_regla": "RSC",
              "criterio": "El poder indica las facultades conferidas.", "severidad": "MEDIA_ALTA",
              "recomendacion": "Solicitar el poder con las facultades."}]


@pytest.fixture
def llamadas(monkeypatch):
    # Sin "nombre", la consulta del nombre del documento real no da uno válido (respaldo de la categoría).
    registro = {"verificacion": 0, "vigencia": 0, "consultas_nombre": 0, "nombre": {}}

    def generar_json(prompt, system):
        if system == analisis_semantico.SYSTEM_PROMPT_NOMBRE:
            registro["consultas_nombre"] += 1
            if isinstance(registro["nombre"], Exception):
                raise registro["nombre"]
            return registro["nombre"]
        if system == verificacion_contenido.SYSTEM_PROMPT:
            registro["verificacion"] += 1
            return {"verificaciones": [{"codigo_regla": "RSC-PODER-FAC", "cumple": False, "cita": None,
                                        "observacion": "No se encontraron facultades."}]}
        return registro["extraccion"]

    def evaluar_vigencia(tipo, emision, venc, ref):
        registro["vigencia"] += 1
        return {"tipo_documento": tipo, "resultado": "VENCIDO", "evaluaciones": [
            {"codigo_regla": "RCV-01", "nombre_regla": "Vigencia", "resultado": "VENCIDO", "detalle": "Vencido."}]}

    monkeypatch.setattr(groq_client, "generar_json", generar_json)
    monkeypatch.setattr(rules_client, "evaluar_vigencia", evaluar_vigencia)
    return registro


def _extraccion(tipo, rfc=None, razon="JUAN PEREZ LOPEZ", vencimiento="2025-01-01", **extra):
    return {"tipo_documento_detectado": tipo, "rfc_detectado": rfc, "razon_social_detectada": razon,
            "fecha_emision": "2020-01-01", "fecha_vencimiento": vencimiento, "nivel_confianza": 0.95,
            "observaciones": "Credencial legible.", **extra}


def _analizar(tipo_registrado="PODER_NOTARIAL", nombre="Poder Notarial", criterios=RSC_PODER):
    return analisis_semantico.analizar(TEXTO_INE, rfc_titular=RFC, razon_social_titular=RAZON, fecha_referencia=HOY,
                                       tipo_documento_registrado=tipo_registrado, criterios_contenido=criterios,
                                       nombre_tipo_registrado=nombre)


def _motivo(r):
    return next(o for o in r.observaciones if o.startswith("Dictamen "))


def test_la_discrepancia_decide_el_motivo(llamadas):
    llamadas["extraccion"] = _extraccion("IDENTIFICACION_OFICIAL")
    r = _analizar()
    assert r.tipo_coincide is False and r.estatus_preliminar == "EN_REVISION" and r.requiere_revision_humana
    motivo = _motivo(r)
    assert motivo.startswith("Dictamen EN_REVISION: Discrepancia de documento:"), motivo
    assert "«Poder Notarial»" in motivo and "«Identificación Oficial»" in motivo, motivo
    assert "No es posible validar los criterios de cumplimiento del documento solicitado." in motivo
    # Ningún otro motivo de dictamen ni texto del tipo esperado.
    assert sum(o.startswith("Dictamen ") for o in r.observaciones) == 1, r.observaciones
    assert not any("no incluye RFC" in o or "vigencia" in o.lower() or "RCV" in o for o in r.observaciones), \
        r.observaciones


def test_no_se_aplican_las_reglas_del_tipo_esperado(llamadas):
    llamadas["extraccion"] = _extraccion("CONTRATO", apoderados=[
        {"nombre": "Juan Perez Lopez", "cargo": "Apoderado", "cita": "NOMBRE PEREZ LOPEZ JUAN"}])
    r = _analizar()
    assert llamadas["vigencia"] == 0, "no se consulta la vigencia del tipo esperado"
    assert r.verificaciones == [] and r.recomendaciones and r.representacion is None
    assert r.vigente is None and r.vigencia_nivel_2.get("evaluada") is False


def test_un_rfc_ajeno_en_otro_tipo_queda_en_revision(llamadas):
    llamadas["extraccion"] = _extraccion("CONTRATO", rfc="PLU180514AB3", razon="PLURIONE S.A. DE C.V.")
    r = _analizar()
    assert r.titularidad == "AJENA" and r.estatus_preliminar == "EN_REVISION"
    assert _motivo(r).startswith("Dictamen EN_REVISION: Discrepancia de documento:")


def test_campos_de_la_respuesta(llamadas):
    llamadas["extraccion"] = _extraccion("OTRO")
    datos = _analizar().a_dict()
    assert datos["tipo_esperado"] == "PODER_NOTARIAL" and datos["tipo_esperado_nombre"] == "Poder Notarial"
    assert datos["tipo_detectado"] == "OTRO" and datos["discrepancia_tipo"] is True
    assert "un documento que no corresponde a ninguna categoría del catálogo" in datos["tipo_detectado_nombre"]
    assert datos["descripcion_coherente"].startswith("Discrepancia de documento: Se esperaba")


def test_el_dictamen_persistido_no_lleva_datos_del_archivo_equivocado(llamadas, monkeypatch):
    llamadas["extraccion"] = _extraccion("CONTRATO")
    r = _analizar()
    enviado = {}
    monkeypatch.setattr(core_client, "registrar_dictamen", lambda carga: enviado.update(carga) or {"id": "d-1"})
    monkeypatch.setattr(rules_client, "version_catalogo", lambda: None)
    analisis_controller._persistir_dictamen("doc-1", r, "analista")
    assert enviado["fecha_emision"] is None and enviado["fecha_vencimiento"] is None
    assert enviado["representacion"] is None and enviado["verificaciones"] == []
    assert enviado["estatus"] == "EN_REVISION" and enviado["tipo_documento_detectado"] == "CONTRATO"


def test_sin_discrepancia_no_cambia(llamadas):
    llamadas["extraccion"] = _extraccion("PODER_NOTARIAL", rfc=RFC, vencimiento=None)
    r = _analizar(criterios=[])
    assert r.tipo_coincide is True and llamadas["vigencia"] == 1
    datos = r.a_dict()
    assert datos["discrepancia_tipo"] is False
    assert datos["descripcion_coherente"] == _motivo(r).split(":", 1)[1].strip()[:1].upper() + \
        _motivo(r).split(":", 1)[1].strip()[1:]


def test_una_senal_del_archivo_no_deja_el_motivo_de_conforme(llamadas):
    """El veredicto «En revisión» por una señal del archivo no se acompaña del motivo de CONFORME."""
    llamadas["extraccion"] = _extraccion("PODER_NOTARIAL", rfc=RFC, vencimiento=None)
    llamadas_vigencia = rules_client.evaluar_vigencia
    rules_client.evaluar_vigencia = lambda *a: {"resultado": "SIN_REGLAS", "evaluaciones": []}
    try:
        r = _analizar(criterios=[])
    finally:
        rules_client.evaluar_vigencia = llamadas_vigencia
    assert r.estatus_preliminar == "CONFORME"
    analisis_controller._tope_revision(r, ["El PDF contiene JavaScript: se recomienda pedir otra versión."])
    assert r.estatus_preliminar == "EN_REVISION"
    assert not any(o.startswith("Dictamen CONFORME:") for o in r.observaciones), r.observaciones
    assert r.a_dict()["descripcion_coherente"].startswith("El PDF contiene JavaScript")


# ── Nombre del documento real (consulta breve solo con discrepancia) ──────────


def test_con_discrepancia_el_motivo_nombra_el_documento_real(llamadas, monkeypatch):
    llamadas["extraccion"] = _extraccion("IDENTIFICACION_OFICIAL")
    llamadas["nombre"] = {"nombre_documento_real": "  «Credencial para Votar»  "}
    r = _analizar()
    assert llamadas["consultas_nombre"] == 1
    assert r.nombre_documento_real == "Credencial para Votar"
    assert "identificó «Credencial para Votar»." in _motivo(r)
    assert r.a_dict()["nombre_documento_real"] == "Credencial para Votar"
    enviado = {}
    monkeypatch.setattr(core_client, "registrar_dictamen", lambda carga: enviado.update(carga) or {"id": "d-1"})
    monkeypatch.setattr(rules_client, "version_catalogo", lambda: None)
    analisis_controller._persistir_dictamen("doc-1", r, "analista")
    assert enviado["nombre_documento_real"] == "Credencial para Votar"


def test_sin_discrepancia_no_se_consulta_el_nombre(llamadas, monkeypatch):
    llamadas["extraccion"] = _extraccion("PODER_NOTARIAL", rfc=RFC, vencimiento=None)
    r = _analizar(criterios=[])
    assert llamadas["consultas_nombre"] == 0 and r.nombre_documento_real is None
    enviado = {}
    monkeypatch.setattr(core_client, "registrar_dictamen", lambda carga: enviado.update(carga) or {"id": "d-1"})
    monkeypatch.setattr(rules_client, "version_catalogo", lambda: None)
    analisis_controller._persistir_dictamen("doc-1", r, "analista")
    assert "nombre_documento_real" not in enviado


@pytest.mark.parametrize("respuesta", [{"nombre_documento_real": None}, {"nombre_documento_real": "x" * 200},
                                       groq_client.GroqNoDisponibleError("429")])
def test_sin_un_nombre_valido_se_usa_la_categoria(llamadas, respuesta):
    llamadas["extraccion"] = _extraccion("CONTRATO")
    llamadas["nombre"] = respuesta
    r = _analizar()
    assert r.estatus_preliminar == "EN_REVISION" and r.nombre_documento_real == "Contrato"
    assert "identificó «Contrato»." in _motivo(r)


def test_el_chat_reconoce_la_discrepancia():
    from pipelines import respuestas_directas
    dictamen = {"estatus": "EN_REVISION", "requiere_revision_humana": True,
                "nombre_documento_real": "Formato de Evaluación de Residencia Profesional"}
    ficha = {"tipo_registrado": "PODER_NOTARIAL", "tipo_esperado_nombre": "Poder Notarial", "verificaciones": []}
    respuesta = respuestas_directas.responder("¿Qué le falta a este documento?", "", ficha, dictamen)
    assert respuesta.startswith("Este documento ha sido identificado por el motor de IA como "
                                "**Formato de Evaluación de Residencia Profesional**. Dado que el expediente requiere "
                                "**Poder Notarial**, no se localizan los elementos correspondientes a la matriz")
    # Sin discrepancia, la respuesta de faltantes no cambia.
    sin = respuestas_directas.responder("¿Qué le falta a este documento?", "", ficha, {"estatus": "CONFORME"})
    assert sin.startswith("Según el dictamen del motor")
    # Al modelo le llega la instrucción en el estado del sistema, solo con discrepancia.
    from pipelines.repositorio_texto import TextoDocumento
    doc = TextoDocumento("texto", {"nombre_archivo_original": "eval.pdf", "tipo_documento": "PODER_NOTARIAL",
                                   "nombre_tipo_documento": "Poder Notarial"}, {}, True, "a" * 64)
    estado = analisis_controller._estado_en_sistema(doc, [], dictamen, breve=True)
    assert "Discrepancia de tipo: el motor identificó este archivo como «Formato de Evaluación" in estado
    assert "Discrepancia de tipo" not in analisis_controller._estado_en_sistema(doc, [], {"estatus": "CONFORME"})
