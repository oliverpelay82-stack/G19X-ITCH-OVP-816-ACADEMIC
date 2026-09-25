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


class DocumentoObligatorioResponse(BaseModel):
    tipo_documento: str
    codigo_regla: str
    severidad: str
    presente: bool


class EstadoDocumentoResponse(BaseModel):
    """Estado del documento vigente de un tipo dentro del semáforo."""
    documento_id: str
    tipo_documento: str
    nombre_archivo_original: str
    obligatorio: bool
    estado: str = Field(description="CONFORME, EN_REVISION, NO_CONFORME o SIN_DICTAMEN")
    dictamen_id: Optional[str] = None
    revisado_por_humano: bool = False
    estado_integridad: str = "INTEGRO"


class EvaluacionExpedienteResponse(BaseModel):
    """Desglose del estado consolidado del expediente (RN-01, RN-02, RN-05)."""
    estado: str
    porcentaje_completitud: float
    obligatorios: list[DocumentoObligatorioResponse]
    faltantes: list[str]
    documentos: list[EstadoDocumentoResponse]
    motivos: list[str]
    fuente_obligatorios: str = Field(description="rules-service o respaldo-doc02")
    advertencia: Optional[str] = None
    sustituidos: int = Field(0, description="Archivos reemplazados por uno más reciente del mismo tipo")


class ExpedienteResponse(BaseModel):
    """Datos de respuesta al consultar un expediente."""
    id: str
    titular_id: str
    codigo_expediente: str
    estado_cumplimiento: str
    porcentaje_completitud: float
    actualizado_en: datetime
    titular: Optional[TitularResponse] = None
    evaluacion: Optional[EvaluacionExpedienteResponse] = None

    class Config:
        from_attributes = True
