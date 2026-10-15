"""
PLUS-21 — Folio de seguimiento entre servicios (ESTADO_DEL_DESARROLLO §6.7; HU-57). Core-service.

  1. Una petición con X-Request-ID lo recibe de vuelta; sin él, o con uno
     inválido, la respuesta trae uno nuevo, expuesto por CORS al navegador.
  2. El evento de bitácora que registra la acción lleva el folio, sellado.
  3. Un error no controlado devuelve el folio en el cuerpo y en la cabecera.
  4. Cada petición deja una línea JSON en el registro (los sondeos de salud no).
  5. El cliente del rules-service propaga el folio.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

import json  # noqa: E402
import logging  # noqa: E402
from types import SimpleNamespace  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import observabilidad, seguridad  # noqa: E402
from config.database import engine, init_db  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
_obtener_real = rules_client.obtener_documentos_obligatorios
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)
ORIGEN = "http://127.0.0.1:5173"


class _Lineas(logging.Handler):
    def __init__(self):
        super().__init__()
        self.lineas = []

    def emit(self, registro):
        self.lineas.append(json.loads(registro.getMessage()))


def test_el_folio_recibido_vuelve_y_uno_invalido_se_reemplaza():
    r = client.get("/api/v1/titulares", headers={"X-Request-ID": "folio-de-prueba-01", "Origin": ORIGEN})
    assert r.headers["X-Request-ID"] == "folio-de-prueba-01"
    assert "x-request-id" in r.headers.get("access-control-expose-headers", "").lower()

    nuevo = client.get("/api/v1/titulares").headers["X-Request-ID"]
    invalido = client.get("/api/v1/titulares", headers={"X-Request-ID": "no valido; <script>"}).headers["X-Request-ID"]
    assert len(nuevo) == 16 and invalido != "no valido; <script>" and len(invalido) == 16


def test_el_evento_de_bitacora_lleva_el_folio():
    r = client.post("/api/v1/titulares", headers={"X-Request-ID": "folio-alta-titular"},
                    json={"rfc": "FOL010101AB1", "razon_social": "Folio S.A. de C.V.", "tipo_persona": "MORAL"})
    assert r.status_code == 201, r.text
    exp = client.post("/api/v1/expedientes", headers={"X-Request-ID": "folio-expediente-01"},
                      json={"titular_id": r.json()["id"]}).json()
    eventos = client.get("/api/v1/bitacora", params={"expediente_id": exp["id"]}).json()
    assert eventos and all(e["detalle"].get("id_peticion") == "folio-expediente-01" for e in eventos)
    assert client.get("/api/v1/bitacora/verificar-cadena").json()["integra"], "El folio queda sellado"


def test_un_error_no_controlado_devuelve_su_folio():
    ruta = "/api/v1/__prueba-folio-error"

    def _falla():
        raise RuntimeError("fallo simulado")

    app.add_api_route(ruta, _falla, methods=["GET"])
    try:
        r = TestClient(app, raise_server_exceptions=False).get(ruta, headers={"X-Request-ID": "folio-del-error"})
    finally:
        app.router.routes[:] = [x for x in app.router.routes if getattr(x, "path", None) != ruta]
    assert r.status_code == 500
    assert r.json()["id_peticion"] == "folio-del-error" and r.headers["X-Request-ID"] == "folio-del-error"


def test_cada_peticion_deja_una_linea_json():
    captura = _Lineas()
    registro = logging.getLogger("plurione.core-service.peticiones")
    registro.addHandler(captura)
    try:
        client.get("/api/v1/titulares", headers={"X-Request-ID": "folio-del-registro"})
        client.get("/api/v1/health", headers={"X-Request-ID": "folio-del-sondeo"})
    finally:
        registro.removeHandler(captura)
    [linea] = [x for x in captura.lineas if x["id_peticion"] == "folio-del-registro"]
    assert linea["servicio"] == "core-service" and linea["ruta"] == "/api/v1/titulares" and linea["estado"] == 200
    assert linea["duracion_ms"] >= 0
    assert not [x for x in captura.lineas if x["id_peticion"] == "folio-del-sondeo"], "Sin ruido de los sondeos"


def test_el_cliente_del_rules_service_propaga_el_folio(monkeypatch):
    import requests

    enviadas = {}

    def falso_get(url, **kwargs):
        enviadas.update(kwargs.get("headers") or {})
        return SimpleNamespace(json=lambda: [{"tipo_documento": "CSF_SAT", "codigo_regla": "RIE-01-CSF",
                                              "severidad": "CRITICA"}],
                               headers={}, raise_for_status=lambda: None)

    monkeypatch.setattr(requests, "get", falso_get)
    token = observabilidad._actual.set("folio-hacia-rules")
    try:
        _obtener_real("CORPORATIVO")
    finally:
        observabilidad._actual.reset(token)
    assert enviadas["X-Request-ID"] == "folio-hacia-rules"
    # Módulo 7: la misma llamada lleva el token SISTEMA del core (PRD §5.2).
    identidad = seguridad.leer_token(enviadas["Authorization"].removeprefix("Bearer "))
    assert identidad.es_sistema and identidad.sub == "core-service"
