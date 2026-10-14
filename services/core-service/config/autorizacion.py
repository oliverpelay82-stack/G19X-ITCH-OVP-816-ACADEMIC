"""
Autorización por rol del core-service (RF-26, PRD §5.1 y §5.2).

``requiere(*roles)`` es la dependencia de FastAPI de cada endpoint protegido:

- un token de persona se confirma contra su cuenta en cada petición, y se
  autoriza con el rol guardado en la base, no con el del token: desactivar una
  cuenta o cambiarle el rol surte efecto en la siguiente llamada;
- una cuenta con contraseña temporal solo puede usar los endpoints que lo
  permiten (``cambio_pendiente=True``) hasta cambiarla;
- un token SISTEMA (otro microservicio) solo entra a los endpoints que lo
  admiten, y la persona que pidió la acción llega en ``X-Usuario-Actor`` para la
  bitácora (HU-07). Con un token de persona esa cabecera se ignora.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import seguridad
from config.database import get_db
from models.usuario import Usuario

# Un correo razonable, sin espacios ni caracteres de control (llega en una cabecera).
_ACTOR_VALIDO = re.compile(r"^[^\s@]{1,64}@[^\s@]{1,85}$")


@dataclass
class Actor:
    """Quién hace la petición: su correo (o SISTEMA) para la bitácora, su rol y su IP."""

    email: str
    rol: str
    ip: str | None
    usuario: Usuario | None = None

    @property
    def es_sistema(self) -> bool:
        return self.rol == seguridad.SISTEMA


def ip_de(request: Request) -> str | None:
    return request.client.host if request.client else None


def _actor_de_sistema(request: Request) -> str:
    actor = (request.headers.get(seguridad.CABECERA_ACTOR) or "").strip().lower()
    return actor if _ACTOR_VALIDO.match(actor) else seguridad.SISTEMA


def requiere(*roles: str, cambio_pendiente: bool = False):
    """Dependencia que exige uno de ``roles``; SISTEMA debe nombrarse para admitirlo."""
    permitidos = frozenset(roles)

    def dependencia(
        request: Request,
        identidad: seguridad.Identidad = Depends(seguridad.identidad_actual),
        db: Session = Depends(get_db),
    ) -> Actor:
        if identidad.es_sistema:
            if seguridad.SISTEMA not in permitidos:
                raise seguridad.sin_permiso()
            return Actor(email=_actor_de_sistema(request), rol=seguridad.SISTEMA, ip=ip_de(request))

        usuario = db.query(Usuario).filter(Usuario.id == identidad.sub).first()
        if usuario is None or not usuario.activo:
            raise seguridad.no_autenticado("La cuenta no existe o está desactivada. Consulte al administrador.")
        if usuario.debe_cambiar_contrasena and not cambio_pendiente:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña temporal antes de continuar.",
            )
        if usuario.rol not in permitidos:
            raise seguridad.sin_permiso()
        return Actor(email=usuario.email, rol=usuario.rol, ip=ip_de(request), usuario=usuario)

    return dependencia


# Combinaciones de la matriz de permisos (PRD §5.1).
lectura = requiere(*seguridad.LECTURA)
operacion = requiere(*seguridad.OPERACION)
lectura_o_sistema = requiere(*seguridad.LECTURA, seguridad.SISTEMA)
solo_sistema = requiere(seguridad.SISTEMA)
solo_admin = requiere(seguridad.ADMIN)
cualquier_usuario = requiere(*seguridad.ROLES_PERSONA)
