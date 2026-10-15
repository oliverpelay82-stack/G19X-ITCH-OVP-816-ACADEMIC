"""
Zona horaria del negocio (Q-a, ESTADO_DEL_DESARROLLO §6.6).

Las vigencias se deciden por día: un documento vence «el 15 de octubre» en la
hora de México, no en la del servidor. ``date.today()`` usa la zona del sistema
operativo, y un contenedor Docker corre en UTC: desde las 18:00 de México un
documento vencía un día antes y las alertas de 30, 15 y 5 días se adelantaban.

``ZONA_HORARIA`` (por omisión America/Mexico_City, sin horario de verano desde
2022) fija la referencia en todos los servicios. Las fechas de la base se
guardan en UTC sin zona (config/database.py fija la sesión de PostgreSQL en
UTC); ``fecha_local`` las lleva a esta zona antes de contarlas por día. Requiere el paquete ``tzdata`` (Windows y las imágenes slim
no traen la base de zonas del sistema).
"""
from __future__ import annotations

import os
from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

ZONA = ZoneInfo(os.getenv("ZONA_HORARIA", "America/Mexico_City"))


def ahora() -> datetime:
    """Fecha y hora actuales en la zona del negocio."""
    return datetime.now(ZONA)


def hoy(instante: datetime | None = None) -> date:
    """Día actual (o el de ``instante``) en la zona del negocio."""
    return fecha_local(instante) if instante else ahora().date()


def fecha_local(instante: datetime) -> date:
    """Día de un instante en la zona del negocio; sin zona se interpreta como UTC (así se guarda en la base)."""
    return (instante if instante.tzinfo else instante.replace(tzinfo=timezone.utc)).astimezone(ZONA).date()
