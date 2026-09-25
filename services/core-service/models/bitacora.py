"""
Modelo / Entidad BitacoraAuditoria.
Mapea la tabla 'bitacora_auditoria' en PostgreSQL (RF-27, protocolo DOC-05 §5.6).

La bitácora solo admite inserciones: un trigger de PostgreSQL rechaza cualquier
UPDATE o DELETE (ver ``config.database.init_db``). Los identificadores de
expediente, documento y dictamen se guardan sin llave foránea a propósito: el
registro de un evento debe sobrevivir a la entidad que lo originó.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import JSON, Column, DateTime, String

from config.database import Base

# Catálogo de eventos registrados por el core-service.
EVENTO_APERTURA_EXPEDIENTE = "APERTURA_EXPEDIENTE"
EVENTO_INGESTA_DOCUMENTO = "INGESTA_DOCUMENTO"
EVENTO_EVALUACION_REGLAS = "EVALUACION_REGLAS"
EVENTO_DICTAMEN_IA = "DICTAMEN_IA"
EVENTO_RATIFICACION_HUMANA = "RATIFICACION_HUMANA"
EVENTO_ALERTA_INTEGRIDAD = "ALERTA_INTEGRIDAD"


class BitacoraAuditoria(Base):
    __tablename__ = "bitacora_auditoria"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    evento = Column(String(40), nullable=False, index=True)
    expediente_id = Column(String(36), nullable=True, index=True)
    documento_id = Column(String(36), nullable=True, index=True)
    dictamen_id = Column(String(36), nullable=True)
    usuario = Column(String(100), nullable=False, default="OPERADOR")
    ip_origen = Column(String(45), nullable=True)
    detalle = Column(JSON, nullable=False, default=dict)
    creado_en = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True)

    def __repr__(self):
        return f"<Bitacora {self.evento} {self.creado_en}>"
