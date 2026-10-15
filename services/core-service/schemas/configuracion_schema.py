"""Esquemas de la configuración de operación (HU-14)."""
from datetime import datetime

from pydantic import BaseModel, Field


class UmbralesUpdate(BaseModel):
    """Los tres días de anticipación de las alertas de vencimiento, de mayor a menor."""
    umbrales: list[int] = Field(..., examples=[[30, 15, 5]])


class UmbralesResponse(BaseModel):
    umbrales: list[int]
    # False: rige el valor por omisión de UMBRALES_ALERTA_VENCIMIENTO.
    configurado: bool
    actualizado_en: datetime | None = None
    actualizado_por: str | None = None
