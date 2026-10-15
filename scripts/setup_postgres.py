"""
Script de inicialización de Base de Datos PostgreSQL para la arquitectura de
microservicios desacoplados.
1. Crea la base de datos 'plurione_compliance' si no existe.
2. Sincroniza las tablas de 'core-service' (titulares_expediente, expedientes,
   documentos) y de 'rules-service' (reglas_validacion), cada uno en su
   propio subproceso (ver scripts/crear_tablas.py para el porqué).
3. Precarga el catálogo de reglas de validación (DOC-05) vía rules-service.
4. Crea un titular y expediente de demostración vía core-service.

Ejecuta (desde la raíz del proyecto): python scripts/setup_postgres.py
"""
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
CORE_SERVICE_DIR = ROOT / "services" / "core-service"
RULES_SERVICE_DIR = ROOT / "services" / "rules-service"

load_dotenv(CORE_SERVICE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "plurione_compliance")

print(f"[*] Conectando a PostgreSQL en {DB_HOST}:{DB_PORT} con usuario '{DB_USER}'...")

# Paso 1: Conectar a la base default 'postgres' para crear 'plurione_compliance' si no existe
try:
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
    if not cursor.fetchone():
        cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"[+] Base de datos '{DB_NAME}' creada con éxito en PostgreSQL.")
    else:
        print(f"[i] La base de datos '{DB_NAME}' ya existe.")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"[!] Error conectando a PostgreSQL inicial: {e}")
    exit(1)

# Paso 2: Sincronizar tablas de cada microservicio (subproceso aislado por servicio)
print("\n[*] Sincronizando tablas de los microservicios...")
INIT_DB_SNIPPET = "from config.database import init_db; init_db()"
for nombre, carpeta in [("core-service", CORE_SERVICE_DIR), ("rules-service", RULES_SERVICE_DIR)]:
    print(f"  -> {nombre}")
    subprocess.run([sys.executable, "-c", INIT_DB_SNIPPET], cwd=carpeta, check=True)
print("[OK] Tablas (titulares_expediente, expedientes, documentos, reglas_validacion) sincronizadas.")

# Paso 3: Precargar el catálogo de reglas de negocio DOC-05 (rules-service)
print("\n[*] Precargando catálogo de reglas de validación (DOC-05)...")
subprocess.run([sys.executable, "seed_reglas_validacion.py"], cwd=RULES_SERVICE_DIR, check=True)

# Paso 4: Crear un titular y expediente de demostración si no existe ninguno (core-service)
print("\n[*] Creando titular y expediente de demostración (core-service)...")
subprocess.run([sys.executable, "seed_demo.py"], cwd=CORE_SERVICE_DIR, check=True)

print("\n" + "=" * 60)
print("[EXITO] Base de datos PostgreSQL 'plurione_compliance' 100% lista y poblada.")
print("=" * 60)
