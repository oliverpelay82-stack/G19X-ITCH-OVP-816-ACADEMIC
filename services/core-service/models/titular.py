"""
Modelo / Entidad TitularExpediente.
Mapea la tabla 'titulares_expediente' en PostgreSQL.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, String, DateTime
from config.database import Base


class TitularExpediente(Base):
    """
    Representa a una empresa (cliente o proveedor) titular de un expediente de cumplimiento.
    """
    __tablename__ = "titulares_expediente"

    # Clave primaria UUID de 36 caracteres
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # RFC: 12 caracteres (Moral) o 13 caracteres (Física)
    rfc = Column(String(13), unique=True, nullable=False, index=True)
    
    # Razón Social o Nombre Completo
    razon_social = Column(String(200), nullable=False)
    
    # Tipo de Persona: 'MORAL' o 'FISICA'
    tipo_persona = Column(String(10), nullable=False)
    
    # Categoría: 'PROVEEDOR', 'CLIENTE'
    categoria = Column(String(50), default="PROVEEDOR", nullable=False)
    
    # Fecha de registro en UTC
    creado_en = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<Titular {self.rfc} - {self.razon_social}>"
