"""
Esquemas de validación de datos (DTOs).
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator

from motor import rfc as rfc_sat


class TitularCreate(BaseModel):
    """Datos que recibimos al registrar un nuevo titular."""
    rfc: str = Field(..., min_length=12, max_length=13, description="RFC del titular (12 o 13 caracteres)")
    razon_social: str = Field(..., min_length=3, max_length=200, description="Razón Social o Nombre Completo")
    tipo_persona: str = Field("MORAL", description="MORAL o FISICA")
    categoria: str = Field("PROVEEDOR", description="PROVEEDOR o CLIENTE")

    @model_validator(mode="after")
    def _rfc_valido(self) -> "TitularCreate":
        """M1: formato, longitud por tipo de persona y fecha; el dígito solo con RFC_DIGITO_ESTRICTO."""
        self.tipo_persona = (self.tipo_persona or "MORAL").strip().upper()
        self.rfc = rfc_sat.validar(self.rfc, self.tipo_persona)
        return self


class TitularUpdate(BaseModel):
    """
    Corrección de datos de captura (ESTADO_DEL_DESARROLLO §3). El RFC y el tipo de persona no
    se editan: identifican al titular, y un error ahí se resuelve con un
    registro nuevo. Un campo desconocido (rfc incluido) responde 422.
    """
    razon_social: Optional[str] = Field(None, min_length=3, max_length=200)
    categoria: Optional[str] = Field(None, min_length=1, max_length=50)

    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="after")
    def _normalizar(self) -> "TitularUpdate":
        if self.razon_social is not None:
            self.razon_social = " ".join(self.razon_social.split())
            if len(self.razon_social) < 3:
                raise ValueError("La razón social debe tener al menos 3 caracteres.")
        if self.categoria is not None:
            self.categoria = self.categoria.strip().upper()
        if self.razon_social is None and self.categoria is None:
            raise ValueError("Indique la razón social o la categoría a corregir.")
        return self


class TitularResponse(BaseModel):
    """Datos que devolvemos en la respuesta JSON."""
    id: str
    rfc: str
    razon_social: str
    tipo_persona: str
    categoria: str
    creado_en: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field(description="M1: VERIFICADO, GENERICO o DIGITO_NO_COINCIDE (dígito verificador del SAT)")
    @property
    def rfc_verificacion(self) -> str:
        return rfc_sat.verificar(self.rfc)
