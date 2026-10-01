"""
RF-09 — Tipos de documento declarados por reglas dinámicas (RDS-01, RDS-02;
docs/uml/rf09-actividad-tipo-documento-nuevo.puml).

  1. Agrupación (unitaria, sin BD): un tipo por código, con el nombre y el
     tipo de expediente de la regla RDS más antigua; activo si alguna de sus
     reglas lo está; las reglas de otras familias o sin tipo no cuentan.
  2. GET /reglas/tipos-documento responde contra el catálogo real.

Solo lectura: no modifica el catálogo (como test_rules_service).
"""
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from controllers.regla_controller import agrupar_tipos_declarados  # noqa: E402

client = TestClient(app)


def _regla(codigo, tipo, nombre, creado, familia="RDS", activo=True, expediente="REGULATORIO"):
    return SimpleNamespace(codigo_regla=codigo, tipo_documento=tipo, nombre_regla=nombre, creado_en=creado,
                           familia_regla=familia, activo=activo, tipo_expediente=expediente)


def test_un_tipo_por_codigo_con_el_nombre_de_su_primera_regla():
    tipos = agrupar_tipos_declarados([
        _regla("RDS-PIA-2", "PERMISO_DE_IMPACTO_AMBIENTAL", "Vigencia del permiso", "2026-10-02"),
        _regla("RDS-PERMISO_DE_IMPACTO_AMBIENTAL", "permiso_de_impacto_ambiental ", "Permiso de Impacto Ambiental",
               "2026-10-01", activo=False),
        _regla("RDS-DEPC", "DICTAMEN_PROTECCION_CIVIL", "Dictamen de Protección Civil", "2026-10-01", activo=False),
        _regla("RIE-01-X", "OTRO_TIPO", "Completitud", "2026-09-01", familia="RIE"),
        _regla("RDS-04", None, "Regla general", "2026-09-01"),
    ])
    por_codigo = {t.tipo_documento: t for t in tipos}

    assert set(por_codigo) == {"PERMISO_DE_IMPACTO_AMBIENTAL", "DICTAMEN_PROTECCION_CIVIL"}
    pia = por_codigo["PERMISO_DE_IMPACTO_AMBIENTAL"]
    assert pia.nombre == "Permiso de Impacto Ambiental" and pia.codigo_regla == "RDS-PERMISO_DE_IMPACTO_AMBIENTAL"
    assert pia.activo is True, "Activo si alguna de sus reglas lo está"
    assert pia.tipo_expediente == "REGULATORIO"
    assert por_codigo["DICTAMEN_PROTECCION_CIVIL"].activo is False, "Con todas sus reglas pausadas"


def test_el_endpoint_responde_con_el_catalogo_real():
    r = client.get("/api/v1/reglas/tipos-documento")
    assert r.status_code == 200
    assert all({"tipo_documento", "nombre", "activo", "codigo_regla"} <= set(t) for t in r.json())
