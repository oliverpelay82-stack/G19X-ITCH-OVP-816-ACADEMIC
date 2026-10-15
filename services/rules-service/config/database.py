"""
Configuración de la base de datos del rules-service: PostgreSQL 17 (DOC-08), el único
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
# create_all() no altera tablas existentes: estas sentencias agregan las
# columnas nuevas del catálogo sobre una tabla ya poblada.
_MIGRACIONES_POSTGRES = [
    # RF-06: reglas por tipo de expediente. RIE-02 / RF-07: anexos vinculados.
    "ALTER TABLE reglas_validacion ADD COLUMN IF NOT EXISTS tipo_expediente VARCHAR(20)",
    "ALTER TABLE reglas_validacion ADD COLUMN IF NOT EXISTS documento_principal VARCHAR(50)",
    # Códigos compuestos del alta por tipos («RDS-04-COMP_DOMICILIO»): hasta 45
    # caracteres. Ampliar un VARCHAR no reescribe la tabla; solo se aplica si
    # la columna aún es más corta.
    """
    DO $$
    BEGIN
        IF (SELECT character_maximum_length FROM information_schema.columns
             WHERE table_schema = current_schema() AND table_name = 'reglas_validacion'
               AND column_name = 'codigo_regla') < 50 THEN
            ALTER TABLE reglas_validacion ALTER COLUMN codigo_regla TYPE VARCHAR(50);
        END IF;
    END $$
    """,
]

# Migración de datos, una sola vez (cuando la columna tipo_expediente se crea):
# el inventario obligatorio previo (CSF, domicilio y acta) es el del expediente
# corporativo del DOC-02. Sin esto, un expediente jurídico exigiría la CSF.
_ASIGNAR_INVENTARIO_CORPORATIVO = """
    UPDATE reglas_validacion SET tipo_expediente = 'CORPORATIVO'
     WHERE codigo_regla IN ('RIE-01-CSF', 'RIE-01-DOM', 'RIE-01-ACTA') AND tipo_expediente IS NULL
"""


def _sentencias_check() -> list[str]:
    """
    CHECK de la familia normativa, de la severidad y del tipo de expediente, construidos con los
    mismos Literal que valida la API (schemas/regla_schema.py). Se reemplazan en
    cada arranque, así que un valor nuevo en el esquema llega a la base solo.
    """
    from typing import get_args

    from schemas.regla_schema import FamiliaRegla, Severidad, TipoExpediente

    def lista(valores) -> str:
        return ", ".join("'" + v.replace("'", "''") + "'" for v in valores)

    restricciones = {
        "ck_reglas_validacion_familia_regla": f"familia_regla IN ({lista(get_args(FamiliaRegla))})",
        "ck_reglas_validacion_severidad": f"severidad IN ({lista(get_args(Severidad))})",
        # Nulo: la regla aplica a todos los tipos de expediente (RF-06).
        "ck_reglas_validacion_tipo_expediente": f"tipo_expediente IS NULL OR tipo_expediente IN ({lista(get_args(TipoExpediente))})",
    }
    sentencias = []
    for nombre, condicion in restricciones.items():
        sentencias.append(f"ALTER TABLE reglas_validacion DROP CONSTRAINT IF EXISTS {nombre}")
        sentencias.append(f"ALTER TABLE reglas_validacion ADD CONSTRAINT {nombre} CHECK ({condicion})")
    return sentencias


def init_db():
    """
    Crea las tablas que aún no existen y aplica las migraciones idempotentes.
    """
    import models  # noqa: F401  (registra todas las entidades en Base.metadata)

    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        columna_previa = conn.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND table_name = 'reglas_validacion' AND column_name = 'tipo_expediente'"
        )).first()
        for sentencia in _MIGRACIONES_POSTGRES:
            conn.execute(text(sentencia))
        if columna_previa is None:
            conn.execute(text(_ASIGNAR_INVENTARIO_CORPORATIVO))
        for sentencia in _sentencias_check():
            conn.execute(text(sentencia))
    print("[Base de Datos] Tablas y migraciones sincronizadas con éxito.")
