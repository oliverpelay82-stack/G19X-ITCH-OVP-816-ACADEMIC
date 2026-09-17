"""
Script de inicialización de Base de Datos PostgreSQL.
1. Crea la base de datos 'plurione_compliance' si no existe.
2. Importa todos los modelos para que Base.metadata contenga las 4 tablas.
3. Sincroniza todas las tablas en PostgreSQL.
4. Inserta las reglas de validación y un titular de prueba.
"""
import os
import sys
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from dotenv import load_dotenv

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "backend", ".env"))

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "plurione-demo")
DB_NAME = os.getenv("DB_NAME", "plurione_compliance")

print(f"[*] Conectando a PostgreSQL en {DB_HOST}:{DB_PORT} con usuario '{DB_USER}'...")

# Paso 1: Conectar a la base default 'postgres' para crear 'plurione_compliance' si no existe
try:
    conn = psycopg2.connect(
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
        host=DB_HOST,
        port=DB_PORT,
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
    if not cursor.fetchone():
        cursor.execute(f'CREATE DATABASE "{DB_NAME}"')
        print(f"[+] Base de datos '{DB_NAME}' creada con éxito en PostgreSQL.")
    else:
        print(f"[i] La base de datos '{DB_NAME}' ya existe.")

    cursor.close()
    conn.close()
except Exception as e:
    print(f"[!] Error conectando a PostgreSQL inicial: {e}")
    exit(1)

# Paso 2: Importar TODOS los modelos para registrar las entidades en SQLAlchemy
import models.titular
import models.expediente
import models.documento
import models.regla
from config.database import init_db, SessionLocal, engine, Base

print("[*] Sincronizando tablas en PostgreSQL con SQLAlchemy...")
Base.metadata.create_all(bind=engine)
print("[OK] Tablas (titulares_expediente, expedientes, documentos, reglas_validacion) sincronizadas con éxito.")

# Paso 3: Precargar el catálogo de reglas de negocio DOC-05
from seed_reglas_validacion import precargar_reglas
precargar_reglas()

# Paso 4: Crear un titular inicial de prueba si no existe ninguno
db = SessionLocal()
try:
    from models.titular import TitularExpediente
    from models.expediente import Expediente

    titular_existente = db.query(TitularExpediente).first()
    if not titular_existente:
        titular = TitularExpediente(
            rfc="BIM980101XYZ",
            razon_social="GRUPO BIMBO S.A.B. DE C.V.",
            tipo_persona="MORAL",
            categoria="PROVEEDOR_CRITICO",
        )
        db.add(titular)
        db.flush()

        expediente = Expediente(
            titular_id=titular.id,
            codigo_expediente=f"EXP-{titular.rfc}-001",
            estado_cumplimiento="EN_REVISION",
            porcentaje_completitud=0.0,
        )
        db.add(expediente)
        db.commit()
        print(f"[+] Titular y Expediente demo inicial creados: {titular.razon_social} ({expediente.codigo_expediente})")
    else:
        print("[i] Ya existen titulares en la base de datos.")
finally:
    db.close()

print("\n" + "=" * 60)
print("[EXITO] Base de datos PostgreSQL 'plurione_compliance' 100% lista y poblada.")
print("=" * 60)
