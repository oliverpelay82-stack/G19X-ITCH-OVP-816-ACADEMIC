"""
Un error no controlado del core-service responde 500 en JSON y con cabeceras
CORS, para que el frontend muestre el error real y no «¿el microservicio está
corriendo?» (sin CORS, el navegador oculta la respuesta).

Aislamiento: base de datos de pruebas (tests/bd_pruebas.py); la ruta que falla
se agrega solo durante la prueba.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from config.database import init_db  # noqa: E402

init_db()
auth = bd_pruebas.Autenticacion()

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


def _ok():
    return {"ok": True}


def test_cabeceras_de_seguridad_en_toda_respuesta():
    """Q-c (OWASP ZAP): X-Content-Type-Options, CORP y Cache-Control, también en un 500."""
    app.add_api_route(RUTA + "-ok", _ok, methods=["GET"])
    app.add_api_route(RUTA, _falla, methods=["GET"])
    try:
        cliente = TestClient(app, raise_server_exceptions=False)
        respuestas = [cliente.get(RUTA + "-ok"), cliente.get(RUTA, headers={"Origin": ORIGEN})]
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", None) not in (RUTA, RUTA + "-ok")]
    for r in respuestas:
        assert r.headers["x-content-type-options"] == "nosniff"
        assert r.headers["cross-origin-resource-policy"] == "same-origin"
        assert r.headers["cache-control"] == "no-store"


def test_caracter_nulo_en_un_filtro_responde_422_y_no_500():
    """Q-c (OWASP ZAP): ?expediente_id=%00 llegaba a PostgreSQL y respondía 500."""
    cliente = auth.cliente(app, raise_server_exceptions=False)
    for ruta in ("/api/v1/bitacora?expediente_id=%00", "/api/v1/dictamenes?documento_id=%00"):
        r = cliente.get(ruta)
        assert r.status_code == 422, (ruta, r.status_code, r.text)
        assert "carácter nulo" in r.json()["detail"] and r.json()["id_peticion"]


if __name__ == "__main__":
    test_error_no_controlado_responde_json_con_cors()
    print("PASÓ: error no controlado del core-service con JSON y CORS")
