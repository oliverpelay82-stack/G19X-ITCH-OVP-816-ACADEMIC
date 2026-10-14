"""
Autorización por rol del ai-service y propagación de la identidad (RF-26, HU-07;
PRD §5.1 y §5.2; docs/uml/m7-secuencia-propagacion-sistema.puml).

- Un token de persona se valida aquí (firma y vigencia) y la cuenta se confirma con
  ``GET /auth/me`` del core, que responde con el rol guardado y si la cuenta sigue
  activa. La respuesta se recuerda ``CACHE_SEGUNDOS`` por token: desactivar una
  cuenta surte efecto aquí a más tardar en ese lapso (en el core, de inmediato).
- El correo de la persona queda en una variable de contexto de la petición, y los
  clientes la envían al core y al rules en ``X-Usuario-Actor`` junto con un token
  SISTEMA del ai-service (``cabeceras_servicio``). Así la bitácora registra a quien
  pidió la auditoría y no al servicio que la ejecutó.
- Las tareas de fondo (lectura anticipada, procesamiento diferido) corren en otros
  hilos, sin esa variable: llaman al core como SISTEMA, sin persona.

La dependencia es ``async`` a propósito: FastAPI ejecuta los endpoints síncronos en
un hilo con una copia del contexto de la petición, y una variable fijada dentro de
una dependencia síncrona (otro hilo, otra copia) no llegaría al endpoint.
"""
from __future__ import annotations

import hashlib
import threading
import time
from contextvars import ContextVar
from dataclasses import dataclass

import requests
from fastapi import Depends, HTTPException, status
from fastapi.concurrency import run_in_threadpool
from fastapi.security import HTTPAuthorizationCredentials

from config import observabilidad, seguridad, settings

SERVICIO = "ai-service"
CACHE_SEGUNDOS = 60
_MAX_CACHE = 1000
TIMEOUT_SEGUNDOS = (3, 10)

_actor: ContextVar[str | None] = ContextVar("usuario_actor", default=None)


@dataclass(frozen=True)
class Cuenta:
    email: str
    rol: str
    debe_cambiar_contrasena: bool


_cache: dict[str, tuple[float, Cuenta]] = {}
_candado = threading.Lock()


def actor_actual() -> str | None:
    """Correo de la persona que hizo la petición en curso (None en una tarea de fondo)."""
    return _actor.get()


def cabeceras_servicio() -> dict[str, str]:
    """Cabeceras de una llamada al core o al rules: folio, token SISTEMA y la persona."""
    return {**observabilidad.cabeceras(), **seguridad.cabeceras_sistema(SERVICIO, actor_actual())}


def confirmar_cuenta(token: str) -> Cuenta:
    """Cuenta vigente del token según el core (401 si ya no vale; 503 si el core no responde)."""
    clave = hashlib.sha256(token.encode("utf-8")).hexdigest()
    ahora = time.monotonic()
    with _candado:
        guardada = _cache.get(clave)
        if guardada and guardada[0] > ahora:
            return guardada[1]
    try:
        respuesta = requests.get(
            f"{settings.CORE_BASE_URL}/api/v1/auth/me", timeout=TIMEOUT_SEGUNDOS,
            headers={**observabilidad.cabeceras(), "Authorization": f"Bearer {token}"},
        )
    except requests.RequestException:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible confirmar la sesión con el servicio principal; intente de nuevo.",
        )
    if respuesta.status_code in (401, 403, 404):
        raise seguridad.no_autenticado("La sesión expiró o la cuenta ya no está activa. Inicie sesión de nuevo.")
    if not respuesta.ok:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No fue posible confirmar la sesión con el servicio principal; intente de nuevo.",
        )
    datos = respuesta.json()
    cuenta = Cuenta(email=datos["email"], rol=datos["rol"],
                    debe_cambiar_contrasena=bool(datos.get("debe_cambiar_contrasena")))
    with _candado:
        if len(_cache) >= _MAX_CACHE:
            for vencida in [k for k, (expira, _) in _cache.items() if expira <= ahora] or list(_cache)[:_MAX_CACHE // 2]:
                _cache.pop(vencida, None)
        _cache[clave] = (ahora + CACHE_SEGUNDOS, cuenta)
    return cuenta


def olvidar_cuentas() -> None:
    with _candado:
        _cache.clear()


def requiere(*roles: str):
    """Dependencia que exige que la persona tenga uno de ``roles`` (SISTEMA no llama al ai-service)."""
    permitidos = frozenset(roles)

    async def dependencia(
        identidad: seguridad.Identidad = Depends(seguridad.identidad_actual),
        credenciales: HTTPAuthorizationCredentials | None = Depends(seguridad.portador),
    ) -> Cuenta:
        if identidad.es_sistema:
            raise seguridad.sin_permiso()
        cuenta = await run_in_threadpool(confirmar_cuenta, credenciales.credentials)
        if cuenta.debe_cambiar_contrasena:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Debe cambiar su contraseña temporal antes de continuar.",
            )
        if cuenta.rol not in permitidos:
            raise seguridad.sin_permiso()
        _actor.set(cuenta.email)
        return cuenta

    return dependencia


# Combinaciones de la matriz de permisos (PRD §5.1).
lectura = requiere(*seguridad.LECTURA)
operacion = requiere(*seguridad.OPERACION)
