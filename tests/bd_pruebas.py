"""
Entorno aislado para las pruebas del core-service.

Las pruebas que escriben (cargas, dictámenes, bitácora) no pueden ejecutarse
contra ``plurione_compliance``: la bitácora y los dictámenes son inmutables por
diseño (triggers de PostgreSQL), así que lo que una prueba escribiera ahí se
quedaría para siempre junto a los expedientes reales. Este módulo:

  1. Recrea desde cero la base ``plurione_compliance_test`` en el mismo servidor.
  2. Apunta la bóveda (STORAGE_VAULT_PATH) a un directorio temporal.
  3. Fija un JWT_SECRET de pruebas y apaga las cuentas de demostración (Módulo 7)
     y el envío de correo (RF-20).

Debe invocarse ANTES de importar cualquier módulo del core-service, porque
``config.database`` y ``config.boveda`` leen el entorno al importarse. Si varias
suites corren en el mismo proceso (``pytest tests/``), la base se recrea solo
la primera vez: recrearla de nuevo cortaría las conexiones de la suite anterior.
Cada llamada, en cambio, recibe su propia bóveda y una copia limpia de los
módulos del core-service (``servicios.activar``).
"""
import os
import random
import shutil
import sys
import tempfile
import uuid

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

CORE_SERVICE_DIR = servicios.directorio("core-service")
NOMBRE_BD_PRUEBAS = "plurione_compliance_test"
SECRETO_PRUEBAS = servicios.SECRETO_PRUEBAS

_bd_recreada = False


def preparar_entorno() -> str:
    """Recrea la BD de pruebas, aísla la bóveda y deja importable el core-service. Devuelve la bóveda temporal."""
    servicios.activar("core-service")
    load_dotenv(os.path.join(CORE_SERVICE_DIR, ".env"))
    os.environ.pop("DATABASE_URL", None)
    os.environ["DB_NAME"] = NOMBRE_BD_PRUEBAS
    boveda = tempfile.mkdtemp(prefix="plurione_boveda_pruebas_")
    os.environ["STORAGE_VAULT_PATH"] = boveda
    os.environ["JWT_SECRET"] = SECRETO_PRUEBAS
    os.environ["USUARIOS_DEMO"] = "false"
    # RF-20: un SMTP_HOST del .env local mandaría correos reales desde las pruebas.
    for variable in ("ADMIN_INICIAL_EMAIL", "ADMIN_INICIAL_CONTRASENA", "CORS_ORIGENES", "SMTP_HOST"):
        os.environ.pop(variable, None)

    global _bd_recreada
    if not _bd_recreada:
        _recrear_bd()
        _bd_recreada = True
    return boveda


def verificar_aislamiento(engine) -> None:
    """Aborta si el engine del core-service no apunta a la base de pruebas."""
    if engine.url.database != NOMBRE_BD_PRUEBAS:
        raise RuntimeError(
            f"Las pruebas del core-service apuntan a '{engine.url.database}' y no a '{NOMBRE_BD_PRUEBAS}': "
            "se detienen para no escribir en la bitácora inmutable de la base real."
        )


def rfc_ficticio(prefijo: str) -> str:
    """
    RFC de persona moral ficticio y único en la corrida: el prefijo de 3 letras de la suite,
    una fecha AAMMDD al azar (día 01 a 28: siempre existe) y una homoclave de 3 posiciones.
    Con la fecha fija 010101 solo variaba la homoclave (4,096 combinaciones) y, con decenas de
    titulares por suite, dos podían coincidir y chocar con el RFC único (fallas intermitentes).
    """
    azar = random.SystemRandom()
    fecha = f"{azar.randrange(100):02d}{azar.randrange(1, 13):02d}{azar.randrange(1, 29):02d}"
    return f"{prefijo}{fecha}{uuid.uuid4().hex[:3].upper()}"


def _recrear_bd() -> None:
    conexion = psycopg2.connect(
        dbname="postgres",
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", ""),
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
    )
    conexion.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conexion.cursor() as cursor:
        cursor.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s AND pid <> pg_backend_pid()",
            (NOMBRE_BD_PRUEBAS,),
        )
        cursor.execute(f'DROP DATABASE IF EXISTS "{NOMBRE_BD_PRUEBAS}"')
        cursor.execute(f'CREATE DATABASE "{NOMBRE_BD_PRUEBAS}"')
    conexion.close()


def limpiar_boveda(boveda: str) -> None:
    shutil.rmtree(boveda, ignore_errors=True)


class Autenticacion:
    """
    Sesiones para las pruebas del core (Módulo 7). Se crea en cada módulo de prueba
    después de importar el core-service y de ``init_db()``, y se queda con esos
    módulos: al correr, ``sys.modules`` puede tener ya los de otro servicio.

    Los tokens son reales (firmados con SECRETO_PRUEBAS) y las cuentas existen en la
    base de pruebas, así que cada petición pasa por la autorización verdadera.
    """

    def __init__(self) -> None:
        from config import seguridad
        from config.database import SessionLocal
        from models.usuario import Usuario

        self._seguridad, self._sesion, self._usuario = seguridad, SessionLocal, Usuario

    @staticmethod
    def correo(rol: str) -> str:
        return f"prueba-{rol.lower()}@example.com"

    def cuenta(self, rol: str = "ADMIN") -> tuple[str, str, str]:
        """(id, correo, nombre) de la cuenta de prueba de ese rol; la crea si falta."""
        correo = self.correo(rol)
        with self._sesion() as db:
            usuario = db.query(self._usuario).filter(self._usuario.email == correo).first()
            if usuario is None:
                usuario = self._usuario(email=correo, nombre_completo=f"Prueba {rol}", rol=rol,
                                        password_hash=self._seguridad.hash_contrasena(f"Clave-{rol}-pruebas"))
                db.add(usuario)
                db.commit()
            return usuario.id, usuario.email, usuario.nombre_completo

    def cabeceras(self, rol: str = "ADMIN") -> dict[str, str]:
        id_, correo, nombre = self.cuenta(rol)
        token, _ = self._seguridad.emitir_token(id_, correo, nombre, rol)
        return {"Authorization": f"Bearer {token}"}

    def sistema(self, actor: str | None = None) -> dict[str, str]:
        """Cabeceras del ai-service: token SISTEMA y, si se da, la persona que pidió la acción."""
        return self._seguridad.cabeceras_sistema("ai-service", actor)

    def cliente(self, app, rol: str = "ADMIN", **kwargs):
        """TestClient que envía en cada petición el token de la cuenta de ese rol."""
        from fastapi.testclient import TestClient

        return TestClient(app, headers=self.cabeceras(rol), **kwargs)
