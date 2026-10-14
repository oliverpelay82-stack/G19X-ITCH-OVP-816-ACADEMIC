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
from datetime import date, datetime, timezone  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

import pytest  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402

from sqlalchemy.orm import Session  # noqa: E402

from config import zona_horaria  # noqa: E402
from config.database import engine, init_db  # noqa: E402
from controllers.expediente_controller import consultar_expedientes  # noqa: E402

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
    "ck_usuarios_rol",
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


def test_tipo_documento_valida_el_formato_del_codigo():
    """
    RF-09: el catálogo de tipos no es una lista cerrada, así que la base valida
    el formato del código (la API valida que el tipo exista). El heredado OTRO
    y un tipo declarado por una regla RDS se admiten; un código mal formado no.
    """
    with engine.connect() as c:
        tx = c.begin()
        try:
            _insertar_expediente(c)
            expediente = c.execute(text("SELECT id FROM expedientes ORDER BY actualizado_en DESC LIMIT 1")).scalar()
            for tipo, admitido in (("OTRO", True), ("PERMISO_DE_IMPACTO_AMBIENTAL", True), ("csf_sat", False),
                                   ("TIPO CON ESPACIOS", False), ("1_EMPIEZA_CON_CIFRA", False)):
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


def test_la_sesion_guarda_las_fechas_en_utc():
    """
    Hallazgo 1 (auditoría del 14/10/2026): psycopg2 convierte una fecha con zona a
    la de la sesión antes de guardarla en un TIMESTAMP sin zona. Con la zona del
    servidor, la base local guardaba la hora de México y la del contenedor, la de
    UTC. La sesión se fija en UTC: lo guardado es UTC en cualquier despliegue.
    """
    instante = datetime(2026, 1, 10, 20, 0, tzinfo=timezone.utc)
    with engine.connect() as c:
        assert c.execute(text("SHOW timezone")).scalar() == "UTC"
        c.execute(text("CREATE TEMP TABLE t_zona (v TIMESTAMP)"))
        c.execute(text("INSERT INTO t_zona VALUES (:v)"), {"v": instante})
        assert c.execute(text("SELECT v FROM t_zona")).scalar() == datetime(2026, 1, 10, 20, 0)


def test_el_filtro_por_dia_usa_la_zona_del_negocio(monkeypatch):
    """
    El filtro desde/hasta corta los días en ZONA_HORARIA, no en la del sistema
    operativo (UTC en el contenedor). Con Tokio como zona del negocio, las 20:00
    UTC del 10 de enero son el 11 de enero; en México o en UTC serían el 10.
    """
    monkeypatch.setattr(zona_horaria, "ZONA", ZoneInfo("Asia/Tokyo"))
    titular, expediente = str(uuid.uuid4()), str(uuid.uuid4())
    with engine.connect() as c:
        tx = c.begin()
        try:
            c.execute(text("INSERT INTO titulares_expediente (id, rfc, razon_social, tipo_persona, categoria, creado_en) "
                           "VALUES (:id, 'ZON010101AAA', 'Zona S.A. de C.V.', 'MORAL', 'PROVEEDOR', now())"), {"id": titular})
            c.execute(text("INSERT INTO expedientes (id, titular_id, codigo_expediente, estado_cumplimiento, porcentaje_completitud, "
                           "creado_en, actualizado_en, tipo_expediente) VALUES (:id, :t, 'EXP-TEST-ZONA', 'EN_REVISION', 0, "
                           "'2026-01-10 20:00:00', now(), 'CORPORATIVO')"), {"id": expediente, "t": titular})
            db = Session(bind=c)
            dia = lambda d: [e.id for e in consultar_expedientes(db, q="EXP-TEST-ZONA", desde=d, hasta=d)]  # noqa: E731
            assert dia(date(2026, 1, 11)) == [expediente]
            assert dia(date(2026, 1, 10)) == []
        finally:
            tx.rollback()


if __name__ == "__main__":
    test_indice_documentos_expediente_id()
    test_fk_de_custodia_en_restrict_incluso_desde_una_base_antigua()
    test_borrar_un_titular_con_expediente_se_rechaza()
    test_restricciones_check_presentes()
    for campos in ({"estado": "APROBADO"}, {"tipo": "FISCAL"}):
        test_valor_fuera_del_catalogo_se_rechaza(campos)
    test_tipo_documento_valida_el_formato_del_codigo()
    print("PASÓ: índice, claves foráneas de custodia y restricciones CHECK")


def test_tablas_del_modulo_7():
    """
    Módulo 7 (PRD §5.2): usuarios con correo único y solo los cuatro roles del DOC-04
    (SISTEMA no se asigna a personas); asignaciones únicas por par y sin borrado en
    cascada; el usuario de la bitácora y de la ratificación admite el correo completo.
    """
    inspector = inspect(engine)
    assert {"email", "password_hash", "nombre_completo", "rol", "activo", "creado_en", "debe_cambiar_contrasena",
            "intentos_fallidos", "bloqueado_hasta", "ultimo_acceso"} <= {c["name"] for c in inspector.get_columns("usuarios")}
    assert any(u["column_names"] == ["expediente_id", "usuario_id"]
               for u in inspector.get_unique_constraints("expediente_asignaciones"))
    with engine.connect() as c:
        borrados = dict(c.execute(text("""
            SELECT a.attname, c.confdeltype FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND c.conrelid = 'expediente_asignaciones'::regclass""")).all())
        assert borrados == {"expediente_id": "r", "usuario_id": "r"}
        longitudes = dict(c.execute(text("""
            SELECT table_name, character_maximum_length FROM information_schema.columns
             WHERE (table_name, column_name) IN (('bitacora_auditoria', 'usuario'), ('dictamenes_auditoria', 'revisado_por'))""")).all())
        assert longitudes == {"bitacora_auditoria": 150, "dictamenes_auditoria": 150}
        c.rollback()  # cierra la transacción implícita de las consultas anteriores
        for rol, admitido in (("VALIDADOR", True), ("SISTEMA", False), ("OPERADOR", False)):
            tx = c.begin()
            try:
                c.execute(text("INSERT INTO usuarios (id, email, password_hash, nombre_completo, rol, activo, creado_en, "
                               "debe_cambiar_contrasena, intentos_fallidos) VALUES (:id, :email, 'x', 'X', :rol, true, now(), "
                               "false, 0)"), {"id": str(uuid.uuid4()), "email": f"{uuid.uuid4().hex}@example.com", "rol": rol})
                assert admitido, f"{rol} debió rechazarse"
            except IntegrityError as exc:
                assert not admitido and exc.orig.pgcode == "23514", rol
            finally:
                tx.rollback()
