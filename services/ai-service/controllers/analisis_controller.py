"""
Controlador del Nivel 4 — Análisis semántico y consulta conversacional.

Reúne los puntos de contacto con el modelo de lenguaje (Groq Cloud):

  * ``POST /api/v1/ai/documentos/{id}/preparar`` — resuelve el texto del
    documento (Nivel 3) sin llamar al modelo. El frontend lo usa como primera
    etapa visible de la auditoría ("Leyendo documento…").
  * ``POST /api/v1/ai/analisis-semantico`` — dictamen estructurado del documento
    (tipo documental, RFC, fechas, coincidencia con el titular y estatus
    preliminar), pensado para alimentar el tablero de cumplimiento.
  * ``POST /api/v1/ai/chat-documento`` — interrogatorio en lenguaje natural
    sobre un documento concreto, para que el analista resuelva dudas puntuales
    sin tener que leer el expediente completo.

El texto de cada documento se resuelve una sola vez (memoria → SQLite → OCR,
ver ``pipelines/repositorio_texto.py``). Al modelo no se le envía el inicio del
documento, sino su encabezado y los fragmentos más relevantes para la consulta
(``pipelines/fragmentos.py``), de modo que una cláusula de la página 26 es tan
alcanzable como una de la página 1. Cada respuesta informa de dónde salió el
texto, qué fragmentos vio el modelo y cuánto tardó cada fase.
"""
import re
import threading
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

from fastapi import APIRouter, HTTPException, status

from clients import core_client, groq_client, rules_client
from clients.core_client import CoreNoDisponibleError, DocumentoAlteradoError, DocumentoNoEncontradoError
from clients.groq_client import GroqNoDisponibleError, GroqRespuestaInvalidaError
from clients.rules_client import ReglasNoDisponiblesError
from config import settings
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import (
    cache_chat, fragmentos, pasajes, persistencia_texto, presupuesto_tokens, repositorio_texto, respuestas_directas,
    verificacion_contenido,
)
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError, version_lectura
from pipelines.version_instrucciones import version_instrucciones
from pipelines import cuota_diaria, diferidos, legibilidad, qr_sat
from schemas.analisis_schema import AnalisisSemanticoRequest, ChatDocumentoRequest

router = APIRouter(prefix="/api/v1/ai", tags=["Nivel 4 — Análisis Semántico con IA"])

SYSTEM_PROMPT_CHAT = (
    "Eres el asistente de cumplimiento documental de PluriOne. Respondes las preguntas del "
    "analista sobre UN documento con dos fuentes: el CONTENIDO DEL DOCUMENTO y su ESTADO EN "
    "EL SISTEMA (tipo registrado, dictamen del motor y elementos que el catálogo exige a ese tipo).\n"
    "Reglas:\n"
    "1. Responde solo con lo que dicen esas fuentes. Si un dato no aparece, dilo explícitamente "
    "(«No aparece en el texto disponible») y sugiere qué sección o documento revisar; nunca lo supongas.\n"
    "2. Empieza por la respuesta directa, en una o dos frases, con los datos clave en **negritas**.\n"
    "3. Sustenta cada dato tomado del documento con una cita LITERAL y breve entre comillas angulares "
    "«…», copiada tal cual del contenido; no la parafrasees.\n"
    "4. Si te preguntan qué falta, qué se recomienda o si el documento cumple, básate en el dictamen y "
    "en los elementos del catálogo; no inventes requisitos que no estén en esas fuentes y recuerda que "
    "la decisión final corresponde al analista. NO_LOCALIZADO significa que el elemento no se encontró; "
    "NO_VERIFICABLE, que no pudo confirmarse con una cita (no que falte): si el contenido del documento "
    "sí lo muestra, dilo con su cita. NO_CUMPLE significa que el documento contradice el requisito de "
    "forma explícita (por ejemplo, una opinión de cumplimiento en sentido negativo).\n"
    "5. El texto puede provenir de un reconocimiento óptico con errores; interprétalo pese al ruido y "
    "advierte cuando un dato clave sea dudoso.\n"
    "6. Responde en español, de forma profesional y concisa (máximo ocho renglones, salvo que pidan un "
    "resumen). Los fragmentos separados por […] son extractos del mismo documento elegidos por su "
    "relevancia para la pregunta."
)

# Preguntas generales sobre el documento («resume», «¿qué le falta?», «¿cumple?»):
# no apuntan a una palabra concreta del texto, así que la búsqueda de fragmentos
# se amplía con los datos que revisa la auditoría y los criterios del catálogo.
_PREGUNTA_GENERAL = re.compile(
    r"\b(resum|trata|falta|recomiend|recomendac|cumple|cumplimiento|revis|analiz|clave|observac|"
    r"vigen|venc|dictamen|problema|riesgo|valid|correct|complet)"
)
# Citas entre comillas angulares en la respuesta del modelo.
_CITA = re.compile(r"«([^»]{8,400})»")


def _es_pregunta_general(pregunta: str) -> bool:
    normalizada = unicodedata.normalize("NFKD", pregunta.lower())
    return bool(_PREGUNTA_GENERAL.search("".join(c for c in normalizada if not unicodedata.combining(c))))


def _estado_en_sistema(
    documento: repositorio_texto.TextoDocumento | None, criterios: list[dict], dictamen: dict | None,
    breve: bool = False,
) -> str | None:
    """
    Resumen del documento dentro del sistema: tipo, dictamen vigente y elementos exigidos.
    ``breve`` (T2): solo tipo, dictamen y fechas, para preguntas puntuales sobre el contenido;
    las reglas evaluadas y los elementos exigidos van en las preguntas generales.
    """
    if documento is None or not documento.metadatos:
        return None
    meta = documento.metadatos
    lineas = [
        f"Archivo: {meta.get('nombre_archivo_original')}",
        f"Tipo registrado en el expediente: {meta.get('tipo_documento')}",
    ]
    if dictamen:
        ratificado = f"sí, por {dictamen.get('revisado_por')}" if dictamen.get("revisado_por_humano") else "no"
        confianza = dictamen.get("nivel_confianza")
        lineas += [
            f"Dictamen vigente del motor: {dictamen.get('estatus')} (preliminar {dictamen.get('estatus_preliminar')}; "
            f"confianza {f'{confianza:.2f}' if isinstance(confianza, (int, float)) else 'no disponible'}; "
            f"ratificado por un analista: {ratificado})",
            # «No extraída por el motor», no «no declarada»: que la auditoría no la extrajera
            # no prueba que el documento no la tenga, y el modelo la repetía como ausencia.
            f"Fechas extraídas: emisión {dictamen.get('fecha_emision_extraida') or 'no extraída por el motor'}, "
            f"vencimiento {dictamen.get('fecha_vencimiento_extraida') or 'no extraído por el motor'}; "
            f"vigencia según las reglas: {dictamen.get('vigencia_resultado') or 'no evaluada'}",
        ]
        if breve:
            return "\n".join(lineas)
        reglas = [r for r in dictamen.get("reglas_aplicadas") or [] if r.get("codigo_regla")]
        if reglas:
            lineas.append("Reglas evaluadas:")
            for r in reglas[:12]:
                recomendacion = f" Recomendación: {r['recomendacion']}" if r.get("recomendacion") else ""
                lineas.append(f"- {r['codigo_regla']} {r.get('nombre_regla') or ''}: {r.get('resultado')}. "
                              f"{r.get('detalle') or ''}{recomendacion}".strip())
        for obs in (dictamen.get("observaciones") or [])[:4]:
            lineas.append(f"Observación del dictamen: {obs}")
    else:
        lineas.append("El documento aún no tiene dictamen del motor.")
    if criterios and not breve:
        lineas.append("Elementos que el catálogo exige a este tipo de documento: "
                      + "; ".join(c["nombre_regla"] for c in criterios))
    return "\n".join(lineas)


# T4 (PLUS-11): el dictamen se consulta al core en paralelo con la lectura del
# texto; los criterios del catálogo se conservan unos minutos en memoria.
_consultas_chat = ThreadPoolExecutor(max_workers=4, thread_name_prefix="chat-estado")
_criterios_en_memoria: dict[str, tuple[float, list[dict]]] = {}
_candado_criterios = threading.Lock()


def _criterios_chat(tipo_documento: str | None) -> list[dict]:
    """
    Criterios de contenido del tipo de documento para el chat, con vencimiento de
    ``CHAT_TTL_CRITERIOS_SEGUNDOS``. La auditoría no los usa: consulta siempre al
    rules-service, porque una regla pausada debe dejar de exigirse de inmediato.
    Un fallo del rules-service no se guarda.
    """
    clave = (tipo_documento or "").upper()
    ahora = time.monotonic()
    with _candado_criterios:
        guardado = _criterios_en_memoria.get(clave)
    if guardado and ahora - guardado[0] < settings.CHAT_TTL_CRITERIOS_SEGUNDOS:
        return guardado[1]
    try:
        criterios = rules_client.criterios_contenido(tipo_documento)
    except ReglasNoDisponiblesError:
        return []
    with _candado_criterios:
        _criterios_en_memoria[clave] = (ahora, criterios)
    return criterios


def _historial_acotado(historial: list) -> list:
    """
    T2: los últimos ``CHAT_MENSAJES_HISTORIAL`` mensajes, con cada respuesta previa del
    asistente recortada. El documento se vuelve a buscar en cada turno, así que el
    historial solo aporta el tema de la conversación.
    """
    recientes = list(historial)[-settings.CHAT_MENSAJES_HISTORIAL:] if settings.CHAT_MENSAJES_HISTORIAL else []
    acotado = []
    for turno in recientes:
        contenido = turno.contenido
        if turno.rol.lower().startswith("asist") and len(contenido) > settings.CHAT_CARACTERES_TURNO_ASISTENTE:
            contenido = contenido[:settings.CHAT_CARACTERES_TURNO_ASISTENTE].rsplit(" ", 1)[0] + "…"
        acotado.append(SimpleNamespace(rol=turno.rol, contenido=contenido))
    return acotado


def _mensajes_chat(
    contexto: str, estado: str | None, historial: list, pregunta: str
) -> list[dict[str, str]]:
    mensajes = [{"role": "system", "content": SYSTEM_PROMPT_CHAT}]
    if estado:
        mensajes.append({"role": "system", "content": f"=== ESTADO EN EL SISTEMA ===\n{estado}\n=== FIN ==="})
    mensajes.append({"role": "system", "content": f"=== CONTENIDO DEL DOCUMENTO ===\n{contexto}\n=== FIN ==="})
    for turno in historial:
        rol = "assistant" if turno.rol.lower().startswith("asist") else "user"
        mensajes.append({"role": rol, "content": turno.contenido})
    mensajes.append({"role": "user", "content": pregunta})
    return mensajes


def _marcar_citas(contenido: str, texto: str, estado: str | None) -> list[dict]:
    """
    Cada cita «…» se contrasta con el texto completo y, si no está ahí, con el
    estado en el sistema (una recomendación del catálogo, p. ej.). La que no
    aparece literalmente en ninguna fuente se señala en lugar de presentarse
    como evidencia.
    """
    citas = []
    for c in _CITA.findall(str(contenido)):
        fuente_cita = (
            "documento" if verificacion_contenido.cita_literal(c, texto)
            else "sistema" if estado and verificacion_contenido.cita_en_texto(c, estado)
            else None
        )
        citas.append({"texto": c.strip(), "verificada": fuente_cita is not None, "fuente": fuente_cita})
    return citas


def _con_documento(respuesta: dict, documento: repositorio_texto.TextoDocumento | None, documento_id: str | None):
    if documento and documento.metadatos:
        respuesta["documento"] = {
            "id": documento.metadatos.get("id"),
            "nombre_archivo_original": documento.metadatos.get("nombre_archivo_original"),
        }
    if documento:
        respuesta["extraccion_nivel_3"] = _estado_lectura(documento_id, documento)
    return respuesta


def _respuesta_desde_dictamen(
    pregunta: str, texto: str, documento: repositorio_texto.TextoDocumento | None, dictamen: dict | None
) -> str | None:
    """
    T0 (PLUS-07): respuesta con los datos de la última auditoría, sin modelo. Solo si
    la ficha guardada es la del dictamen vigente y el dictamen es el de este binario.
    """
    if not documento or not documento.sha256 or not dictamen or dictamen.get("hash_sha256") != documento.sha256:
        return None
    guardada = persistencia_texto.leer_ficha(documento.sha256)
    if not guardada or guardada["dictamen_id"] != dictamen.get("id"):
        return None
    return respuestas_directas.responder(pregunta, texto, guardada["ficha"], dictamen)


def _documento(
    documento_id: str, forzar_ocr: bool = False, completar_en_fondo: bool = True, texto_completo: bool = False
) -> repositorio_texto.TextoDocumento:
    """Resuelve el texto de un documento de la bóveda y traduce los errores a HTTP."""
    try:
        return repositorio_texto.obtener_por_documento(documento_id, forzar_ocr, completar_en_fondo, texto_completo)
    except DocumentoNoEncontradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except DocumentoAlteradoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except CoreNoDisponibleError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except FormatoNoSoportadoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"[Nivel 3] {exc}") from exc
    except MotorOcrNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 3] {exc}"
        ) from exc


def _resolver_contenido(
    documento_id: str | None,
    texto: str | None,
    forzar_ocr: bool = False,
    completar_en_fondo: bool = True,
    texto_completo: bool = False,
) -> tuple[str, repositorio_texto.TextoDocumento | None, str]:
    """Devuelve (texto, documento resuelto o None, fuente del texto)."""
    if texto and texto.strip():
        return texto.strip(), None, "cliente"
    documento = _documento(documento_id or "", forzar_ocr, completar_en_fondo, texto_completo)
    return documento.texto, documento, documento.fuente


def _estado_lectura(documento_id: str | None, documento: repositorio_texto.TextoDocumento | None) -> dict:
    """Resumen del Nivel 3 que acompaña a cada respuesta."""
    if documento is None:
        return {}
    traza = {k: v for k, v in documento.traza.items() if k != "detalle_paginas"}
    traza["lectura_completa"] = documento.completo
    traza["lectura_completa_en_curso"] = bool(documento_id) and repositorio_texto.lectura_completa_en_curso(
        documento_id
    )
    return traza


def _sellos_del_documento(documento: repositorio_texto.TextoDocumento | None) -> list[dict]:
    """Sellos en tinta de color detectados por el Nivel 3, con su página y recuadro normalizado."""
    if documento is None:
        return []
    return [
        {"pagina": p["pagina"], **sello}
        for p in documento.traza.get("detalle_paginas") or []
        for sello in p.get("sellos") or []
    ]


def _observaciones_de_sellos(documento: repositorio_texto.TextoDocumento | None, sellos: list[dict]) -> list[str]:
    """
    Presencia de sellos como evidencia del dictamen (DOC-08: «presencia de
    Sello Digital SAT»; los sellos físicos identifican al fedatario o al
    registro). Es informativa: no cambia el estatus, que siguen decidiendo las
    reglas.
    """
    observaciones = []
    if sellos:
        paginas = ", ".join(str(n) for n in sorted({s["pagina"] for s in sellos}))
        observaciones.append(f"Se detectaron sellos en tinta de color en la(s) página(s) {paginas}; "
                             "su presencia puede verificarse en el visor del documento.")
    if documento and documento.traza.get("sello_digital_sat"):
        observaciones.append("El documento incluye el Sello Digital del SAT (cadena original o sello digital).")
    return observaciones


def _ms(inicio: float) -> int:
    return round((time.perf_counter() - inicio) * 1000)


def versiones_dictamen() -> dict[str, str | None]:
    """
    Versión de la lectura del Nivel 3 y huella de las instrucciones (P5, dictamen
    reproducible), más la versión del catálogo de reglas (M6).
    """
    return {"version_lectura": version_lectura(), "version_instrucciones": version_instrucciones(),
            "version_catalogo": rules_client.version_catalogo()}


def _persistir_dictamen(
    documento_id: str, resultado: pipeline_analisis.ResultadoAnalisis, usuario: str, origen: str | None = None,
    qr: dict | None = None,
) -> dict:
    """
    Guarda el dictamen en el core-service (tabla dictamenes_auditoria y
    bitácora). Si el core no responde, el dictamen se devuelve igualmente pero
    marcado como no persistido, para que la interfaz no lo presente como
    definitivo. Una alteración RIE-03 detectada en ese momento sí se propaga.
    """
    rfc = resultado.rfc_detectado if resultado.rfc_detectado and len(resultado.rfc_detectado) <= 13 else None
    carga = {
        "documento_id": documento_id,
        "estatus": resultado.estatus_preliminar,
        "nivel_confianza": round(resultado.nivel_confianza, 4),
        "requiere_revision_humana": resultado.requiere_revision_humana,
        "tipo_documento_detectado": resultado.tipo_documento_detectado,
        "rfc_detectado": rfc,
        # Un documento ilegible no se cotejó: no hay coincidencia que informar.
        "match_titular": None if origen == ORIGEN_ILEGIBLE else resultado.match_titular,
        "fecha_emision": resultado.fecha_emision,
        "fecha_vencimiento": resultado.fecha_vencimiento,
        "vigencia": resultado.vigencia_nivel_2 or None,
        "observaciones": resultado.observaciones,
        "verificaciones": resultado.verificaciones,
        "representacion": resultado.representacion,
        "modelo_utilizado": resultado.modelo_utilizado,
        # P5: con qué lectura e instrucciones se emitió, para reproducirlo.
        **versiones_dictamen(),
        **({"origen": origen} if origen else {}),
        **({"qr_sat": qr} if qr else {}),
        "usuario": usuario,
    }
    try:
        return {"guardado": True, "dictamen": core_client.registrar_dictamen(carga)}
    except DocumentoAlteradoError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except (CoreNoDisponibleError, DocumentoNoEncontradoError) as exc:
        return {"guardado": False, "detalle": str(exc)}


@router.post(
    "/documentos/{documento_id}/preparar",
    status_code=status.HTTP_200_OK,
    summary="Resolver el texto de un documento (Nivel 3) sin invocar al modelo",
)
def preparar_documento(documento_id: str):
    """
    Deja listo el texto del documento completo en memoria y en disco. Si ya se
    había leído, responde al instante; si no, ejecuta el Nivel 3 sobre todas
    las páginas una única vez. Es la primera etapa de la auditoría: después, el
    análisis, el chat y el visor reutilizan esa lectura.
    """
    inicio = time.perf_counter()
    documento = _documento(documento_id, completar_en_fondo=False, texto_completo=True)
    return {
        "documento_id": documento_id,
        "fuente_texto": documento.fuente,
        "extraccion_nivel_3": _estado_lectura(documento_id, documento),
        "tiempos_ms": {"resolucion_texto": _ms(inicio)},
    }


@router.post(
    "/analisis-semantico",
    status_code=status.HTTP_200_OK,
    summary="Dictaminar un documento con el modelo de lenguaje (tipo, RFC, vigencia y estatus)",
)
def analizar_documento(peticion: AnalisisSemanticoRequest):
    """
    Ejecuta el Nivel 4 sobre el documento indicado (ver ``auditar``).

    P5 (DOC-05, Tabla 1): si el proveedor de IA no responde tras sus 3 intentos,
    la auditoría de un documento de la bóveda queda en la cola de procesamiento
    diferido, el core muestra la alerta y la respuesta es 503 con esa explicación.
    """
    try:
        return auditar(peticion)
    except GroqNoDisponibleError as exc:
        if not peticion.documento_id:
            raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 4] {exc}") from exc
        diferida = diferidos.registrar_fallo(peticion.model_dump(mode="json"), str(exc))
        core_client.marcar_diferido(diferida.documento_id, diferida.aviso())
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=("El servicio de IA no respondió tras 3 intentos. La auditoría quedó programada y se "
                    "reintentará automáticamente (procesamiento diferido)."),
        ) from exc


ORIGEN_ILEGIBLE = "NIVEL_3_ILEGIBLE"


def _auditoria_ilegible(
    peticion: AnalisisSemanticoRequest, documento: repositorio_texto.TextoDocumento, motivo: str
) -> dict:
    """
    P5 (DOC-05, Tabla 1): dictamen «Documento ilegible, se requiere recarga» sin
    llamar al modelo. Queda En revisión, con origen NIVEL_3_ILEGIBLE, y el core
    lo distingue de una revisión por contenido.
    """
    confianza = float(documento.traza.get("confidence_score") or 0.0)
    tipo_registrado = (documento.metadatos or {}).get("tipo_documento")
    resultado = pipeline_analisis.ResultadoAnalisis(
        tipo_documento_detectado=tipo_registrado or "DESCONOCIDO",
        rfc_detectado=None, rfc_valido=False, match_titular=False, razon_social_detectada=None,
        fecha_emision=None, fecha_vencimiento=None, vigente=None, dias_para_vencimiento=None,
        nivel_confianza=min(max(confianza, 0.0), 1.0),
        estatus_preliminar="EN_REVISION",
        requiere_revision_humana=True,
        observaciones=[f"Documento ilegible, se requiere recarga: {motivo}"],
        modelo_utilizado="sin modelo (lectura ilegible)",
        recomendaciones=["Recargar el archivo con mejor resolución (escaneo a 300 ppp, sin sombras ni inclinación)."],
    )
    respuesta = resultado.a_dict()
    respuesta["ilegible"] = True
    respuesta["fuente_texto"] = documento.fuente
    respuesta["versiones"] = versiones_dictamen()
    respuesta["tiempos_ms"] = {"resolucion_texto": 0, "inferencia": 0}
    respuesta["extraccion_nivel_3"] = _estado_lectura(peticion.documento_id, documento)
    respuesta["persistencia"] = _persistir_dictamen(peticion.documento_id, resultado, peticion.usuario, ORIGEN_ILEGIBLE)
    return respuesta


def _qr_del_documento(
    documento: repositorio_texto.TextoDocumento | None, tipo: str | None, rfc_referencia: str | None
) -> dict | None:
    """
    PLUS-17: QR del SAT de una constancia, opinión 32-D o cédula. Lee el binario
    verificado por el core; si el core no lo entrega, la auditoría sigue sin QR.
    """
    metadatos = (documento.metadatos or {}) if documento else {}
    if tipo not in qr_sat.TIPOS_CON_QR or metadatos.get("mime_type", "application/pdf") != "application/pdf":
        return None
    try:
        contenido = core_client.leer_binario(metadatos)
    except (CoreNoDisponibleError, DocumentoNoEncontradoError, DocumentoAlteradoError):
        return None
    return qr_sat.leer(contenido, rfc_referencia)


def _tope_revision(resultado: pipeline_analisis.ResultadoAnalisis, motivos: list[str], qr: dict | None) -> None:
    """
    Una señal del archivo deja la auditoría En revisión (Nivel 5: la decide un
    analista); no cambia un No conforme. El primer motivo explica la revisión.
    """
    if qr and qr.get("url"):
        resultado.recomendaciones.append(f"Validar el documento en el portal del SAT con su código QR: {qr['url']}")
    if not motivos:
        return
    resultado.requiere_revision_humana = True
    if resultado.estatus_preliminar == "CONFORME":
        resultado.estatus_preliminar = "EN_REVISION"
        primero, *demas = motivos
        resultado.observaciones.append(f"Dictamen EN_REVISION: {primero[:1].lower()}{primero[1:]}")
        resultado.observaciones.extend(demas)
    else:
        resultado.observaciones.extend(motivos)


def auditar(peticion: AnalisisSemanticoRequest) -> dict:
    """
    Ejecuta el Nivel 4 sobre el documento indicado.

    La inferencia corre a temperatura 0.0 contra Groq Cloud, de modo
    que un mismo documento produzca siempre el mismo dictamen. El veredicto
    (``estatus_preliminar``) lo calculan reglas deterministas a partir de lo que
    el modelo extrajo, no el modelo mismo.
    """
    inicio = time.perf_counter()
    # La auditoría lee todas las páginas: la verificación de contenido busca
    # elementos que pueden estar al final del documento.
    texto, documento, fuente = _resolver_contenido(
        peticion.documento_id, peticion.texto, peticion.forzar_ocr, completar_en_fondo=False, texto_completo=True
    )
    paginas = (documento.traza.get("detalle_paginas") if documento else None) or None
    ms_texto = _ms(inicio)

    # P5: sin texto suficiente no hay nada que analizar; tampoco se gasta cuota del modelo.
    if documento and peticion.documento_id:
        motivo = legibilidad.motivo_ilegible(documento.texto, documento.traza)
        if motivo:
            return _auditoria_ilegible(peticion, documento, motivo)

    confianza_extraccion = documento.traza.get("confidence_score") if documento else None
    tipo_registrado = (documento.metadatos or {}).get("tipo_documento") if documento else None

    # Elementos que el catálogo exige a este tipo de documento (reglas RSC y RDS).
    # Sin rules-service la auditoría continúa: la vigencia ya se turna a revisión
    # humana en ese caso, y la nota explica que el contenido no se verificó.
    nota_criterios = None
    try:
        criterios = rules_client.criterios_contenido(tipo_registrado)
    except ReglasNoDisponiblesError:
        criterios = []
        nota_criterios = ("No fue posible consultar los criterios de contenido del catálogo; los elementos del "
                          "documento no se verificaron.")

    inicio = time.perf_counter()
    try:
        resultado = pipeline_analisis.analizar(
            texto=texto,
            rfc_titular=peticion.rfc_titular,
            razon_social_titular=peticion.razon_social_titular,
            confianza_extraccion=confianza_extraccion,
            # El tipo registrado en el expediente decide qué reglas de vigencia aplican.
            tipo_documento_registrado=tipo_registrado,
            criterios_contenido=criterios,
            paginas=paginas,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)) from exc
    except GroqRespuestaInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"[Nivel 4] {exc}"
        ) from exc

    if nota_criterios:
        resultado.observaciones.append(nota_criterios)
    # P6 (PLUS-16 a PLUS-18): las señales del archivo que calculó el core y el QR
    # del SAT llevan la auditoría a revisión humana; nunca la rechazan.
    qr = _qr_del_documento(documento, tipo_registrado, peticion.rfc_titular or resultado.rfc_detectado)
    motivos_archivo = list(((documento.metadatos or {}).get("senales_revision") or []) if documento else [])
    _tope_revision(resultado, motivos_archivo + qr_sat.motivos(qr), qr)
    sellos_detectados = _sellos_del_documento(documento)
    resultado.observaciones.extend(_observaciones_de_sellos(documento, sellos_detectados))
    respuesta = resultado.a_dict()
    respuesta["sellos"] = sellos_detectados
    respuesta["sello_digital_sat"] = bool(documento and documento.traza.get("sello_digital_sat"))
    respuesta["fuente_texto"] = fuente
    respuesta["versiones"] = versiones_dictamen()
    respuesta["qr_sat"] = qr
    respuesta["tiempos_ms"] = {"resolucion_texto": ms_texto, "inferencia": _ms(inicio)}
    if documento and documento.metadatos:
        respuesta["documento"] = {
            "id": documento.metadatos.get("id"),
            "nombre_archivo_original": documento.metadatos.get("nombre_archivo_original"),
            "tipo_documento_registrado": documento.metadatos.get("tipo_documento"),
            "hash_sha256": documento.metadatos.get("hash_sha256"),
        }
    if documento:
        respuesta["extraccion_nivel_3"] = _estado_lectura(peticion.documento_id, documento)
    # Solo el dictamen de un documento de la bóveda se persiste: un texto suelto
    # enviado por el cliente no pertenece a ningún expediente.
    if documento and peticion.documento_id:
        respuesta["persistencia"] = _persistir_dictamen(peticion.documento_id, resultado, peticion.usuario, qr=qr)
        # T0 (PLUS-07): ficha de lo verificado, ligada al dictamen que el core acaba de guardar.
        dictamen_guardado = respuesta["persistencia"].get("dictamen") or {}
        if respuesta["persistencia"].get("guardado") and dictamen_guardado.get("id") and documento.sha256:
            persistencia_texto.guardar_ficha(
                documento.sha256, dictamen_guardado["id"],
                respuestas_directas.ficha_de(resultado, tipo_registrado, respuesta["sello_digital_sat"]),
            )
    return respuesta


@router.post(
    "/chat-documento",
    status_code=status.HTTP_200_OK,
    summary="Preguntar en lenguaje natural sobre el contenido de un documento",
)
def chat_documento(peticion: ChatDocumentoRequest):
    """
    Responde una pregunta del analista usando el documento como único contexto.

    En cada turno se eligen los fragmentos del documento más relevantes para la
    pregunta (más el encabezado) y se inyectan como mensaje de sistema. Así el
    modelo alcanza cualquier cláusula del documento sin exceder el límite de
    tokens de Groq, y el hilo de la conversación no desplaza al documento.
    """
    inicio = time.perf_counter()
    dictamen_en_curso = (
        _consultas_chat.submit(core_client.ultimo_dictamen, peticion.documento_id)
        if peticion.documento_id and not (peticion.texto or "").strip() else None
    )
    try:
        texto, documento, fuente = _resolver_contenido(peticion.documento_id, peticion.texto)
    except HTTPException:
        if dictamen_en_curso:
            dictamen_en_curso.cancel()
        raise
    ms_texto = _ms(inicio)

    if not texto.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="[Nivel 4] El documento no tiene texto legible sobre el cual responder.",
        )

    dictamen = dictamen_en_curso.result() if dictamen_en_curso else None
    directa = None if peticion.forzar_modelo else _respuesta_desde_dictamen(
        peticion.pregunta, texto, documento, dictamen)
    if directa:
        return _con_documento({
            "pregunta": peticion.pregunta,
            "respuesta": directa,
            "citas": _marcar_citas(directa, texto, None),
            "con_estado_del_sistema": True,
            # DATOS_DEL_DICTAMEN (PLUS-07): sin modelo, sin fragmentos y sin tokens.
            "origen_respuesta": "DATOS_DEL_DICTAMEN",
            "modelo_utilizado": None,
            "caracteres_de_contexto": 0,
            "contexto_truncado": False,
            "contexto_llm": {"estrategia_contexto": "datos_del_dictamen",
                             "uso_tokens": dict(cache_chat.USO_DESDE_CACHE, desde_cache=False)},
            "fuente_texto": fuente,
            "tiempos_ms": {"resolucion_texto": ms_texto, "inferencia": 0},
        }, documento, peticion.documento_id)

    # T1 (PLUS-08): la cláusula nombrada o el monto, como pasaje literal con su página.
    paginas = (documento.traza.get("detalle_paginas") if documento else None) or None
    pasaje = None if peticion.forzar_modelo else pasajes.responder(peticion.pregunta, texto, paginas)
    if pasaje:
        contenido, pagina = pasaje
        return _con_documento({
            "pregunta": peticion.pregunta,
            "respuesta": contenido,
            "citas": _marcar_citas(contenido, texto, None),
            "con_estado_del_sistema": False,
            "origen_respuesta": "PASAJE_DEL_DOCUMENTO",
            "modelo_utilizado": None,
            "caracteres_de_contexto": 0,
            "contexto_truncado": False,
            "contexto_llm": {"estrategia_contexto": "pasaje_del_documento", "pagina": pagina,
                             "uso_tokens": dict(cache_chat.USO_DESDE_CACHE, desde_cache=False)},
            "fuente_texto": fuente,
            "tiempos_ms": {"resolucion_texto": ms_texto, "inferencia": 0},
        }, documento, peticion.documento_id)

    # En un seguimiento corto ("¿y quién lo firma?") la pregunta anterior aporta
    # el tema; una pregunta completa se busca sola para no arrastrar el anterior.
    consulta = peticion.pregunta
    if len(fragmentos.tokenizar(consulta)) < 3:
        anterior = next(
            (t.contenido for t in reversed(peticion.historial) if not t.rol.lower().startswith("asist")), ""
        )
        consulta = f"{consulta} {anterior}"

    tipo_registrado = (documento.metadatos or {}).get("tipo_documento") if documento else None
    criterios = _criterios_chat(tipo_registrado) if tipo_registrado else []

    general = _es_pregunta_general(peticion.pregunta)
    if general:
        consulta = " ".join([consulta, pipeline_analisis.CONSULTA_AUDITORIA,
                             *(f"{c['nombre_regla']} {c['criterio']}" for c in criterios)])
        seleccion = fragmentos.seleccionar(texto, consulta, max_fragmentos=settings.MAX_FRAGMENTOS_CHAT + 2,
                                           paginas=paginas)
    else:
        # T2 (PLUS-09): una pregunta puntual recibe un contexto enfocado y el estado breve.
        seleccion = fragmentos.seleccionar_enfocado(
            texto, consulta, presupuesto=settings.CHAT_PRESUPUESTO_PUNTUAL,
            max_fragmentos=settings.CHAT_FRAGMENTOS_PUNTUALES, paginas=paginas)

    estado = _estado_en_sistema(documento, criterios, dictamen, breve=not general)
    historial = _historial_acotado(peticion.historial)
    mensajes = _mensajes_chat(seleccion.texto, estado, historial, peticion.pregunta)

    inicio = time.perf_counter()
    # T3 (PLUS-10): a temperatura 0.0 una respuesta ya obtenida se reutiliza. La clave
    # por pregunta normalizada solo aplica al primer turno: con historial, el sentido
    # de una pregunta corta depende de lo anterior.
    claves: list[str | None] = []
    if cache_chat.activo() and not peticion.forzar_modelo:
        claves.append(cache_chat.clave_exacta(mensajes, settings.CHAT_MAX_TOKENS))
        if not peticion.historial and documento:
            claves.append(cache_chat.clave_pregunta(documento.sha256, estado, peticion.pregunta))
    contenido = cache_chat.leer(claves)
    origen = "CACHE" if contenido is not None else "MODELO"
    presupuesto = None
    if contenido is None and presupuesto_tokens.presupuesto.activo():
        # T4 (PLUS-11): si la petición no cabe en lo que queda del minuto (una auditoría
        # acaba de consumir la cuota), se acota el contexto en lugar de esperar los
        # reintentos del SDK. La respuesta a un contexto acotado no se guarda bajo las
        # claves del contexto completo.
        estimado = presupuesto_tokens.estimar(mensajes)
        usados = presupuesto_tokens.presupuesto.usados()
        presupuesto = {"limite": presupuesto_tokens.presupuesto.limite, "usados_ultimo_minuto": usados,
                       "estimado": estimado, "reducido": False}
        if not presupuesto_tokens.presupuesto.cabe(estimado):
            seleccion = fragmentos.seleccionar(
                texto, consulta, max_fragmentos=2, paginas=paginas,
                presupuesto=settings.MAX_CARACTERES_CONTEXTO // 3,
            )
            mensajes = _mensajes_chat(seleccion.texto, estado, historial[-2:], peticion.pregunta)
            claves = [cache_chat.clave_exacta(mensajes, settings.CHAT_MAX_TOKENS)] if claves else []
            presupuesto.update(reducido=True, estimado_reducido=presupuesto_tokens.estimar(mensajes))
    if contenido is None:
        try:
            contenido = groq_client.conversar(mensajes)
        except GroqNoDisponibleError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 4] {exc}"
            ) from exc
        cache_chat.guardar(claves, contenido)

    respuesta = {
        "pregunta": peticion.pregunta,
        "respuesta": contenido,
        "citas": _marcar_citas(contenido, texto, estado),
        "con_estado_del_sistema": bool(estado),
        # MODELO o CACHE (PLUS-10); las respuestas sin modelo usan DATOS_DEL_DICTAMEN (PLUS-07)
        # o PASAJE_DEL_DOCUMENTO (PLUS-08). Campo opcional.
        "origen_respuesta": origen,
        "modelo_utilizado": settings.GROQ_MODEL,
        "caracteres_de_contexto": len(seleccion.texto),
        "contexto_truncado": seleccion.recortado,
        "contexto_llm": {**seleccion.traza(), "uso_tokens": groq_client.uso_de(contenido),
                         **({"presupuesto_tokens": presupuesto} if presupuesto else {})},
        "fuente_texto": fuente,
        "tiempos_ms": {"resolucion_texto": ms_texto, "inferencia": _ms(inicio)},
    }
    return _con_documento(respuesta, documento, peticion.documento_id)


# ── P5 (DOC-05, Tabla 1): ciclo de procesamiento diferido ──────────────

class _SinReintento(Exception):
    """El documento ya no puede auditarse (no existe, está alterado o no es legible por formato)."""


class _ReintentarDespues(Exception):
    """Algo externo no respondió (el proveedor o el core): se reintenta en la siguiente vuelta."""


def _auditar_diferida(peticion: dict) -> None:
    try:
        auditar(AnalisisSemanticoRequest(**peticion))
    except GroqNoDisponibleError as exc:
        raise _ReintentarDespues(str(exc)) from exc
    except HTTPException as exc:
        if exc.status_code >= 500 and exc.status_code != status.HTTP_502_BAD_GATEWAY:
            raise _ReintentarDespues(str(exc.detail)) from exc
        raise _SinReintento(str(exc.detail)) from exc


def procesar_diferidos() -> dict[str, int]:
    """Una vuelta del ciclo en segundo plano (lo arranca main.py)."""
    # PLUS-19: con la cuota diaria agotada, reintentar solo gastaría intentos.
    if cuota_diaria.agotada():
        return {"auditadas": 0, "reprogramadas": 0, "agotadas": 0, "descartadas": 0}
    return diferidos.procesar_vencidas(
        _auditar_diferida, core_client.marcar_diferido, _ReintentarDespues, (_SinReintento,)
    )

