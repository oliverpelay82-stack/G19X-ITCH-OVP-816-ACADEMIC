"""
Modelo / Entidad Expediente.
Equivalente a una clase @Entity en Spring Boot.
Mapea la tabla 'expedientes' en MySQL.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, String, Numeric, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base


class Expediente(Base):
    """
    Agrupador lógico de documentos que pertenecen a un titular.
    """
    __tablename__ = "expedientes"

    # Clave primaria UUID
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Clave foránea que apunta a titulares_expediente
    titular_id = Column(
        String(36),
        ForeignKey("titulares_expediente.id", ondelete="CASCADE"),
        nullable=False,
    )
    
    # Código único visible (Ej: EXP-PLU-20260913)
    codigo_expediente = Column(String(50), unique=True, nullable=False, index=True)
    
    # Estado: 'EN_REVISION', 'CONFORME', 'NO_CONFORME', 'BLOQUEADO'
    estado_cumplimiento = Column(String(30), default="EN_REVISION", nullable=False)
    
    # Porcentaje de completitud documental (0.00 a 100.00)
    porcentaje_completitud = Column(Numeric(5, 2), default=0.00, nullable=False)
    
    # Marcas de tiempo
    actualizado_en = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relación inversa con Titular
    titular = relationship("TitularExpediente", backref="expedientes")

    def __repr__(self):
        return f"<Expediente {self.codigo_expediente} ({self.estado_cumplimiento})>"
