"""
Esquemas de validación de datos (DTOs) del AI Service.

Los endpoints de análisis y de chat aceptan el documento de dos maneras
intercambiables: por ``documento_id`` —y entonces el servicio lo recupera del
core-service y lo pasa por el Nivel 3— o por ``texto``, cuando el cliente ya
dispone del contenido extraído y quiere ahorrarse una segunda pasada de OCR.
"""
from pydantic import BaseModel, Field, model_validator


class _FuenteDocumental(BaseModel):
    """Base común: exige exactamente una de las dos fuentes de contenido."""

    documento_id: str | None = Field(
        default=None,
        description="Identificador del documento ya registrado en el core-service (:8001).",
    )
    texto: str | None = Field(
        default=None,
        description="Texto del documento, cuando ya fue extraído previamente.",
    )

    @model_validator(mode="after")
    def _validar_fuente(self):
        if not self.documento_id and not (self.texto or "").strip():
            raise ValueError("Debe proporcionar 'documento_id' o 'texto'.")
        return self


class AnalisisSemanticoRequest(_FuenteDocumental):
    """Petición del Nivel 4 — análisis semántico de un documento."""

    rfc_titular: str | None = Field(
        default=None,
        description="RFC del titular registrado en el expediente, para el cruce de titularidad.",
        examples=["PLU180514AB3"],
    )
    razon_social_titular: str | None = Field(
        default=None,
        description="Razón social del titular registrada en el expediente.",
        examples=["PLURIONE S.A. DE C.V."],
    )
    forzar_ocr: bool = Field(
        default=False,
        description="Ignora la capa vectorial del PDF y rasteriza todas las páginas.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "texto": "CONSTANCIA DE SITUACION FISCAL. RFC: PLU180514AB3 ...",
                    "rfc_titular": "PLU180514AB3",
                    "razon_social_titular": "PLURIONE S.A. DE C.V.",
                }
            ]
        }
    }


class MensajeChat(BaseModel):
    """Turno previo de la conversación, para preservar el hilo."""

    rol: str = Field(description="'usuario' o 'asistente'.", examples=["usuario"])
    contenido: str


class ChatDocumentoRequest(_FuenteDocumental):
    """Petición del endpoint conversacional sobre un documento."""

    pregunta: str = Field(
        min_length=3,
        description="Pregunta en lenguaje natural sobre el contenido del documento.",
        examples=["¿Quiénes firman este contrato?"],
    )
    historial: list[MensajeChat] = Field(
        default_factory=list,
        description="Turnos anteriores de la conversación, del más antiguo al más reciente.",
    )

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "documento_id": "3f2a9c5e-1b7d-4e8a-9c10-5d6e7f8a9b0c",
                    "pregunta": "¿Cuál es la suma asegurada?",
                }
            ]
        }
    }
