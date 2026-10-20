"""
Cifra los archivos de la bóveda que siguen en claro (RNF-04).

Desde que se define BOVEDA_LLAVE, el core guarda cifrado cada documento nuevo y
sigue leyendo los anteriores en claro. Este script los cifra con la misma
llave. Por cada archivo en claro:

  1. comprueba que su SHA-256 empiece con el prefijo de su nombre (la
     convención de la bóveda: 12 caracteres de la huella y el nombre original);
     si no coincide, no lo toca: es una alteración que RIE-03 debe detectar;
  2. lo cifra, comprueba que el descifrado devuelva exactamente el original y
     lo reemplaza de forma atómica (os.replace).

Puede correr con los servicios en marcha. Los archivos ya cifrados se omiten,
así que repetirlo no cambia nada. Antes de correrlo, respalde la bóveda y
guarde BOVEDA_LLAVE fuera del equipo: sin ella los documentos no se recuperan.

Uso, desde la raíz del repositorio (lee services/core-service/.env):
  python scripts/cifrar_boveda.py [--simular]
Código de salida 0 si no quedó ningún archivo pendiente ni con huella distinta.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

RAIZ = Path(__file__).resolve().parent.parent
CORE = RAIZ / "services" / "core-service"
LARGO_PREFIJO = 12

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def _cargar_cifrado():
    """config/cifrado_boveda.py del core, sin importar el resto del servicio."""
    spec = importlib.util.spec_from_file_location("cifrado_boveda", CORE / "config" / "cifrado_boveda.py")
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def cifrar_boveda(boveda: Path, simular: bool = False) -> dict[str, list[str]]:
    cifrado_boveda = _cargar_cifrado()
    if not cifrado_boveda.activo():
        raise SystemExit("Falta BOVEDA_LLAVE: defina la llave en services/core-service/.env antes de cifrar.")
    resultado: dict[str, list[str]] = {"cifrados": [], "ya_cifrados": [], "huella_distinta": []}
    for ruta in sorted(p for p in boveda.iterdir() if p.is_file()):
        datos = ruta.read_bytes()
        if cifrado_boveda.esta_cifrado(datos):
            resultado["ya_cifrados"].append(ruta.name)
            continue
        if not hashlib.sha256(datos).hexdigest().startswith(ruta.name[:LARGO_PREFIJO]):
            resultado["huella_distinta"].append(ruta.name)
            continue
        if not simular:
            cifrado = cifrado_boveda.cifrar(datos)
            if cifrado_boveda.descifrar(cifrado) != datos:
                raise RuntimeError(f"El descifrado de {ruta.name} no devuelve el original; no se reemplazó.")
            temporal = ruta.with_name(ruta.name + ".cifrando")
            temporal.write_bytes(cifrado)
            os.replace(temporal, ruta)
        resultado["cifrados"].append(ruta.name)
    return resultado


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--simular", action="store_true", help="solo informa qué cifraría")
    args = parser.parse_args()
    load_dotenv(CORE / ".env")
    boveda = Path(os.getenv("STORAGE_VAULT_PATH") or RAIZ / "storage_vault")
    if not boveda.is_dir():
        print(f"No existe la bóveda {boveda}.")
        return 1
    resultado = cifrar_boveda(boveda, simular=args.simular)
    verbo = "Se cifrarían" if args.simular else "Cifrados"
    print(f"Bóveda: {boveda}")
    print(f"{verbo}: {len(resultado['cifrados'])} · ya cifrados: {len(resultado['ya_cifrados'])}")
    if resultado["huella_distinta"]:
        print(f"Sin tocar, su huella no coincide con su nombre ({len(resultado['huella_distinta'])}); "
              "RIE-03 los marcará al leerlos:")
        for nombre in resultado["huella_distinta"]:
            print(f"  - {nombre}")
    return 1 if resultado["huella_distinta"] or (args.simular and resultado["cifrados"]) else 0


if __name__ == "__main__":
    sys.exit(main())
