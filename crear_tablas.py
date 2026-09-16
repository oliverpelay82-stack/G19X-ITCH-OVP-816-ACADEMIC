"""
Script para sincronizar las tablas en MySQL (ddl-auto=update).
Ejecuta: python crear_tablas.py
"""
from config.database import init_db
from models import TitularExpediente

if __name__ == "__main__":
    print("=" * 60)
    print("Creando tablas en MySQL (plurione_compliance)...")
    init_db()
    print("=" * 60)
