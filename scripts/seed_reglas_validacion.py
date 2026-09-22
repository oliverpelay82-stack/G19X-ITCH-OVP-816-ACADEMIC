"""
Wrapper de conveniencia: precarga el catálogo de Reglas de Validación (DOC-05)
delegando en el script propio del rules-service, que es quien posee los
modelos y la lógica de negocio de ese dominio.

Ejecuta (desde la raíz del proyecto): python scripts/seed_reglas_validacion.py
Requiere que las tablas ya existan (ejecutar antes: python scripts/crear_tablas.py).
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RULES_SERVICE_DIR = ROOT / "services" / "rules-service"


def main():
    subprocess.run(
        [sys.executable, "seed_reglas_validacion.py"],
        cwd=RULES_SERVICE_DIR,
        check=True,
    )


if __name__ == "__main__":
    main()
