"""
M6 — Versión del catálogo en el rules-service (PRD §21.6; HU-54).

  1. La versión no depende del orden de las reglas ni de su identificador o
     fecha de alta, y cambia al pausar una regla o editar su descripción.
  2. GET /reglas/version la publica y coincide con la cabecera
     X-Version-Catalogo del inventario de documentos obligatorios.

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
from motor import version_catalogo  # noqa: E402

client = TestClient(app)


def _regla(codigo: str, **cambios) -> SimpleNamespace:
    base = dict(id=codigo.lower(), codigo_regla=codigo, nombre_regla=f"Regla {codigo}", familia_regla="RIE",
                descripcion="Documento exigido.", severidad="CRITICA", accion="Solicitar.", tipo_documento="CSF_SAT",
                documento_obligatorio=True, tipo_expediente="CORPORATIVO", documento_principal=None,
                dias_maximos_vigencia=None, activo=True, creado_en="2026-09-30")
    return SimpleNamespace(**{**base, **cambios})


def test_la_version_es_estable_y_sensible_a_los_cambios():
    reglas = [_regla("RIE-01-A"), _regla("RIE-01-B")]
    version = version_catalogo.calcular(reglas)

    assert version.startswith("cat-") and len(version) == 16
    assert version_catalogo.calcular(list(reversed(reglas))) == version, "El orden no cuenta"
    assert version_catalogo.calcular([_regla("RIE-01-A", id="otro", creado_en="2027-01-01"), reglas[1]]) == version
    assert version_catalogo.calcular([_regla("RIE-01-A", activo=False), reglas[1]]) != version, "Pausar la cambia"
    assert version_catalogo.calcular([_regla("RIE-01-A", descripcion="Otra."), reglas[1]]) != version


def test_el_endpoint_y_la_cabecera_coinciden():
    publicada = client.get("/api/v1/reglas/version")
    assert publicada.status_code == 200
    datos = publicada.json()
    assert datos["version_catalogo"].startswith("cat-") and datos["reglas"] >= datos["reglas_activas"] > 0

    inventario = client.get("/api/v1/reglas/documentos-obligatorios", params={"tipo_expediente": "CORPORATIVO"})
    assert inventario.headers["X-Version-Catalogo"] == datos["version_catalogo"]
