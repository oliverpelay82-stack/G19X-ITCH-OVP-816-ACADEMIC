"""
Módulo 7 — Autorización del rules-service (RF-26; PRD §5.1 y §5.2;
docs/uml/m7-secuencia-propagacion-sistema.puml).

Corre sobre la base de pruebas plurione_compliance_test con cuentas reales,
creadas por el core (su tabla ``usuarios``), sin cuentas ficticias:

  1. Matriz del rules: lectura del catálogo y evaluación de la vigencia para
     ADMIN, VALIDADOR, AUDITOR y SISTEMA; la consulta no entra; pausar una regla es
     solo del ADMIN.
  2. Alta de reglas: el ADMIN, de cualquier familia; el VALIDADOR, solo RDS (un
     tipo de documento nuevo, RDS-01); SISTEMA no da de alta reglas.
  3. La cuenta se confirma en la base en cada petición: desactivada → 401, con
     contraseña temporal → 403, aunque el token siga vigente.
  4. El core llama al rules con un token SISTEMA que el rules acepta.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402
import servicios  # noqa: E402

# 1) Core sobre la base de pruebas: crea la tabla usuarios y las cuentas.
bd_pruebas.preparar_entorno()
from config.database import SessionLocal as SesionCore, init_db as init_core  # noqa: E402
from clients import rules_client as rules_client_core  # noqa: E402
from models.usuario import Usuario  # noqa: E402

init_core()
auth = bd_pruebas.Autenticacion()

# 2) Rules sobre la misma base de pruebas.
servicios.activar("rules-service")
os.environ.pop("DATABASE_URL", None)
os.environ["DB_NAME"] = bd_pruebas.NOMBRE_BD_PRUEBAS

from fastapi.testclient import TestClient  # noqa: E402
from config import seguridad  # noqa: E402
from config.database import engine, init_db  # noqa: E402
from main import app  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
cliente = TestClient(app)

A, V, AU, C, S = "ADMIN", "VALIDADOR", "AUDITOR", "CONSULTA", "SISTEMA"
X = "00000000-0000-0000-0000-000000000000"


def _cabeceras(rol: str) -> dict:
    return auth.sistema() if rol == S else auth.cabeceras(rol)


def _regla(familia: str) -> dict:
    return {"codigo_regla": f"{familia}-M7-{uuid.uuid4().hex[:6]}", "nombre_regla": "Regla de la prueba M7",
            "familia_regla": familia, "descripcion": "Alta de una regla para probar los permisos.",
            "severidad": "MEDIA", "accion": "Revisar", "tipo_documento": "PERMISO_M7_PRUEBA"}


def test_matriz_de_permisos_del_rules():
    casos = [
        ("GET", "/api/v1/reglas", None, (A, V, AU, S)),
        ("GET", f"/api/v1/reglas/{X}", None, (A, V, AU, S)),
        ("GET", "/api/v1/reglas/version", None, (A, V, AU, S)),
        ("GET", "/api/v1/reglas/tipos-documento", None, (A, V, AU, S)),
        ("GET", "/api/v1/reglas/documentos-obligatorios", None, (A, V, AU, S)),
        ("POST", "/api/v1/reglas/evaluar-vigencia", {"documentos": []}, (A, V, AU, S)),
        ("POST", "/api/v1/reglas", {}, (A, V)),
        ("PATCH", f"/api/v1/reglas/{X}/activo?activo=false", None, (A,)),
    ]
    for metodo, ruta, cuerpo, permitidos in casos:
        for rol in (A, V, AU, C, S):
            estado = cliente.request(metodo, ruta, headers=_cabeceras(rol),
                                     **({"json": cuerpo} if cuerpo is not None else {})).status_code
            if rol in permitidos:
                assert estado not in (401, 403) and estado < 500, f"{rol} {metodo} {ruta}: {estado}"
            else:
                assert estado == 403, f"{rol} no debe poder {metodo} {ruta} (respondió {estado})"
    assert cliente.get("/api/v1/reglas").status_code == 401, "Sin token"
    assert cliente.get("/api/v1/health").status_code == 200, "La salud es pública"


def test_alta_de_reglas_segun_el_rol():
    assert cliente.post("/api/v1/reglas", headers=_cabeceras(V), json=_regla("RIE")).status_code == 403
    assert cliente.post("/api/v1/reglas", headers=_cabeceras(S), json=_regla("RDS")).status_code == 403
    assert cliente.post("/api/v1/reglas", headers=_cabeceras(V), json=_regla("RDS")).status_code == 201
    creada = cliente.post("/api/v1/reglas", headers=_cabeceras(A), json=_regla("RIE"))
    assert creada.status_code == 201, creada.text
    regla_id = creada.json()["id"]
    assert cliente.patch(f"/api/v1/reglas/{regla_id}/activo", params={"activo": "false"},
                         headers=_cabeceras(V)).status_code == 403
    pausada = cliente.patch(f"/api/v1/reglas/{regla_id}/activo", params={"activo": "false"}, headers=_cabeceras(A))
    assert pausada.status_code == 200 and pausada.json()["activo"] is False


def _actualizar(correo: str, **campos) -> None:
    with SesionCore() as db:
        db.query(Usuario).filter(Usuario.email == correo).update(campos)
        db.commit()


def test_la_cuenta_se_confirma_en_la_base_en_cada_peticion():
    cabeceras = auth.cabeceras(A)
    correo = auth.correo(A)
    try:
        _actualizar(correo, activo=False)
        assert cliente.get("/api/v1/reglas", headers=cabeceras).status_code == 401
        _actualizar(correo, activo=True, debe_cambiar_contrasena=True)
        r = cliente.get("/api/v1/reglas", headers=cabeceras)
        assert r.status_code == 403 and "contraseña temporal" in r.json()["detail"]
        _actualizar(correo, debe_cambiar_contrasena=False, rol=AU)
        assert cliente.post("/api/v1/reglas", headers=cabeceras, json=_regla("RDS")).status_code == 403, (
            "Autoriza con el rol guardado, no con el del token")
    finally:
        _actualizar(correo, activo=True, debe_cambiar_contrasena=False, rol=A)
    assert cliente.get("/api/v1/reglas", headers=cabeceras).status_code == 200


def test_el_core_llama_al_rules_con_un_token_sistema():
    cabeceras = rules_client_core._cabeceras()
    identidad = seguridad.leer_token(cabeceras["Authorization"].removeprefix("Bearer "))
    assert identidad.es_sistema and identidad.sub == "core-service"
    assert cliente.get("/api/v1/reglas/documentos-obligatorios", headers=cabeceras).status_code == 200
