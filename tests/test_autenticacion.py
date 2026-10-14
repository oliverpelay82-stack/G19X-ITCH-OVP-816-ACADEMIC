"""
Módulo 7 — Autenticación del core-service (RF-25, HU-06, HU-07; PRD §5.2;
docs/uml/m7-secuencia-inicio-sesion.puml).

  1. El inicio de sesión correcto emite un JWT HS256 que abre /auth/me y queda en la
     bitácora (INICIO_SESION, con el correo y la IP).
  2. Un correo inexistente y una contraseña incorrecta reciben el mismo 401.
  3. Bloqueo: al quinto fallo seguido la cuenta se bloquea 15 min (429 con
     Retry-After, aunque llegue la contraseña correcta); al vencer, entra y el
     conteo se reinicia.
  4. Tokens: sin token, firma ajena o vencido → 401; desactivar la cuenta o cambiarle
     el rol surte efecto en la siguiente petición, aunque el token siga vigente.
  5. Contraseña temporal: hasta cambiarla solo se usan /auth/me y
     /auth/cambiar-contrasena.
  6. Configuración: sin JWT_SECRET o con uno corto el servicio no arranca.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import jwt
import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from main import app  # noqa: E402
from config import seguridad  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from controllers import auth_controller  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from models.usuario import Usuario  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
auth = bd_pruebas.Autenticacion()
anonimo = TestClient(app)
admin = auth.cliente(app)

CLAVE = "Clave-de-prueba-2026"


def _cuenta(rol: str = "VALIDADOR", *, temporal: bool = False, activo: bool = True) -> Usuario:
    with SessionLocal() as db:
        usuario = Usuario(email=f"m7-{uuid.uuid4().hex[:10]}@example.com", nombre_completo="Cuenta de prueba",
                          rol=rol, password_hash=seguridad.hash_contrasena(CLAVE),
                          debe_cambiar_contrasena=temporal, activo=activo)
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario


def _login(email: str, contrasena: str = CLAVE):
    return anonimo.post("/api/v1/auth/login", json={"email": email, "contrasena": contrasena})


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _eventos(evento: str, usuario: str) -> list[dict]:
    return [e for e in admin.get("/api/v1/bitacora", params={"evento": evento, "limite": 500}).json()
            if e["usuario"] == usuario]


def _actualizar(usuario_id: str, **campos) -> None:
    with SessionLocal() as db:
        db.query(Usuario).filter(Usuario.id == usuario_id).update(campos)
        db.commit()


def test_inicio_de_sesion_correcto_emite_el_token_y_queda_en_la_bitacora():
    cuenta = _cuenta("AUDITOR")
    r = _login(cuenta.email.upper())  # el correo no distingue mayúsculas
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["token_type"] == "bearer" and cuerpo["expira_en"] == 480 * 60
    assert cuerpo["usuario"]["rol"] == "AUDITOR" and "password_hash" not in cuerpo["usuario"]
    carga = jwt.decode(cuerpo["access_token"], bd_pruebas.SECRETO_PRUEBAS, algorithms=["HS256"])
    assert carga["sub"] == cuenta.id and carga["rol"] == "AUDITOR" and carga["exp"] - carga["iat"] == 480 * 60

    me = anonimo.get("/api/v1/auth/me", headers=_bearer(cuerpo["access_token"]))
    assert me.status_code == 200 and me.json()["email"] == cuenta.email
    [evento] = _eventos("INICIO_SESION", cuenta.email)
    assert evento["ip_origen"] and evento["hash_evento"], "Sellado, con la IP de origen"


def test_correo_inexistente_y_contrasena_incorrecta_reciben_la_misma_respuesta():
    cuenta = _cuenta()
    inexistente = _login("nadie-" + uuid.uuid4().hex[:8] + "@example.com")
    incorrecta = _login(cuenta.email, "Otra-clave-incorrecta")
    assert inexistente.status_code == incorrecta.status_code == 401
    assert inexistente.json()["detail"] == incorrecta.json()["detail"] == "Correo o contraseña incorrectos."
    assert inexistente.headers.get("www-authenticate") == "Bearer"
    [fallo] = _eventos("INICIO_SESION_FALLIDO", cuenta.email)
    assert fallo["detalle"]["motivo"] == "CREDENCIALES_INVALIDAS"


def test_bloqueo_tras_cinco_fallos_seguidos_y_desbloqueo_al_vencer():
    cuenta = _cuenta()
    for _ in range(auth_controller.INTENTOS_MAXIMOS - 1):
        assert _login(cuenta.email, "Clave-equivocada-1").status_code == 401
    # Un acierto antes del quinto fallo reinicia el conteo.
    assert _login(cuenta.email).status_code == 200
    for _ in range(auth_controller.INTENTOS_MAXIMOS):
        assert _login(cuenta.email, "Clave-equivocada-2").status_code == 401

    bloqueada = _login(cuenta.email)  # contraseña correcta, pero la cuenta está bloqueada
    assert bloqueada.status_code == 429, bloqueada.text
    assert 0 < int(bloqueada.headers["retry-after"]) <= auth_controller.MINUTOS_BLOQUEO * 60 + 1
    motivos = [e["detalle"]["motivo"] for e in _eventos("INICIO_SESION_FALLIDO", cuenta.email)]
    assert motivos.count("CUENTA_BLOQUEADA_AHORA") == 1 and "CUENTA_BLOQUEADA" in motivos

    _actualizar(cuenta.id, bloqueado_hasta=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1))
    assert _login(cuenta.email).status_code == 200, "Al vencer el bloqueo vuelve a entrar"
    with SessionLocal() as db:
        guardada = db.get(Usuario, cuenta.id)
        assert guardada.intentos_fallidos == 0 and guardada.bloqueado_hasta is None and guardada.ultimo_acceso


def test_cuenta_desactivada_no_entra_y_su_token_deja_de_servir():
    cuenta = _cuenta()
    token = _login(cuenta.email).json()["access_token"]
    assert anonimo.get("/api/v1/expedientes/asignados", headers=_bearer(token)).status_code == 200

    _actualizar(cuenta.id, activo=False)
    assert anonimo.get("/api/v1/expedientes/asignados", headers=_bearer(token)).status_code == 401, (
        "Revocación inmediata")
    r = _login(cuenta.email)
    assert r.status_code == 401 and r.json()["detail"] == "Correo o contraseña incorrectos."
    assert [e["detalle"]["motivo"] for e in _eventos("INICIO_SESION_FALLIDO", cuenta.email)] == ["CUENTA_DESACTIVADA"]


def test_el_rol_vigente_es_el_de_la_base_y_no_el_del_token():
    cuenta = _cuenta("ADMIN")
    token = _login(cuenta.email).json()["access_token"]
    assert anonimo.get("/api/v1/usuarios", headers=_bearer(token)).status_code == 200
    _actualizar(cuenta.id, rol="AUDITOR")  # el token sigue diciendo ADMIN
    assert anonimo.get("/api/v1/usuarios", headers=_bearer(token)).status_code == 403
    assert anonimo.get("/api/v1/auth/me", headers=_bearer(token)).json()["rol"] == "AUDITOR"


@pytest.mark.parametrize("cabecera", [
    None,
    "Basic dXN1YXJpbzpjbGF2ZQ==",
    "Bearer no-es-un-jwt",
])
def test_sin_token_o_con_token_ilegible_responde_401(cabecera):
    headers = {"Authorization": cabecera} if cabecera else {}
    r = anonimo.get("/api/v1/usuarios", headers=headers)
    assert r.status_code == 401 and r.headers.get("www-authenticate") == "Bearer"


def test_token_vencido_o_firmado_con_otra_clave_responde_401():
    id_, correo, nombre = auth.cuenta("ADMIN")
    ahora = int(time.time())
    vencido = jwt.encode({"sub": id_, "email": correo, "nombre": nombre, "rol": "ADMIN",
                          "iat": ahora - 600, "exp": ahora - 60}, bd_pruebas.SECRETO_PRUEBAS, algorithm="HS256")
    ajeno = jwt.encode({"sub": id_, "email": correo, "nombre": nombre, "rol": "ADMIN",
                        "iat": ahora, "exp": ahora + 600}, "otra-clave-de-al-menos-32-caracteres!!", algorithm="HS256")
    sin_algoritmo = jwt.encode({"sub": id_, "rol": "ADMIN", "iat": ahora, "exp": ahora + 600}, None, algorithm="none")
    for token in (vencido, ajeno, sin_algoritmo):
        r = anonimo.get("/api/v1/usuarios", headers=_bearer(token))
        assert r.status_code == 401, r.text
        assert r.json()["detail"] == "La sesión expiró o no es válida. Inicie sesión de nuevo."


def test_contrasena_temporal_solo_permite_cambiarla():
    cuenta = _cuenta("VALIDADOR", temporal=True)
    login = _login(cuenta.email)
    assert login.status_code == 200 and login.json()["usuario"]["debe_cambiar_contrasena"]
    token = login.json()["access_token"]

    assert anonimo.get("/api/v1/auth/me", headers=_bearer(token)).status_code == 200
    bloqueada = anonimo.get("/api/v1/expedientes/asignados", headers=_bearer(token))
    assert bloqueada.status_code == 403 and "contraseña temporal" in bloqueada.json()["detail"]

    url = "/api/v1/auth/cambiar-contrasena"
    assert anonimo.post(url, headers=_bearer(token), json={
        "contrasena_actual": "No-es-la-actual", "contrasena_nueva": "Nueva-clave-2026"}).status_code == 400
    assert anonimo.post(url, headers=_bearer(token), json={
        "contrasena_actual": CLAVE, "contrasena_nueva": CLAVE}).status_code == 400
    assert anonimo.post(url, headers=_bearer(token), json={
        "contrasena_actual": CLAVE, "contrasena_nueva": "corta"}).status_code == 422
    r = anonimo.post(url, headers=_bearer(token), json={
        "contrasena_actual": CLAVE, "contrasena_nueva": "Nueva-clave-2026"})
    assert r.status_code == 200 and not r.json()["debe_cambiar_contrasena"]

    assert anonimo.get("/api/v1/expedientes/asignados", headers=_bearer(token)).status_code == 200
    assert _login(cuenta.email).status_code == 401 and _login(cuenta.email, "Nueva-clave-2026").status_code == 200
    [cambio] = _eventos("CAMBIO_CONTRASENA", cuenta.email)
    assert cambio["detalle"]["era_temporal"] is True and "Nueva-clave" not in str(cambio["detalle"])


def test_el_servicio_no_arranca_sin_un_secreto_valido(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    with pytest.raises(seguridad.ConfiguracionInvalidaError, match="JWT_SECRET"):
        seguridad.verificar_configuracion()
    monkeypatch.setenv("JWT_SECRET", "corto")
    with pytest.raises(seguridad.ConfiguracionInvalidaError, match="32"):
        seguridad.verificar_configuracion()
    monkeypatch.setenv("JWT_SECRET", seguridad.SECRETO_DEMOSTRACION)
    seguridad.verificar_configuracion()
    salud = anonimo.get("/api/v1/health").json()
    assert salud["advertencias"] and "JWT_SECRET" in salud["advertencias"][0], "El secreto de demostración se advierte"


def test_contrasenas_con_bcrypt():
    guardado = seguridad.hash_contrasena("Una-clave-segura")
    assert guardado.startswith("$2b$") and "Una-clave" not in guardado
    assert seguridad.verificar_contrasena("Una-clave-segura", guardado)
    assert not seguridad.verificar_contrasena("Otra-clave", guardado)
    assert not seguridad.verificar_contrasena("Una-clave-segura", None), "Sin cuenta: falso, con el mismo costo"
    assert seguridad.problema_de_contrasena("corta") and seguridad.problema_de_contrasena("ñ" * 40)
    assert seguridad.problema_de_contrasena("          ") and not seguridad.problema_de_contrasena("Diez-chars")
