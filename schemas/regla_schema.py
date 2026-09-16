"""
Esquemas de validación de datos para Reglas de Validación (DTOs).
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ReglaCreate(BaseModel):
    """Datos necesarios para dar de alta una regla en el catálogo (RDS-01)."""
    codigo_regla: str = Field(..., min_length=3, max_length=20, description="Identificador único, ej. 'RIE-01'")
    nombre_regla: str = Field(..., min_length=3, max_length=150, description="Nombre corto de la regla")
    familia_regla: str = Field(..., description="RIE, RCV, RSC o RDS")
    descripcion: str = Field(..., min_length=10, description="Descripción funcional de la regla")
    severidad: str = Field(..., description="CRITICA, ALTA, MEDIA o MEDIA_ALTA")
    accion: str = Field(..., max_length=255, description="Acción del sistema ante incumplimiento")
    tipo_documento: Optional[str] = Field(None, max_length=50, description="Tipo de documento al que aplica")
    documento_obligatorio: bool = Field(True, description="Completitud obligatoria del tipo de documento")
    dias_maximos_vigencia: Optional[int] = Field(None, ge=0, description="Vigencia temporal en días máximos")
    activo: bool = Field(True, description="Bandera de alta/baja lógica de la regla")


class ReglaResponse(BaseModel):
    """Datos de respuesta al consultar una regla del catálogo."""
    id: str
    codigo_regla: str
    nombre_regla: str
    familia_regla: str
    descripcion: str
    severidad: str
    accion: str
    tipo_documento: Optional[str] = None
    documento_obligatorio: bool
    dias_maximos_vigencia: Optional[int] = None
    activo: bool
    creado_en: datetime

    class Config:
        from_attributes = True
