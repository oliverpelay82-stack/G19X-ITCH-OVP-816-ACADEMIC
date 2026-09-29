"""
Esquemas de validación de datos para Expedientes (DTOs).
"""
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from schemas.titular_schema import TitularResponse


class TipoExpedienteEnum(str, Enum):
    """Clasificación temática del expediente (RF-01, HU-01; DOC-02 Tabla 5)."""
    JURIDICO = "JURIDICO"
    CORPORATIVO = "CORPORATIVO"
    REGULATORIO = "REGULATORIO"


class ExpedienteCreate(BaseModel):
    """Datos necesarios para aperturar un expediente."""
    titular_id: str = Field(..., description="ID único del titular en la base de datos")
    tipo_expediente: TipoExpedienteEnum = Field(
        TipoExpedienteEnum.CORPORATIVO,
        description="Clasificación temática; decide qué documentos exige el catálogo de reglas (RF-06)",
    )
    nombre: Optional[str] = Field(None, max_length=150, description="Nombre descriptivo del expediente (RF-01)")


class DocumentoObligatorioResponse(BaseModel):
    tipo_documento: str
    codigo_regla: str
    severidad: str
    presente: bool
    documento_principal: Optional[str] = Field(
        None, description="Si es un anexo exigido (RIE-02): documento principal que lo vuelve obligatorio"
    )


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
    vigencia: Optional[str] = Field(
        None, description="VIGENTE, PROXIMO_A_VENCER o VENCIDO a la fecha de la consulta; nulo sin fechas"
    )
    fecha_caducidad: Optional[date] = None
    dias_para_vencer: Optional[int] = None
    anexo_de: Optional[str] = Field(None, description="Documento principal del que es anexo obligatorio (RIE-02)")


class AlertaResponse(BaseModel):
    """Alerta accionable con su recomendación correctiva (RF-18, RF-21)."""
    codigo: str = Field(description="DOCUMENTO_FALTANTE, ANEXO_FALTANTE, DOCUMENTO_VENCIDO, PROXIMO_A_VENCER, ...")
    severidad: str
    titulo: str
    detalle: str
    recomendacion: str
    tipo_documento: Optional[str] = None
    regla: Optional[str] = None
    documento_id: Optional[str] = None


class AnexoFaltanteResponse(BaseModel):
    tipo_documento: str
    documento_principal: str
    codigo_regla: str
    severidad: str


class CotejoRepresentacionResponse(BaseModel):
    """Cotejo del firmante de un contrato con los apoderados del expediente (P2: RSC-02, RN-03)."""
    documento_id: str
    tipo_documento: str
    nombre_archivo_original: str
    estado: str                      # ACREDITADO, NO_ACREDITADO, PODER_VENCIDO o PENDIENTE
    motivo: str
    recomendacion: Optional[str] = None
    firmantes: list[dict[str, Any]] = Field(default_factory=list)
    apoderados: list[dict[str, Any]] = Field(default_factory=list)
    coincidencias: list[dict[str, Any]] = Field(default_factory=list)
    ratificado: bool = False


class ReglaEvaluadaResponse(BaseModel):
    """Una evaluación del índice de cumplimiento (DOC-05, PRD §10.5)."""
    regla: str
    nombre: str
    resultado: str = Field(description="CUMPLIDA, INCUMPLIDA o PENDIENTE")
    tipo_documento: Optional[str] = None
    documento_id: Optional[str] = None
    bloqueante: bool = False


class IndiceCumplimientoResponse(BaseModel):
    """Reglas cumplidas / reglas aplicables × 100, con el bloqueo por criticidad del DOC-05 (C6)."""
    porcentaje: Optional[float] = Field(None, description="Nulo si no hay reglas aplicables")
    cumplidas: int
    incumplidas: int
    pendientes: int
    aplicables: int
    bloqueado: bool
    bloqueos: list[str] = Field(default_factory=list)
    reglas: list[ReglaEvaluadaResponse] = Field(default_factory=list)


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
    tipo_expediente: str = "CORPORATIVO"
    anexos_faltantes: list[AnexoFaltanteResponse] = Field(default_factory=list)
    alertas: list[AlertaResponse] = Field(default_factory=list)
    representacion: list[CotejoRepresentacionResponse] = Field(default_factory=list)
    indice_cumplimiento: Optional[IndiceCumplimientoResponse] = None


class ExpedienteResponse(BaseModel):
    """Datos de respuesta al consultar un expediente."""
    id: str
    titular_id: str
    codigo_expediente: str
    tipo_expediente: str = "CORPORATIVO"
    nombre: Optional[str] = None
    estado_cumplimiento: str
    porcentaje_completitud: float
    creado_en: Optional[datetime] = None
    actualizado_en: datetime
    titular: Optional[TitularResponse] = None
    evaluacion: Optional[EvaluacionExpedienteResponse] = None

    model_config = ConfigDict(from_attributes=True)


class AlertaExpedienteResponse(AlertaResponse):
    """Alerta de la bandeja general, con el expediente al que pertenece (HU-15)."""
    expediente_id: str
    codigo_expediente: str
    tipo_expediente: str
    nombre_expediente: Optional[str] = None
    razon_social: Optional[str] = None
    rfc: Optional[str] = None
    estado_expediente: str
