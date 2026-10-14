"""
Controlador de autenticación del Módulo 7 (RF-25, HU-06; DOC-08: POST /auth/login
y GET /auth/me; diagrama docs/uml/m7-secuencia-inicio-sesion.puml).

- Un correo inexistente, una cuenta desactivada y una contraseña incorrecta reciben
  el mismo 401, y la verificación tarda lo mismo: el inicio de sesión no revela
  qué cuentas existen.
- Tras ``INTENTOS_MAXIMOS`` fallos seguidos la cuenta se bloquea
  ``MINUTOS_BLOQUEO`` minutos (429 con Retry-After), aunque luego llegue la
  contraseña correcta. Un inicio de sesión exitoso reinicia el conteo.
- Cada intento queda en la bitácora sellada con el correo y la IP (RF-27, HU-07).
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import seguridad
from config.autorizacion import Actor, ip_de, requiere
from config.database import get_db
from models.bitacora import EVENTO_CAMBIO_CONTRASENA, EVENTO_INICIO_SESION, EVENTO_INICIO_SESION_FALLIDO
from models.usuario import Usuario
from motor import bitacora
from schemas.usuario_schema import CambioContrasenaRequest, LoginRequest, LoginResponse, UsuarioResponse

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."

# Endpoints que una cuenta con contraseña temporal sí puede usar.
_con_sesion = requiere(*seguridad.ROLES_PERSONA, cambio_pendiente=True)


def ahora_utc() -> datetime:
    """Hora UTC sin zona, como la guardan las columnas TIMESTAMP (sesión de PostgreSQL en UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _fallido(db: Session, correo: str, ip: str | None, motivo: str) -> None:
    bitacora.registrar(
        db, EVENTO_INICIO_SESION_FALLIDO, usuario=correo[:150] or seguridad.SISTEMA, ip_origen=ip,
        detalle={"correo": correo[:150], "motivo": motivo},
    )
    db.commit()


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Iniciar sesión con correo y contraseña; devuelve el token Bearer (JWT)",
    responses={401: {"description": "Credenciales incorrectas"}, 429: {"description": "Cuenta bloqueada temporalmente"}},
)
def iniciar_sesion(dto: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = ip_de(request)
    # FOR UPDATE: dos intentos simultáneos no pueden perder un fallo del conteo.
    usuario = db.query(Usuario).filter(Usuario.email == dto.email).with_for_update().first()
    ahora = ahora_utc()

    if usuario is not None and usuario.bloqueado_hasta and usuario.bloqueado_hasta > ahora:
        _fallido(db, dto.email, ip, "CUENTA_BLOQUEADA")
        segundos = int((usuario.bloqueado_hasta - ahora).total_seconds()) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Cuenta bloqueada temporalmente por intentos fallidos. Intente de nuevo en {segundos // 60 + 1} min.",
            headers={"Retry-After": str(segundos)},
        )

    valida = seguridad.verificar_contrasena(dto.contrasena, usuario.password_hash if usuario else None)
    if usuario is None or not valida or not usuario.activo:
        motivo = "CREDENCIALES_INVALIDAS"
        if usuario is not None and valida:
            motivo = "CUENTA_DESACTIVADA"
        elif usuario is not None:
            usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
            if usuario.intentos_fallidos >= INTENTOS_MAXIMOS:
                usuario.intentos_fallidos = 0
                usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
                motivo = "CUENTA_BLOQUEADA_AHORA"
        _fallido(db, dto.email, ip, motivo)
        raise seguridad.no_autenticado(_CREDENCIALES_INVALIDAS)

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    bitacora.registrar(db, EVENTO_INICIO_SESION, usuario=usuario.email, ip_origen=ip, detalle={"rol": usuario.rol})
    db.commit()
    db.refresh(usuario)

    token, vigencia = seguridad.emitir_token(usuario.id, usuario.email, usuario.nombre_completo, usuario.rol)
    return LoginResponse(access_token=token, expira_en=vigencia, usuario=UsuarioResponse.model_validate(usuario))


@router.get("/me", response_model=UsuarioResponse, summary="Perfil y rol del usuario en sesión")
def perfil(actor: Actor = Depends(_con_sesion)):
    return actor.usuario


@router.post(
    "/cambiar-contrasena",
    response_model=UsuarioResponse,
    summary="Cambiar la contraseña propia (obligatorio tras una contraseña temporal)",
)
def cambiar_contrasena(dto: CambioContrasenaRequest, actor: Actor = Depends(_con_sesion), db: Session = Depends(get_db)):
    usuario = actor.usuario
    if not seguridad.verificar_contrasena(dto.contrasena_actual, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual no es correcta.")
    if dto.contrasena_nueva == dto.contrasena_actual:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña nueva debe ser distinta de la actual."
        )
    usuario.password_hash = seguridad.hash_contrasena(dto.contrasena_nueva)
    era_temporal = usuario.debe_cambiar_contrasena
    usuario.debe_cambiar_contrasena = False
    bitacora.registrar(
        db, EVENTO_CAMBIO_CONTRASENA, usuario=usuario.email, ip_origen=actor.ip,
        detalle={"usuario_id": usuario.id, "era_temporal": era_temporal},
    )
    db.commit()
    db.refresh(usuario)
    return usuario
