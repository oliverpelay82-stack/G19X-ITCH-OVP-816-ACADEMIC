"""
Cuentas que el core crea al arrancar (Módulo 7, PRD §5.2).

- Administrador inicial: si no existe ninguna cuenta y el .env define
  ``ADMIN_INICIAL_EMAIL`` y ``ADMIN_INICIAL_CONTRASENA``, se crea con esa
  contraseña como temporal (debe cambiarla en su primer acceso).
- Usuarios de demostración: con ``USUARIOS_DEMO=true`` (el docker-compose de la
  entrega) se crea, si falta, un usuario ficticio por rol, con correos del dominio
  reservado example.com (RFC 2606) y las contraseñas del README, para que PluriOne
  pruebe los roles de inmediato. No se reescriben si ya existen: una contraseña
  cambiada se respeta.

Cada alta queda en la bitácora como ALTA_USUARIO hecha por SISTEMA.
"""
from __future__ import annotations

import os

from sqlalchemy.orm import Session

from config import seguridad
from models.bitacora import EVENTO_ALTA_USUARIO
from models.usuario import Usuario
from motor import bitacora

USUARIOS_DEMO = (
    (seguridad.ADMIN, "admin@example.com", "Administración (demostración)", "Admin-Demo-2026"),
    (seguridad.VALIDADOR, "validador@example.com", "Validación (demostración)", "Validador-Demo-2026"),
    (seguridad.AUDITOR, "auditor@example.com", "Auditoría (demostración)", "Auditor-Demo-2026"),
    (seguridad.CONSULTA, "consulta@example.com", "Consulta (demostración)", "Consulta-Demo-2026"),
)


def demo_activo() -> bool:
    return os.getenv("USUARIOS_DEMO", "false").strip().lower() in {"1", "true", "yes", "on"}


def _alta(db: Session, rol: str, email: str, nombre: str, contrasena: str, temporal: bool) -> Usuario:
    usuario = Usuario(
        email=email.strip().lower(), nombre_completo=nombre, rol=rol,
        password_hash=seguridad.hash_contrasena(contrasena), debe_cambiar_contrasena=temporal,
    )
    db.add(usuario)
    db.flush()
    bitacora.registrar(
        db, EVENTO_ALTA_USUARIO, usuario=seguridad.SISTEMA,
        detalle={"usuario_id": usuario.id, "email": usuario.email, "nombre_completo": nombre, "rol": rol,
                 "origen": "DEMOSTRACION" if not temporal else "ADMINISTRADOR_INICIAL"},
    )
    return usuario


def hay_cuentas(db: Session) -> bool:
    return db.query(Usuario.id).first() is not None


def crear(db: Session) -> list[str]:
    """Crea las cuentas que falten; devuelve los correos creados. Confirma la transacción."""
    creados: list[str] = []
    if not hay_cuentas(db):
        email = os.getenv("ADMIN_INICIAL_EMAIL", "").strip()
        contrasena = os.getenv("ADMIN_INICIAL_CONTRASENA", "")
        if email and contrasena:
            problema = seguridad.problema_de_contrasena(contrasena)
            if problema:
                raise seguridad.ConfiguracionInvalidaError(f"ADMIN_INICIAL_CONTRASENA no es válida: {problema}")
            creados.append(_alta(db, seguridad.ADMIN, email, "Administrador del sistema", contrasena, True).email)
    if demo_activo():
        existentes = {e for (e,) in db.query(Usuario.email).all()}
        for rol, email, nombre, contrasena in USUARIOS_DEMO:
            if email not in existentes:
                creados.append(_alta(db, rol, email, nombre, contrasena, False).email)
    db.commit()
    return creados
