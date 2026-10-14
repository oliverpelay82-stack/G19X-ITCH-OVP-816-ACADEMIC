"""
Módulo 7, fase F3 — Segundo factor TOTP opcional (RF-25, HU-05, HU-06, HU-07; PRD §5.2;
docs/uml/m7-actividad-mfa.puml).

  1. Sin MFA, la cuenta entra con correo y contraseña, como antes; un código enviado
     de más se ignora.
  2. Alta en dos pasos: generar (con la contraseña) no habilita nada; activar exige un
     código del secreto generado.
  3. Con MFA: la contraseña correcta sin código responde requiere_codigo sin token ni
     evento de acceso; el código válido entrega el token; uno inválido cuenta como
     intento fallido y, al quinto, bloquea la cuenta. Una contraseña incorrecta no
     revela que la cuenta tiene MFA.
  4. Ventana de ±30 s: el código del intervalo anterior sirve; el de hace 90 s no.
  5. Baja propia (contraseña y código) y restablecimiento por el administrador.
  6. El secreto nunca sale en el perfil ni en la bitácora.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import time
import uuid

import pyotp

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


def _cuenta() -> Usuario:
    with SessionLocal() as db:
        usuario = Usuario(email=f"mfa-{uuid.uuid4().hex[:10]}@example.com", nombre_completo="Cuenta MFA",
                          rol="VALIDADOR", password_hash=seguridad.hash_contrasena(CLAVE))
        db.add(usuario)
        db.commit()
        db.refresh(usuario)
        return usuario


def _login(email: str, contrasena: str = CLAVE, codigo: str | None = None):
    cuerpo = {"email": email, "contrasena": contrasena, **({"codigo": codigo} if codigo else {})}
    return anonimo.post("/api/v1/auth/login", json=cuerpo)


def _sesion(email: str, codigo: str | None = None) -> dict:
    return {"Authorization": f"Bearer {_login(email, codigo=codigo).json()['access_token']}"}


def _eventos(evento: str, usuario: str) -> list[dict]:
    return [e for e in admin.get("/api/v1/bitacora", params={"evento": evento, "limite": 500}).json()
            if e["usuario"] == usuario]


def _codigo_ajeno(totp: pyotp.TOTP) -> str:
    """Un código de 6 dígitos que no vale en la ventana vigente (±30 s)."""
    ahora = time.time()
    validos = {totp.at(ahora + d) for d in (-30, 0, 30)}
    return next(c for c in ("000000", "111111", "222222", "333333") if c not in validos)


def _con_mfa() -> tuple[Usuario, pyotp.TOTP, dict]:
    """Cuenta con el segundo factor ya habilitado, su generador de códigos y una sesión abierta antes."""
    cuenta = _cuenta()
    sesion = _sesion(cuenta.email)
    secreto = anonimo.post("/api/v1/auth/mfa/generar", headers=sesion, json={"contrasena": CLAVE}).json()["secreto"]
    totp = pyotp.TOTP(secreto)
    r = anonimo.post("/api/v1/auth/mfa/activar", headers=sesion, json={"codigo": totp.now()})
    assert r.status_code == 200 and r.json()["mfa_habilitado"], r.text
    return cuenta, totp, sesion


def test_sin_mfa_la_cuenta_entra_directo():
    cuenta = _cuenta()
    r = _login(cuenta.email, codigo="123456")  # un código de más no estorba
    assert r.status_code == 200 and r.json()["access_token"] and not r.json()["requiere_codigo"]
    assert r.json()["usuario"]["mfa_habilitado"] is False


def test_alta_en_dos_pasos():
    cuenta = _cuenta()
    sesion = _sesion(cuenta.email)
    assert anonimo.post("/api/v1/auth/mfa/activar", headers=sesion, json={"codigo": "123456"}).status_code == 409, (
        "Sin secreto generado no hay nada que activar")
    assert anonimo.post("/api/v1/auth/mfa/generar", headers=sesion,
                        json={"contrasena": "No-es-la-clave"}).status_code == 400

    r = anonimo.post("/api/v1/auth/mfa/generar", headers=sesion, json={"contrasena": CLAVE})
    assert r.status_code == 200, r.text
    secreto, uri = r.json()["secreto"], r.json()["uri"]
    assert len(secreto) == 32 and uri.startswith("otpauth://totp/") and "issuer=Motor%20de%20Validaci" in uri
    assert cuenta.email.replace("@", "%40") in uri
    assert _login(cuenta.email).json()["access_token"], "Generar no habilita el segundo factor"

    assert anonimo.post("/api/v1/auth/mfa/activar", headers=sesion, json={"codigo": "000000"}).status_code == 400
    r = anonimo.post("/api/v1/auth/mfa/activar", headers=sesion, json={"codigo": pyotp.TOTP(secreto).now()})
    assert r.status_code == 200 and r.json()["mfa_habilitado"]
    assert anonimo.post("/api/v1/auth/mfa/generar", headers=sesion,
                        json={"contrasena": CLAVE}).status_code == 409, "Ya habilitado: no se reemplaza a escondidas"
    [evento] = _eventos("CAMBIO_MFA", cuenta.email)
    assert evento["detalle"]["accion"] == "ACTIVADO"


def test_inicio_de_sesion_con_segundo_factor():
    cuenta, totp, _ = _con_mfa()
    accesos_previos = len(_eventos("INICIO_SESION", cuenta.email))  # el de _con_mfa, antes de habilitar

    paso1 = _login(cuenta.email)
    assert paso1.status_code == 200 and paso1.json() == {
        "requiere_codigo": True, "access_token": None, "token_type": "bearer", "expira_en": None, "usuario": None}
    assert len(_eventos("INICIO_SESION", cuenta.email)) == accesos_previos, "Sin el código no hay acceso registrado"

    incorrecta = _login(cuenta.email, "Otra-clave-mala-1")
    assert incorrecta.status_code == 401 and "requiere_codigo" not in incorrecta.text, (
        "Con la contraseña incorrecta no se revela que la cuenta tiene MFA")

    paso2 = _login(cuenta.email, codigo=totp.now())
    assert paso2.status_code == 200 and paso2.json()["access_token"]
    assert anonimo.get("/api/v1/auth/me",
                       headers={"Authorization": f"Bearer {paso2.json()['access_token']}"}).status_code == 200
    accesos = _eventos("INICIO_SESION", cuenta.email)
    assert len(accesos) == accesos_previos + 1 and accesos[0]["detalle"]["segundo_factor"] is True


def test_codigos_invalidos_cuentan_y_bloquean():
    cuenta, totp, _ = _con_mfa()
    malo = _codigo_ajeno(totp)
    for _ in range(auth_controller.INTENTOS_MAXIMOS - 1):
        r = _login(cuenta.email, codigo=malo)
        assert r.status_code == 401 and "código" in r.json()["detail"]
    assert _login(cuenta.email, codigo=malo).status_code == 401
    assert _login(cuenta.email, codigo=totp.now()).status_code == 429, "Bloqueada aunque llegue el código bueno"
    motivos = [e["detalle"]["motivo"] for e in _eventos("INICIO_SESION_FALLIDO", cuenta.email)]
    assert motivos.count("CODIGO_INVALIDO") == auth_controller.INTENTOS_MAXIMOS - 1
    assert "CUENTA_BLOQUEADA_AHORA" in motivos


def test_ventana_de_treinta_segundos():
    cuenta, totp, _ = _con_mfa()
    ahora = time.time()
    assert _login(cuenta.email, codigo=totp.at(ahora - 30)).status_code == 200, "El intervalo anterior sirve"
    viejo = totp.at(ahora - 90)
    if viejo not in {totp.at(ahora - 30), totp.now(), totp.at(ahora + 30)}:
        assert _login(cuenta.email, codigo=viejo).status_code == 401, "Hace 90 s ya no sirve"


def test_baja_propia_y_restablecimiento_del_administrador():
    cuenta, totp, sesion = _con_mfa()
    url = "/api/v1/auth/mfa/desactivar"
    assert anonimo.post(url, headers=sesion, json={"contrasena": "Otra-clave", "codigo": totp.now()}).status_code == 400
    assert anonimo.post(url, headers=sesion,
                        json={"contrasena": CLAVE, "codigo": _codigo_ajeno(totp)}).status_code == 400
    r = anonimo.post(url, headers=sesion, json={"contrasena": CLAVE, "codigo": totp.now()})
    assert r.status_code == 200 and not r.json()["mfa_habilitado"]
    assert _login(cuenta.email).json()["access_token"], "Sin MFA vuelve a entrar directo"
    assert [e["detalle"]["accion"] for e in _eventos("CAMBIO_MFA", cuenta.email)] == ["DESACTIVADO", "ACTIVADO"]

    perdida, _, _ = _con_mfa()
    r = admin.patch(f"/api/v1/usuarios/{perdida.id}", json={"restablecer_mfa": True})
    assert r.status_code == 200 and not r.json()["mfa_habilitado"]
    assert _login(perdida.email).json()["access_token"], "El teléfono perdido ya no impide entrar"
    [cambio] = [e for e in _eventos("ACTUALIZACION_USUARIO", auth.correo("ADMIN"))
                if e["detalle"]["usuario_id"] == perdida.id]
    assert cambio["detalle"]["cambios"] == {"mfa": {"restablecido": True}}
    assert admin.patch(f"/api/v1/usuarios/{perdida.id}", json={"restablecer_mfa": True}).status_code == 200
    assert len([e for e in _eventos("ACTUALIZACION_USUARIO", auth.correo("ADMIN"))
                if e["detalle"]["usuario_id"] == perdida.id]) == 1, "Sin MFA que quitar no hay evento"


def test_el_secreto_no_sale_en_el_perfil_ni_en_la_bitacora():
    cuenta, totp, sesion = _con_mfa()
    with SessionLocal() as db:
        secreto = db.get(Usuario, cuenta.id).mfa_secreto
    perfil = anonimo.get("/api/v1/auth/me", headers=sesion).text
    lista = admin.get("/api/v1/usuarios").text
    bitacora = admin.get("/api/v1/bitacora", params={"limite": 500}).text
    assert secreto and secreto not in perfil and secreto not in lista and secreto not in bitacora
