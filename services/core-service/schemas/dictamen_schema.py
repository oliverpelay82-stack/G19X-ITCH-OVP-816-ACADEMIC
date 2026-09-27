"""
Esquemas de validación de datos para Dictámenes y Bitácora (DTOs).
"""
from datetime import date, datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

EstatusDictamen = Literal["CONFORME", "NO_CONFORME", "EN_REVISION"]


class DictamenCreate(BaseModel):
    """
    Dictamen del Nivel 4 que el ai-service entrega para su persistencia.
    El core-service añade la huella del archivo, el expediente y las reglas
    aplicadas; nunca confía en el cliente para esos datos.
    """
    documento_id: str = Field(..., min_length=1, max_length=36)
    estatus: EstatusDictamen = Field(..., description="Estatus preliminar calculado por el motor")
    nivel_confianza: float = Field(..., ge=0.0, le=1.0)
    requiere_revision_humana: bool = False
    tipo_documento_detectado: Optional[str] = Field(None, max_length=50)
    rfc_detectado: Optional[str] = Field(None, max_length=13)
    match_titular: Optional[bool] = None
    fecha_emision: Optional[date] = None
    fecha_vencimiento: Optional[date] = None
    vigencia: Optional[dict[str, Any]] = Field(
        None, description="Respuesta del rules-service (evaluar-vigencia), o {'disponible': false}"
    )
    observaciones: list[str] = Field(default_factory=list)
    verificaciones: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Elementos del documento verificados contra las reglas RSC/RDS: "
                    "{codigo_regla, nombre_regla, resultado, cita, observacion, recomendacion}",
    )
    modelo_utilizado: Optional[str] = Field(None, max_length=100)
    usuario: str = Field("SISTEMA", min_length=1, max_length=100)


class RatificacionRequest(BaseModel):
    """Decisión del analista sobre un dictamen (Nivel 5, RN-05)."""
    nuevo_estatus: Literal["CONFORME", "NO_CONFORME"]
    justificacion: str = Field(..., min_length=10, max_length=2000)
    usuario: str = Field("OPERADOR", min_length=1, max_length=100)

    @field_validator("justificacion", "usuario")
    @classmethod
    def _sin_espacios_sobrantes(cls, valor: str) -> str:
        limpio = valor.strip()
        if not limpio:
            raise ValueError("No puede estar vacío.")
        return limpio

    @field_validator("justificacion")
    @classmethod
    def _justificacion_suficiente(cls, valor: str) -> str:
        if len(valor) < 10:
            raise ValueError("La justificación debe tener al menos 10 caracteres.")
        return valor


class DictamenResponse(BaseModel):
    id: str
    documento_id: str
    expediente_id: str
    estatus: str
    estatus_preliminar: str
    origen: str
    nivel_confianza: Optional[float] = None
    requiere_revision_humana: bool
    reglas_aplicadas: list[dict[str, Any]]
    vigencia_resultado: Optional[str] = None
    observaciones: list[str]
    tipo_documento_detectado: Optional[str] = None
    rfc_detectado: Optional[str] = None
    match_titular: Optional[bool] = None
    fecha_emision_extraida: Optional[date] = None
    fecha_vencimiento_extraida: Optional[date] = None
    modelo_utilizado: Optional[str] = None
    hash_sha256: str
    revisado_por_humano: bool
    justificacion_humana: Optional[str] = None
    revisado_por: Optional[str] = None
    revisado_en: Optional[datetime] = None
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)


class BitacoraResponse(BaseModel):
    id: str
    evento: str
    expediente_id: Optional[str] = None
    documento_id: Optional[str] = None
    dictamen_id: Optional[str] = None
    usuario: str
    ip_origen: Optional[str] = None
    detalle: dict[str, Any]
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)
