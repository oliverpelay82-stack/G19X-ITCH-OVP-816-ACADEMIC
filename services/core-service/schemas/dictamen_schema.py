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
    origen: Optional[Literal["NIVEL_4_IA", "NIVEL_3_ILEGIBLE"]] = Field(
        None, description="P5: NIVEL_3_ILEGIBLE si la lectura no obtuvo texto suficiente (sin modelo); por omisión, NIVEL_4_IA"
    )
    version_lectura: Optional[str] = Field(
        None, max_length=160, description="P5: versión de la lectura del Nivel 3 (pipeline, Tesseract, idioma, DPI)"
    )
    version_instrucciones: Optional[str] = Field(
        None, max_length=40, description="P5: huella de las instrucciones al modelo"
    )
    qr_sat: Optional[dict[str, Any]] = Field(
        None, description="P6 (PLUS-17): lectura del QR del SAT (url, dominio_sat, rfc_qr, coincide_rfc)"
    )
    version_catalogo: Optional[str] = Field(
        None, max_length=20, description="P6 (M6): versión del catálogo de reglas (cat-…)"
    )
    version_reglas_tipo: Optional[str] = Field(
        None, max_length=20, description="P7 (M7): versión de las reglas del tipo de documento (tip-…)"
    )
    usuario: str = Field("SISTEMA", min_length=1, max_length=100)
    representacion: Optional[dict[str, Any]] = Field(
        None,
        description="P2 (RSC-02, HU-37): {rol: FIRMANTES|APODERADOS, personas: [{nombre, cargo, empresa|facultades, "
                    "cita, cita_verificada}]}",
    )


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
    version_lectura: Optional[str] = None
    version_instrucciones: Optional[str] = None
    qr_sat: Optional[dict[str, Any]] = None
    version_catalogo: Optional[str] = None
    version_reglas_tipo: Optional[str] = None
    representacion_legal: Optional[dict[str, Any]] = None
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
    # P3: sello encadenado (nulos en los eventos anteriores al sellado).
    secuencia: Optional[int] = None
    hash_anterior: Optional[str] = None
    hash_evento: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class HallazgoCadenaResponse(BaseModel):
    secuencia: Optional[int] = None
    evento_id: Optional[str] = None
    problema: str


class SelloTiempoResponse(BaseModel):
    """Sello de tiempo RFC 3161 sobre un eslabón de la bitácora (P7, PLUS-22)."""
    id: str
    secuencia: int
    evento_id: str
    hash_evento: str
    autoridad: str
    politica: Optional[str] = None
    numero_serie: str
    fecha_sello: str
    origen: str
    # Si la huella del eslabón cubierto sigue coincidiendo con la cadena (None: no se verificó).
    coincide: Optional[bool] = None


class SolicitudSelloTiempoResponse(BaseModel):
    nuevo: bool
    sello: SelloTiempoResponse


class VerificacionCadenaResponse(BaseModel):
    """Resultado de recalcular la cadena de la bitácora (P3, PLUS-05)."""
    integra: bool
    sellada: bool
    eventos_sellados: int
    eventos_previos: int
    ultimo_hash: Optional[str] = None
    ultima_secuencia: Optional[int] = None
    verificado_en: Optional[str] = None
    algoritmo: str
    total_hallazgos: int = 0
    hallazgos: list[HallazgoCadenaResponse] = Field(default_factory=list)
    # P7 (PLUS-22): último sello de tiempo de un tercero y si sigue coincidiendo.
    sello_tiempo: Optional[SelloTiempoResponse] = None


class ProcesamientoDiferidoRequest(BaseModel):
    """P5 (DOC-05, Tabla 1): el ai-service avisa que la auditoría de un documento quedó diferida."""
    motivo: str = Field(..., min_length=1, max_length=500)
    intentos: int = Field(0, ge=0)
    max_intentos: int = Field(..., ge=1)
    proximo_intento: Optional[datetime] = None
    agotado: bool = False

