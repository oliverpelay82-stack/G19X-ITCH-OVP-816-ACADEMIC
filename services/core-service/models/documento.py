"""
Modelo / Entidad Documento.
Equivalente a una clase @Entity en Spring Boot.
Mapea la tabla 'documentos' en MySQL.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import JSON, Column, String, BigInteger, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base


class Documento(Base):
    """
    Representa un archivo binario digitalizado asociado a un expediente.
    """
    __tablename__ = "documentos"

    # Clave primaria UUID
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    
    # Clave foránea que apunta a expedientes. Indexada: cada evaluación del
    # semáforo y cada listado del expediente filtran por ella. RESTRICT: un
    # expediente con documentos custodiados no puede borrarse (cadena de custodia).
    expediente_id = Column(
        String(36),
        ForeignKey("expedientes.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    
    # Tipo documental corporativo: 'CSF_SAT', 'COMP_DOMICILIO', 'ACTA_CONSTITUTIVA'
    tipo_documento = Column(String(50), nullable=False)
    
    # Nombre del archivo que subió el usuario
    nombre_archivo_original = Column(String(255), nullable=False)
    
    # Ruta física donde se almacena en el servidor
    ruta_almacenamiento = Column(String(500), nullable=False)
    
    # Hash criptográfico SHA-256 (64 caracteres hexadecimales para NOM-151)
    hash_sha256 = Column(String(64), nullable=False, index=True)
    # P5 (DOC-05, Tabla 1): auditoría diferida porque la IA no respondió. Se
    # limpia al guardarse el dictamen. {motivo, intentos, max_intentos,
    # proximo_intento, agotado, desde}.
    procesamiento_diferido = Column(JSON, nullable=True)
    # P6 (PLUS-18): contenido activo del PDF calculadas en la carga o en el barrido
    # programado (motor/senales_pdf.py). Nulo: aún sin calcular.
    senales_pdf = Column(JSON, nullable=True)
    
    # Tamaño en bytes y tipo MIME
    tamanio_bytes = Column(BigInteger, nullable=False)
    mime_type = Column(String(100), nullable=False)

    # Resultado de la última verificación RIE-03: INTEGRO o ALTERADO. Un
    # documento alterado queda bloqueado para lectura y análisis.
    estado_integridad = Column(String(20), nullable=False, default="INTEGRO", server_default="INTEGRO")

    # Fecha de carga en UTC
    creado_en = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relación con el Expediente
    expediente = relationship("Expediente", backref="documentos")

    def __repr__(self):
        return f"<Documento {self.tipo_documento} - {self.nombre_archivo_original}>"
