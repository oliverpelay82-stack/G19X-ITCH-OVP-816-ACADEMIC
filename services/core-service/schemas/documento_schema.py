"""
Esquemas de validación de datos para Documentos (DTOs).
Equivalente a las clases DTO / Response en Spring Boot.
"""
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, ConfigDict, Field, computed_field

from motor import senales_pdf as senales


class TipoDocumentoEnum(str, Enum):
    """
    Catálogo oficial de tipos documentales (DOC-02, Tablas 2 a 4; DOC-05 regla
    RIE). Los nombres legibles viven en ``config/catalogo.py``.
    """
    # Expediente corporativo
    CSF_SAT = "CSF_SAT"                           # Constancia de Situación Fiscal (SAT)
    COMP_DOMICILIO = "COMP_DOMICILIO"             # Comprobante de Domicilio Fiscal
    ACTA_CONSTITUTIVA = "ACTA_CONSTITUTIVA"       # Acta Constitutiva
    PODER_NOTARIAL = "PODER_NOTARIAL"             # Poder notarial del representante
    ESTATUTOS_SOCIALES = "ESTATUTOS_SOCIALES"
    ACTA_ASAMBLEA = "ACTA_ASAMBLEA"
    CEDULA_RFC = "CEDULA_RFC"                     # Registro Federal de Contribuyentes (empresa)
    AVISO_PRIVACIDAD = "AVISO_PRIVACIDAD"
    OPINION_CUMPLIMIENTO = "OPINION_CUMPLIMIENTO" # Opinión de Cumplimiento SAT (Art. 32-D)
    ESTADO_CUENTA = "ESTADO_CUENTA"               # Carátula de Estado de Cuenta Bancario
    # Expediente jurídico
    CONTRATO_SERVICIOS = "CONTRATO_SERVICIOS"
    ACUERDO_CONFIDENCIALIDAD = "ACUERDO_CONFIDENCIALIDAD"  # NDA
    ANEXO_CONTRATO = "ANEXO_CONTRATO"             # Anexos legales referenciados en el contrato
    DICTAMEN_PERICIAL = "DICTAMEN_PERICIAL"
    CONVENIO_MODIFICATORIO = "CONVENIO_MODIFICATORIO"
    # Expediente regulatorio
    LICENCIA_OPERACION = "LICENCIA_OPERACION"
    PERMISO_SECTORIAL = "PERMISO_SECTORIAL"       # Permisos municipales o sectoriales
    CERTIFICACION = "CERTIFICACION"               # ISO, calidad, ambiental
    POLIZA_SEGURO = "POLIZA_SEGURO"
    POLIZA_RC = "POLIZA_RC"                       # Póliza de responsabilidad civil
    FIANZA = "FIANZA"
    CONSTANCIA_CAPACITACION = "CONSTANCIA_CAPACITACION"
    REGISTRO_SECTORIAL = "REGISTRO_SECTORIAL"     # Registros ante autoridades sectoriales


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
    # Solo en la respuesta de la carga: folios de otros expedientes que ya
    # custodian el mismo archivo (PLUS-01 lo admite y solo lo informa).
    huella_en_otros_expedientes: list[str] = Field(default_factory=list)
    # Solo en la respuesta de la carga: el PDF exige contraseña de apertura y
    # quedó custodiado como NO_CONFORME (PLUS-02).
    advertencia_nivel_1: str | None = None
    # P6 (PLUS-16, PLUS-18): señales del PDF; nulo si aún no se calculan.
    senales_pdf: dict | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field(description="P6: motivos por los que la auditoría queda en revisión humana (señales del archivo)")
    @property
    def senales_revision(self) -> list[str]:
        return senales.revision(self.tipo_documento, self.senales_pdf)
