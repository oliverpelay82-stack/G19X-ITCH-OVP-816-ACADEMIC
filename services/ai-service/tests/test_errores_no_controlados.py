"""
Un error no controlado del ai-service responde 500 en JSON y con cabeceras
CORS, para que el frontend muestre el error real y no «¿el microservicio está
corriendo?» (sin CORS, el navegador oculta la respuesta).

Sin red: la ruta que falla se agrega solo durante la prueba.

Uso:  cd services/ai-service && python tests/test_errores_no_controlados.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
    print("PASÓ: error no controlado del ai-service con JSON y CORS")
