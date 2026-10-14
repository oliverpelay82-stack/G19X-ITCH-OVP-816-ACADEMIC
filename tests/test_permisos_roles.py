"""
Módulo 7 — Autorización por rol del core-service (RF-26, HU-05, HU-07, HU-31;
PRD §5.1 y §5.2; docs/uml/m7-casos-de-uso-acceso.puml y
m7-secuencia-propagacion-sistema.puml).

  1. Matriz de permisos: cada endpoint con cada rol (y con un token SISTEMA). Un rol
     sin permiso recibe 403; uno con permiso pasa la autorización (la respuesta puede
     ser 404 o 422 por los datos de la prueba, nunca 401 ni 403).
  2. Usuario de consulta: solo el semáforo de sus expedientes asignados.
  3. Gestión de cuentas: alta con contraseña temporal, cambios con su valor anterior
     y nuevo en la bitácora, sin poder quitarse a sí mismo el rol de administrador.
  4. Bitácora con el usuario real: el correo de la cuenta en sesión; con un token
     SISTEMA, la persona de X-Usuario-Actor; con un token de persona, esa cabecera se
     ignora.
  5. Cuentas iniciales: administrador del .env y un usuario ficticio por rol con
     USUARIOS_DEMO, sin duplicarse.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import os
import sys
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import seguridad  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from motor import usuarios_iniciales  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
admin = auth.cliente(app)
anonimo = TestClient(app)

A, V, AU, C, S = "ADMIN", "VALIDADOR", "AUDITOR", "CONSULTA", "SISTEMA"
TODOS = (A, V, AU, C, S)
X = "00000000-0000-0000-0000-000000000000"  # id inexistente: el permitido llega a 404 sin efectos

# (método, ruta, roles con permiso) — PRD §5.1, core-service.
MATRIZ = [
    ("GET", "/api/v1/auth/me", (A, V, AU, C)),
    ("POST", "/api/v1/auth/cambiar-contrasena", (A, V, AU, C)),
    ("POST", "/api/v1/auth/mfa/generar", (A, V, AU, C)),
    ("POST", "/api/v1/auth/mfa/activar", (A, V, AU, C)),
    ("POST", "/api/v1/auth/mfa/desactivar", (A, V, AU, C)),
    ("GET", "/api/v1/usuarios", (A,)),
    ("POST", "/api/v1/usuarios", (A,)),
    ("PATCH", f"/api/v1/usuarios/{X}", (A,)),
    ("GET", f"/api/v1/usuarios/{X}/expedientes", (A,)),
    ("PUT", f"/api/v1/usuarios/{X}/expedientes", (A,)),
    ("GET", f"/api/v1/expedientes/{X}/asignaciones", (A,)),
    ("PUT", f"/api/v1/expedientes/{X}/asignaciones", (A,)),
    ("GET", "/api/v1/expedientes/asignados", (A, V, AU, C)),
    ("POST", "/api/v1/titulares", (A, V)),
    ("PATCH", f"/api/v1/titulares/{X}", (A, V)),
    ("POST", "/api/v1/expedientes", (A, V)),
    ("PATCH", f"/api/v1/expedientes/{X}", (A, V)),
    ("POST", "/api/v1/documentos/upload", (A, V)),
    ("POST", f"/api/v1/dictamenes/{X}/ratificar", (A, V)),
    ("GET", "/api/v1/titulares", (A, V, AU)),
    ("GET", "/api/v1/expedientes", (A, V, AU)),
    ("GET", f"/api/v1/expedientes/{X}", (A, V, AU)),
    ("GET", "/api/v1/alertas", (A, V, AU)),
    ("GET", "/api/v1/bitacora", (A, V, AU)),
    ("GET", "/api/v1/bitacora/verificar-cadena", (A, V, AU)),
    ("GET", f"/api/v1/reportes/expedientes/{X}", (A, V, AU)),
    ("GET", f"/api/v1/reportes/documentos/{X}/custodia", (A, V, AU)),
    ("GET", "/api/v1/reportes/cumplimiento", (A, V, AU)),
    ("GET", "/api/v1/documentos", (A, V, AU, S)),
    ("GET", f"/api/v1/documentos/{X}", (A, V, AU, S)),
    ("GET", f"/api/v1/documentos/expediente/{X}", (A, V, AU, S)),
    ("GET", f"/api/v1/documentos/{X}/integridad", (A, V, AU, S)),
    ("GET", "/api/v1/dictamenes", (A, V, AU, S)),
    ("GET", f"/api/v1/dictamenes/{X}", (A, V, AU, S)),
    ("GET", f"/api/v1/documentos/{X}/contenido?descarga=true", (A, V, AU)),
    ("GET", f"/api/v1/documentos/{X}/contenido", (S,)),
    ("POST", "/api/v1/dictamenes", (S,)),
    ("POST", f"/api/v1/documentos/{X}/procesamiento-diferido", (S,)),
]


def _cabeceras(rol: str) -> dict:
    return auth.sistema() if rol == S else auth.cabeceras(rol)


def _pedir(cliente, metodo: str, ruta: str, rol: str):
    cuerpo = {"json": {}} if metodo in ("POST", "PUT", "PATCH") and "upload" not in ruta else {}
    return cliente.request(metodo, ruta, headers=_cabeceras(rol), **cuerpo)


@pytest.mark.parametrize("metodo,ruta,permitidos", MATRIZ, ids=[f"{m} {r}" for m, r, _ in MATRIZ])
def test_matriz_de_permisos(metodo, ruta, permitidos):
    cliente = TestClient(app, raise_server_exceptions=False)
    for rol in TODOS:
        estado = _pedir(cliente, metodo, ruta, rol).status_code
        if rol in permitidos:
            assert estado not in (401, 403), f"{rol} debe poder usar {metodo} {ruta} (respondió {estado})"
            assert estado < 500, f"{rol} en {metodo} {ruta}: error del servidor {estado}"
        else:
            assert estado == 403, f"{rol} no debe poder usar {metodo} {ruta} (respondió {estado})"


def test_toda_ruta_esta_en_la_matriz_o_es_publica():
    """Una ruta nueva sin su fila en la matriz (y en el PRD §5.1) hace fallar esta prueba."""
    publicas = {("GET", "/api/v1/health"), ("POST", "/api/v1/auth/login")}
    cubiertas = {(m, r.split("?")[0].replace(X, "{}")) for m, r, _ in MATRIZ}
    for ruta, operaciones in app.openapi()["paths"].items():
        for metodo, operacion in operaciones.items():
            clave = (metodo.upper(), ruta)
            normalizada = (metodo.upper(), "/".join("{}" if p.startswith("{") else p for p in ruta.split("/")))
            if clave in publicas:
                continue
            assert operacion.get("security"), f"{clave} no exige token"
            assert normalizada in cubiertas, f"{clave} no está en la matriz de permisos"


# ── Usuario de consulta (HU-31) ──────────────────────────────────

def _expediente() -> dict:
    with SessionLocal() as db:
        titular = TitularExpediente(rfc="ASG" + "010101" + uuid.uuid4().hex[:3].upper(),
                                    razon_social="Asignaciones de Prueba S.A.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    r = admin.post("/api/v1/expedientes", json={"titular_id": titular_id, "nombre": "Proveedor asignado"})
    assert r.status_code == 201, r.text
    return r.json()


def test_el_usuario_de_consulta_solo_ve_el_semaforo_de_sus_expedientes():
    asignado, ajeno = _expediente(), _expediente()
    consulta_id, consulta_correo, _ = auth.cuenta(C)
    validador_id, _, _ = auth.cuenta(V)
    consulta = auth.cliente(app, C)

    r = admin.put(f"/api/v1/expedientes/{asignado['id']}/asignaciones",
                  json={"usuario_ids": [consulta_id, validador_id, consulta_id]})
    assert r.status_code == 200 and {u["id"] for u in r.json()} == {consulta_id, validador_id}

    vistos = consulta.get("/api/v1/expedientes/asignados").json()
    ids = {e["id"] for e in vistos}
    assert asignado["id"] in ids and ajeno["id"] not in ids
    [visto] = [e for e in vistos if e["id"] == asignado["id"]]
    assert set(visto) == {"id", "codigo_expediente", "nombre", "tipo_expediente", "razon_social", "rfc",
                          "estado_cumplimiento", "actualizado_en"}, "Solo el semáforo, sin documentos ni alertas"
    assert visto["estado_cumplimiento"] == "NO_CONFORME", "Le falta el obligatorio crítico"
    assert consulta.get(f"/api/v1/expedientes/{asignado['id']}").status_code == 403
    assert consulta.get("/api/v1/alertas").status_code == 403

    [evento] = admin.get("/api/v1/bitacora", params={"expediente_id": asignado["id"],
                                                     "evento": "ASIGNACION_EXPEDIENTE"}).json()
    assert evento["usuario"] == auth.correo(A) and evento["detalle"]["anteriores"] == []
    assert consulta_correo in evento["detalle"]["nuevos"]

    # La misma lista no deja otro evento; quitar a uno sí, con la lista anterior.
    admin.put(f"/api/v1/expedientes/{asignado['id']}/asignaciones", json={"usuario_ids": [validador_id, consulta_id]})
    admin.put(f"/api/v1/expedientes/{asignado['id']}/asignaciones", json={"usuario_ids": [validador_id]})
    eventos = admin.get("/api/v1/bitacora", params={"expediente_id": asignado["id"],
                                                    "evento": "ASIGNACION_EXPEDIENTE"}).json()
    assert len(eventos) == 2 and consulta_correo in eventos[0]["detalle"]["anteriores"]
    assert asignado["id"] not in {e["id"] for e in consulta.get("/api/v1/expedientes/asignados").json()}

    r = admin.put(f"/api/v1/expedientes/{asignado['id']}/asignaciones", json={"usuario_ids": [X]})
    assert r.status_code == 422 and X in r.json()["detail"]


def test_asignar_los_expedientes_de_una_persona():
    """Vista Usuarios (F4): se eligen los expedientes de una cuenta; cada expediente afectado deja su evento."""
    uno, dos, tres = _expediente(), _expediente(), _expediente()
    persona = admin.post("/api/v1/usuarios", json={"email": f"asig{uuid.uuid4().hex[:6]}@example.com",
                                                   "nombre_completo": "Consulta asignada", "rol": "CONSULTA",
                                                   "contrasena_temporal": "Temporal-2026"}).json()
    validador_id, validador_correo, _ = auth.cuenta(V)
    admin.put(f"/api/v1/expedientes/{dos['id']}/asignaciones", json={"usuario_ids": [validador_id]})
    url = f"/api/v1/usuarios/{persona['id']}/expedientes"

    r = admin.put(url, json={"expediente_ids": [uno["id"], dos["id"]]})
    assert r.status_code == 200 and r.json() == sorted([uno["id"], dos["id"]])
    asignados_dos = admin.get(f"/api/v1/expedientes/{dos['id']}/asignaciones").json()
    assert {u["email"] for u in asignados_dos} == {persona["email"], validador_correo}, "No quita a los demás"

    r = admin.put(url, json={"expediente_ids": [dos["id"], tres["id"]]})
    assert r.json() == sorted([dos["id"], tres["id"]]) and admin.get(url).json() == r.json()
    por_expediente = {
        clave: len(admin.get("/api/v1/bitacora", params={"expediente_id": exp["id"],
                                                         "evento": "ASIGNACION_EXPEDIENTE"}).json())
        for clave, exp in (("uno", uno), ("dos", dos), ("tres", tres))
    }
    assert por_expediente == {"uno": 2, "dos": 2, "tres": 1}, por_expediente  # alta y baja; validador + persona; alta
    assert admin.put(url, json={"expediente_ids": [dos["id"], tres["id"]]}).json() == r.json()
    assert len(admin.get("/api/v1/bitacora", params={"expediente_id": tres["id"],
                                                     "evento": "ASIGNACION_EXPEDIENTE"}).json()) == 1, "Sin cambio, sin evento"
    assert admin.put(url, json={"expediente_ids": [X]}).status_code == 422
    assert admin.get(f"/api/v1/usuarios/{X}/expedientes").status_code == 404


# ── Gestión de cuentas (HU-05) ───────────────────────────────────

def test_alta_y_cambios_de_una_cuenta_quedan_en_la_bitacora():
    correo = f"Nueva.{uuid.uuid4().hex[:8]}@Example.com"
    r = admin.post("/api/v1/usuarios", json={"email": correo, "nombre_completo": "  Ana   López ",
                                             "rol": "AUDITOR", "contrasena_temporal": "Temporal-2026"})
    assert r.status_code == 201, r.text
    nueva = r.json()
    assert nueva["email"] == correo.lower() and nueva["nombre_completo"] == "Ana López"
    assert nueva["debe_cambiar_contrasena"] and nueva["activo"]
    assert admin.post("/api/v1/usuarios", json={"email": correo, "nombre_completo": "Otra", "rol": "AUDITOR",
                                                "contrasena_temporal": "Temporal-2026"}).status_code == 409
    for invalido in ({"email": "sin-arroba"}, {"rol": "SISTEMA"}, {"contrasena_temporal": "corta"}):
        cuerpo = {"email": f"x{uuid.uuid4().hex[:6]}@example.com", "nombre_completo": "X", "rol": "AUDITOR",
                  "contrasena_temporal": "Temporal-2026", **invalido}
        assert admin.post("/api/v1/usuarios", json=cuerpo).status_code == 422, invalido

    r = admin.patch(f"/api/v1/usuarios/{nueva['id']}", json={"rol": "VALIDADOR", "activo": False})
    assert r.status_code == 200 and r.json()["rol"] == "VALIDADOR" and not r.json()["activo"]
    r = admin.patch(f"/api/v1/usuarios/{nueva['id']}", json={"activo": True, "contrasena_temporal": "Restablecida-2026"})
    assert r.status_code == 200 and r.json()["debe_cambiar_contrasena"]
    assert admin.patch(f"/api/v1/usuarios/{nueva['id']}", json={"rol": "VALIDADOR"}).status_code == 200

    eventos = [e for e in admin.get("/api/v1/bitacora", params={"limite": 500}).json()
               if (e["detalle"] or {}).get("usuario_id") == nueva["id"]]
    assert [e["evento"] for e in eventos] == ["ACTUALIZACION_USUARIO", "ACTUALIZACION_USUARIO", "ALTA_USUARIO"], (
        "Sin cambios no hay evento")
    assert eventos[1]["detalle"]["cambios"] == {"rol": {"anterior": "AUDITOR", "nuevo": "VALIDADOR"},
                                                "activo": {"anterior": True, "nuevo": False}}
    assert eventos[0]["detalle"]["cambios"]["contrasena"] == {"restablecida": True}
    assert all(e["usuario"] == auth.correo(A) for e in eventos)
    assert "Restablecida-2026" not in str(eventos) and "Temporal-2026" not in str(eventos)


def test_el_administrador_no_puede_quitarse_su_propio_acceso():
    admin_id, _, _ = auth.cuenta(A)
    for cambio in ({"rol": "AUDITOR"}, {"activo": False}):
        r = admin.patch(f"/api/v1/usuarios/{admin_id}", json=cambio)
        assert r.status_code == 409, cambio
    assert admin.patch(f"/api/v1/usuarios/{admin_id}", json={"rol": "ADMIN"}).status_code == 200


def test_restablecer_la_contrasena_desbloquea_la_cuenta():
    r = admin.post("/api/v1/usuarios", json={"email": f"bloq{uuid.uuid4().hex[:6]}@example.com",
                                             "nombre_completo": "Bloqueada", "rol": "VALIDADOR",
                                             "contrasena_temporal": "Temporal-2026"})
    cuenta = r.json()
    for _ in range(5):
        anonimo.post("/api/v1/auth/login", json={"email": cuenta["email"], "contrasena": "Equivocada-2026"})
    assert anonimo.post("/api/v1/auth/login", json={"email": cuenta["email"],
                                                    "contrasena": "Temporal-2026"}).status_code == 429
    admin.patch(f"/api/v1/usuarios/{cuenta['id']}", json={"contrasena_temporal": "Restablecida-2026"})
    assert anonimo.post("/api/v1/auth/login", json={"email": cuenta["email"],
                                                    "contrasena": "Restablecida-2026"}).status_code == 200


# ── Usuario real en la bitácora (HU-07) ──────────────────────────

def _documento() -> dict:
    exp = _expediente()
    r = admin.post("/api/v1/documentos/upload", data={"expediente_id": exp["id"], "tipo_documento": "CSF_SAT"},
                   files={"file": ("csf.pdf", b"%PDF-1.4 " + os.urandom(16), "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json()


def _evento(documento_id: str, evento: str) -> dict:
    [e] = admin.get("/api/v1/bitacora", params={"documento_id": documento_id, "evento": evento}).json()
    return e


def test_la_bitacora_registra_a_la_persona_y_no_al_servicio():
    doc = _documento()
    assert _evento(doc["id"], "INGESTA_DOCUMENTO")["usuario"] == auth.correo(A)

    # El ai-service registra el dictamen con SISTEMA y la persona que pidió la auditoría.
    validador = auth.correo(V)
    r = admin.post("/api/v1/dictamenes", headers=auth.sistema(validador),
                   json={"documento_id": doc["id"], "estatus": "EN_REVISION", "nivel_confianza": 0.8,
                         "usuario": "nombre-escrito-a-mano"})
    assert r.status_code == 201, r.text
    dictamen_id = r.json()["id"]
    assert _evento(doc["id"], "DICTAMEN_IA")["usuario"] == validador

    # Una tarea de fondo, sin persona: SISTEMA. Una cabecera malformada no se toma.
    r = admin.post(f"/api/v1/documentos/{doc['id']}/procesamiento-diferido",
                   headers={**auth.sistema(), seguridad.CABECERA_ACTOR: "no es un correo"},
                   json={"motivo": "La IA no respondió.", "intentos": 1, "max_intentos": 6})
    assert r.status_code == 200, r.text
    assert _evento(doc["id"], "PROCESAMIENTO_DIFERIDO")["usuario"] == "SISTEMA"

    # Con un token de persona, X-Usuario-Actor no suplanta a nadie; ratifica el validador en sesión.
    r = admin.post(f"/api/v1/dictamenes/{dictamen_id}/ratificar",
                   headers={**auth.cabeceras(V), seguridad.CABECERA_ACTOR: "otra.persona@example.com"},
                   json={"nuevo_estatus": "CONFORME", "justificacion": "Cotejada contra el portal del SAT.",
                         "usuario": "otra.persona"})
    assert r.status_code == 200 and r.json()["revisado_por"] == validador
    assert _evento(doc["id"], "RATIFICACION_HUMANA")["usuario"] == validador


def test_la_descarga_del_original_registra_a_quien_descarga():
    doc = _documento()
    r = admin.get(f"/api/v1/documentos/{doc['id']}/contenido", params={"descarga": "true"},
                  headers=auth.cabeceras(AU))
    assert r.status_code == 200
    assert _evento(doc["id"], "DESCARGA_DOCUMENTO")["usuario"] == auth.correo(AU)


# ── Cuentas iniciales ────────────────────────────────────────────

def test_usuarios_de_demostracion_y_administrador_inicial(monkeypatch):
    monkeypatch.setenv("USUARIOS_DEMO", "true")
    with SessionLocal() as db:
        primera = usuarios_iniciales.crear(db)
        segunda = usuarios_iniciales.crear(db)
    demo = [e for _, e, _, _ in usuarios_iniciales.USUARIOS_DEMO]
    assert set(demo) <= set(primera) | _existentes(demo) and segunda == [], "No se duplican"
    for rol, correo, _, contrasena in usuarios_iniciales.USUARIOS_DEMO:
        r = anonimo.post("/api/v1/auth/login", json={"email": correo, "contrasena": contrasena})
        assert r.status_code == 200 and r.json()["usuario"]["rol"] == rol
        assert not r.json()["usuario"]["debe_cambiar_contrasena"]

    # Base sin cuentas: el administrador del .env se crea con su contraseña como temporal.
    correo = f"admin.inicial.{uuid.uuid4().hex[:6]}@example.com"
    monkeypatch.setenv("USUARIOS_DEMO", "false")
    monkeypatch.setenv("ADMIN_INICIAL_EMAIL", correo)
    monkeypatch.setenv("ADMIN_INICIAL_CONTRASENA", "Inicial-2026")
    monkeypatch.setattr(usuarios_iniciales, "hay_cuentas", lambda db: False)
    with SessionLocal() as db:
        assert usuarios_iniciales.crear(db) == [correo]
        cuenta = db.query(Usuario).filter(Usuario.email == correo).one()
        assert cuenta.rol == "ADMIN" and cuenta.debe_cambiar_contrasena
    monkeypatch.setenv("ADMIN_INICIAL_CONTRASENA", "corta")
    with SessionLocal() as db, pytest.raises(seguridad.ConfiguracionInvalidaError):
        usuarios_iniciales.crear(db)


def _existentes(correos: list[str]) -> set[str]:
    with SessionLocal() as db:
        return {e for (e,) in db.query(Usuario.email).filter(Usuario.email.in_(correos)).all()}
