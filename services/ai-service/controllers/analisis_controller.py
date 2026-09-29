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
import time
import unicodedata

from fastapi import APIRouter, HTTPException, status

from clients import core_client, groq_client, rules_client
from clients.core_client import CoreNoDisponibleError, DocumentoAlteradoError, DocumentoNoEncontradoError
from clients.groq_client import GroqNoDisponibleError, GroqRespuestaInvalidaError
from clients.rules_client import ReglasNoDisponiblesError
from config import settings
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import fragmentos, repositorio_texto, verificacion_contenido
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError
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


def _estado_en_sistema(documento: repositorio_texto.TextoDocumento | None, criterios: list[dict]) -> str | None:
    """Resumen del documento dentro del sistema: tipo, dictamen vigente y elementos exigidos."""
    if documento is None or not documento.metadatos:
        return None
    meta = documento.metadatos
    lineas = [
        f"Archivo: {meta.get('nombre_archivo_original')}",
        f"Tipo registrado en el expediente: {meta.get('tipo_documento')}",
    ]
    dictamen = core_client.ultimo_dictamen(meta.get("id", ""))
    if dictamen:
        ratificado = f"sí, por {dictamen.get('revisado_por')}" if dictamen.get("revisado_por_humano") else "no"
        confianza = dictamen.get("nivel_confianza")
        lineas += [
            f"Dictamen vigente del motor: {dictamen.get('estatus')} (preliminar {dictamen.get('estatus_preliminar')}; "
            f"confianza {f'{confianza:.2f}' if isinstance(confianza, (int, float)) else 'no disponible'}; "
            f"ratificado por un analista: {ratificado})",
            f"Fechas extraídas: emisión {dictamen.get('fecha_emision_extraida') or 'no localizada'}, "
            f"vencimiento {dictamen.get('fecha_vencimiento_extraida') or 'no declarado'}; "
            f"vigencia según las reglas: {dictamen.get('vigencia_resultado') or 'no evaluada'}",
        ]
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
    if criterios:
        lineas.append("Elementos que el catálogo exige a este tipo de documento: "
                      + "; ".join(c["nombre_regla"] for c in criterios))
    return "\n".join(lineas)


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


def _persistir_dictamen(documento_id: str, resultado: pipeline_analisis.ResultadoAnalisis, usuario: str) -> dict:
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
        "match_titular": resultado.match_titular,
        "fecha_emision": resultado.fecha_emision,
        "fecha_vencimiento": resultado.fecha_vencimiento,
        "vigencia": resultado.vigencia_nivel_2 or None,
        "observaciones": resultado.observaciones,
        "verificaciones": resultado.verificaciones,
        "modelo_utilizado": resultado.modelo_utilizado,
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
    except GroqNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 4] {exc}"
        ) from exc
    except GroqRespuestaInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"[Nivel 4] {exc}"
        ) from exc

    if nota_criterios:
        resultado.observaciones.append(nota_criterios)
    sellos_detectados = _sellos_del_documento(documento)
    resultado.observaciones.extend(_observaciones_de_sellos(documento, sellos_detectados))
    respuesta = resultado.a_dict()
    respuesta["sellos"] = sellos_detectados
    respuesta["sello_digital_sat"] = bool(documento and documento.traza.get("sello_digital_sat"))
    respuesta["fuente_texto"] = fuente
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
        respuesta["persistencia"] = _persistir_dictamen(peticion.documento_id, resultado, peticion.usuario)
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
    texto, documento, fuente = _resolver_contenido(peticion.documento_id, peticion.texto)
    ms_texto = _ms(inicio)

    if not texto.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="[Nivel 4] El documento no tiene texto legible sobre el cual responder.",
        )

    # En un seguimiento corto ("¿y quién lo firma?") la pregunta anterior aporta
    # el tema; una pregunta completa se busca sola para no arrastrar el anterior.
    consulta = peticion.pregunta
    if len(fragmentos.tokenizar(consulta)) < 3:
        anterior = next(
            (t.contenido for t in reversed(peticion.historial) if not t.rol.lower().startswith("asist")), ""
        )
        consulta = f"{consulta} {anterior}"

    tipo_registrado = (documento.metadatos or {}).get("tipo_documento") if documento else None
    try:
        criterios = rules_client.criterios_contenido(tipo_registrado)
    except ReglasNoDisponiblesError:
        criterios = []

    max_fragmentos = settings.MAX_FRAGMENTOS_CHAT
    if _es_pregunta_general(peticion.pregunta):
        consulta = " ".join([consulta, pipeline_analisis.CONSULTA_AUDITORIA,
                             *(f"{c['nombre_regla']} {c['criterio']}" for c in criterios)])
        max_fragmentos += 2
    paginas = (documento.traza.get("detalle_paginas") if documento else None) or None
    seleccion = fragmentos.seleccionar(texto, consulta, max_fragmentos=max_fragmentos, paginas=paginas)

    mensajes = [{"role": "system", "content": SYSTEM_PROMPT_CHAT}]
    estado = _estado_en_sistema(documento, criterios)
    if estado:
        mensajes.append({"role": "system", "content": f"=== ESTADO EN EL SISTEMA ===\n{estado}\n=== FIN ==="})
    mensajes.append(
        {"role": "system", "content": f"=== CONTENIDO DEL DOCUMENTO ===\n{seleccion.texto}\n=== FIN ==="}
    )
    for turno in peticion.historial:
        rol = "assistant" if turno.rol.lower().startswith("asist") else "user"
        mensajes.append({"role": rol, "content": turno.contenido})
    mensajes.append({"role": "user", "content": peticion.pregunta})

    inicio = time.perf_counter()
    try:
        contenido = groq_client.conversar(mensajes)
    except GroqNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 4] {exc}"
        ) from exc

    # Cada cita «…» se contrasta con el texto completo y, si no está ahí, con el
    # estado en el sistema (una recomendación del catálogo, p. ej.). La que no
    # aparece literalmente en ninguna fuente se señala en lugar de presentarse
    # como evidencia.
    citas = []
    for c in _CITA.findall(str(contenido)):
        fuente = (
            "documento" if verificacion_contenido.cita_literal(c, texto)
            else "sistema" if estado and verificacion_contenido.cita_en_texto(c, estado)
            else None
        )
        citas.append({"texto": c.strip(), "verificada": fuente is not None, "fuente": fuente})
    respuesta = {
        "pregunta": peticion.pregunta,
        "respuesta": contenido,
        "citas": citas,
        "con_estado_del_sistema": bool(estado),
        "modelo_utilizado": settings.GROQ_MODEL,
        "caracteres_de_contexto": len(seleccion.texto),
        "contexto_truncado": seleccion.recortado,
        "contexto_llm": {**seleccion.traza(), "uso_tokens": groq_client.uso_de(contenido)},
        "fuente_texto": fuente,
        "tiempos_ms": {"resolucion_texto": ms_texto, "inferencia": _ms(inicio)},
    }
    if documento and documento.metadatos:
        respuesta["documento"] = {
            "id": documento.metadatos.get("id"),
            "nombre_archivo_original": documento.metadatos.get("nombre_archivo_original"),
        }
    if documento:
        respuesta["extraccion_nivel_3"] = _estado_lectura(peticion.documento_id, documento)
    return respuesta
