"""
Módulo de Configuración de Base de Datos.
Equivalente a application.properties en Spring Boot.
Conecta SQLAlchemy con la base de datos MySQL local.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables del archivo .env (ubicado en backend/.env, resuelto de forma
# independiente al directorio de trabajo actual para que scripts/ y tests/
# también puedan importar este módulo desde fuera de backend/)
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# Parámetros de conexión configurables vía .env
DB_DIALECT = os.getenv("DB_DIALECT", "postgresql")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432" if DB_DIALECT == "postgresql" else "3306")
DB_NAME = os.getenv("DB_NAME", "plurione_compliance")

# URL de conexión: respeta DATABASE_URL si existe, o la construye dinámicamente
if os.getenv("DATABASE_URL"):
    DATABASE_URL = os.getenv("DATABASE_URL")
elif DB_DIALECT == "mysql":
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
else:
    DATABASE_URL = f"postgresql+psycopg2://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Crear el Engine de conexión
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,  # Verifica que la conexión siga viva antes de cada consulta
    echo=True,           # Imprime en consola el SQL ejecutado (igual que show-sql=true en Hibernate)
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
           OR NEW.reglas_aplicadas::text IS DISTINCT FROM OLD.reglas_aplicadas::text
           OR NEW.observaciones::text IS DISTINCT FROM OLD.observaciones::text
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


def init_db():
    """
    Equivalente a: spring.jpa.hibernate.ddl-auto=update
    Crea las tablas que aún no existen y aplica las migraciones idempotentes.
    """
    import models  # noqa: F401  (registra todas las entidades en Base.metadata)

    Base.metadata.create_all(bind=engine)
    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            for sentencia in _MIGRACIONES_POSTGRES:
                conn.execute(text(sentencia))
    print("[Base de Datos] Tablas y migraciones sincronizadas con éxito.")
