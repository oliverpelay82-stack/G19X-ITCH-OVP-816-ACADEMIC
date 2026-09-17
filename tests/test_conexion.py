"""
Script simple de verificación de conexión a MySQL.
Ejecuta: python test_conexion.py
"""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from config.database import engine
from sqlalchemy import text

def probar():
    print("=" * 60)
    print("Probando conexión a MySQL (plurione_compliance)...")
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT VERSION();"))
            version = result.scalar()
            print(f"[OK] Conexión exitosa a MySQL!")
            print(f"[OK] Versión detectada: {version}")
        print("=" * 60)
        return True
    except Exception as e:
        print("[ERROR] No se pudo conectar a MySQL.")
        print(f"Detalle del error: {e}")
        print("\nSugerencia: Revisa que la contraseña en el archivo .env sea la correcta.")
        print("=" * 60)
        return False

if __name__ == "__main__":
    probar()
