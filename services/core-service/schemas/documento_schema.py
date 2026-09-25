"""
Esquemas de validación de datos para Documentos (DTOs).
Equivalente a las clases DTO / Response en Spring Boot.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel


class TipoDocumentoEnum(str, Enum):
    """
    Catálogo oficial de tipos documentales requeridos para expedientes B2B.
    Conforme al DOC-05 (Regla RIE) y DOC-08.
    """
    CSF_SAT = "CSF_SAT"                           # Constancia de Situación Fiscal (SAT)
    COMP_DOMICILIO = "COMP_DOMICILIO"             # Comprobante de Domicilio Fiscal
    ACTA_CONSTITUTIVA = "ACTA_CONSTITUTIVA"       # Acta Constitutiva / Poder Notarial
    OPINION_CUMPLIMIENTO = "OPINION_CUMPLIMIENTO" # Opinión de Cumplimiento SAT (Art. 32-D)
    ESTADO_CUENTA = "ESTADO_CUENTA"               # Carátula de Estado de Cuenta Bancario


class DocumentoResponse(BaseModel):
    """Datos devueltos al registrar o consultar un documento."""
    id: str
    expediente_id: str
    tipo_documento: str
    nombre_archivo_original: str
    hash_sha256: str
    tamanio_bytes: int
    mime_type: str
    estado_integridad: str = "INTEGRO"
    creado_en: datetime

    class Config:
        from_attributes = True
