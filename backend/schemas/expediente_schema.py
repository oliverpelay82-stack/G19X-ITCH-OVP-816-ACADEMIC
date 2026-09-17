"""
Esquemas de validación de datos para Expedientes (DTOs).
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field

from schemas.titular_schema import TitularResponse


class ExpedienteCreate(BaseModel):
    """Datos necesarios para aperturar un expediente."""
    titular_id: str = Field(..., description="ID único del titular en la base de datos")


class ExpedienteResponse(BaseModel):
    """Datos de respuesta al consultar un expediente."""
    id: str
    titular_id: str
    codigo_expediente: str
    estado_cumplimiento: str
    porcentaje_completitud: float
    actualizado_en: datetime
    titular: Optional[TitularResponse] = None

    class Config:
        from_attributes = True
