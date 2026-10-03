"""
Compresión de las respuestas del core-service (GZip, RNF-01).

  1. Una respuesta JSON de más de 1 KB se comprime si el cliente la acepta.
  2. Una respuesta pequeña no se comprime (no vale la pena).
  3. Los originales de la bóveda (/documentos/{id}/contenido) y los reportes
     no se comprimen: ya van comprimidos y el ai-service lee hasta 15 MB por auditoría.
  4. La compresión conserva las cabeceras CORS y de seguridad.

Solo lectura: las rutas se agregan únicamente durante la prueba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("core-service")

import pytest  # noqa: E402
from fastapi import Response  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

GRANDE = {"expedientes": [{"folio": f"EXP-{i:05d}", "estado": "EN_REVISION"} for i in range(200)]}
BINARIO = b"%PDF-1.7 " + b"0" * 50_000
RUTAS = {
    "/api/v1/__prueba-json-grande": lambda: GRANDE,
    "/api/v1/__prueba-json-chico": lambda: {"ok": True},
    # Fuera del prefijo de la ruta real, que atraparía /documentos/{id}/contenido; el filtro mira el sufijo.
    "/api/v1/__prueba/documentos/x/contenido": lambda: Response(BINARIO, media_type="application/pdf"),
    "/api/v1/reportes/__prueba": lambda: Response(BINARIO, media_type="application/pdf"),
}


@pytest.fixture(scope="module")
def cliente():
    for ruta, funcion in RUTAS.items():
        app.add_api_route(ruta, funcion, methods=["GET"])
    try:
        yield TestClient(app)
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in RUTAS]


def _pedir(cliente, ruta):
    return cliente.get(ruta, headers={"Accept-Encoding": "gzip", "Origin": "http://127.0.0.1:5173"})


def test_json_grande_comprimido(cliente):
    r = _pedir(cliente, "/api/v1/__prueba-json-grande")
    assert r.headers.get("content-encoding") == "gzip"
    assert r.json() == GRANDE                                   # el cliente lo descomprime íntegro
    assert r.headers.get("access-control-allow-origin") and r.headers.get("x-content-type-options") == "nosniff"


def test_json_chico_sin_comprimir(cliente):
    assert "content-encoding" not in _pedir(cliente, "/api/v1/__prueba-json-chico").headers


@pytest.mark.parametrize("ruta", ["/api/v1/__prueba/documentos/x/contenido", "/api/v1/reportes/__prueba"])
def test_binarios_sin_comprimir(cliente, ruta):
    r = _pedir(cliente, ruta)
    assert "content-encoding" not in r.headers and r.content == BINARIO
