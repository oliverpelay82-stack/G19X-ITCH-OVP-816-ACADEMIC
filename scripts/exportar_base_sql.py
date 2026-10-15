"""
Genera db/base-de-datos.sql: la estructura completa de la base (tablas, índices,
triggers de inmutabilidad) con datos de prueba ficticios, para importarla en una
base vacía sin Python (guía de entrega de la plataforma académica).

Pasos, sobre una base temporal que nunca es la productiva:
  1. setup_postgres.py: tablas del core y del rules, catálogo de reglas DOC-05 y el
     titular y expediente de demostración;
  2. las cuatro cuentas de demostración del README (USUARIOS_DEMO=true);
  3. pg_dump sin dueño ni privilegios a db/base-de-datos.sql, sin las líneas
     \restrict de pg_dump 17.6 (así también se importa con pgAdmin o un psql anterior);
  4. comprobación: importa el archivo con psql en otra base vacía y cuenta reglas,
     cuentas y expedientes. Las dos bases temporales se borran al terminar.

Uso, desde la raíz: python scripts/exportar_base_sql.py
Requiere PostgreSQL con las credenciales del .env del core-service. Código 0 si la
importación de prueba quedó completa.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

from respaldo import binario_pg

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "services" / "core-service"
DESTINO = ROOT / "db" / "base-de-datos.sql"
BASE_EXPORTAR = "plurione_compliance_exportar"
BASE_COMPROBAR = "plurione_compliance_importar"

load_dotenv(CORE / ".env")
CONEXION = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": os.getenv("DB_PORT", "5432"),
    "user": os.getenv("DB_USER", "postgres"),
    "password": os.getenv("DB_PASSWORD", "postgres"),
}
ENTORNO_PG = {**os.environ, "PGPASSWORD": CONEXION["password"]}


def recrear(nombre: str, crear: bool = True) -> None:
    conn = psycopg2.connect(dbname="postgres", **CONEXION)
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conn.cursor() as cur:
        cur.execute(f'DROP DATABASE IF EXISTS "{nombre}" WITH (FORCE)')
        if crear:
            cur.execute(f'CREATE DATABASE "{nombre}"')
    conn.close()


def contar(nombre: str) -> dict[str, int]:
    conn = psycopg2.connect(dbname=nombre, **CONEXION)
    with conn.cursor() as cur:
        conteos = {}
        for tabla in ("reglas_validacion", "usuarios", "titulares_expediente", "expedientes", "bitacora_auditoria"):
            cur.execute(f"SELECT count(*) FROM {tabla}")
            conteos[tabla] = cur.fetchone()[0]
    conn.close()
    return conteos


def main() -> int:
    entorno = {**os.environ, "DB_NAME": BASE_EXPORTAR, "USUARIOS_DEMO": "true",
               "ADMIN_INICIAL_EMAIL": "", "ADMIN_INICIAL_CONTRASENA": ""}
    recrear(BASE_EXPORTAR)
    try:
        subprocess.run([sys.executable, str(ROOT / "scripts" / "setup_postgres.py")], env=entorno, check=True)
        subprocess.run([sys.executable, "-c", "from config.database import SessionLocal\n"
                        "from motor import usuarios_iniciales\n"
                        "print('cuentas de demostración:', usuarios_iniciales.crear(SessionLocal()))"],
                       cwd=CORE, env=entorno, check=True)
        esperado = contar(BASE_EXPORTAR)
        DESTINO.parent.mkdir(exist_ok=True)
        subprocess.run([binario_pg("pg_dump"), "-h", CONEXION["host"], "-p", CONEXION["port"], "-U", CONEXION["user"],
                        "--no-owner", "--no-privileges", "--encoding=UTF8", "-f", str(DESTINO), BASE_EXPORTAR],
                       env=ENTORNO_PG, check=True)
        # pg_dump 17.6 encierra el script entre \restrict y \unrestrict con una clave al azar: solo los entiende
        # un psql igual de reciente (pgAdmin o un psql anterior fallan) y cambian en cada corrida.
        lineas = DESTINO.read_text(encoding="utf-8").splitlines(keepends=True)
        DESTINO.write_text("".join(l for l in lineas if not l.startswith(("\\restrict ", "\\unrestrict "))),
                           encoding="utf-8", newline="")
    finally:
        recrear(BASE_EXPORTAR, crear=False)

    recrear(BASE_COMPROBAR)
    try:
        subprocess.run([binario_pg("psql"), "-h", CONEXION["host"], "-p", CONEXION["port"], "-U", CONEXION["user"],
                        "-q", "-v", "ON_ERROR_STOP=1", "-d", BASE_COMPROBAR, "-f", str(DESTINO)],
                       env=ENTORNO_PG, check=True, stdout=subprocess.DEVNULL)
        importado = contar(BASE_COMPROBAR)
    finally:
        recrear(BASE_COMPROBAR, crear=False)

    print(f"\n{DESTINO.relative_to(ROOT)}: {DESTINO.stat().st_size / 1024:.0f} KB")
    for tabla, n in esperado.items():
        print(f"  {tabla}: {n} generados, {importado[tabla]} importados")
    completo = esperado == importado and all(esperado.values())
    print("OK: la importación en una base vacía quedó completa" if completo else "FALLA: la importación difiere")
    return 0 if completo else 1


if __name__ == "__main__":
    sys.exit(main())
