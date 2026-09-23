"""
Controlador del Nivel 4 — Análisis semántico y consulta conversacional.

Reúne los dos puntos de contacto con el modelo de lenguaje (Groq Cloud):

  * ``POST /api/v1/ai/analisis-semantico`` — dictamen estructurado del documento
    (tipo documental, RFC, fechas, coincidencia con el titular y estatus
    preliminar), pensado para alimentar el tablero de cumplimiento.
  * ``POST /api/v1/ai/chat-documento`` — interrogatorio en lenguaje natural
    sobre un documento concreto, para que el analista resuelva dudas puntuales
    sin tener que leer el expediente completo.
"""
from fastapi import APIRouter, HTTPException, status

from clients import core_client, groq_client
from clients.core_client import DocumentoNoEncontradoError
from clients.groq_client import GroqNoDisponibleError, GroqRespuestaInvalidaError
from config import settings
from pipelines import analisis_semantico as pipeline_analisis
from pipelines import extraccion_pipeline
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError
from schemas.analisis_schema import AnalisisSemanticoRequest, ChatDocumentoRequest

router = APIRouter(prefix="/api/v1/ai", tags=["Nivel 4 — Análisis Semántico con IA"])

SYSTEM_PROMPT_CHAT = (
    "Eres un asistente de cumplimiento documental de PluriOne. Respondes preguntas "
    "sobre un documento que se te entrega como contexto. Reglas: responde únicamente "
    "con información contenida en el documento; si la respuesta no está ahí, dilo "
    "explícitamente en lugar de suponerla; cita textualmente la parte relevante cuando "
    "exista; responde en español, de forma breve y profesional."
)


def _resolver_contenido(
    documento_id: str | None, texto: str | None, forzar_ocr: bool = False
) -> tuple[str, dict | None, dict | None]:
    """
    Obtiene el texto a analizar y, cuando procede, la traza de su extracción.

    Devuelve la tripleta (texto, metadatos del documento, resumen del Nivel 3).
    Si el cliente envió el texto directamente, las dos últimas son ``None``.
    """
    if texto and texto.strip():
        return texto.strip(), None, None

    try:
        contenido, metadatos = core_client.obtener_binario(documento_id or "")
    except DocumentoNoEncontradoError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        extraccion = extraccion_pipeline.extraer_texto(
            contenido=contenido,
            nombre_archivo=metadatos.get("nombre_archivo_original", "documento"),
            forzar_ocr=forzar_ocr,
        )
    except FormatoNoSoportadoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"[Nivel 3] {exc}") from exc
    except MotorOcrNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 3] {exc}"
        ) from exc

    return extraccion.texto, metadatos, extraccion.a_dict(incluir_paginas=False)


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
    texto, metadatos, traza_extraccion = _resolver_contenido(
        peticion.documento_id, peticion.texto, peticion.forzar_ocr
    )

    confianza_extraccion = traza_extraccion["confidence_score"] if traza_extraccion else None

    try:
        resultado = pipeline_analisis.analizar(
            texto=texto,
            rfc_titular=peticion.rfc_titular,
            razon_social_titular=peticion.razon_social_titular,
            confianza_extraccion=confianza_extraccion,
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
    if metadatos:
        respuesta["documento"] = {
            "id": metadatos.get("id"),
            "nombre_archivo_original": metadatos.get("nombre_archivo_original"),
            "tipo_documento_registrado": metadatos.get("tipo_documento"),
            "hash_sha256": metadatos.get("hash_sha256"),
        }
    if traza_extraccion:
        respuesta["extraccion_nivel_3"] = traza_extraccion
    return respuesta


@router.post(
    "/chat-documento",
    status_code=status.HTTP_200_OK,
    summary="Preguntar en lenguaje natural sobre el contenido de un documento",
)
def chat_documento(peticion: ChatDocumentoRequest):
    """
    Responde una pregunta del analista usando el documento como único contexto.

    El documento se inyecta como mensaje de sistema en cada turno en lugar de
    confiarlo a la memoria de la conversación: garantiza que el modelo siempre
    tenga el texto completo delante y evita que el hilo lo desplace de la
    ventana de contexto.
    """
    texto, metadatos, traza_extraccion = _resolver_contenido(peticion.documento_id, peticion.texto)

    if not texto.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="[Nivel 4] El documento no tiene texto legible sobre el cual responder.",
        )

    contexto = texto[: settings.MAX_CARACTERES_CONTEXTO]
    mensajes = [
        {"role": "system", "content": SYSTEM_PROMPT_CHAT},
        {"role": "system", "content": f"=== CONTENIDO DEL DOCUMENTO ===\n{contexto}\n=== FIN ==="},
    ]
    for turno in peticion.historial:
        rol = "assistant" if turno.rol.lower().startswith("asist") else "user"
        mensajes.append({"role": rol, "content": turno.contenido})
    mensajes.append({"role": "user", "content": peticion.pregunta})

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
        "caracteres_de_contexto": len(contexto),
        "contexto_truncado": len(texto) > len(contexto),
    }
    if metadatos:
        respuesta["documento"] = {
            "id": metadatos.get("id"),
            "nombre_archivo_original": metadatos.get("nombre_archivo_original"),
        }
    if traza_extraccion:
        respuesta["extraccion_nivel_3"] = traza_extraccion
    return respuesta
