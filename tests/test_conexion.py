"""
Script simple de verificación de conexión a PostgreSQL, usando la
configuración del core-service (ambos microservicios apuntan a la misma
base de datos física 'plurione_compliance').
Ejecuta: python test_conexion.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("core-service")

from config.database import engine
from sqlalchemy import text

def probar():
    print("=" * 60)
    print("Probando conexión a PostgreSQL (plurione_compliance)...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION();"))
            version = result.scalar()
            print("[OK] Conexión exitosa a PostgreSQL!")
            print(f"[OK] Versión detectada: {version}")
        print("=" * 60)
        return True
    except Exception as e:
        print("[ERROR] No se pudo conectar a PostgreSQL.")
        print(f"Detalle del error: {e}")
        print("\nSugerencia: Revisa que la contraseña en el archivo .env sea la correcta.")
        print("=" * 60)
        return False

def test_conexion_postgresql():
    assert probar(), "No se pudo conectar a PostgreSQL con la configuración del core-service"


if __name__ == "__main__":
    probar()
