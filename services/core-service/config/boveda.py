"""
Ubicación de la bóveda física de binarios (storage_vault).

- En desarrollo local: raíz del proyecto (services/core-service/config -> raíz).
- En Docker: la variable STORAGE_VAULT_PATH (volumen montado en /app/storage_vault).
"""
import os

_DEFAULT_STORAGE_VAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))), "storage_vault"
)
STORAGE_VAULT = os.getenv("STORAGE_VAULT_PATH", _DEFAULT_STORAGE_VAULT)
os.makedirs(STORAGE_VAULT, exist_ok=True)


def nombre_en_boveda(hash_sha256: str, nombre_original: str) -> str:
    """Convención de nombrado: los 12 primeros caracteres de la huella y el nombre original."""
    return f"{hash_sha256[:12]}_{os.path.basename(nombre_original or 'documento')}"


def ruta_en_boveda(hash_sha256: str, nombre_original: str) -> str:
    return os.path.join(STORAGE_VAULT, nombre_en_boveda(hash_sha256, nombre_original))
