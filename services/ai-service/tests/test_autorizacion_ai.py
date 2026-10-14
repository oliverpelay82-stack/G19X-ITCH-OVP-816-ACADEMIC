"""
Módulo 7 — Autorización del ai-service y propagación de la identidad (RF-26, HU-07;
PRD §5.1 y §5.2; docs/uml/m7-secuencia-propagacion-sistema.puml). Sin red.

  1. Matriz: auditar, preguntar, anticipar y extraer son de la operación (ADMIN,
     VALIDADOR); el visor y la configuración del OCR, de la lectura (más AUDITOR); la
     consulta no entra; un token SISTEMA tampoco; sin token, 401; /health es pública.
  2. Propagación: dentro de una petición, las llamadas al core y al rules llevan un
     token SISTEMA del ai-service y X-Usuario-Actor con el correo de la persona; en
     una tarea de fondo (otro hilo) van sin persona.
  3. La cuenta se confirma con GET /auth/me del core: manda el rol del core, no el del
     token; cuenta inactiva → 401; contraseña temporal → 403; core caído → 503; la
     respuesta se recuerda por token.
"""
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests
from fastapi import Depends
from fastapi.testclient import TestClient

import sesion
import main
from config import autorizacion, seguridad, settings

A, V, AU, C = "ADMIN", "VALIDADOR", "AUDITOR", "CONSULTA"
X = "00000000-0000-0000-0000-000000000000"

MATRIZ = [
    ("POST", "/api/v1/ai/analisis-semantico", {}, (A, V)),
    ("POST", f"/api/v1/ai/documentos/{X}/preparar", None, (A, V)),
    ("POST", f"/api/v1/ai/documentos/{X}/anticipar", None, (A, V)),
    ("POST", "/api/v1/ai/chat-documento", {}, (A, V)),
    ("POST", "/api/v1/ai/extraer-texto", None, (A, V)),
    ("GET", "/api/v1/ai/configuracion-ocr", None, (A, V, AU)),
    ("GET", f"/api/v1/ai/documentos/{X}/visor", None, (A, V, AU)),
    ("GET", f"/api/v1/ai/documentos/{X}/paginas/1", None, (A, V, AU)),
    ("POST", f"/api/v1/ai/documentos/{X}/localizar", {}, (A, V, AU)),
]


@pytest.fixture
def sin_red(monkeypatch):
    # Un core y un rules inalcanzables al instante: la prueba mide la autorización, no los datos.
    monkeypatch.setattr(settings, "CORE_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "RULES_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setattr(settings, "LECTURA_ANTICIPADA", False, raising=False)


@pytest.mark.parametrize("metodo,ruta,cuerpo,permitidos", MATRIZ, ids=[f"{m} {r}" for m, r, _, _ in MATRIZ])
def test_matriz_de_permisos_del_ai(sin_red, metodo, ruta, cuerpo, permitidos):
    cliente = TestClient(main.app, raise_server_exceptions=False)
    extra = {"json": cuerpo} if cuerpo is not None else {}
    for rol in (A, V, AU, C):
        estado = cliente.request(metodo, ruta, headers=sesion.cabeceras(rol), **extra).status_code
        if rol in permitidos:
            assert estado not in (401, 403), f"{rol} debe poder usar {metodo} {ruta} (respondió {estado})"
        else:
            assert estado == 403, f"{rol} no debe poder usar {metodo} {ruta} (respondió {estado})"
    sistema = cliente.request(metodo, ruta, headers=seguridad.cabeceras_sistema("core-service"), **extra)
    assert sistema.status_code == 403, "Ningún servicio llama al ai-service en nombre de otro"
    assert cliente.request(metodo, ruta, **extra).status_code == 401


def test_toda_ruta_del_ai_esta_en_la_matriz_o_es_publica():
    cubiertas = {(m, r.replace(X, "{}").replace("/paginas/1", "/paginas/{}")) for m, r, _, _ in MATRIZ}
    for ruta, operaciones in main.app.openapi()["paths"].items():
        for metodo, operacion in operaciones.items():
            if (metodo.upper(), ruta) == ("GET", "/api/v1/health"):
                assert not operacion.get("security")
                continue
            normalizada = (metodo.upper(), "/".join("{}" if p.startswith("{") else p for p in ruta.split("/")))
            assert operacion.get("security") and normalizada in cubiertas, f"{metodo.upper()} {ruta} sin matriz"


def test_las_llamadas_al_core_llevan_el_token_sistema_y_la_persona():
    ruta = "/api/v1/ai/__prueba-cabeceras"
    fondo = ThreadPoolExecutor(max_workers=1)

    def cabeceras():  # síncrona, como los endpoints reales: corre en un hilo del pool de FastAPI
        return {"peticion": autorizacion.cabeceras_servicio(),
                "fondo": fondo.submit(autorizacion.cabeceras_servicio).result()}

    main.app.add_api_route(ruta, cabeceras, methods=["GET"], dependencies=[Depends(autorizacion.operacion)])
    try:
        r = sesion.cliente(main.app, V).get(ruta, headers={"X-Request-ID": "folio-m7"})
    finally:
        main.app.router.routes[:] = [x for x in main.app.router.routes if getattr(x, "path", None) != ruta]
        fondo.shutdown()
    assert r.status_code == 200, r.text
    peticion, en_fondo = r.json()["peticion"], r.json()["fondo"]
    assert peticion[seguridad.CABECERA_ACTOR] == sesion.correo(V) and peticion["X-Request-ID"] == "folio-m7"
    identidad = seguridad.leer_token(peticion["Authorization"].removeprefix("Bearer "))
    assert identidad.es_sistema and identidad.sub == "ai-service"
    assert seguridad.CABECERA_ACTOR not in en_fondo, "Una tarea de fondo llama al core como SISTEMA, sin persona"
    assert seguridad.leer_token(en_fondo["Authorization"].removeprefix("Bearer ")).es_sistema
    assert autorizacion.actor_actual() is None, "La persona no se filtra fuera de su petición"


class _Respuesta:
    def __init__(self, estado: int, cuerpo: dict | None = None):
        self.status_code, self._cuerpo = estado, cuerpo or {}
        self.ok = 200 <= estado < 300

    def json(self):
        return self._cuerpo


def _core(monkeypatch, *respuestas):
    llamadas = []

    def get(url, timeout, headers):
        llamadas.append((url, headers["Authorization"]))
        siguiente = respuestas[min(len(llamadas), len(respuestas)) - 1]
        if isinstance(siguiente, Exception):
            raise siguiente
        return siguiente

    monkeypatch.setattr(autorizacion.requests, "get", get)
    return llamadas


def _perfil(rol: str, **extra) -> _Respuesta:
    return _Respuesta(200, {"email": sesion.correo(V), "rol": rol, "debe_cambiar_contrasena": False, **extra})


@pytest.mark.cuenta_real
def test_manda_el_rol_que_confirma_el_core(sin_red, monkeypatch):
    llamadas = _core(monkeypatch, _perfil(AU))  # el token dice VALIDADOR; el core, AUDITOR
    cliente = sesion.cliente(main.app, V, raise_server_exceptions=False)
    assert cliente.post("/api/v1/ai/chat-documento", json={}).status_code == 403
    assert cliente.get("/api/v1/ai/configuracion-ocr").status_code == 200
    assert len(llamadas) == 1, "La cuenta confirmada se recuerda por token"
    url, autorizacion_enviada = llamadas[0]
    assert url.endswith("/api/v1/auth/me"), "Pregunta al core por la cuenta del propio token"
    assert seguridad.leer_token(autorizacion_enviada.removeprefix("Bearer ")).email == sesion.correo(V)
    autorizacion.olvidar_cuentas()
    cliente.get("/api/v1/ai/configuracion-ocr")
    assert len(llamadas) == 2


@pytest.mark.cuenta_real
@pytest.mark.parametrize("respuesta,estado", [
    (_Respuesta(401), 401),
    (_perfil(V, debe_cambiar_contrasena=True), 403),
    (requests.ConnectionError("core caído"), 503),
    (_Respuesta(500), 503),
])
def test_la_cuenta_que_el_core_no_confirma_no_entra(monkeypatch, respuesta, estado):
    _core(monkeypatch, respuesta)
    r = sesion.cliente(main.app, V).get("/api/v1/ai/configuracion-ocr")
    assert r.status_code == estado, r.text


def test_salud_publica():
    assert TestClient(main.app).get("/api/v1/health").status_code == 200
