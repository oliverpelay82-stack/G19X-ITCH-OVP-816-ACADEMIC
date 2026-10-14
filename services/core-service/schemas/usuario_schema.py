"""
DTOs del Módulo 7: inicio de sesión, cuentas y asignación de expedientes (PRD §5.2).
"""
import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from config import seguridad

RolUsuario = Literal["ADMIN", "VALIDADOR", "AUDITOR", "CONSULTA"]

_CORREO = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _correo(valor: str) -> str:
    correo = valor.strip().lower()
    if not _CORREO.match(correo):
        raise ValueError("Escriba un correo electrónico válido (nombre@dominio).")
    return correo


def _contrasena_nueva(valor: str) -> str:
    problema = seguridad.problema_de_contrasena(valor)
    if problema:
        raise ValueError(problema)
    return valor


def _nombre(valor: str) -> str:
    nombre = " ".join(valor.split())
    if not nombre:
        raise ValueError("Escriba el nombre completo.")
    return nombre


class LoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=150)
    contrasena: str = Field(..., min_length=1, max_length=200)

    @field_validator("email")
    @classmethod
    def normalizar_correo(cls, v: str) -> str:
        # En el inicio de sesión no se valida el formato: un correo mal escrito recibe
        # el mismo 401 que una contraseña incorrecta.
        return v.strip().lower()


class UsuarioResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre_completo: str
    rol: str
    activo: bool
    debe_cambiar_contrasena: bool
    bloqueado_hasta: Optional[datetime] = None
    ultimo_acceso: Optional[datetime] = None
    creado_en: datetime


class LoginResponse(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expira_en: int = Field(..., description="Segundos de vigencia del token")
    usuario: UsuarioResponse


class CambioContrasenaRequest(BaseModel):
    contrasena_actual: str = Field(..., min_length=1, max_length=200)
    contrasena_nueva: str = Field(..., max_length=200)

    @field_validator("contrasena_nueva")
    @classmethod
    def validar_nueva(cls, v: str) -> str:
        return _contrasena_nueva(v)


class UsuarioCreate(BaseModel):
    email: str = Field(..., max_length=150)
    nombre_completo: str = Field(..., max_length=150)
    rol: RolUsuario
    contrasena_temporal: str = Field(..., max_length=200, description="Debe cambiarse en el primer acceso")

    @field_validator("email")
    @classmethod
    def validar_correo(cls, v: str) -> str:
        return _correo(v)

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre(cls, v: str) -> str:
        return _nombre(v)

    @field_validator("contrasena_temporal")
    @classmethod
    def validar_contrasena(cls, v: str) -> str:
        return _contrasena_nueva(v)


class UsuarioUpdate(BaseModel):
    """Cambios del administrador; un campo omitido no cambia."""

    nombre_completo: Optional[str] = Field(None, max_length=150)
    rol: Optional[RolUsuario] = None
    activo: Optional[bool] = None
    contrasena_temporal: Optional[str] = Field(
        None, max_length=200, description="Restablece la contraseña y desbloquea la cuenta"
    )

    @field_validator("nombre_completo")
    @classmethod
    def validar_nombre(cls, v: Optional[str]) -> Optional[str]:
        return _nombre(v) if v is not None else None

    @field_validator("contrasena_temporal")
    @classmethod
    def validar_contrasena(cls, v: Optional[str]) -> Optional[str]:
        return _contrasena_nueva(v) if v is not None else None


class UsuarioResumen(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    nombre_completo: str
    rol: str
    activo: bool


class AsignacionesUpdate(BaseModel):
    """Lista completa de usuarios asignados al expediente (reemplaza la anterior)."""

    usuario_ids: list[str] = Field(default_factory=list, max_length=200)


class ExpedienteAsignadoResponse(BaseModel):
    """Lo único que ve el usuario de consulta de un expediente (HU-31)."""

    id: str
    codigo_expediente: str
    nombre: Optional[str] = None
    tipo_expediente: str
    razon_social: str
    rfc: str
    estado_cumplimiento: str
    actualizado_en: Optional[datetime] = None
