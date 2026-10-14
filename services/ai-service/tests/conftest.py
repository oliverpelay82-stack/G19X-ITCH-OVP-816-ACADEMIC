"""
Aislamiento común de las pruebas del ai-service con pytest.

Cada prueba usa una SQLite temporal propia: las respuestas simuladas del modelo
que el caché del chat guarda (PLUS-10) y los textos de documentos de prueba
nunca llegan a ``services/ai-service/data/``, la base de desarrollo.

Módulo 7: las sesiones se firman con una clave de pruebas (tests/sesion.py). Sin
core, la cuenta de un token se toma de lo que dice el token (activa, con su rol);
la consulta real a GET /auth/me del core la prueba test_autorizacion_ai, marcada
con ``cuenta_real``.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sesion  # noqa: E402

sesion.preparar()  # antes de importar el servicio

from config import autorizacion, seguridad, settings  # noqa: E402


def pytest_configure(config):
    config.addinivalue_line("markers", "cuenta_real: confirma la cuenta con el core (sin la cuenta del token)")


@pytest.fixture(autouse=True)
def _sqlite_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EXTRACCIONES_DB_PATH", str(tmp_path / "extracciones.sqlite3"))


@pytest.fixture(autouse=True)
def _cuenta_del_token(request, monkeypatch):
    autorizacion.olvidar_cuentas()
    if request.node.get_closest_marker("cuenta_real"):
        return

    def desde_el_token(token: str) -> autorizacion.Cuenta:
        identidad = seguridad.leer_token(token)
        return autorizacion.Cuenta(email=identidad.email, rol=identidad.rol, debe_cambiar_contrasena=False)

    monkeypatch.setattr(autorizacion, "confirmar_cuenta", desde_el_token)
