"""
Autorización por rol del rules-service (RF-26, PRD §5.1 y §5.2).

El rules-service comparte la base con el core: un token de persona se confirma
contra la tabla ``usuarios`` en cada petición (cuenta activa y rol guardado), igual
que en el core, así que una cuenta desactivada no puede pausar ni crear reglas
aunque su token siga vigente. Un token SISTEMA (core y ai-service) entra solo
donde la matriz lo admite.

La tabla ``usuarios`` es del core (models/usuario.py); aquí solo se lee.
"""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError
from sqlalchemy.orm import Session

from config import seguridad
from config.database import get_db


@dataclass(frozen=True)
class Cuenta:
    id: str
    email: str
    rol: str
    activo: bool
    debe_cambiar_contrasena: bool


@dataclass(frozen=True)
class Actor:
    email: str
    rol: str

    @property
    def es_sistema(self) -> bool:
        return self.rol == seguridad.SISTEMA


def buscar_cuenta(db: Session, usuario_id: str) -> Cuenta | None:
    try:
        fila = db.execute(
            text("SELECT id, email, rol, activo, debe_cambiar_contrasena FROM usuarios WHERE id = :id"),
            {"id": usuario_id},
        ).first()
    except ProgrammingError:
        # La tabla aún no existe: el core no ha arrancado sobre esta base.
        db.rollback()
        return None
    return Cuenta(*fila) if fila else None


def requiere(*roles: str):
    """Dependencia que exige uno de ``roles``; SISTEMA debe nombrarse para admitirlo."""
    permitidos = frozenset(roles)

    def dependencia(
        identidad: seguridad.Identidad = Depends(seguridad.identidad_actual),
        db: Session = Depends(get_db),
    ) -> Actor:
        if identidad.es_sistema:
            if seguridad.SISTEMA not in permitidos:
                raise seguridad.sin_permiso()
            return Actor(email=seguridad.SISTEMA, rol=seguridad.SISTEMA)
        cuenta = buscar_cuenta(db, identidad.sub)
        if cuenta is None or not cuenta.activo:
            raise seguridad.no_autenticado("La cuenta no existe o está desactivada. Consulte al administrador.")
        if cuenta.debe_cambiar_contrasena:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña temporal antes de continuar.",
            )
        if cuenta.rol not in permitidos:
            raise seguridad.sin_permiso()
        return Actor(email=cuenta.email, rol=cuenta.rol)

    return dependencia


# Combinaciones de la matriz de permisos (PRD §5.1).
lectura_o_sistema = requiere(*seguridad.LECTURA, seguridad.SISTEMA)
operacion = requiere(*seguridad.OPERACION)
solo_admin = requiere(seguridad.ADMIN)
