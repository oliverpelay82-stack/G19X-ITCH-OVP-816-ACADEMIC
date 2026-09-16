"""
Módulo de Configuración de Base de Datos.
Equivalente a application.properties en Spring Boot.
Conecta SQLAlchemy con la base de datos MySQL local.
"""
import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Cargar variables del archivo .env
load_dotenv()

DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME", "plurione_compliance")

# URL de conexión estándar a MySQL mediante PyMySQL
# Formato: mysql+pymysql://usuario:password@host:puerto/nombre_bd
DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

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


def init_db():
    """
    Equivalente a: spring.jpa.hibernate.ddl-auto=update
    Crea automáticamente las tablas en MySQL si aún no existen.
    """
    Base.metadata.create_all(bind=engine)
    print("[Base de Datos] Tablas sincronizadas con éxito en MySQL.")
