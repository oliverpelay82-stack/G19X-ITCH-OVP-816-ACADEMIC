"""
Nivel 4 del pipeline de validación (DOC-05) — Análisis semántico asistido por IA.

El nivel recibe el texto que produjo el Nivel 3 y lo somete a un modelo de
lenguaje servido por Groq Cloud (qwen/qwen3.8-27b). Solo viaja el texto
extraído, nunca el documento original. El modelo
actúa como extractor estructurado: su única tarea es localizar en el texto el
tipo documental, el RFC, la razón social y las fechas de emisión y vigencia, y
devolverlas en un objeto JSON de forma estricta.

Una decisión de diseño deliberada es que **el veredicto no lo emite el modelo**.
El LLM extrae; el dictamen (coincidencia de titular, vigencia y estatus
preliminar) lo calcula código determinista de este módulo. Así el resultado es
reproducible y auditable ante un revisor, y la responsabilidad del modelo queda
acotada a una tarea de lectura, que es donde su desempeño es fiable.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any
import re
import unicodedata

from clients import groq_client, rules_client
from clients.rules_client import ReglasNoDisponiblesError
from config import settings
from pipelines import fragmentos, verificacion_contenido

# La extracción de datos y la verificación de contenido son dos consultas
# independientes a Groq: corren a la vez y la auditoría espera solo a la más
# lenta. El consumo de tokens es el mismo; solo cambia el tiempo de respuesta.
_verificaciones = ThreadPoolExecutor(max_workers=4, thread_name_prefix="verificacion")

# Catálogo cerrado de tipos documentales, con el rasgo que distingue a cada uno.
#
# El discriminador no es decorativo: un catálogo enumerado a secas obliga al
# modelo a elegir por parecido léxico, y basta un encabezado como "DATOS DE
# IDENTIFICACIÓN DEL CONTRIBUYENTE" para que una constancia fiscal se confunda
# con una identificación oficial. Describir qué caracteriza a cada categoría
# convierte la elección en una comprobación de rasgos y no en una asociación de
# palabras, que es justamente lo que se degrada cuando el texto llega con ruido.
TIPOS_DOCUMENTALES: dict[str, str] = {
    "CONSTANCIA_SITUACION_FISCAL":
        "emitida por el SAT a un contribuyente; trae RFC, régimen fiscal, "
        "domicilio fiscal y cadena original del sello digital",
    "OPINION_CUMPLIMIENTO":
        "emitida por el SAT conforme al artículo 32-D; declara el sentido "
        "positivo o negativo de la opinión de cumplimiento de obligaciones",
    "COMPROBANTE_DOMICILIO":
        "recibo de un servicio (luz, agua, teléfono, predial) con domicilio y "
        "periodo facturado",
    "ACTA_CONSTITUTIVA":
        "instrumento notarial de constitución de una sociedad; menciona "
        "notario, número de escritura, socios y objeto social",
    "ESTADO_CUENTA":
        "carátula bancaria con número de cuenta o CLABE, periodo y saldos",
    "PODER_NOTARIAL":
        "instrumento notarial por el que una persona o sociedad otorga a un apoderado "
        "facultades de representación (pleitos y cobranzas, actos de administración o de dominio)",
    "CONTRATO":
        "acuerdo entre dos o más partes con cláusulas, obligaciones y firmas",
    "POLIZA":
        "contrato de seguro con número de póliza, suma asegurada, coberturas y "
        "periodo de vigencia",
    "LICENCIA":
        "autorización administrativa para operar o ejercer una actividad, "
        "expedida por una autoridad",
    "CERTIFICACION":
        "certificado que acredita el cumplimiento de una norma o estándar",
    "IDENTIFICACION_OFICIAL":
        "credencial de una PERSONA FÍSICA con fotografía (INE, pasaporte, "
        "licencia de conducir, cédula profesional). No lo uses solo porque el "
        "texto contenga la palabra identificación",
    "OTRO":
        "no encaja con claridad en ninguna de las categorías anteriores",
}

# Consulta fija con la que la auditoría elige qué fragmentos de un documento
# extenso ve el modelo, además del encabezado: los datos de identificación que
# extrae (RFC, razón social, fechas) y, para actas y poderes, las cláusulas que
# un auditor revisa (capital social, acciones, comisario, facultades y firmas).
CONSULTA_AUDITORIA = (
    "RFC registro federal de contribuyentes razón social denominación "
    "fecha de emisión fecha de expedición lugar y fecha vigencia vencimiento válido hasta "
    "capital social acciones serie valor nominal comisario consejo de administración "
    "administrador único facultades poder apoderado firma firmas notario corredor público "
    "escritura pública instrumento fe"
)

# Equivalencia entre el catálogo del Nivel 4 y el catálogo oficial de tipos del
# core-service (TipoDocumentoEnum), que es el que usan las reglas de vigencia.
TIPO_A_CATALOGO_CORE: dict[str, str] = {
    "CONSTANCIA_SITUACION_FISCAL": "CSF_SAT",
    "COMPROBANTE_DOMICILIO": "COMP_DOMICILIO",
    "ACTA_CONSTITUTIVA": "ACTA_CONSTITUTIVA",
    "OPINION_CUMPLIMIENTO": "OPINION_CUMPLIMIENTO",
    "ESTADO_CUENTA": "ESTADO_CUENTA",
}

# Tipos del Nivel 4 con los que es compatible cada tipo registrado en el
# expediente. El Cap. I del DOC-01 asigna a la IA confirmar «que el documento sea
# del tipo que el usuario seleccionó». Los tipos sin equivalente en el catálogo
# del Nivel 4 (aviso de privacidad, dictamen pericial, registros sectoriales…)
# no se contrastan: el modelo no tiene con qué clasificarlos.
TIPOS_COMPATIBLES: dict[str, set[str]] = {
    "CSF_SAT": {"CONSTANCIA_SITUACION_FISCAL"},
    "COMP_DOMICILIO": {"COMPROBANTE_DOMICILIO"},
    "ACTA_CONSTITUTIVA": {"ACTA_CONSTITUTIVA"},
    "PODER_NOTARIAL": {"PODER_NOTARIAL", "ACTA_CONSTITUTIVA"},
    "OPINION_CUMPLIMIENTO": {"OPINION_CUMPLIMIENTO"},
    "ESTADO_CUENTA": {"ESTADO_CUENTA"},
    "CONTRATO_SERVICIOS": {"CONTRATO"},
    "ACUERDO_CONFIDENCIALIDAD": {"CONTRATO"},
    "CONVENIO_MODIFICATORIO": {"CONTRATO"},
    "POLIZA_SEGURO": {"POLIZA"},
    "POLIZA_RC": {"POLIZA"},
    "FIANZA": {"POLIZA"},
    "LICENCIA_OPERACION": {"LICENCIA"},
    "PERMISO_SECTORIAL": {"LICENCIA"},
    "CERTIFICACION": {"CERTIFICACION"},
}

# Terminaciones societarias que no distinguen a una empresa de otra al comparar
# razones sociales (S.A. de C.V., S.A.P.I. de C.V., S.C., A.C., S. de R.L.…).
_SUFIJOS_SOCIETARIOS = re.compile(
    r"\b(s\s*a\s*p\s*i|s\s*a\s*b|s\s*a|s\s*de\s*r\s*l|s\s*c|a\s*c|s\s*r\s*l)(\s*de\s*c\s*v)?\b"
)

# RFC mexicano: 3 caracteres para persona moral o 4 para persona física,
# seguidos de la fecha AAMMDD y la homoclave de 3 posiciones.
PATRON_RFC = re.compile(r"^[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}$")

ESTATUS_CONFORME = "CONFORME"
ESTATUS_EN_REVISION = "EN_REVISION"
ESTATUS_NO_CONFORME = "NO_CONFORME"

SYSTEM_PROMPT = (
    "Eres un auditor documental especializado en expedientes corporativos mexicanos "
    "(SAT, CNBV, normatividad PLD). Tu única función es LEER el texto de un documento "
    "y extraer datos verificables.\n"
    "\n"
    "EL TEXTO PROVIENE DE UN RECONOCIMIENTO ÓPTICO Y PUEDE LLEGAR DEGRADADO. "
    "Es normal encontrar acentos perdidos, mayúsculas y minúsculas mezcladas, "
    "caracteres confundidos entre sí (O por 0, I por 1 o l, S por 5, B por 8), "
    "palabras partidas o unidas, espacios dentro de un número y renglones "
    "desordenados o fundidos en uno solo. Interpreta el documento pese a ese "
    "ruido: no lo trates como ilegible ni cambies tu lectura por esos defectos. "
    "Refleja la degradación en el nivel de confianza y en las observaciones, "
    "no en los campos extraídos.\n"
    "\n"
    "Reglas inviolables:\n"
    "1. No inventes ningún dato. Si un campo no aparece de forma explícita en el "
    "texto, devuélvelo como null. No rellenes un hueco con una suposición "
    "verosímil.\n"
    "2. No infieras el RFC a partir del nombre ni completes homoclaves. "
    "Transcríbelo tal como aparece, en mayúsculas y sin espacios ni guiones.\n"
    "3. Las fechas se devuelven siempre en formato ISO 8601 (AAAA-MM-DD).\n"
    "4. Para clasificar el documento decide por el conjunto de rasgos que lo "
    "caracterizan (quién lo emite, qué acredita y qué campos contiene), no por "
    "una palabra suelta del texto. Un encabezado de apartado no determina el "
    "tipo de documento; el título y la autoridad emisora, sí.\n"
    "5. Respondes exclusivamente con un objeto JSON válido, sin texto adicional, "
    "sin explicaciones y sin bloques de código."
)


def _plantilla_prompt(texto: str, rfc_titular: str | None, razon_social_titular: str | None) -> str:
    contexto_titular = "No se proporcionó el titular esperado."
    if rfc_titular or razon_social_titular:
        contexto_titular = (
            f"RFC del titular en el expediente: {rfc_titular or 'no proporcionado'}\n"
            f"Razón social del titular en el expediente: {razon_social_titular or 'no proporcionada'}"
        )

    catalogo = "\n".join(f"  - {clave}: {rasgo}." for clave, rasgo in TIPOS_DOCUMENTALES.items())

    return f"""Analiza el siguiente documento y extrae sus datos de identificación.

=== DATOS DEL TITULAR REGISTRADO EN EL EXPEDIENTE ===
{contexto_titular}

=== TEXTO DEL DOCUMENTO (procedente de reconocimiento óptico) ===
{texto}
=== FIN DEL TEXTO ===

=== CATÁLOGO DE TIPOS DOCUMENTALES ===
Elige exactamente una clave de esta lista. Junto a cada una se indica el rasgo
que la distingue; compara el documento contra esos rasgos antes de decidir.
{catalogo}

Para clasificar, localiza primero el TÍTULO del documento y la AUTORIDAD que lo
emite. Los encabezados de los apartados interiores describen secciones, no el
documento: no decidas a partir de ellos.

Devuelve EXACTAMENTE este objeto JSON, respetando nombres y tipos de cada campo:

{{
  "tipo_documento_detectado": "una clave del catálogo anterior",
  "rfc_detectado": "el RFC que aparece en el documento, en mayúsculas y sin espacios, o null",
  "razon_social_detectada": "el nombre o razón social del titular del documento, o null",
  "fecha_emision": "fecha en que se expidió el documento, AAAA-MM-DD o null. Búscala bajo etiquetas como 'Fecha de emisión', 'Fecha de expedición' o 'Lugar y fecha'. NO la confundas con la fecha de inicio de operaciones, la de alta en el régimen ni la de constitución de la sociedad",
  "fecha_vencimiento": "fecha hasta la que el documento es válido, AAAA-MM-DD o null. Búscala bajo etiquetas como 'Fecha de vencimiento', 'Vigencia hasta' o 'Válido hasta'. Devuelve null solo si el documento no declara vigencia alguna",
  "nivel_confianza": 0.0,
  "observaciones": "una o dos frases en español sobre la legibilidad del texto y cualquier dato faltante o ambiguo"
}}

El campo nivel_confianza es un número entre 0.0 y 1.0 que expresa qué tan seguro
estás de la extracción. Bájalo cuando falten campos clave, cuando el texto llegue
tan degradado que dudes de lo que lees o cuando el tipo documental no sea claro.
Un texto con erratas de reconocimiento pero legible no justifica por sí solo una
confianza baja."""


@dataclass
class ResultadoAnalisis:
    """Dictamen consolidado del Nivel 4."""
    tipo_documento_detectado: str
    rfc_detectado: str | None
    rfc_valido: bool
    match_titular: bool
    razon_social_detectada: str | None
    fecha_emision: str | None
    fecha_vencimiento: str | None
    vigente: bool | None
    dias_para_vencimiento: int | None
    nivel_confianza: float
    estatus_preliminar: str
    requiere_revision_humana: bool
    observaciones: list[str]
    modelo_utilizado: str
    contexto_llm: dict[str, Any] = field(default_factory=dict)
    vigencia_nivel_2: dict[str, Any] = field(default_factory=dict)
    # RFC, RAZON_SOCIAL, NO_LOCALIZADA, AJENA o SIN_REFERENCIA.
    titularidad: str = "SIN_REFERENCIA"
    tipo_coincide: bool | None = None
    verificaciones: list[dict[str, Any]] = field(default_factory=list)
    recomendaciones: list[str] = field(default_factory=list)

    def a_dict(self) -> dict[str, Any]:
        return {
            "tipo_documento_detectado": self.tipo_documento_detectado,
            "rfc_detectado": self.rfc_detectado,
            "rfc_estructura_valida": self.rfc_valido,
            "match_titular": self.match_titular,
            "razon_social_detectada": self.razon_social_detectada,
            "fecha_emision": self.fecha_emision,
            "fecha_vencimiento": self.fecha_vencimiento,
            "vigente": self.vigente,
            "dias_para_vencimiento": self.dias_para_vencimiento,
            "nivel_confianza": round(self.nivel_confianza, 4),
            "estatus_preliminar": self.estatus_preliminar,
            "requiere_revision_humana": self.requiere_revision_humana,
            "umbral_confianza_conforme": settings.UMBRAL_CONFIANZA_CONFORME,
            "umbral_confianza_hitl": settings.UMBRAL_CONFIANZA_HITL,
            "observaciones": self.observaciones,
            "modelo_utilizado": self.modelo_utilizado,
            "contexto_llm": self.contexto_llm,
            "vigencia_nivel_2": self.vigencia_nivel_2,
            "titularidad": self.titularidad,
            "tipo_coincide": self.tipo_coincide,
            "verificaciones": self.verificaciones,
            "recomendaciones": self.recomendaciones,
        }


# ── Normalizadores deterministas ────────────────────────────────────
def normalizar_rfc(valor: Any) -> str | None:
    """Deja el RFC en mayúsculas sin espacios, guiones ni puntos."""
    if not isinstance(valor, str):
        return None
    limpio = re.sub(r"[\s\-.]", "", valor).upper()
    return limpio or None


def normalizar_fecha(valor: Any) -> str | None:
    """Acepta las variantes que suele emitir el modelo y las lleva a ISO 8601."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = valor.strip()
    for formato in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(texto, formato).date().isoformat()
        except ValueError:
            continue
    return None


def normalizar_razon_social(valor: Any) -> str | None:
    """Razón social comparable: sin acentos, signos ni terminación societaria."""
    if not isinstance(valor, str) or not valor.strip():
        return None
    texto = unicodedata.normalize("NFKD", valor.lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    texto = re.sub(r"[^\w\s]", " ", texto)
    texto = _SUFIJOS_SOCIETARIOS.sub(" ", re.sub(r"\s+", " ", texto))
    return re.sub(r"\s+", " ", texto).strip() or None


def _normalizar_confianza(valor: Any) -> float:
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        return 0.0
    # Algunos modelos devuelven la confianza en escala porcentual.
    if numero > 1.0:
        numero = numero / 100.0
    return max(0.0, min(1.0, numero))


def _normalizar_tipo(valor: Any) -> str:
    if not isinstance(valor, str):
        return "OTRO"
    candidato = re.sub(r"[\s\-]", "_", valor.strip().upper())
    return candidato if candidato in TIPOS_DOCUMENTALES else "OTRO"


def _texto_a_lista(valor: Any) -> list[str]:
    if isinstance(valor, list):
        return [str(v).strip() for v in valor if str(v).strip()]
    if isinstance(valor, str) and valor.strip():
        return [valor.strip()]
    return []


# ── Orquestador del Nivel 4 ─────────────────────────────────────────
def analizar(
    texto: str,
    rfc_titular: str | None = None,
    razon_social_titular: str | None = None,
    confianza_extraccion: float | None = None,
    fecha_referencia: date | None = None,
    tipo_documento_registrado: str | None = None,
    criterios_contenido: list[dict[str, Any]] | None = None,
    paginas: list[dict[str, Any]] | None = None,
) -> ResultadoAnalisis:
    """
    Somete el texto al modelo (Groq Cloud) y calcula el dictamen preliminar.

    :param confianza_extraccion: score del Nivel 3. Cuando se recibe, acota por
        arriba la confianza final: por sólido que sea el razonamiento del modelo,
        no puede estar más seguro que la calidad del texto que se le entregó.
    :param tipo_documento_registrado: tipo con el que el documento se registró
        en el expediente (catálogo del core-service). Determina qué reglas de
        vigencia aplican; si falta, se usa el tipo que detectó el modelo.
    :param criterios_contenido: reglas RSC/RDS activas del tipo de documento
        (``rules_client.criterios_contenido``). Si se reciben, una segunda
        consulta verifica que el documento contenga cada elemento.
    :param paginas: ``detalle_paginas`` del Nivel 3; cada fragmento enviado al
        modelo queda asociado a su página en la traza.
    """
    hoy = fecha_referencia or date.today()
    if not texto.strip():
        raise ValueError(
            "No hay texto que analizar: ejecute primero el Nivel 3 (extracción) "
            "o envíe el contenido del documento."
        )

    # La verificación de contenido arranca ya, en paralelo con la extracción.
    verificacion_en_curso = _verificaciones.submit(
        verificacion_contenido.verificar, texto, criterios_contenido or [], paginas
    )

    # Documento extenso: encabezado + fragmentos relevantes, no solo el inicio.
    seleccion = fragmentos.seleccionar(texto, CONSULTA_AUDITORIA, paginas=paginas)

    crudo = groq_client.generar_json(
        prompt=_plantilla_prompt(seleccion.texto, rfc_titular, razon_social_titular),
        system=SYSTEM_PROMPT,
    )

    observaciones = _texto_a_lista(crudo.get("observaciones"))

    tipo = _normalizar_tipo(crudo.get("tipo_documento_detectado"))
    rfc_detectado = normalizar_rfc(crudo.get("rfc_detectado"))
    razon_social = crudo.get("razon_social_detectada")
    razon_social = razon_social.strip() if isinstance(razon_social, str) and razon_social.strip() else None
    fecha_emision = normalizar_fecha(crudo.get("fecha_emision"))
    fecha_vencimiento = normalizar_fecha(crudo.get("fecha_vencimiento"))
    confianza = _normalizar_confianza(crudo.get("nivel_confianza"))

    if confianza_extraccion is not None:
        confianza = min(confianza, confianza_extraccion)

    # Coincidencia de titular: comparación determinista, no delegada al modelo.
    rfc_valido = bool(rfc_detectado and PATRON_RFC.match(rfc_detectado))
    rfc_esperado = normalizar_rfc(rfc_titular)
    if rfc_esperado is None:
        match_titular = False
        observaciones.append(
            "No se proporcionó el RFC del titular: la coincidencia no pudo verificarse."
        )
    elif rfc_detectado is None:
        # Sin RFC en el documento no hay un RFC ajeno: la titularidad se contrasta
        # por la razón social (Cap. I: «el nombre o el RFC»); si tampoco coincide,
        # la decide un analista, porque un dato ausente no prueba que sea de otro.
        esperada = normalizar_razon_social(razon_social_titular)
        match_titular = bool(esperada and esperada == normalizar_razon_social(razon_social))
        if match_titular:
            observaciones.append(
                "El documento no incluye RFC; la titularidad se verificó por la razón social del titular."
            )
        else:
            observaciones.append("No se localizó ningún RFC en el documento.")
    else:
        match_titular = rfc_detectado == rfc_esperado
        if not match_titular:
            observaciones.append(
                f"El RFC del documento ({rfc_detectado}) no coincide con el del "
                f"titular registrado ({rfc_esperado})."
            )

    if rfc_detectado and not rfc_valido:
        observaciones.append(
            f"El RFC extraído ({rfc_detectado}) no respeta la estructura oficial del SAT."
        )

    # Vigencia temporal. Los plazos no se deciden aquí: se consultan las reglas
    # RCV activas del rules-service (Nivel 2). El cálculo local contra la fecha
    # de vencimiento solo se usa como respaldo si ese servicio no responde.
    dias_restantes: int | None = None
    vigente_local: bool | None = None
    if fecha_vencimiento:
        dias_restantes = (date.fromisoformat(fecha_vencimiento) - hoy).days
        vigente_local = dias_restantes >= 0
    vigente, vigencia_pendiente, vigencia_nivel_2, notas_vigencia = _evaluar_vigencia(
        tipo_registrado=tipo_documento_registrado,
        tipo_detectado=tipo,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        hoy=hoy,
        vigente_local=vigente_local,
        dias_restantes=dias_restantes,
    )
    observaciones.extend(notas_vigencia)

    if rfc_esperado is None:
        titularidad = "SIN_REFERENCIA"
    elif rfc_detectado is None:
        titularidad = "RAZON_SOCIAL" if match_titular else "NO_LOCALIZADA"
    else:
        titularidad = "RFC" if match_titular else "AJENA"

    compatibles = TIPOS_COMPATIBLES.get((tipo_documento_registrado or "").upper())
    tipo_coincide = None if compatibles is None else tipo in compatibles
    if tipo_coincide is False:
        observaciones.append(
            f"El documento se registró como {tipo_documento_registrado} pero su contenido corresponde a "
            f"{tipo}; debe confirmarse que se cargó el documento correcto."
        )

    # verificar() nunca lanza por Groq: una falla vuelve como disponible=False con su nota.
    verificacion = verificacion_en_curso.result()
    if verificacion.nota:
        observaciones.append(verificacion.nota)

    estatus, requiere_hitl, motivos = _dictaminar(
        confianza=confianza,
        match_titular=match_titular,
        rfc_esperado=rfc_esperado,
        vigente=vigente,
        vigencia_pendiente=vigencia_pendiente,
        rfc_localizado=rfc_detectado is not None,
        tipo_coincide=tipo_coincide,
        elementos_pendientes=[v["nombre_regla"] for v in verificacion.pendientes],
        elementos_incumplidos=verificacion.incumplidos,
        verificacion_incompleta=not verificacion.disponible,
        reglas_dinamicas=verificacion.incluye_reglas_dinamicas,
    )
    observaciones.extend(motivos)
    recomendaciones = [
        v["recomendacion"] for v in verificacion.incumplidos + verificacion.pendientes if v.get("recomendacion")
    ]

    return ResultadoAnalisis(
        tipo_documento_detectado=tipo,
        rfc_detectado=rfc_detectado,
        rfc_valido=rfc_valido,
        match_titular=match_titular,
        razon_social_detectada=razon_social,
        fecha_emision=fecha_emision,
        fecha_vencimiento=fecha_vencimiento,
        vigente=vigente,
        dias_para_vencimiento=dias_restantes,
        nivel_confianza=confianza,
        estatus_preliminar=estatus,
        requiere_revision_humana=requiere_hitl,
        observaciones=observaciones,
        modelo_utilizado=settings.GROQ_MODEL,
        contexto_llm={
            **seleccion.traza(),
            "uso_tokens": groq_client.uso_de(crudo),
            "uso_tokens_verificacion": verificacion.uso_tokens,
        },
        vigencia_nivel_2=vigencia_nivel_2,
        titularidad=titularidad,
        tipo_coincide=tipo_coincide,
        verificaciones=verificacion.verificaciones,
        recomendaciones=recomendaciones,
    )


def _evaluar_vigencia(
    tipo_registrado: str | None,
    tipo_detectado: str,
    fecha_emision: str | None,
    fecha_vencimiento: str | None,
    hoy: date,
    vigente_local: bool | None,
    dias_restantes: int | None,
) -> tuple[bool | None, bool, dict[str, Any], list[str]]:
    """
    Consulta las reglas de vigencia del rules-service.

    Devuelve (vigente, vigencia_pendiente, traza, observaciones). ``vigente`` es
    False solo ante un vencimiento comprobado; ``vigencia_pendiente`` obliga a la
    revisión humana cuando la vigencia no pudo verificarse (faltan fechas o el
    rules-service no respondió), porque aprobar sin esa verificación podría dar
    por bueno un comprobante con más antigüedad de la permitida.
    """
    tipo_regla = (tipo_registrado or TIPO_A_CATALOGO_CORE.get(tipo_detectado) or tipo_detectado).upper()
    traza: dict[str, Any] = {
        "tipo_evaluado": tipo_regla,
        "origen_tipo": "registrado" if tipo_registrado else "detectado",
    }
    notas: list[str] = []
    try:
        respuesta = rules_client.evaluar_vigencia(tipo_regla, fecha_emision, fecha_vencimiento, hoy)
    except ReglasNoDisponiblesError as exc:
        traza.update(disponible=False, detalle=str(exc))
        notas.append("No fue posible consultar las reglas de vigencia del rules-service (:8002); la antigüedad "
                     "máxima del documento no se verificó y el caso se turna a revisión humana.")
        if vigente_local is False:
            notas.append(f"El documento venció el {fecha_vencimiento} ({abs(dias_restantes)} días atrás).")
        return vigente_local, vigente_local is not False, traza, notas

    traza.update(disponible=True, **respuesta)
    resultado = respuesta.get("resultado")
    for evaluacion in respuesta.get("evaluaciones", []):
        if evaluacion.get("resultado") in ("VENCIDO", "INDETERMINADO"):
            notas.append(f"{evaluacion['codigo_regla']} ({evaluacion['nombre_regla']}): {evaluacion['detalle']}")
    if resultado == "VENCIDO":
        return False, False, traza, notas
    if resultado == "INDETERMINADO":
        return None, True, traza, notas
    if resultado in ("VIGENTE", "PROXIMO_A_VENCER"):
        return True, False, traza, notas
    return vigente_local, False, traza, notas   # SIN_REGLAS: ninguna regla de vigencia cubre el documento


def _dictaminar(
    confianza: float,
    match_titular: bool,
    rfc_esperado: str | None,
    vigente: bool | None,
    vigencia_pendiente: bool = False,
    rfc_localizado: bool = True,
    tipo_coincide: bool | None = None,
    elementos_pendientes: list[str] | None = None,
    elementos_incumplidos: list[dict[str, Any]] | None = None,
    verificacion_incompleta: bool = False,
    reglas_dinamicas: bool = False,
) -> tuple[str, bool, list[str]]:
    """
    Reglas deterministas que convierten la extracción en un estatus preliminar.

    Reproduce la clasificación en tres estados del DOC-08 §6.2. El orden importa:
    un hecho que descalifica el documento —RFC ajeno o vigencia expirada— pesa
    más que cualquier confianza, mientras que una confianza insuficiente nunca
    produce un rechazo automático. La duda del modelo es una duda sobre la
    lectura, no sobre el documento, y por eso deriva al Nivel 5 de gobernanza
    humana en lugar de resolverse en contra del expediente.
    """
    motivos: list[str] = []

    if vigente is False:
        return (
            ESTATUS_NO_CONFORME,
            False,
            motivos + ["Dictamen NO_CONFORME: la vigencia del documento ya expiró."],
        )

    if rfc_esperado is not None and rfc_localizado and not match_titular:
        return (
            ESTATUS_NO_CONFORME,
            False,
            motivos + ["Dictamen NO_CONFORME: el documento no pertenece al titular del expediente."],
        )

    # Un elemento que el documento contradice de forma explícita (hoy, una
    # opinión 32-D en sentido negativo) es un hecho del documento, como la
    # vigencia expirada: pesa más que cualquier duda sobre la titularidad.
    if elementos_incumplidos:
        detalle = "; ".join(f"{v['nombre_regla']} ({v['codigo_regla']}): {v['observacion']}"
                            for v in elementos_incumplidos)
        return (
            ESTATUS_NO_CONFORME,
            False,
            motivos + [f"Dictamen NO_CONFORME: el documento incumple un requisito de forma explícita. {detalle}"],
        )

    if rfc_esperado is None:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: sin RFC de referencia no es posible cerrar la "
                "verificación de titularidad en automático."
            ],
        )

    if not match_titular:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: el documento no incluye RFC y su razón social no coincide con la del "
                "titular; un analista debe confirmar a quién pertenece."
            ],
        )

    if tipo_coincide is False:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: el tipo de documento detectado no corresponde al tipo con el que se "
                "registró en el expediente."
            ],
        )

    if vigencia_pendiente:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: la vigencia del documento no pudo verificarse contra las "
                "reglas RCV; un analista debe confirmarla antes de aprobarlo."
            ],
        )

    if elementos_pendientes:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: omisión relevante; no se localizaron o no pudieron verificarse "
                f"estos elementos: {', '.join(elementos_pendientes)} (RSC-01)."
            ],
        )

    if verificacion_incompleta:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos + ["Dictamen EN_REVISION: la verificación de contenido del documento no pudo completarse."],
        )

    if reglas_dinamicas:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                "Dictamen EN_REVISION: el documento se evaluó con criterios definidos por el usuario (RDS-02), "
                "que siempre requieren ratificación humana (RDS-03)."
            ],
        )

    if confianza < settings.UMBRAL_CONFIANZA_HITL:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                f"Dictamen EN_REVISION: la confianza ({confianza:.2f}) queda por debajo "
                f"de la banda de revisión ({settings.UMBRAL_CONFIANZA_HITL:.2f}); la "
                "lectura no es fiable y el caso se turna al Nivel 5."
            ],
        )

    if confianza < settings.UMBRAL_CONFIANZA_CONFORME:
        return (
            ESTATUS_EN_REVISION,
            True,
            motivos
            + [
                f"Dictamen EN_REVISION: la confianza ({confianza:.2f}) se sitúa en la "
                f"banda de ratificación humana "
                f"({settings.UMBRAL_CONFIANZA_HITL:.2f} a "
                f"{settings.UMBRAL_CONFIANZA_CONFORME - 0.01:.2f}) definida en el DOC-08."
            ],
        )

    return (
        ESTATUS_CONFORME,
        False,
        motivos + ["Dictamen CONFORME: titularidad y vigencia verificadas con confianza suficiente."],
    )
