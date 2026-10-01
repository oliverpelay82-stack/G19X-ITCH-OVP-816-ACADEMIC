"""
Esquemas de validación de datos para Reglas de Validación (DTOs).
"""
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

# Clasificación temática del expediente (RF-01, DOC-02 Tabla 5).
TipoExpediente = Literal["JURIDICO", "CORPORATIVO", "REGULATORIO"]

# Familias normativas del catálogo (DOC-05): Integridad y Estructura,
# Cronológicas y de Vigencia, Semánticas y Contractuales, Dinámicas y Sectoriales.
FamiliaRegla = Literal["RIE", "RCV", "RSC", "RDS"]


class ReglaCreate(BaseModel):
    """Datos necesarios para dar de alta una regla en el catálogo (RDS-01)."""
    codigo_regla: str = Field(
        ..., min_length=3, max_length=50,
        description="Identificador único, ej. 'RIE-01' o, en el alta por tipos, 'RDS-04-COMP_DOMICILIO'",
    )
    nombre_regla: str = Field(..., min_length=3, max_length=150, description="Nombre corto de la regla")
    familia_regla: FamiliaRegla = Field(..., description="RIE, RCV, RSC o RDS")
    descripcion: str = Field(..., min_length=10, description="Descripción funcional de la regla")
    severidad: str = Field(..., description="CRITICA, ALTA, MEDIA o MEDIA_ALTA")
    accion: str = Field(..., max_length=255, description="Acción del sistema ante incumplimiento")
    tipo_documento: Optional[str] = Field(None, max_length=50, description="Tipo de documento al que aplica")
    documento_obligatorio: bool = Field(True, description="Completitud obligatoria del tipo de documento")
    dias_maximos_vigencia: Optional[int] = Field(None, ge=0, description="Vigencia temporal en días máximos")
    activo: bool = Field(True, description="Bandera de alta/baja lógica de la regla")
    tipo_expediente: Optional[TipoExpediente] = Field(
        None, description="Tipo de expediente al que aplica (RF-06); nulo = todos"
    )
    documento_principal: Optional[str] = Field(
        None, max_length=50,
        description="RIE-02: el tipo_documento es anexo obligatorio de este documento principal (RF-07)",
    )

    @field_validator("tipo_expediente", mode="before")
    @classmethod
    def _tipo_expediente_mayusculas(cls, valor):
        return valor.strip().upper() or None if isinstance(valor, str) else valor


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
    tipo_expediente: Optional[str] = None
    documento_principal: Optional[str] = None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class DocumentoObligatorioResponse(BaseModel):
    """Tipo de documento que exige el expediente y la regla RIE que lo exige."""
    tipo_documento: str
    codigo_regla: str
    severidad: str
    documento_principal: Optional[str] = Field(
        None, description="Solo en anexos (RIE-02): documento cuya presencia vuelve exigible este anexo"
    )
    tipo_expediente: Optional[str] = Field(None, description="Tipo de expediente de la regla; nulo = todos")


class TipoDocumentoDeclaradoResponse(BaseModel):
    """
    Tipo de documento declarado por reglas dinámicas (RF-09, RDS-01): el nombre y
    el tipo de expediente son los de la regla RDS más antigua que lo declara.
    """
    tipo_documento: str
    nombre: str
    activo: bool = Field(description="Alguna regla RDS activa lo declara; con todas pausadas no se admite en la carga")
    tipo_expediente: Optional[str] = None
    codigo_regla: str = Field(description="Regla RDS que lo declaró")


class EvaluacionVigenciaRequest(BaseModel):
    """Fechas de un documento a contrastar con las reglas Cronológicas y de Vigencia (RCV)."""
    tipo_documento: str = Field(..., min_length=2, max_length=50, description="Tipo documental, ej. 'COMP_DOMICILIO'")
    fecha_emision: Optional[date] = Field(None, description="Fecha de emisión del documento (ISO 8601)")
    fecha_vencimiento: Optional[date] = Field(None, description="Fecha de vencimiento declarada, si existe")
    fecha_referencia: Optional[date] = Field(None, description="Fecha contra la que se evalúa; por defecto, hoy")

    model_config = {
        "json_schema_extra": {
            "examples": [{"tipo_documento": "COMP_DOMICILIO", "fecha_emision": "2026-06-15"}]
        }
    }


class EvaluacionReglaResponse(BaseModel):
    """Resultado de una regla RCV sobre el documento."""
    codigo_regla: str
    nombre_regla: str
    severidad: str
    criterio: str = Field(description="ANTIGUEDAD_DESDE_EMISION o DIAS_PARA_VENCIMIENTO")
    resultado: str = Field(description="VIGENTE, PROXIMO_A_VENCER, VENCIDO, INDETERMINADO o NO_APLICA")
    limite_dias: int
    dias_calculados: Optional[int] = None
    detalle: str


class EvaluacionVigenciaResponse(BaseModel):
    """Dictamen consolidado de vigencia: el resultado más grave de las reglas aplicadas."""
    tipo_documento: str
    fecha_referencia: date
    resultado: str = Field(description="VIGENTE, PROXIMO_A_VENCER, VENCIDO, INDETERMINADO o SIN_REGLAS")
    es_vigente: Optional[bool] = Field(None, description="Nulo cuando la vigencia no pudo determinarse")
    dias_calculados: Optional[int] = Field(None, description="Días transcurridos entre la emisión y la validación")
    evaluaciones: list[EvaluacionReglaResponse]
