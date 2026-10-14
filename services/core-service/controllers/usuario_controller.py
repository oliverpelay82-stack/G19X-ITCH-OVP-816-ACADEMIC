"""
Gestión de cuentas por el administrador (HU-05, RF-26; PRD §5.1 y §5.2).

Sin borrado físico (RN-04): una cuenta se desactiva y puede reactivarse. Cada
alta y cada cambio quedan en la bitácora sellada con el valor anterior y el nuevo
(RF-27); la contraseña nunca se escribe en la bitácora, solo que se restableció.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from config import seguridad
from config.autorizacion import Actor, solo_admin
from config.database import get_db
from models.bitacora import EVENTO_ACTUALIZACION_USUARIO, EVENTO_ALTA_USUARIO
from models.usuario import Usuario
from motor import bitacora
from schemas.usuario_schema import UsuarioCreate, UsuarioResponse, UsuarioUpdate

router = APIRouter(prefix="/api/v1/usuarios", tags=["Usuarios"])


def _usuario_o_404(db: Session, usuario_id: str) -> Usuario:
    usuario = db.query(Usuario).filter(Usuario.id == usuario_id).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Usuario con ID '{usuario_id}' no encontrado.")
    return usuario


@router.get("", response_model=list[UsuarioResponse], summary="Listar las cuentas de usuario")
def listar_usuarios(_: Actor = Depends(solo_admin), db: Session = Depends(get_db)):
    return db.query(Usuario).order_by(Usuario.activo.desc(), Usuario.nombre_completo).all()


@router.post(
    "",
    response_model=UsuarioResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Dar de alta una cuenta con su rol y una contraseña temporal",
)
def crear_usuario(dto: UsuarioCreate, actor: Actor = Depends(solo_admin), db: Session = Depends(get_db)):
    if db.query(Usuario.id).filter(Usuario.email == dto.email).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Ya existe una cuenta con el correo '{dto.email}'.")
    usuario = Usuario(
        email=dto.email,
        nombre_completo=dto.nombre_completo,
        rol=dto.rol,
        password_hash=seguridad.hash_contrasena(dto.contrasena_temporal),
        debe_cambiar_contrasena=True,
    )
    db.add(usuario)
    db.flush()
    bitacora.registrar(
        db, EVENTO_ALTA_USUARIO, usuario=actor.email, ip_origen=actor.ip,
        detalle={"usuario_id": usuario.id, "email": usuario.email, "nombre_completo": usuario.nombre_completo,
                 "rol": usuario.rol},
    )
    db.commit()
    db.refresh(usuario)
    return usuario


@router.patch(
    "/{usuario_id}",
    response_model=UsuarioResponse,
    summary="Cambiar el nombre o el rol, desactivar o reactivar, o restablecer la contraseña de una cuenta",
)
def actualizar_usuario(usuario_id: str, dto: UsuarioUpdate, actor: Actor = Depends(solo_admin),
                       db: Session = Depends(get_db)):
    usuario = _usuario_o_404(db, usuario_id)
    if usuario.id == actor.usuario.id and (
        (dto.rol is not None and dto.rol != seguridad.ADMIN) or dto.activo is False
    ):
        # Así siempre queda al menos un administrador activo: el que hace el cambio.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No puede quitarse a sí mismo el rol de administrador ni desactivar su propia cuenta.",
        )

    cambios: dict[str, dict] = {}
    for campo in ("nombre_completo", "rol", "activo"):
        valor = getattr(dto, campo)
        if valor is not None and getattr(usuario, campo) != valor:
            cambios[campo] = {"anterior": getattr(usuario, campo), "nuevo": valor}
            setattr(usuario, campo, valor)
    if dto.contrasena_temporal is not None:
        usuario.password_hash = seguridad.hash_contrasena(dto.contrasena_temporal)
        usuario.debe_cambiar_contrasena = True
        usuario.intentos_fallidos = 0
        usuario.bloqueado_hasta = None
        cambios["contrasena"] = {"restablecida": True}

    if cambios:
        bitacora.registrar(
            db, EVENTO_ACTUALIZACION_USUARIO, usuario=actor.email, ip_origen=actor.ip,
            detalle={"usuario_id": usuario.id, "email": usuario.email, "cambios": cambios},
        )
        db.commit()
        db.refresh(usuario)
    return usuario
