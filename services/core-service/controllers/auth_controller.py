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
- Segundo factor TOTP opcional (fase F3, docs/uml/m7-actividad-mfa.puml): con MFA
  habilitado, la contraseña correcta sin código responde ``requiere_codigo`` sin
  token, y un código inválido cuenta como intento fallido. Las cuentas sin MFA
  entran como antes.
"""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from config import seguridad
from config.autorizacion import Actor, cualquier_usuario, ip_de, requiere
from config.database import get_db
from models.bitacora import (
    EVENTO_CAMBIO_CONTRASENA,
    EVENTO_CAMBIO_MFA,
    EVENTO_INICIO_SESION,
    EVENTO_INICIO_SESION_FALLIDO,
)
from models.usuario import Usuario
from motor import bitacora, segundo_factor
from schemas.usuario_schema import (
    CambioContrasenaRequest,
    LoginRequest,
    LoginResponse,
    MfaActivarRequest,
    MfaDesactivarRequest,
    MfaGenerarRequest,
    MfaGenerarResponse,
    UsuarioResponse,
)

router = APIRouter(prefix="/api/v1/auth", tags=["Autenticación"])

INTENTOS_MAXIMOS = 5
MINUTOS_BLOQUEO = 15
_CREDENCIALES_INVALIDAS = "Correo o contraseña incorrectos."

# Endpoints que una cuenta con contraseña temporal sí puede usar.
_con_sesion = requiere(*seguridad.ROLES_PERSONA, cambio_pendiente=True)


def ahora_utc() -> datetime:
    """Hora UTC sin zona, como la guardan las columnas TIMESTAMP (sesión de PostgreSQL en UTC)."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sumar_fallo(usuario: Usuario, ahora: datetime, motivo: str) -> str:
    """Cuenta un fallo (contraseña o código); al llegar al máximo, bloquea la cuenta."""
    usuario.intentos_fallidos = (usuario.intentos_fallidos or 0) + 1
    if usuario.intentos_fallidos >= INTENTOS_MAXIMOS:
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = ahora + timedelta(minutes=MINUTOS_BLOQUEO)
        return "CUENTA_BLOQUEADA_AHORA"
    return motivo


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
            motivo = _sumar_fallo(usuario, ahora, motivo)
        _fallido(db, dto.email, ip, motivo)
        raise seguridad.no_autenticado(_CREDENCIALES_INVALIDAS)

    if usuario.mfa_habilitado:
        if not dto.codigo:
            # La contraseña ya se probó: falta el segundo factor. No es un fallo ni un acceso.
            db.rollback()
            return LoginResponse(requiere_codigo=True)
        if not segundo_factor.codigo_valido(usuario.mfa_secreto, dto.codigo):
            _fallido(db, dto.email, ip, _sumar_fallo(usuario, ahora, "CODIGO_INVALIDO"))
            raise seguridad.no_autenticado("El código de verificación no es correcto o ya venció.")

    usuario.intentos_fallidos = 0
    usuario.bloqueado_hasta = None
    usuario.ultimo_acceso = ahora
    bitacora.registrar(db, EVENTO_INICIO_SESION, usuario=usuario.email, ip_origen=ip,
                       detalle={"rol": usuario.rol, "segundo_factor": bool(usuario.mfa_habilitado)})
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


# ── Segundo factor TOTP (fase F3) ────────────────────────────────

def _contrasena_correcta(usuario: Usuario, contrasena: str) -> None:
    if not seguridad.verificar_contrasena(contrasena, usuario.password_hash):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña no es correcta.")


def _ya_habilitado() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail="La verificación en dos pasos ya está activa. Desactívela antes de configurar otra app.",
    )


@router.post(
    "/mfa/generar",
    response_model=MfaGenerarResponse,
    summary="Generar el secreto TOTP para registrarlo en la app autenticadora (aún sin activar)",
)
def generar_mfa(dto: MfaGenerarRequest, actor: Actor = Depends(cualquier_usuario), db: Session = Depends(get_db)):
    usuario = actor.usuario
    _contrasena_correcta(usuario, dto.contrasena)
    if usuario.mfa_habilitado:
        raise _ya_habilitado()
    # Un secreto nuevo en cada intento: el generado antes y no confirmado deja de servir.
    usuario.mfa_secreto = segundo_factor.nuevo_secreto()
    db.commit()
    return MfaGenerarResponse(secreto=usuario.mfa_secreto, uri=segundo_factor.uri(usuario.mfa_secreto, usuario.email))


@router.post(
    "/mfa/activar",
    response_model=UsuarioResponse,
    summary="Activar la verificación en dos pasos con el primer código de la app",
)
def activar_mfa(dto: MfaActivarRequest, actor: Actor = Depends(cualquier_usuario), db: Session = Depends(get_db)):
    usuario = actor.usuario
    if usuario.mfa_habilitado:
        raise _ya_habilitado()
    if not usuario.mfa_secreto:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Primero genere el código para su app.")
    if not segundo_factor.codigo_valido(usuario.mfa_secreto, dto.codigo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="El código no corresponde o ya venció. Escriba el que muestra ahora su app.")
    usuario.mfa_habilitado = True
    bitacora.registrar(db, EVENTO_CAMBIO_MFA, usuario=usuario.email, ip_origen=actor.ip,
                       detalle={"usuario_id": usuario.id, "accion": "ACTIVADO"})
    db.commit()
    db.refresh(usuario)
    return usuario


@router.post(
    "/mfa/desactivar",
    response_model=UsuarioResponse,
    summary="Desactivar la verificación en dos pasos (contraseña y un código vigente)",
)
def desactivar_mfa(dto: MfaDesactivarRequest, actor: Actor = Depends(cualquier_usuario),
                   db: Session = Depends(get_db)):
    usuario = actor.usuario
    if not usuario.mfa_habilitado:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="La verificación en dos pasos no está activa.")
    _contrasena_correcta(usuario, dto.contrasena)
    if not segundo_factor.codigo_valido(usuario.mfa_secreto, dto.codigo):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="El código no corresponde o ya venció.")
    usuario.mfa_habilitado = False
    usuario.mfa_secreto = None
    bitacora.registrar(db, EVENTO_CAMBIO_MFA, usuario=usuario.email, ip_origen=actor.ip,
                       detalle={"usuario_id": usuario.id, "accion": "DESACTIVADO"})
    db.commit()
    db.refresh(usuario)
    return usuario
