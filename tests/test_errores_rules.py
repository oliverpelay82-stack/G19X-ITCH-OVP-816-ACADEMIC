"""
Un error no controlado del rules-service responde 500 en JSON y con cabeceras
CORS, para que el frontend muestre el error real y no «¿el microservicio está
corriendo?» (sin CORS, el navegador oculta la respuesta).

Solo lectura: la ruta que falla se agrega únicamente durante la prueba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402

RUTA = "/api/v1/__prueba-error-no-controlado"
ORIGEN = "http://127.0.0.1:5173"


def _falla():
    raise RuntimeError("fallo simulado")


def test_error_no_controlado_responde_json_con_cors():
    app.add_api_route(RUTA, _falla, methods=["GET"])
    try:
        respuesta = TestClient(app, raise_server_exceptions=False).get(RUTA, headers={"Origin": ORIGEN})
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) != RUTA]
    assert respuesta.status_code == 500
    assert respuesta.headers.get("access-control-allow-origin") in ("*", ORIGEN), dict(respuesta.headers)
    assert respuesta.headers["content-type"].startswith("application/json")
    assert respuesta.json()["detail"]


if __name__ == "__main__":
    test_error_no_controlado_responde_json_con_cors()
    print("PASÓ: error no controlado del rules-service con JSON y CORS")
