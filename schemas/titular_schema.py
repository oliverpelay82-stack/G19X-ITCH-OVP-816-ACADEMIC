"""
Esquemas de validación de datos (DTOs).
Equivalente a las clases DTO / Request en Spring Boot.
"""
from datetime import datetime
from pydantic import BaseModel, Field


class TitularCreate(BaseModel):
    """Datos que recibimos al registrar un nuevo titular."""
    rfc: str = Field(..., min_length=12, max_length=13, description="RFC del titular (12 o 13 caracteres)")
    razon_social: str = Field(..., min_length=3, max_length=200, description="Razón Social o Nombre Completo")
    tipo_persona: str = Field("MORAL", description="MORAL o FISICA")
    categoria: str = Field("PROVEEDOR", description="PROVEEDOR o CLIENTE")


class TitularResponse(BaseModel):
    """Datos que devolvemos en la respuesta JSON."""
    id: str
    rfc: str
    razon_social: str
    tipo_persona: str
    categoria: str
    creado_en: datetime

    class Config:
        from_attributes = True
