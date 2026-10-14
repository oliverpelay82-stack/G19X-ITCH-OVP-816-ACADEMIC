"""
Seguridad del Módulo 7: roles, JWT HMAC-SHA256 y contraseñas con bcrypt
(RF-25, RF-26; DOC-08; PRD §5.1 y §5.2).

Este archivo es idéntico en core-service, rules-service y ai-service: cada servicio
se construye en su propio contexto de Docker y no pueden compartir un paquete. Por
eso aquí solo vive lo que no depende de la base de un servicio (roles, firma y
lectura del token, token de servicio SISTEMA y hash de contraseñas); la comprobación
de que la cuenta sigue activa y con su rol la hace cada servicio con sus datos.
"""
from __future__ import annotations

import os
import time
from dataclasses import dataclass
from functools import lru_cache

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# Roles del DOC-04 (Tabla 1) y de la HU-05. El OPERADOR del DOC-08 es el VALIDADOR.
ADMIN = "ADMIN"
VALIDADOR = "VALIDADOR"
AUDITOR = "AUDITOR"
CONSULTA = "CONSULTA"
# Perfil de servicio del DOC-08 para las llamadas entre microservicios: nunca se asigna a una persona.
SISTEMA = "SISTEMA"

ROLES_PERSONA = (ADMIN, VALIDADOR, AUDITOR, CONSULTA)
# Grupos de la matriz de permisos (PRD §5.1).
LECTURA = (ADMIN, VALIDADOR, AUDITOR)
OPERACION = (ADMIN, VALIDADOR)

ALGORITMO = "HS256"
# Valor que trae el docker-compose de la entrega para que el sistema levante con un
# solo comando; /health del core advierte mientras siga en uso.
SECRETO_DEMOSTRACION = "secreto-de-demostracion-del-motor-cambielo-en-produccion"
LONGITUD_MINIMA_SECRETO = 32
EXPIRACION_PREDETERMINADA_MINUTOS = 480
MINUTOS_TOKEN_SISTEMA = 5
# Con un token SISTEMA, correo de la persona que pidió la acción (bitácora, HU-07).
CABECERA_ACTOR = "X-Usuario-Actor"

LONGITUD_MINIMA_CONTRASENA = 10
# bcrypt solo considera los primeros 72 bytes; una contraseña más larga se rechaza.
MAXIMO_BYTES_CONTRASENA = 72


class ConfiguracionInvalidaError(RuntimeError):
    """JWT_SECRET ausente o demasiado corto: el servicio no debe arrancar."""


class TokenInvalidoError(ValueError):
    """Token con firma, vigencia o contenido inválidos."""


def secreto() -> str:
    valor = os.getenv("JWT_SECRET", "")
    if not valor:
        raise ConfiguracionInvalidaError(
            "Falta JWT_SECRET en el .env: es la clave con que se firman las sesiones (Módulo 7). "
            f"Defina una cadena aleatoria de al menos {LONGITUD_MINIMA_SECRETO} caracteres, la misma en los tres servicios."
        )
    if len(valor) < LONGITUD_MINIMA_SECRETO:
        raise ConfiguracionInvalidaError(
            f"JWT_SECRET debe tener al menos {LONGITUD_MINIMA_SECRETO} caracteres (HMAC-SHA256)."
        )
    return valor


def verificar_configuracion() -> None:
    """Se llama al arrancar: sin un secreto válido, el servicio no levanta."""
    secreto()


def usa_secreto_demostracion() -> bool:
    return os.getenv("JWT_SECRET", "") == SECRETO_DEMOSTRACION


def minutos_expiracion() -> int:
    try:
        return max(1, int(os.getenv("JWT_EXPIRACION_MINUTOS", str(EXPIRACION_PREDETERMINADA_MINUTOS))))
    except ValueError:
        return EXPIRACION_PREDETERMINADA_MINUTOS


@dataclass(frozen=True)
class Identidad:
    """Lo que dice un token válido. El rol de una persona se confirma contra su cuenta."""

    sub: str
    email: str
    nombre: str
    rol: str
    emitido_en: int

    @property
    def es_sistema(self) -> bool:
        return self.rol == SISTEMA


def emitir_token(sub: str, email: str, nombre: str, rol: str, minutos: int | None = None) -> tuple[str, int]:
    """Token de una persona. Devuelve el token y sus segundos de vigencia."""
    if rol not in ROLES_PERSONA:
        raise ValueError(f"Rol no asignable a una persona: {rol}")
    vigencia = (minutos or minutos_expiracion()) * 60
    ahora = int(time.time())
    carga = {"sub": sub, "email": email, "nombre": nombre, "rol": rol, "iat": ahora, "exp": ahora + vigencia}
    return jwt.encode(carga, secreto(), algorithm=ALGORITMO), vigencia


def emitir_token_sistema(servicio: str) -> str:
    """Token de servicio (perfil SISTEMA del DOC-08), de vida corta."""
    ahora = int(time.time())
    carga = {"sub": servicio, "email": SISTEMA, "nombre": servicio, "rol": SISTEMA,
             "iat": ahora, "exp": ahora + MINUTOS_TOKEN_SISTEMA * 60}
    return jwt.encode(carga, secreto(), algorithm=ALGORITMO)


def cabeceras_sistema(servicio: str, actor: str | None = None) -> dict[str, str]:
    """Cabeceras de una llamada de servicio a servicio, con el actor si lo hay."""
    cabeceras = {"Authorization": f"Bearer {emitir_token_sistema(servicio)}"}
    if actor:
        cabeceras[CABECERA_ACTOR] = actor
    return cabeceras


def leer_token(token: str) -> Identidad:
    try:
        carga = jwt.decode(
            token, secreto(), algorithms=[ALGORITMO], options={"require": ["sub", "rol", "iat", "exp"]}
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalidoError(str(exc)) from exc
    rol = carga.get("rol")
    if rol not in ROLES_PERSONA + (SISTEMA,):
        raise TokenInvalidoError(f"Rol desconocido en el token: {rol!r}")
    return Identidad(
        sub=str(carga["sub"]),
        email=str(carga.get("email") or ""),
        nombre=str(carga.get("nombre") or ""),
        rol=rol,
        emitido_en=int(carga["iat"]),
    )


_portador = HTTPBearer(
    auto_error=False,
    description="Token de sesión de POST /api/v1/auth/login (JWT HMAC-SHA256).",
)


def no_autenticado(detalle: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED, detail=detalle, headers={"WWW-Authenticate": "Bearer"}
    )


def identidad_actual(credenciales: HTTPAuthorizationCredentials | None = Depends(_portador)) -> Identidad:
    """Dependencia de FastAPI: exige un token Bearer válido (401 si falta o no sirve)."""
    if credenciales is None or credenciales.scheme.lower() != "bearer":
        raise no_autenticado("Inicie sesión para usar el sistema.")
    try:
        return leer_token(credenciales.credentials)
    except TokenInvalidoError:
        raise no_autenticado("La sesión expiró o no es válida. Inicie sesión de nuevo.")


def sin_permiso() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Su rol no tiene permiso para realizar esta acción."
    )


# ── Contraseñas (bcrypt, DOC-08) ──────────────────────────────────
# bcrypt se importa al usarse: rules-service y ai-service no guardan contraseñas.

def problema_de_contrasena(contrasena: str) -> str | None:
    """Motivo por el que una contraseña nueva no se admite, o None si es válida."""
    if len(contrasena) < LONGITUD_MINIMA_CONTRASENA:
        return f"La contraseña debe tener al menos {LONGITUD_MINIMA_CONTRASENA} caracteres."
    if len(contrasena.encode("utf-8")) > MAXIMO_BYTES_CONTRASENA:
        return f"La contraseña no puede pasar de {MAXIMO_BYTES_CONTRASENA} bytes."
    if not contrasena.strip():
        return "La contraseña no puede estar en blanco."
    return None


def hash_contrasena(contrasena: str) -> str:
    import bcrypt

    return bcrypt.hashpw(contrasena.encode("utf-8"), bcrypt.gensalt()).decode("ascii")


def verificar_contrasena(contrasena: str, hash_guardado: str | None) -> bool:
    """Compara contra el hash; sin hash (cuenta inexistente) gasta el mismo tiempo y responde False."""
    import bcrypt

    datos = contrasena.encode("utf-8")
    if len(datos) > MAXIMO_BYTES_CONTRASENA:
        datos = datos[:MAXIMO_BYTES_CONTRASENA]
    if not hash_guardado:
        bcrypt.checkpw(datos, _hash_senuelo())
        return False
    try:
        return bcrypt.checkpw(datos, hash_guardado.encode("ascii"))
    except ValueError:
        return False


@lru_cache(maxsize=1)
def _hash_senuelo() -> bytes:
    """Hash fijo para que un correo inexistente tarde lo mismo que uno real (no revela cuentas)."""
    import bcrypt

    return bcrypt.hashpw(b"senuelo-sin-cuenta", bcrypt.gensalt())
