"""
init_db() de cada servicio crea sus tablas en una base vacía, ejecutado solo,
como lo hace scripts/setup_postgres.py (un subproceso con
``from config.database import init_db; init_db()``).

Regresión del 15/10/2026: el rules-service no importaba sus modelos dentro de
init_db(), así que en una base nueva create_all no creaba reglas_validacion y la
primera migración (ALTER TABLE reglas_validacion) fallaba. Desde el arranque del
servicio no se notaba, porque los controladores ya habían importado los modelos.
"""
import os
import subprocess
import sys
from pathlib import Path

import psycopg2
import pytest
from dotenv import dotenv_values
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

RAIZ = Path(__file__).resolve().parent.parent
BASE = "plurione_compliance_init_vacia"
_ENV = dotenv_values(RAIZ / "services" / "core-service" / ".env")
CONEXION = {k: os.getenv(f"DB_{k.upper()}", _ENV.get(f"DB_{k.upper()}", d))
            for k, d in (("host", "127.0.0.1"), ("port", "5432"), ("user", "postgres"), ("password", "postgres"))}


def _admin(sentencia: str) -> None:
    conn = psycopg2.connect(dbname="postgres", **CONEXION)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute(sentencia)
    conn.close()


@pytest.fixture
def base_vacia():
    _admin(f'DROP DATABASE IF EXISTS "{BASE}" WITH (FORCE)')
    _admin(f'CREATE DATABASE "{BASE}"')
    yield BASE
    _admin(f'DROP DATABASE IF EXISTS "{BASE}" WITH (FORCE)')


def _tablas(base: str) -> set[str]:
    conn = psycopg2.connect(dbname=base, **CONEXION)
    with conn.cursor() as cur:
        cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        nombres = {fila[0] for fila in cur.fetchall()}
    conn.close()
    return nombres


@pytest.mark.parametrize("servicio, tablas", [
    ("rules-service", {"reglas_validacion"}),
    ("core-service", {"titulares_expediente", "expedientes", "documentos", "dictamenes_auditoria",
                      "bitacora_auditoria", "usuarios", "expediente_asignaciones"}),
])
def test_init_db_crea_sus_tablas_en_una_base_vacia(base_vacia, servicio, tablas):
    entorno = {**os.environ, "DB_NAME": base_vacia, **{f"DB_{k.upper()}": v for k, v in CONEXION.items()}}
    resultado = subprocess.run([sys.executable, "-c", "from config.database import init_db; init_db()"],
                               cwd=RAIZ / "services" / servicio, env=entorno, capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr[-1500:]
    assert tablas <= _tablas(base_vacia)
