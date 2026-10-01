"""
PLUS-21 — Folio de seguimiento en el ai-service (PRD §21.7; HU-57). Sin red.

  1. El folio recibido vuelve en la respuesta; sin él se crea uno.
  2. Los clientes del core y del rules-service lo propagan, dentro de una
     petición real al ai-service.
  3. Un error no controlado devuelve el folio.
"""
from types import SimpleNamespace

from fastapi.testclient import TestClient

import main
from clients import core_client, rules_client

client = TestClient(main.app)


def test_el_folio_vuelve_y_se_crea_si_falta():
    assert client.get("/api/v1/health", headers={"X-Request-ID": "folio-ai-01"}).headers["X-Request-ID"] == "folio-ai-01"
    assert len(client.get("/api/v1/health").headers["X-Request-ID"]) == 16


def test_los_clientes_propagan_el_folio_de_la_peticion(monkeypatch):
    enviadas = []

    def falso(cuerpo):
        def get(*args, **kwargs):
            enviadas.append((kwargs.get("headers") or {}).get("X-Request-ID"))
            return SimpleNamespace(status_code=200, ok=True, json=lambda: cuerpo, raise_for_status=lambda: None)
        return get

    monkeypatch.setattr(core_client._sesion, "get", falso([]))
    monkeypatch.setattr(rules_client._sesion, "get", falso({"version_catalogo": "cat-0123456789ab"}))
    monkeypatch.setattr(rules_client, "_version_en_memoria", (float("-inf"), None))

    ruta = "/api/v1/__prueba-folio-clientes"

    def _llama_a_los_otros():
        core_client.ultimo_dictamen("doc-folio")
        rules_client.version_catalogo()
        return {}

    main.app.add_api_route(ruta, _llama_a_los_otros, methods=["GET"])
    try:
        client.get(ruta, headers={"X-Request-ID": "folio-propagado"})
    finally:
        main.app.router.routes[:] = [r for r in main.app.router.routes if getattr(r, "path", None) != ruta]
    assert enviadas == ["folio-propagado", "folio-propagado"]


def test_un_error_no_controlado_devuelve_su_folio():
    ruta = "/api/v1/__prueba-folio-error-ai"

    def _falla():
        raise RuntimeError("fallo simulado")

    main.app.add_api_route(ruta, _falla, methods=["GET"])
    try:
        r = TestClient(main.app, raise_server_exceptions=False).get(ruta, headers={"X-Request-ID": "folio-error-ai"})
    finally:
        main.app.router.routes[:] = [x for x in main.app.router.routes if getattr(x, "path", None) != ruta]
    assert r.status_code == 500 and r.json()["id_peticion"] == "folio-error-ai"
