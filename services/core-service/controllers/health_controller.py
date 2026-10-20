"""
Controlador de Salud (Health Check) del Core Service.
Permite a Docker Compose y al frontend verificar que el servicio está vivo
y que su conexión con PostgreSQL funciona correctamente.
"""
from fastapi import APIRouter
from sqlalchemy import text

from config import cifrado_boveda, seguridad
from config.database import engine

router = APIRouter(prefix="/api/v1", tags=["Salud"])


@router.get("/health", summary="Estado de salud del core-service")
def health_check():
    conexion_bd = False
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        conexion_bd = True
    except Exception:
        conexion_bd = False

    advertencias = []
    if seguridad.usa_secreto_demostracion():
        advertencias.append("Las sesiones se firman con el secreto de demostración: defina JWT_SECRET en el .env.")
    # RNF-04: sin llave la bóveda guarda los documentos en claro.
    if not cifrado_boveda.activo():
        advertencias.append("La bóveda guarda los documentos sin cifrar: defina BOVEDA_LLAVE en el .env.")
    elif cifrado_boveda.usa_llave_demostracion():
        advertencias.append("La bóveda se cifra con la llave de demostración: defina BOVEDA_LLAVE en el .env.")

    return {
        "status": "online",
        "servicio": "core-service",
        "puerto": 8001,
        "conexion_bd": conexion_bd,
        "version": "1.0.0",
        # Módulo 7 y RNF-04: el secreto y la llave de demostración del docker-compose no sirven para producción.
        "advertencias": advertencias,
    }
