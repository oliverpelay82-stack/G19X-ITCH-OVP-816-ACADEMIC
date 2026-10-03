"""
Compresión de las respuestas del rules-service (GZip, RNF-01): una respuesta
JSON de más de 1 KB, como el catálogo de reglas, se comprime si el cliente la
acepta; una pequeña, no. Solo lectura: la ruta existe únicamente durante la prueba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

CATALOGO = [{"codigo_regla": f"RIE-01-{i:03d}", "descripcion": "Documento obligatorio del expediente."} for i in range(60)]
RUTAS = {"/api/v1/__prueba-catalogo": lambda: CATALOGO, "/api/v1/__prueba-chica": lambda: {"ok": True}}


def test_compresion_del_catalogo():
    for ruta, funcion in RUTAS.items():
        app.add_api_route(ruta, funcion, methods=["GET"])
    try:
        cliente = TestClient(app)
        grande = cliente.get("/api/v1/__prueba-catalogo", headers={"Accept-Encoding": "gzip"})
        chica = cliente.get("/api/v1/__prueba-chica", headers={"Accept-Encoding": "gzip"})
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in RUTAS]
    assert grande.headers.get("content-encoding") == "gzip" and grande.json() == CATALOGO
    assert "content-encoding" not in chica.headers
