"""
PLUS-21 (ESTADO_DEL_DESARROLLO §6.7) — Identificador de petición entre servicios y registro estructurado.

Cada petición lleva la cabecera ``X-Request-ID`` (``id_peticion``): se acepta
la recibida (hasta 64 caracteres alfanuméricos y guiones) o se crea una, se
devuelve en la respuesta y los clientes la propagan al llamar a los otros
servicios (``cabeceras()``). Por cada petición se escribe una línea JSON en la
salida estándar (servicio, id_peticion, método, ruta, estado y duración), que
el despliegue puede recolectar. Así una auditoría se sigue de punta a punta:
interfaz, ai-service, core, rules y bitácora.

El módulo es igual en los tres servicios (cada uno define el suyo: no comparten
código); solo cambia ``SERVICIO``.
"""
from __future__ import annotations

import json
import logging
import re
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone

from fastapi import Request

SERVICIO = "core-service"
CABECERA = "X-Request-ID"
_VALIDO = re.compile(r"^[A-Za-z0-9-]{1,64}$")
# Sondeos que el panel repite cada pocos segundos: llevan folio, pero no se registran.
_SIN_REGISTRO = ("/api/v1/health",)

_actual: ContextVar[str | None] = ContextVar("id_peticion", default=None)

_registro = logging.getLogger(f"plurione.{SERVICIO}.peticiones")
if not _registro.handlers:
    _manejador = logging.StreamHandler(sys.stdout)
    _manejador.setFormatter(logging.Formatter("%(message)s"))
    _registro.addHandler(_manejador)
    _registro.setLevel(logging.INFO)
    _registro.propagate = False


def actual() -> str | None:
    """Folio de la petición en curso (None fuera de una petición, p. ej. en un ciclo programado)."""
    return _actual.get()


def cabeceras() -> dict[str, str]:
    """Cabeceras para propagar el folio a otro servicio."""
    folio = actual()
    return {CABECERA: folio} if folio else {}


def nuevo() -> str:
    return uuid.uuid4().hex[:16]


def registrar(**campos) -> None:
    """Una línea JSON con el servicio, el folio en curso y los campos dados."""
    linea = {"ts": datetime.now(timezone.utc).isoformat(timespec="milliseconds"), "servicio": SERVICIO,
             "id_peticion": actual(), **campos}
    _registro.info(json.dumps(linea, ensure_ascii=False, default=str))


async def middleware(request: Request, call_next):
    recibido = request.headers.get(CABECERA)
    folio = recibido if recibido and _VALIDO.match(recibido) else nuevo()
    token = _actual.set(folio)
    inicio = time.perf_counter()
    estado = 500
    try:
        respuesta = await call_next(request)
        estado = respuesta.status_code
        respuesta.headers[CABECERA] = folio
        return respuesta
    finally:
        if request.url.path not in _SIN_REGISTRO:
            registrar(metodo=request.method, ruta=request.url.path, estado=estado,
                      duracion_ms=round((time.perf_counter() - inicio) * 1000, 1))
        _actual.reset(token)
