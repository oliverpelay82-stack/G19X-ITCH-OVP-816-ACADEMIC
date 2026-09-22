"""
Controlador de Salud (Health Check) del AI Service.
Sprint 0 (Semana 4): el servicio se deja vivo únicamente con su health check.
La lógica de análisis semántico con IA (Nivel 3 y 4 del pipeline, DOC-05) se
implementará a partir de la Semana 5.
"""
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1", tags=["Salud"])


@router.get("/health", summary="Estado de salud del ai-service")
def health_check():
    return {
        "status": "online",
        "servicio": "ai-service",
        "puerto": 8003,
        "estado": "preparado_para_semana_5",
    }
