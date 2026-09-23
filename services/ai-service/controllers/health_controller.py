"""
Controlador de Salud (Health Check) del AI Service.

A diferencia de los otros microservicios, aquí el health check no solo declara
que el proceso está vivo: verifica las dos dependencias externas de las que
depende el análisis —Groq Cloud con su modelo disponible y el motor OCR
Tesseract— para que el frontend pueda avisar al operador *antes* de que intente
analizar un expediente y se encuentre con un error a mitad del flujo.

El endpoint responde siempre 200: un 5xx haría que Docker Compose reiniciara el
contenedor en ciclo cuando el único problema es que falta configurar la API key.
"""
from fastapi import APIRouter

from clients import groq_client
from config import settings
from pipelines import extraccion_pipeline

router = APIRouter(prefix="/api/v1", tags=["Salud"])


@router.get("/health", summary="Estado de salud del ai-service, de Groq y del motor OCR")
def health_check():
    estado_groq = groq_client.verificar_estado()
    estado_ocr = extraccion_pipeline.diagnostico_ocr()

    operativo = estado_groq["modelo_disponible"] and estado_ocr["disponible"]

    return {
        "status": "online",
        "servicio": "ai-service",
        "puerto": 8003,
        "modo_despliegue": "cloud-groq",
        "capacidades_operativas": operativo,
        "motor_inferencia": {
            "proveedor": "Groq Cloud",
            "endpoint": settings.GROQ_BASE_URL,
            "temperatura_auditoria": settings.GROQ_TEMPERATURE,
            **estado_groq,
        },
        "motor_ocr": {
            "proveedor": "Tesseract",
            **estado_ocr,
        },
        "bandas_confianza": {
            "conforme_desde": settings.UMBRAL_CONFIANZA_CONFORME,
            "revision_humana_desde": settings.UMBRAL_CONFIANZA_HITL,
        },
        "umbral_confianza_hitl": settings.UMBRAL_CONFIANZA_HITL,
    }
