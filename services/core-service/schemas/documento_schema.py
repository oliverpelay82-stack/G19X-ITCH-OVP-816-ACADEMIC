"""
Esquemas de validación de datos para Documentos (DTOs).
"""
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field, computed_field

from config.catalogo import etiqueta_documento
from motor import senales_pdf as senales


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
    # P6 (PLUS-18): contenido activo del PDF; nulo si aún no se calcula.
    senales_pdf: dict | None = None

    model_config = ConfigDict(from_attributes=True)

    @computed_field(description="Nombre legible del tipo de documento (catálogo base o tipo declarado, RF-09)")
    @property
    def nombre_tipo_documento(self) -> str:
        return etiqueta_documento(self.tipo_documento)

    @computed_field(description="P6: motivos por los que la auditoría queda en revisión humana (señales del archivo)")
    @property
    def senales_revision(self) -> list[str]:
        return senales.revision(self.tipo_documento, self.senales_pdf)
