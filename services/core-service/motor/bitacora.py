"""
Registro de eventos en la bitácora inmutable (RF-27, protocolo DOC-05 §5.6).

La función solo agrega la entrada a la sesión: la confirma la misma transacción
que produjo el evento, de modo que no puede quedar un evento registrado sin su
efecto ni un efecto sin su evento.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from models.bitacora import BitacoraAuditoria

USUARIO_SISTEMA = "SISTEMA"


def registrar(
    db: Session,
    evento: str,
    *,
    expediente_id: str | None = None,
    documento_id: str | None = None,
    dictamen_id: str | None = None,
    usuario: str = USUARIO_SISTEMA,
    ip_origen: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> BitacoraAuditoria:
    entrada = BitacoraAuditoria(
        evento=evento,
        expediente_id=expediente_id,
        documento_id=documento_id,
        dictamen_id=dictamen_id,
        usuario=usuario or USUARIO_SISTEMA,
        ip_origen=ip_origen,
        detalle=detalle or {},
    )
    db.add(entrada)
    return entrada
