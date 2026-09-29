"""
Esquema de PostgreSQL del core-service tras init_db (índices, claves foráneas
y restricciones). Corre sobre la base de pruebas plurione_compliance_test, que
bd_pruebas recrea en cada ejecución, así que también prueba que las
migraciones idempotentes se apliquen sobre una base nueva y que init_db pueda
repetirse sin error.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

bd_pruebas.preparar_entorno()

import uuid  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from config.database import engine, init_db  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
init_db()  # idempotente: una segunda ejecución no falla ni duplica nada


def test_indice_documentos_expediente_id():
    indices = {i["name"]: i["column_names"] for i in inspect(engine).get_indexes("documentos")}
    assert indices.get("ix_documentos_expediente_id") == ["expediente_id"], indices


_FKS = {("expedientes", "titular_id", "titulares_expediente"), ("documentos", "expediente_id", "expedientes")}


def _borrado_de_fks() -> dict[tuple[str, str], str]:
    """confdeltype de cada FK de custodia: 'r' RESTRICT, 'c' CASCADE."""
    with engine.connect() as c:
        filas = c.execute(text("""
            SELECT c.conrelid::regclass::text, a.attname, c.confdeltype
              FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND c.conrelid::regclass::text IN ('expedientes', 'documentos')"""))
        return {(t, col): tipo for t, col, tipo in filas}


def test_fk_de_custodia_en_restrict_incluso_desde_una_base_antigua():
    # Base antigua simulada: las dos FK vuelven a ON DELETE CASCADE.
    with engine.begin() as c:
        for tabla, columna, destino in _FKS:
            nombre = c.execute(text(
                "SELECT conname FROM pg_constraint c JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1] "
                "WHERE c.contype = 'f' AND c.conrelid = CAST(:t AS regclass) AND a.attname = :col"), {"t": tabla, "col": columna}).scalar()
            c.execute(text(f'ALTER TABLE {tabla} DROP CONSTRAINT "{nombre}"'))
            c.execute(text(f'ALTER TABLE {tabla} ADD CONSTRAINT "{nombre}" FOREIGN KEY ({columna}) REFERENCES {destino} (id) ON DELETE CASCADE'))
    assert set(_borrado_de_fks().values()) == {"c"}
    init_db()
    assert _borrado_de_fks() == {("expedientes", "titular_id"): "r", ("documentos", "expediente_id"): "r"}


def test_borrar_un_titular_con_expediente_se_rechaza():
    titular, expediente = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.connect() as c:
        tx = c.begin()
        try:
            c.execute(text("INSERT INTO titulares_expediente (id, rfc, razon_social, tipo_persona, categoria, creado_en) "
                           "VALUES (:id, 'RES010101AAA', 'Restrict S.A. de C.V.', 'MORAL', 'PROVEEDOR', now())"), {"id": titular})
            c.execute(text("INSERT INTO expedientes (id, titular_id, codigo_expediente, estado_cumplimiento, porcentaje_completitud, "
                           "actualizado_en, tipo_expediente) VALUES (:id, :t, 'EXP-TEST-RESTRICT', 'EN_REVISION', 0, now(), 'CORPORATIVO')"),
                      {"id": expediente, "t": titular})
            with pytest.raises(IntegrityError) as error:
                c.execute(text("DELETE FROM titulares_expediente WHERE id = :id"), {"id": titular})
            assert error.value.orig.pgcode == "23503"  # foreign_key_violation (independiente del idioma del servidor)
        finally:
            tx.rollback()


CHECKS = {
    "ck_expedientes_estado_cumplimiento", "ck_expedientes_tipo_expediente",
    "ck_documentos_tipo_documento", "ck_documentos_estado_integridad",
    "ck_dictamenes_auditoria_estatus", "ck_dictamenes_auditoria_estatus_preliminar",
}


def test_restricciones_check_presentes():
    with engine.connect() as c:
        nombres = {r[0] for r in c.execute(text("SELECT conname FROM pg_constraint WHERE contype = 'c'"))}
    assert CHECKS <= nombres, CHECKS - nombres


def _insertar_expediente(c, **campos) -> None:
    titular = str(uuid.uuid4())
    c.execute(text("INSERT INTO titulares_expediente (id, rfc, razon_social, tipo_persona, categoria, creado_en) "
                   "VALUES (:id, :rfc, 'Check S.A. de C.V.', 'MORAL', 'PROVEEDOR', now())"),
              {"id": titular, "rfc": f"CHK{uuid.uuid4().hex[:9].upper()}"})
    valores = {"estado": "EN_REVISION", "tipo": "CORPORATIVO", **campos}
    c.execute(text("INSERT INTO expedientes (id, titular_id, codigo_expediente, estado_cumplimiento, porcentaje_completitud, "
                   "actualizado_en, tipo_expediente) VALUES (:id, :t, :codigo, :estado, 0, now(), :tipo)"),
              {"id": str(uuid.uuid4()), "t": titular, "codigo": f"EXP-CHK-{uuid.uuid4().hex[:8]}", **valores})


@pytest.mark.parametrize("campos", [{"estado": "APROBADO"}, {"tipo": "FISCAL"}])
def test_valor_fuera_del_catalogo_se_rechaza(campos):
    with engine.connect() as c:
        tx = c.begin()
        try:
            with pytest.raises(IntegrityError) as error:
                _insertar_expediente(c, **campos)
            assert error.value.orig.pgcode == "23514"  # check_violation
        finally:
            tx.rollback()


def test_tipo_documento_heredado_otro_se_admite():
    with engine.connect() as c:
        tx = c.begin()
        try:
            _insertar_expediente(c)
            expediente = c.execute(text("SELECT id FROM expedientes ORDER BY actualizado_en DESC LIMIT 1")).scalar()
            for tipo, admitido in (("OTRO", True), ("INVENTADO", False)):
                c.execute(text("SAVEPOINT prueba"))
                try:
                    c.execute(text("INSERT INTO documentos (id, expediente_id, tipo_documento, nombre_archivo_original, "
                                   "ruta_almacenamiento, hash_sha256, tamanio_bytes, mime_type, estado_integridad, creado_en) "
                                   "VALUES (:id, :e, :tipo, 'x.pdf', '/x', :h, 1, 'application/pdf', 'INTEGRO', now())"),
                              {"id": str(uuid.uuid4()), "e": expediente, "tipo": tipo, "h": "0" * 64})
                    assert admitido, f"{tipo} debió rechazarse"
                except IntegrityError as exc:
                    assert not admitido and exc.orig.pgcode == "23514", exc
                    c.execute(text("ROLLBACK TO SAVEPOINT prueba"))
        finally:
            tx.rollback()


if __name__ == "__main__":
    test_indice_documentos_expediente_id()
    test_fk_de_custodia_en_restrict_incluso_desde_una_base_antigua()
    test_borrar_un_titular_con_expediente_se_rechaza()
    test_restricciones_check_presentes()
    for campos in ({"estado": "APROBADO"}, {"tipo": "FISCAL"}):
        test_valor_fuera_del_catalogo_se_rechaza(campos)
    test_tipo_documento_heredado_otro_se_admite()
    print("PASÓ: índice, claves foráneas de custodia y restricciones CHECK")
