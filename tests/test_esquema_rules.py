"""
Restricciones del catálogo de reglas (rules-service), sin escribir en él:

1. La API rechaza con 422 una familia normativa fuera del DOC-05 (antes se
   aceptaba cualquier texto).
2. La base también la rechaza (CHECK), aunque la escritura no pase por la API;
   la prueba corre dentro de una transacción que se revierte.
"""
import os
import sys
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from config.database import engine, init_db  # noqa: E402
from main import app  # noqa: E402
from schemas.regla_schema import ReglaCreate  # noqa: E402  (antes de que otra suite active otro servicio)

init_db()

REGLA = {
    "codigo_regla": "XYZ-01",
    "nombre_regla": "Regla de prueba",
    "familia_regla": "XYZ",
    "descripcion": "Familia inexistente para probar la validación.",
    "severidad": "MEDIA",
    "accion": "Ninguna",
}


def test_api_rechaza_familia_fuera_del_doc05():
    respuesta = TestClient(app).post("/api/v1/reglas", json=REGLA)
    assert respuesta.status_code == 422, respuesta.text
    assert any(e["loc"][-1] == "familia_regla" for e in respuesta.json()["detail"])


@pytest.mark.parametrize("columna, valor", [("familia_regla", "XYZ"), ("tipo_expediente", "FISCAL")])
def test_base_rechaza_valores_fuera_del_catalogo(columna, valor):
    campos = {"familia_regla": "RDS", "tipo_expediente": None, columna: valor}
    with engine.connect() as c:
        tx = c.begin()
        try:
            with pytest.raises(IntegrityError) as error:
                c.execute(text(
                    "INSERT INTO reglas_validacion (id, codigo_regla, nombre_regla, familia_regla, descripcion, severidad, "
                    "accion, documento_obligatorio, activo, creado_en, tipo_expediente) VALUES (:id, :codigo, 'x', "
                    ":familia_regla, 'descripcion de prueba', 'MEDIA', 'x', false, false, now(), :tipo_expediente)"),
                    {"id": str(uuid.uuid4()), "codigo": f"CHK-{uuid.uuid4().hex[:8]}", **campos})
            assert error.value.orig.pgcode == "23514"  # check_violation
        finally:
            tx.rollback()


# Código compuesto más largo que genera el alta por tipos (ReglasTab): código
# base de hasta 20 caracteres + «-» + el tipo documental más largo del catálogo.
CODIGO_COMPUESTO_MAXIMO = "RDS-04-XXXXXXXXXXXXX-ACUERDO_CONFIDENCIALIDAD"  # 45 caracteres


def test_codigo_compuesto_cabe_en_el_esquema_y_en_la_columna():
    assert len(CODIGO_COMPUESTO_MAXIMO) == 45
    for codigo in ("RDS-04-COMP_DOMICILIO", CODIGO_COMPUESTO_MAXIMO):
        ReglaCreate(**{**REGLA, "familia_regla": "RDS", "codigo_regla": codigo})  # no lanza ValidationError
    with engine.connect() as c:
        longitud = c.execute(text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name = 'reglas_validacion' AND column_name = 'codigo_regla'")).scalar()
    assert longitud >= len(CODIGO_COMPUESTO_MAXIMO), longitud


if __name__ == "__main__":
    test_api_rechaza_familia_fuera_del_doc05()
    test_codigo_compuesto_cabe_en_el_esquema_y_en_la_columna()
    for columna, valor in (("familia_regla", "XYZ"), ("tipo_expediente", "FISCAL")):
        test_base_rechaza_valores_fuera_del_catalogo(columna, valor)
    print("PASÓ: familia normativa y tipo de expediente del catálogo")
