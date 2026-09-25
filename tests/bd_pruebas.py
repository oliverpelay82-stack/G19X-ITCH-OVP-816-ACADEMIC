"""
Entorno aislado para las pruebas del core-service.

Las pruebas que escriben (cargas, dictámenes, bitácora) no pueden ejecutarse
contra ``plurione_compliance``: la bitácora y los dictámenes son inmutables por
diseño (triggers de PostgreSQL), así que lo que una prueba escribiera ahí se
quedaría para siempre junto a los expedientes reales. Este módulo:

  1. Recrea desde cero la base ``plurione_compliance_test`` en el mismo servidor.
  2. Apunta la bóveda (STORAGE_VAULT_PATH) a un directorio temporal.

Debe invocarse ANTES de importar cualquier módulo del core-service, porque
``config.database`` y ``config.boveda`` leen el entorno al importarse.
"""
import os
import shutil
import sys
import tempfile

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CORE_SERVICE_DIR = os.path.join(RAIZ, "services", "core-service")
NOMBRE_BD_PRUEBAS = "plurione_compliance_test"


def preparar_entorno() -> str:
    """Recrea la BD de pruebas, aísla la bóveda y deja importable el core-service. Devuelve la bóveda temporal."""
    load_dotenv(os.path.join(CORE_SERVICE_DIR, ".env"))
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_NAME"] = NOMBRE_BD_PRUEBAS
    boveda = tempfile.mkdtemp(prefix="plurione_boveda_pruebas_")
    os.environ["STORAGE_VAULT_PATH"] = boveda

    conexion = psycopg2.connect(
        dbname="postgres",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
    )
    conexion.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conexion.cursor() as cursor:
        cursor.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (NOMBRE_BD_PRUEBAS,),
        )
        cursor.execute(f'DROP DATABASE IF EXISTS "{NOMBRE_BD_PRUEBAS}"')
        cursor.execute(f'CREATE DATABASE "{NOMBRE_BD_PRUEBAS}"')
    conexion.close()

    if CORE_SERVICE_DIR not in sys.path:
        sys.path.insert(0, CORE_SERVICE_DIR)
    return boveda


def limpiar_boveda(boveda: str) -> None:
    shutil.rmtree(boveda, ignore_errors=True)
