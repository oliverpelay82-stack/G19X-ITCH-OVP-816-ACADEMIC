"""
Modelo / Entidad Regla de Validación.
Equivalente a una clase @Entity en Spring Boot.
Mapea la tabla 'reglas_validacion' en MySQL.

Fuente normativa: DOC-05 (Estrategia de Validación y Catálogo de Reglas de
Negocio) y DOC-08 (Diseño de Arquitectura de Software, APIs y Base de Datos).
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import Column, String, Text, Boolean, Integer, DateTime
from config.database import Base


class Regla(Base):
    """
    Representa una regla de negocio del catálogo definido en el DOC-05,
    organizada en cuatro familias: RIE, RCV, RSC y RDS.
    """
    __tablename__ = "reglas_validacion"

    # Clave primaria UUID
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # Identificador único del catálogo, ej. 'RIE-01', 'RCV-01' (DOC-05)
    codigo_regla = Column(String(20), unique=True, nullable=False, index=True)

    # Nombre corto de la regla, ej. 'Completitud de Expediente'
    nombre_regla = Column(String(150), nullable=False)

    # Familia normativa: RIE (Integridad y Estructura), RCV (Cronológicas y
    # Vigencia), RSC (Semánticas y Contractuales), RDS (Dinámicas y Sectoriales)
    familia_regla = Column(String(10), nullable=False)

    # Descripción funcional completa de la regla (texto del catálogo DOC-05)
    descripcion = Column(Text, nullable=False)

    # Severidad declarada en el catálogo: CRITICA, ALTA, MEDIA, MEDIA_ALTA
    severidad = Column(String(20), nullable=False)

    # Acción del sistema ante incumplimiento (texto del catálogo DOC-05)
    accion = Column(String(255), nullable=False)

    # Tipo de documento al que aplica la regla (ej. 'CSF_SAT'); nulo cuando la
    # regla es de alcance general sobre el expediente (ej. RIE-01, RIE-03)
    tipo_documento = Column(String(50), nullable=True)

    # Completitud obligatoria: si el tipo de documento es obligatorio para el
    # expediente (RIE-01 / HU-09)
    documento_obligatorio = Column(Boolean, default=True, nullable=False)

    # Vigencia temporal en días máximos permitidos (RCV-01)
    dias_maximos_vigencia = Column(Integer, nullable=True)

    # Bandera de activación (alta/baja lógica) de la regla
    activo = Column(Boolean, default=True, nullable=False)

    # Fecha de alta en UTC
    creado_en = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    def __repr__(self):
        return f"<Regla {self.codigo_regla} - {self.nombre_regla}>"
