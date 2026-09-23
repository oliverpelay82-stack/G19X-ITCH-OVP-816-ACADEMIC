"""
Controlador del Nivel 3 — Extracción de texto (DOC-05).

Expone el pipeline híbrido (lectura vectorial con PyMuPDF + OCR con
preprocesamiento OpenCV/Tesseract) como un endpoint de carga directa, de modo
que pueda auditarse un archivo suelto sin necesidad de haberlo registrado antes
en la bóveda del core-service.
"""
from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status

from config import settings
from pipelines import extraccion_pipeline
from pipelines.extraccion_pipeline import FormatoNoSoportadoError, MotorOcrNoDisponibleError

router = APIRouter(prefix="/api/v1/ai", tags=["Nivel 3 — Extracción de Texto"])


@router.post(
    "/extraer-texto",
    status_code=status.HTTP_200_OK,
    summary="Extraer el texto de un PDF o imagen (capa vectorial + OCR con preprocesamiento)",
)
async def extraer_texto(
    file: UploadFile = File(..., description="Documento PDF, JPEG o PNG (máximo 15 MB)."),
    forzar_ocr: bool = Form(
        False,
        description="Ignora la capa vectorial del PDF y rasteriza todas las páginas para pasarlas por OCR.",
    ),
    incluir_texto: bool = Form(
        True,
        description="Devuelve el texto completo. Desactívelo para obtener solo las métricas.",
    ),
):
    """
    Resuelve el Nivel 3 del pipeline y devuelve el texto junto con su
    *confidence score*, el método que resolvió cada página y la señal de
    escalamiento al Nivel 5 cuando la legibilidad es insuficiente.
    """
    contenido = await file.read()

    try:
        resultado = extraccion_pipeline.extraer_texto(
            contenido=contenido,
            nombre_archivo=file.filename or "documento",
            forzar_ocr=forzar_ocr,
        )
    except FormatoNoSoportadoError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"[Nivel 3] {exc}") from exc
    except MotorOcrNoDisponibleError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=f"[Nivel 3] {exc}"
        ) from exc

    respuesta = resultado.a_dict()
    respuesta["archivo"] = file.filename
    respuesta["tamanio_bytes"] = len(contenido)
    if not incluir_texto:
        respuesta.pop("texto_extraido", None)
    return respuesta


@router.get(
    "/configuracion-ocr",
    summary="Consultar los parámetros activos del motor OCR",
)
def configuracion_ocr():
    """Expone la configuración efectiva del Nivel 3 para efectos de auditoría."""
    return {
        "motor": extraccion_pipeline.diagnostico_ocr(),
        "umbral_caracteres_pagina": settings.UMBRAL_CARACTERES_PAGINA,
        "umbral_confianza_conforme": settings.UMBRAL_CONFIANZA_CONFORME,
        "umbral_confianza_hitl": settings.UMBRAL_CONFIANZA_HITL,
        "tamanio_maximo_mb": settings.MAX_FILE_SIZE_BYTES // (1024 * 1024),
        "preprocesamiento": [
            "Conversión a escala de grises (cv2.cvtColor)",
            "Filtro bilateral de reducción de ruido (cv2.bilateralFilter)",
            "Binarización automática de Otsu (cv2.threshold + THRESH_OTSU)",
            "Corrección de polaridad tinta/fondo",
        ],
    }
