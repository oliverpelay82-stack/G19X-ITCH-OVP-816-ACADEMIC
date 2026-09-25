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
import time

from fastapi import APIRouter, HTTPException, status

from clients import core_client, groq_client
from clients.core_client import CoreNoDisponibleError, DocumentoAlteradoError, DocumentoNoEncontradoError
from clients.groq_client import GroqNoDisponibleError, GroqRespuestaInvalidaError
from config import settings
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import fragmentos, repositorio_texto
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError
from schemas.analisis_schema import AnalisisSemanticoRequest, ChatDocumentoRequest

router = APIRouter(prefix="/api/v1/ai", tags=["Nivel 4 — Análisis Semántico con IA"])

SYSTEM_PROMPT_CHAT = (
    "Eres un asistente de cumplimiento documental de PluriOne. Respondes preguntas "
    "sobre un documento que se te entrega como contexto. Reglas: responde únicamente "
    "con información contenida en el documento; si la respuesta no está ahí, dilo "
    "explícitamente en lugar de suponerla; cita textualmente la parte relevante cuando "
    "exista; responde en español, de forma breve y profesional. Si el contexto está "
    "formado por fragmentos separados por […], son extractos del mismo documento "
    "elegidos por su relevancia para la pregunta."
)


def _documento(documento_id: str, forzar_ocr: bool = False) -> repositorio_texto.TextoDocumento:
    """Resuelve el texto de un documento de la bóveda y traduce los errores a HTTP."""
    try:
        return repositorio_texto.obtener_por_documento(documento_id, forzar_ocr)
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
    documento_id: str | None, texto: str | None, forzar_ocr: bool = False
) -> tuple[str, repositorio_texto.TextoDocumento | None, str]:
    """Devuelve (texto, documento resuelto o None, fuente del texto)."""
    if texto and texto.strip():
        return texto.strip(), None, "cliente"
    documento = _documento(documento_id or "", forzar_ocr)
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
    Deja listo el texto del documento en memoria y en disco. Si ya se había
    extraído, responde al instante; si no, ejecuta el Nivel 3 una única vez.
    """
    inicio = time.perf_counter()
    documento = _documento(documento_id)
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
    texto, documento, fuente = _resolver_contenido(peticion.documento_id, peticion.texto, peticion.forzar_ocr)
    ms_texto = _ms(inicio)

    confianza_extraccion = documento.traza.get("confidence_score") if documento else None

    inicio = time.perf_counter()
    try:
        resultado = pipeline_analisis.analizar(
            texto=texto,
            rfc_titular=peticion.rfc_titular,
            razon_social_titular=peticion.razon_social_titular,
            confianza_extraccion=confianza_extraccion,
            # El tipo registrado en el expediente decide qué reglas de vigencia aplican.
            tipo_documento_registrado=(documento.metadatos or {}).get("tipo_documento") if documento else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except GroqNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 4] {exc}"
        ) from exc
    except GroqRespuestaInvalidaError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=f"[Nivel 4] {exc}"
        ) from exc

    respuesta = resultado.a_dict()
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
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
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
    seleccion = fragmentos.seleccionar(texto, consulta, max_fragmentos=settings.MAX_FRAGMENTOS_CHAT)

    mensajes = [
        {"role": "system", "content": SYSTEM_PROMPT_CHAT},
        {"role": "system", "content": f"=== CONTENIDO DEL DOCUMENTO ===\n{seleccion.texto}\n=== FIN ==="},
    ]
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

    respuesta = {
        "pregunta": peticion.pregunta,
        "respuesta": contenido,
        "modelo_utilizado": settings.GROQ_MODEL,
        "caracteres_de_contexto": len(seleccion.texto),
        "contexto_truncado": seleccion.recortado,
        "contexto_llm": seleccion.traza(),
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
