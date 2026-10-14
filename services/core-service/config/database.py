"""
Configuración de la base de datos del core-service: PostgreSQL 17 (DOC-08), el único
motor soportado. La inmutabilidad de la bitácora y de los dictámenes (triggers),
los candados de transacción (pg_advisory_xact_lock) y las columnas JSON son de
PostgreSQL.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Variables del .env del servicio, resuelto respecto de este archivo para que
# scripts/ y tests/ también puedan importar el módulo desde otro directorio.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Parámetros de conexión configurables vía .env
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "plurione_compliance")
# Trazas del SQL ejecutado: apagadas salvo DB_ECHO=true.
DB_ECHO = os.getenv("DB_ECHO", "false").strip().lower() in {"1", "true", "yes", "on"}

# URL de conexión: DATABASE_URL si existe; si no, se arma con los parámetros.
DATABASE_URL = os.getenv("DATABASE_URL") or (
    f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

# Crear el Engine de conexión. Las columnas son TIMESTAMP sin zona y psycopg2
# convierte cada fecha con zona a la de la sesión antes de guardarla: con la zona
# del servidor, una instalación local guardaba la hora de México y el contenedor
# (postgres:17-alpine) la de UTC, y la API las devolvía iguales, sin zona. La
# sesión se fija en UTC para que toda fecha guardada esté en UTC en cualquier
# despliegue; el día del negocio lo decide config/zona_horaria.py.
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verifica que la conexión siga viva antes de cada consulta
    echo=DB_ECHO,        # DB_ECHO=true imprime el SQL ejecutado
    connect_args={"options": "-c timezone=UTC"},
)

# Fábrica de sesiones para interactuar con la BD
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Clase base de la que heredarán todos los Modelos (Entidades)
Base = declarative_base()


def get_db():
    """Generador de sesión para los controladores (inyección de dependencias)."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ── Migraciones idempotentes (PostgreSQL) ──────────────────────────
# create_all() crea las tablas nuevas pero no altera las existentes; estas
# sentencias cubren los cambios de esquema sobre tablas ya pobladas y pueden
# ejecutarse en cada arranque sin efecto adicional.
_MIGRACIONES_POSTGRES = [
    # RIE-03: estado de la última verificación criptográfica del documento.
    "ALTER TABLE documentos ADD COLUMN IF NOT EXISTS estado_integridad VARCHAR(20) NOT NULL DEFAULT 'INTEGRO'",
    # RF-01 / HU-01: clasificación temática y nombre descriptivo del expediente.
    # Los expedientes previos (CSF, domicilio y acta) son corporativos (DOC-02).
    "ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS tipo_expediente VARCHAR(20) NOT NULL DEFAULT 'CORPORATIVO'",
    "ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS nombre VARCHAR(150)",
    "CREATE INDEX IF NOT EXISTS ix_expedientes_tipo_expediente ON expedientes (tipo_expediente)",
    # RF-05: fecha de apertura para filtrar. En los expedientes ya existentes se
    # toma del evento APERTURA_EXPEDIENTE de la bitácora.
    "ALTER TABLE expedientes ADD COLUMN IF NOT EXISTS creado_en TIMESTAMP",
    "CREATE INDEX IF NOT EXISTS ix_expedientes_creado_en ON expedientes (creado_en)",
    # Documentos por expediente: cada evaluación del semáforo filtra por esta FK.
    "CREATE INDEX IF NOT EXISTS ix_documentos_expediente_id ON documentos (expediente_id)",
    # Cadena de custodia: borrar un titular o un expediente no arrastra en cascada
    # a sus expedientes y documentos (antes ON DELETE CASCADE). La FK se busca por
    # tabla y columna y solo se recrea si aún no es RESTRICT ('r').
    """
    DO $$
    DECLARE
        fk RECORD;
    BEGIN
        FOR fk IN
            SELECT c.conname, c.conrelid::regclass AS tabla, a.attname AS columna, c.confrelid::regclass AS destino
              FROM pg_constraint c
              JOIN pg_attribute a ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1]
             WHERE c.contype = 'f' AND c.confdeltype <> 'r'
               AND ((c.conrelid = 'expedientes'::regclass AND a.attname = 'titular_id')
                 OR (c.conrelid = 'documentos'::regclass AND a.attname = 'expediente_id'))
        LOOP
            EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', fk.tabla, fk.conname);
            EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I FOREIGN KEY (%I) REFERENCES %s (id) ON DELETE RESTRICT',
                           fk.tabla, fk.conname, fk.columna, fk.destino);
        END LOOP;
    END $$
    """,
    """
    UPDATE expedientes e
       SET creado_en = COALESCE(
               (SELECT MIN(b.creado_en) FROM bitacora_auditoria b
                 WHERE b.expediente_id = e.id AND b.evento = 'APERTURA_EXPEDIENTE'),
               e.actualizado_en)
     WHERE e.creado_en IS NULL
    """,
    # P2 (RSC-02, RN-03): datos de representación legal del dictamen.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS representacion_legal JSON",
    # P5 (DOC-05, protocolo de auditoría): versión de la lectura y de las instrucciones.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS version_lectura VARCHAR(160)",
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS version_instrucciones VARCHAR(40)",
    # P6 (PLUS-17, retirado): columna del QR del SAT; sin uso, la conserva el trigger de RN-05.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS qr_sat JSON",
    # P6 (M6): versión del catálogo de reglas.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS version_catalogo VARCHAR(20)",
    # P7 (M7): versión de las reglas del tipo de documento.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS version_reglas_tipo VARCHAR(20)",
    # PRD §21.9: nombre del documento identificado cuando no es del tipo registrado.
    "ALTER TABLE dictamenes_auditoria ADD COLUMN IF NOT EXISTS nombre_documento_real VARCHAR(200)",
    # P5 (DOC-05, Tabla 1): marca de procesamiento diferido del documento.
    "ALTER TABLE documentos ADD COLUMN IF NOT EXISTS procesamiento_diferido JSON",
    # P6 (PLUS-18): contenido activo del PDF (las señales de edición se retiraron).
    "ALTER TABLE documentos ADD COLUMN IF NOT EXISTS senales_pdf JSON",
    # P3 (PLUS-04): sello encadenado de la bitácora. Agregar columnas es DDL:
    # el trigger de inmutabilidad (por fila) no lo impide y los eventos previos
    # no se reescriben. El índice único impide dos eventos con la misma secuencia.
    "ALTER TABLE bitacora_auditoria ADD COLUMN IF NOT EXISTS secuencia BIGINT",
    "ALTER TABLE bitacora_auditoria ADD COLUMN IF NOT EXISTS hash_anterior VARCHAR(64)",
    "ALTER TABLE bitacora_auditoria ADD COLUMN IF NOT EXISTS hash_evento VARCHAR(64)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_bitacora_secuencia ON bitacora_auditoria (secuencia)",
    # RF-27: la bitácora solo admite inserciones.
    """
    CREATE OR REPLACE FUNCTION bitacora_inmutable() RETURNS trigger AS $$
    BEGIN
        RAISE EXCEPTION 'bitacora_auditoria es inmutable: operación % no permitida (RF-27)', TG_OP;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE TRIGGER trg_bitacora_inmutable
        BEFORE UPDATE OR DELETE ON bitacora_auditoria
        FOR EACH ROW EXECUTE FUNCTION bitacora_inmutable()
    """,
    # RN-04 y RN-05: un dictamen no se borra, y su contenido original solo
    # admite una modificación: la ratificación humana, una única vez.
    """
    CREATE OR REPLACE FUNCTION dictamen_protegido() RETURNS trigger AS $$
    BEGIN
        IF TG_OP = 'DELETE' THEN
            RAISE EXCEPTION 'dictamenes_auditoria: los dictámenes no se eliminan (RN-04)';
        END IF;
        IF OLD.revisado_por_humano THEN
            RAISE EXCEPTION 'dictamenes_auditoria: el dictamen % ya fue ratificado y es definitivo', OLD.id;
        END IF;
        IF NOT NEW.revisado_por_humano
           OR NEW.documento_id IS DISTINCT FROM OLD.documento_id
           OR NEW.expediente_id IS DISTINCT FROM OLD.expediente_id
           OR NEW.estatus_preliminar IS DISTINCT FROM OLD.estatus_preliminar
           OR NEW.origen IS DISTINCT FROM OLD.origen
           OR NEW.nivel_confianza IS DISTINCT FROM OLD.nivel_confianza
           OR NEW.requiere_revision_humana IS DISTINCT FROM OLD.requiere_revision_humana
           OR NEW.vigencia_resultado IS DISTINCT FROM OLD.vigencia_resultado
           OR NEW.tipo_documento_detectado IS DISTINCT FROM OLD.tipo_documento_detectado
           OR NEW.rfc_detectado IS DISTINCT FROM OLD.rfc_detectado
           OR NEW.match_titular IS DISTINCT FROM OLD.match_titular
           OR NEW.fecha_emision_extraida IS DISTINCT FROM OLD.fecha_emision_extraida
           OR NEW.fecha_vencimiento_extraida IS DISTINCT FROM OLD.fecha_vencimiento_extraida
           OR NEW.modelo_utilizado IS DISTINCT FROM OLD.modelo_utilizado
           OR NEW.reglas_aplicadas::text IS DISTINCT FROM OLD.reglas_aplicadas::text
           OR NEW.observaciones::text IS DISTINCT FROM OLD.observaciones::text
           OR NEW.representacion_legal::text IS DISTINCT FROM OLD.representacion_legal::text
           OR NEW.version_lectura IS DISTINCT FROM OLD.version_lectura
           OR NEW.version_instrucciones IS DISTINCT FROM OLD.version_instrucciones
           OR NEW.qr_sat::text IS DISTINCT FROM OLD.qr_sat::text
           OR NEW.version_catalogo IS DISTINCT FROM OLD.version_catalogo
           OR NEW.version_reglas_tipo IS DISTINCT FROM OLD.version_reglas_tipo
           OR NEW.nombre_documento_real IS DISTINCT FROM OLD.nombre_documento_real
           OR NEW.hash_sha256 IS DISTINCT FROM OLD.hash_sha256
           OR NEW.creado_en IS DISTINCT FROM OLD.creado_en THEN
            RAISE EXCEPTION 'dictamenes_auditoria: solo la ratificación humana puede modificar un dictamen (RN-05)';
        END IF;
        RETURN NEW;
    END;
    $$ LANGUAGE plpgsql
    """,
    """
    CREATE OR REPLACE TRIGGER trg_dictamen_protegido
        BEFORE UPDATE OR DELETE ON dictamenes_auditoria
        FOR EACH ROW EXECUTE FUNCTION dictamen_protegido()
    """,
]


# RF-09: el catálogo de tipos de documento no es una lista cerrada (los tipos
# nuevos se declaran con reglas RDS en el rules-service), así que la base valida
# el formato del código y la API valida que el tipo exista (config/catalogo.py).
# El tipo heredado OTRO, que la API ya no crea, cumple el formato.
_CHECKS_DE_FORMATO = {("documentos", "tipo_documento"): r"^[A-Z][A-Z0-9_]{1,49}$"}


def _restricciones_check() -> dict[tuple[str, str], tuple[str, ...]]:
    """
    Valores permitidos por columna, tomados de los mismos enums y constantes que
    valida la API, para que la base y la API nunca diverjan.
    """
    from typing import get_args

    from motor import cumplimiento, integridad
    from schemas.dictamen_schema import EstatusDictamen
    from schemas.expediente_schema import TipoExpedienteEnum

    estados = (cumplimiento.CONFORME, cumplimiento.EN_REVISION, cumplimiento.NO_CONFORME)
    return {
        ("expedientes", "estado_cumplimiento"): estados,
        ("expedientes", "tipo_expediente"): tuple(t.value for t in TipoExpedienteEnum),
        ("documentos", "estado_integridad"): (integridad.INTEGRO, integridad.ALTERADO),
        ("dictamenes_auditoria", "estatus"): get_args(EstatusDictamen),
        ("dictamenes_auditoria", "estatus_preliminar"): get_args(EstatusDictamen),
    }


def _sentencias_check() -> list[str]:
    """
    Cada CHECK se reemplaza en cada arranque (DROP IF EXISTS + ADD): si un enum
    gana un valor, la restricción lo recoge sin migración manual. Si un registro
    existente no cumple, el arranque falla con el nombre de la restricción.
    """
    sentencias = []
    for (tabla, columna), valores in _restricciones_check().items():
        nombre = f"ck_{tabla}_{columna}"
        lista = ", ".join("'" + v.replace("'", "''") + "'" for v in valores)
        sentencias.append(f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS {nombre}")
        sentencias.append(f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} CHECK ({columna} IN ({lista}))")
    for (tabla, columna), patron in _CHECKS_DE_FORMATO.items():
        nombre = f"ck_{tabla}_{columna}"
        sentencias.append(f"ALTER TABLE {tabla} DROP CONSTRAINT IF EXISTS {nombre}")
        sentencias.append(f"ALTER TABLE {tabla} ADD CONSTRAINT {nombre} CHECK ({columna} ~ '{patron}')")
    return sentencias


def init_db():
    """
    Crea las tablas que aún no existen y aplica las migraciones idempotentes.
    """
    import models  # noqa: F401  (registra todas las entidades en Base.metadata)

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for sentencia in _MIGRACIONES_POSTGRES + _sentencias_check():
            conn.execute(text(sentencia))
    print("[Base de Datos] Tablas y migraciones sincronizadas con éxito.")
