"""
Sincroniza las tablas de PostgreSQL de todos los microservicios
(ddl-auto=update), invocando el init_db() de cada uno en un subproceso
aislado por servicio.

Nota de arquitectura: 'core-service' y 'rules-service' definen cada uno su
propio módulo 'config.database' (con su propia clase Base de SQLAlchemy).
Ambos apuntan a la misma base de datos física 'plurione_compliance', pero
no pueden importarse en el mismo proceso de Python porque comparten nombre
de módulo ('config.database'). Por eso cada sincronización corre en un
subproceso independiente con el directorio del servicio como cwd.

Ejecuta (desde la raíz del proyecto): python scripts/crear_tablas.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SERVICIOS = [
    ("core-service", "Titulares, Expedientes y Documentos"),
    ("rules-service", "Reglas de Validación"),
]

INIT_DB_SNIPPET = "from config.database import init_db; init_db()"


def main():
    print("=" * 60)
    print("Creando/sincronizando tablas en PostgreSQL (plurione_compliance)...")
    for carpeta, descripcion in SERVICIOS:
        servicio_dir = ROOT / "services" / carpeta
        print(f"\n[*] {carpeta} ({descripcion})")
        subprocess.run(
            [sys.executable, "-c", INIT_DB_SNIPPET],
            cwd=servicio_dir,
            check=True,
        )
    print("\n" + "=" * 60)
    print("[OK] Tablas de todos los microservicios sincronizadas con éxito.")


if __name__ == "__main__":
    main()
