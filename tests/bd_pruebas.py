"""
Entorno aislado para las pruebas del core-service.

Las pruebas que escriben (cargas, dictámenes, bitácora) no pueden ejecutarse
contra ``plurione_compliance``: la bitácora y los dictámenes son inmutables por
diseño (triggers de PostgreSQL), así que lo que una prueba escribiera ahí se
quedaría para siempre junto a los expedientes reales. Este módulo:

  1. Recrea desde cero la base ``plurione_compliance_test`` en el mismo servidor.
  2. Apunta la bóveda (STORAGE_VAULT_PATH) a un directorio temporal.

Debe invocarse ANTES de importar cualquier módulo del core-service, porque
``config.database`` y ``config.boveda`` leen el entorno al importarse. Si varias
suites corren en el mismo proceso (``pytest tests/``), la base se recrea solo
la primera vez: recrearla de nuevo cortaría las conexiones de la suite anterior.
Cada llamada, en cambio, recibe su propia bóveda y una copia limpia de los
módulos del core-service (``servicios.activar``).
"""
import os
import shutil
import sys
import tempfile

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

CORE_SERVICE_DIR = servicios.directorio("core-service")
NOMBRE_BD_PRUEBAS = "plurione_compliance_test"

_bd_recreada = False


def preparar_entorno() -> str:
    """Recrea la BD de pruebas, aísla la bóveda y deja importable el core-service. Devuelve la bóveda temporal."""
    servicios.activar("core-service")
    load_dotenv(os.path.join(CORE_SERVICE_DIR, ".env"))
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_NAME"] = NOMBRE_BD_PRUEBAS
    boveda = tempfile.mkdtemp(prefix="plurione_boveda_pruebas_")
    os.environ["STORAGE_VAULT_PATH"] = boveda

    global _bd_recreada
    if not _bd_recreada:
        _recrear_bd()
        _bd_recreada = True
    return boveda


def verificar_aislamiento(engine) -> None:
    """Aborta si el engine del core-service no apunta a la base de pruebas."""
    if engine.url.database != NOMBRE_BD_PRUEBAS:
        raise RuntimeError(
            f"Las pruebas del core-service apuntan a '{engine.url.database}' y no a '{NOMBRE_BD_PRUEBAS}': "
            "se detienen para no escribir en la bitácora inmutable de la base real."
        )


def _recrear_bd() -> None:
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


def limpiar_boveda(boveda: str) -> None:
    shutil.rmtree(boveda, ignore_errors=True)
