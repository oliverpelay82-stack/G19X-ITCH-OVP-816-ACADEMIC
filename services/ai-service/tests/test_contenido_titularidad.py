"""
Pruebas del dictamen del Nivel 4 con la titularidad por razón social, el
contraste de tipo documental y la verificación de contenido (RSC/RDS), sin red:
las respuestas de Groq, del rules-service y del core-service se simulan.

  1. Titularidad: un documento sin RFC no se rechaza como ajeno. Si su razón
     social coincide con la del titular se acepta (Cap. I: «el nombre o el
     RFC»); si no, pasa a revisión humana. Un RFC ajeno sigue siendo NO_CONFORME.
  2. Tipo documental: un documento cuyo contenido no corresponde al tipo con el
     que se registró pasa a revisión humana; los tipos sin equivalente en el
     catálogo del Nivel 4 no se contrastan.
  3. Verificación de contenido: cada elemento exigido por el catálogo resulta
     CUMPLE (con cita literal comprobada), NO_LOCALIZADO (con su recomendación)
     o NO_VERIFICABLE (cita inexistente en el texto); una omisión deja el
     dictamen EN_REVISION, nunca NO_CONFORME (RSC-01).
  4. Reglas dinámicas (RDS-03) y falla de Groq en la verificación: revisión humana.
  5. Chat: detección de preguntas generales y estado del documento en el sistema.

Uso:  cd services/ai-service && python tests/test_contenido_titularidad.py
"""
import os
import sys
from datetime import date
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import groq_client, rules_client  # noqa: E402
from clients.groq_client import GroqNoDisponibleError  # noqa: E402
from pipelines import analisis_semantico, verificacion_contenido  # noqa: E402

HOY = date(2026, 9, 27)
RFC = "CSM150310QK4"
RAZON = "CONSTRUCTORA SIERRA MADRE, S.A. DE C.V."
TEXTO_ACTA = (
    "ESCRITURA PUBLICA NUMERO 18,442. Ante mi, Licenciado Juan Perez, Notario Publico numero 7 de "
    "Chilpancingo, comparecen los socios para constituir Constructora Sierra Madre, S.A. de C.V.\n"
    "La administracion de la sociedad estara a cargo de un Administrador Unico con facultades para "
    "pleitos y cobranzas y actos de administracion."
)
CRITERIOS_ACTA = [
    {"codigo_regla": "RSC-ACTA-ESCR", "nombre_regla": "Escritura pública y notario", "familia_regla": "RSC",
     "criterio": "El acta indica el número de escritura y el notario.", "severidad": "MEDIA_ALTA",
     "recomendacion": "Solicitar la copia certificada completa del acta."},
    {"codigo_regla": "RSC-ACTA-RPC", "nombre_regla": "Inscripción en el Registro Público de Comercio",
     "familia_regla": "RSC", "criterio": "El acta incluye la inscripción en el Registro Público.",
     "severidad": "MEDIA_ALTA", "recomendacion": "Solicitar la boleta de inscripción en el Registro Público."},
    {"codigo_regla": "RSC-ACTA-ADMON", "nombre_regla": "Administración y facultades", "familia_regla": "RSC",
     "criterio": "El acta designa al órgano de administración.", "severidad": "MEDIA_ALTA",
     "recomendacion": "Verificar quién ejerce la representación legal (RN-03)."},
]
_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def simular(mp: pytest.MonkeyPatch, extraccion: dict, verificaciones=None, falla_verificacion=False):
    """Groq: la extracción y la verificación se distinguen por su instrucción de sistema."""
    def generar_json(prompt, system):
        if system == verificacion_contenido.SYSTEM_PROMPT:
            if falla_verificacion:
                raise GroqNoDisponibleError("429 Too Many Requests")
            return {"verificaciones": verificaciones or []}
        return extraccion
    mp.setattr(groq_client, "generar_json", generar_json)
    mp.setattr(rules_client, "evaluar_vigencia", lambda tipo, emision, venc, ref: {
        "tipo_documento": tipo, "fecha_referencia": ref.isoformat(), "resultado": "SIN_REGLAS",
        "es_vigente": None, "dias_calculados": None, "evaluaciones": []})


def extraccion(tipo="ACTA_CONSTITUTIVA", rfc=None, razon=RAZON, confianza=0.93):
    return {"tipo_documento_detectado": tipo, "rfc_detectado": rfc, "razon_social_detectada": razon,
            "fecha_emision": "2015-03-10", "fecha_vencimiento": None, "nivel_confianza": confianza,
            "observaciones": "Texto legible."}


def analizar(tipo_registrado="ACTA_CONSTITUTIVA", criterios=None, texto=TEXTO_ACTA):
    return analisis_semantico.analizar(texto, rfc_titular=RFC, razon_social_titular=RAZON, fecha_referencia=HOY,
                                       tipo_documento_registrado=tipo_registrado, criterios_contenido=criterios)


def main(mp: pytest.MonkeyPatch) -> int:
    print("=== NIVEL 4: TITULARIDAD, TIPO DOCUMENTAL Y VERIFICACIÓN DE CONTENIDO ===\n")
    _resultados.clear()

    print("[1] Titularidad por RFC o razón social")
    simular(mp, extraccion(razon="Constructora Sierra Madre SA de CV"))
    r = analizar()
    verificar(r.titularidad == "RAZON_SOCIAL" and r.match_titular and r.estatus_preliminar == "CONFORME",
              "Sin RFC pero con la razón social del titular: CONFORME por razón social", r.estatus_preliminar)
    simular(mp, extraccion(razon="Juan de la Cruz Jiménez"))
    r = analizar()
    verificar(r.titularidad == "NO_LOCALIZADA" and r.estatus_preliminar == "EN_REVISION" and r.requiere_revision_humana,
              "Sin RFC y con otra razón social: EN_REVISION, no rechazo", r.estatus_preliminar)
    verificar(any("no incluye RFC" in o for o in r.observaciones), "El motivo explica que falta el RFC")
    simular(mp, extraccion(rfc="XAXX010101000"))
    r = analizar()
    verificar(r.titularidad == "AJENA" and r.estatus_preliminar == "NO_CONFORME",
              "Con un RFC ajeno sigue siendo NO_CONFORME", r.estatus_preliminar)
    simular(mp, extraccion(rfc=RFC))
    verificar(analizar().titularidad == "RFC", "Con el RFC del titular: titularidad por RFC")

    print("\n[2] Tipo detectado frente al tipo registrado")
    simular(mp, extraccion(tipo="OTRO", rfc=RFC))
    r = analizar(tipo_registrado="COMP_DOMICILIO")
    verificar(r.tipo_coincide is False and r.estatus_preliminar == "EN_REVISION",
              "Una factura (OTRO) registrada como comprobante de domicilio: EN_REVISION", r.estatus_preliminar)
    verificar(any("se registró como COMP_DOMICILIO" in o for o in r.observaciones), "La observación nombra ambos tipos")
    simular(mp, extraccion(tipo="ACTA_CONSTITUTIVA", rfc=RFC))
    verificar(analizar(tipo_registrado="PODER_NOTARIAL").tipo_coincide is True,
              "Un poder protocolizado en el acta es compatible con PODER_NOTARIAL")
    simular(mp, extraccion(tipo="OTRO", rfc=RFC))
    r = analizar(tipo_registrado="AVISO_PRIVACIDAD")
    verificar(r.tipo_coincide is None and r.estatus_preliminar == "CONFORME",
              "Un tipo sin equivalente en el Nivel 4 no se contrasta", r.estatus_preliminar)

    print("\n[3] Verificación de contenido contra las reglas RSC del catálogo")
    simular(mp, extraccion(rfc=RFC), verificaciones=[
        {"codigo_regla": "RSC-ACTA-ESCR", "cumple": True,
         "cita": "ESCRITURA PÚBLICA NÚMERO 18,442. Ante mí, Licenciado Juan Pérez, Notario Público número 7",
         "observacion": "Escritura y notario identificados."},
        {"codigo_regla": "RSC-ACTA-RPC", "cumple": False, "cita": None, "observacion": "No se menciona el folio."},
        {"codigo_regla": "RSC-ACTA-ADMON", "cumple": True, "cita": "Consejo de Administración de cinco miembros",
         "observacion": "Consejo designado."},
    ])
    r = analizar(criterios=CRITERIOS_ACTA)
    por_codigo = {v["codigo_regla"]: v for v in r.verificaciones}
    verificar(por_codigo["RSC-ACTA-ESCR"]["resultado"] == "CUMPLE" and por_codigo["RSC-ACTA-ESCR"]["cita"],
              "Cita literal comprobada aunque el modelo añada acentos: CUMPLE")
    verificar(por_codigo["RSC-ACTA-RPC"]["resultado"] == "NO_LOCALIZADO"
              and por_codigo["RSC-ACTA-RPC"]["recomendacion"].startswith("Solicitar la boleta"),
              "Elemento ausente: NO_LOCALIZADO con su recomendación del catálogo")
    verificar(por_codigo["RSC-ACTA-ADMON"]["resultado"] == "NO_VERIFICABLE",
              "El modelo dice que cumple pero su cita no está en el texto: NO_VERIFICABLE")
    verificar(r.estatus_preliminar == "EN_REVISION" and r.requiere_revision_humana,
              "Una omisión deja el dictamen EN_REVISION, nunca NO_CONFORME (RSC-01)", r.estatus_preliminar)
    verificar(len(r.recomendaciones) == 2, "El dictamen reúne las recomendaciones de los elementos pendientes",
              f"{len(r.recomendaciones)}")
    simular(mp, extraccion(rfc=RFC), verificaciones=[
        {"codigo_regla": "RSC-ACTA-ESCR", "cumple": True, "cita": "Notario Publico numero 7 de Chilpancingo",
         "observacion": ""},
    ])
    r = analizar(criterios=CRITERIOS_ACTA[:1])
    verificar(r.estatus_preliminar == "CONFORME" and not r.recomendaciones,
              "Todos los elementos localizados con cita: CONFORME", r.estatus_preliminar)
    r = analizar(criterios=CRITERIOS_ACTA[1:2])
    verificar(r.verificaciones[0]["resultado"] == "NO_VERIFICABLE",
              "Un elemento que el modelo no evaluó queda NO_VERIFICABLE")

    print("\n[4] Reglas dinámicas y fallas")
    dinamica = [{**CRITERIOS_ACTA[0], "codigo_regla": "RDS-04", "familia_regla": "RDS"}]
    simular(mp, extraccion(rfc=RFC), verificaciones=[
        {"codigo_regla": "RDS-04", "cumple": True, "cita": "Notario Publico numero 7 de Chilpancingo"}])
    r = analizar(criterios=dinamica)
    verificar(r.estatus_preliminar == "EN_REVISION" and any("RDS-03" in o for o in r.observaciones),
              "Un criterio definido por el usuario siempre pasa a ratificación humana (RDS-03)")
    simular(mp, extraccion(rfc=RFC), falla_verificacion=True)
    r = analizar(criterios=CRITERIOS_ACTA)
    verificar(r.estatus_preliminar == "EN_REVISION" and any("no pudo completarse" in o for o in r.observaciones),
              "Si Groq falla en la verificación, el dictamen pasa a revisión y lo explica")
    verificar(not verificacion_contenido.cita_en_texto("Notario", TEXTO_ACTA),
              "Una cita demasiado corta no prueba nada")
    verificar(verificacion_contenido.cita_en_texto("INSTRUMENTO 13,277 (TRECE MIL DOSCIENTOS SETENTA Y SIETE)",
                                                   "INSTRUMENTO 13,277 (TRECE MIL DOSCIENTOS SETENTA Y SIET E). ---")
              and not verificacion_contenido.cita_en_texto("INSTRUMENTO 13,278 (TRECE MIL DOSCIENTOS SETENTA Y OCHO)",
                                                           "INSTRUMENTO 13,277 (TRECE MIL DOSCIENTOS SETENTA Y SIET E)."),
              "Tolera las palabras que el OCR parte, pero no un dato distinto")
    verificar(verificacion_contenido.cita_en_texto("ESCRITURA PUBLICA NUMERO 18,442. ... Notario Publico numero 7",
                                                   TEXTO_ACTA)
              and not verificacion_contenido.cita_en_texto("ESCRITURA PUBLICA NUMERO 18,442 … Notario Publico numero 9",
                                                           TEXTO_ACTA),
              "Una cita unida con «...» se acepta solo si cada fragmento es literal")

    print("\n[4b] Citas con errores de reconocimiento (anclaje al texto del documento)")
    ocr = ("INSCRITO EN LA DIRECCION GENERAL DEL\nREGISTRO PUBLICO DE PERSONAS MORALE\nCIUDAD DE MEXICO\n"
           "EN EL FOLIO NUMERO 45821 DE FECHA 20 DE MAYO DE 2002")
    anclada = verificacion_contenido.cita_literal(
        "INSCRITO EN LA DIRECCION GENERAL DEL REGISTRO PUBLICO DE PERSONAS MORALES CIUDAD DE MEXICO", ocr)
    verificar(anclada is not None and "PERSONAS MORALE CIUDAD" in anclada[0] and anclada[1],
              "Si el modelo corrige una letra del OCR, la cita se guarda como está en el documento",
              anclada[0] if anclada else "sin anclar")
    verificar(verificacion_contenido.cita_literal("EN EL FOLIO NUMERO 45822 DE FECHA 20 DE MAYO", ocr) is None,
              "Una cifra distinta nunca pasa por error de OCR (folio 45822 ≠ 45821)")
    verificar(verificacion_contenido.cita_literal(
        "La sociedad quedó registrada ante la autoridad de personas morales de la capital", ocr) is None,
        "Una paráfrasis no se acepta como cita")
    simular(mp, extraccion(rfc=RFC), verificaciones=[
        {"codigo_regla": "RSC-ACTA-RPC", "cumple": True,
         "cita": "REGISTRO PUBLICO DE PERSONAS MORALES CIUDAD DE MEXICO EN EL FOLIO NUMERO 45821",
         "observacion": "Sello de inscripción."}])
    r = analizar(criterios=CRITERIOS_ACTA[1:2], texto=TEXTO_ACTA + "\n" + ocr)
    v = r.verificaciones[0]
    verificar(v["resultado"] == "CUMPLE" and "MORALE CIUDAD" in v["cita"] and "corrigió" in v["observacion"],
              "La verificación queda CUMPLE con la cita del documento y lo explica en la observación")

    print("\n[5] Chat documental")
    from controllers import analisis_controller as chat
    verificar(chat._es_pregunta_general("¿Qué le falta a este documento?")
              and chat._es_pregunta_general("Resume el acta")
              and not chat._es_pregunta_general("¿Quién es el comisario?"),
              "Detecta preguntas generales para ampliar la búsqueda de fragmentos")
    # El chat consulta el dictamen en paralelo con la lectura del texto (T4) y se lo pasa al estado.
    dictamen = {
        "estatus": "EN_REVISION", "estatus_preliminar": "EN_REVISION", "nivel_confianza": 0.9,
        "revisado_por_humano": False, "fecha_emision_extraida": "2015-03-10", "fecha_vencimiento_extraida": None,
        "vigencia_resultado": "SIN_REGLAS", "observaciones": ["Dictamen EN_REVISION: omisión relevante."],
        "reglas_aplicadas": [{"codigo_regla": "RSC-ACTA-RPC", "nombre_regla": "Inscripción", "resultado": "NO_LOCALIZADO",
                              "detalle": "Sin folio.", "recomendacion": "Solicitar la boleta."}]}
    documento = SimpleNamespace(metadatos={"id": "doc-1", "nombre_archivo_original": "acta.pdf",
                                           "tipo_documento": "ACTA_CONSTITUTIVA"})
    estado = chat._estado_en_sistema(documento, CRITERIOS_ACTA, dictamen)
    verificar("EN_REVISION" in estado and "Solicitar la boleta" in estado and "Escritura pública" in estado,
              "El chat recibe el dictamen, las recomendaciones y los elementos exigidos")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_contenido_titularidad(monkeypatch):
    assert main(monkeypatch) == 0, "Hay verificaciones en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main(mp))
