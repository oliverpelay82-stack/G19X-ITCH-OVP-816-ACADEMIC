"""
Sesiones para las pruebas del ai-service (Módulo 7, PRD §5.1).

Fija la clave de pruebas antes de que se importe el servicio y entrega clientes que
envían el token de una persona del rol pedido (por omisión, VALIDADOR: puede
auditar, preguntar y ver el visor).
"""
import os

SECRETO_PRUEBAS = "secreto-de-las-pruebas-del-ai-service-del-motor"


def preparar() -> None:
    """Clave de pruebas en el entorno: firma y validación de todas las sesiones."""
    os.environ["JWT_SECRET"] = SECRETO_PRUEBAS


preparar()


def correo(rol: str = "VALIDADOR") -> str:
    return f"prueba-{rol.lower()}@example.com"


def cabeceras(rol: str = "VALIDADOR") -> dict[str, str]:
    from config import seguridad

    token, _ = seguridad.emitir_token(f"id-{rol.lower()}", correo(rol), f"Prueba {rol}", rol)
    return {"Authorization": f"Bearer {token}"}


def cliente(app, rol: str = "VALIDADOR", **kwargs):
    from fastapi.testclient import TestClient

    return TestClient(app, headers=cabeceras(rol), **kwargs)
