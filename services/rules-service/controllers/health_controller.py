"""
Controlador de Salud (Health Check) del Rules Service.
Permite a Docker Compose y al frontend verificar que el servicio está vivo
y que su conexión con PostgreSQL funciona correctamente.
"""
from fastapi import APIRouter
from sqlalchemy import text

from config.database import engine

router = APIRouter(prefix="/api/v1", tags=["Salud"])


@router.get("/health", summary="Estado de salud del rules-service")
def health_check():
    conexion_bd = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        conexion_bd = True
    except Exception:
        conexion_bd = False

    return {
        "status": "online",
        "servicio": "rules-service",
        "puerto": 8002,
        "conexion_bd": conexion_bd,
    }
