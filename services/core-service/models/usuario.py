"""
Modelos del Módulo 7: cuentas de usuario y asignación de expedientes (PRD §5.2).

``usuarios`` sigue la Tabla 4 del DOC-08 (id, email, password_hash bcrypt,
nombre_completo, rol, activo, creado_en) y agrega las columnas de operación de la
sesión. ``expediente_asignaciones`` no está en el DOC-08: la exigen la HU-31 (el
usuario de consulta ve «sus expedientes asignados») y el RF-20 (el correo va a
«los responsables asignados»).

Sin borrado físico de cuentas (RN-04): una cuenta se desactiva.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, false

from config.database import Base


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


class Usuario(Base):
    __tablename__ = "usuarios"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Correo institucional, guardado en minúsculas.
    email = Column(String(150), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    nombre_completo = Column(String(150), nullable=False)
    # ADMIN, VALIDADOR, AUDITOR o CONSULTA (CHECK en config.database).
    rol = Column(String(30), nullable=False)
    activo = Column(Boolean, nullable=False, default=True)
    creado_en = Column(DateTime, nullable=False, default=_ahora)
    # Contraseña temporal (alta o restablecimiento): debe cambiarse en el primer acceso.
    debe_cambiar_contrasena = Column(Boolean, nullable=False, default=False)
    # Bloqueo tras intentos fallidos seguidos (ISO/IEC 27001 A.8.5).
    intentos_fallidos = Column(Integer, nullable=False, default=0)
    bloqueado_hasta = Column(DateTime, nullable=True)
    ultimo_acceso = Column(DateTime, nullable=True)
    # Segundo factor TOTP opcional (RF-25, fase F3). El secreto existe desde que el usuario
    # lo genera; solo cuenta en el inicio de sesión cuando lo confirma con un código.
    mfa_secreto = Column(String(64), nullable=True)
    # Con su DEFAULT en la base, igual que la migración: una base nueva y una migrada coinciden.
    mfa_habilitado = Column(Boolean, nullable=False, default=False, server_default=false())

    def __repr__(self):
        return f"<Usuario {self.email} ({self.rol})>"


class ExpedienteAsignacion(Base):
    __tablename__ = "expediente_asignaciones"
    __table_args__ = (UniqueConstraint("expediente_id", "usuario_id", name="ux_expediente_asignaciones_par"),)

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # RESTRICT como el resto de la custodia: nada se borra en cascada.
    expediente_id = Column(String(36), ForeignKey("expedientes.id", ondelete="RESTRICT"), nullable=False, index=True)
    usuario_id = Column(String(36), ForeignKey("usuarios.id", ondelete="RESTRICT"), nullable=False, index=True)
    # Correo del administrador que hizo la asignación.
    asignado_por = Column(String(150), nullable=False)
    creado_en = Column(DateTime, nullable=False, default=_ahora)
