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

from sqlalchemy import JSON, BigInteger, Column, DateTime, String

from config.database import Base

# Catálogo de eventos registrados por el core-service.
EVENTO_APERTURA_EXPEDIENTE = "APERTURA_EXPEDIENTE"
EVENTO_INGESTA_DOCUMENTO = "INGESTA_DOCUMENTO"
EVENTO_EVALUACION_REGLAS = "EVALUACION_REGLAS"
EVENTO_DICTAMEN_IA = "DICTAMEN_IA"
EVENTO_RATIFICACION_HUMANA = "RATIFICACION_HUMANA"
EVENTO_ALERTA_INTEGRIDAD = "ALERTA_INTEGRIDAD"
# Nivel 1 — PDF con contraseña de apertura custodiado como NO_CONFORME (PLUS-02).
EVENTO_ARCHIVO_PROTEGIDO = "ARCHIVO_PROTEGIDO"
# Módulo 6 — Reportes (RF-23, RF-24).
EVENTO_EXPORTACION_REPORTE = "EXPORTACION_REPORTE"
# P3 — primer evento sellado: resume con su huella el historial previo al sellado.
EVENTO_SELLO_GENESIS = "SELLO_GENESIS"
# P5 (PLUS-14): constancia de cada barrido programado de integridad de la bóveda.
EVENTO_VERIFICACION_INTEGRIDAD = "VERIFICACION_INTEGRIDAD"
# P5 (DOC-05, Tabla 1): la IA no respondió y la auditoría quedó en la cola de reintentos.
EVENTO_PROCESAMIENTO_DIFERIDO = "PROCESAMIENTO_DIFERIDO"
# P7 (PLUS-22): una autoridad RFC 3161 selló en el tiempo un eslabón de la cadena.
EVENTO_SELLO_TIEMPO = "SELLO_TIEMPO"


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

    # P3 (PLUS-04): sello encadenado. Nulos en los eventos anteriores al
    # sellado, que cubre la huella del evento SELLO_GENESIS (motor/bitacora.py).
    secuencia = Column(BigInteger, nullable=True, unique=True)
    hash_anterior = Column(String(64), nullable=True)
    hash_evento = Column(String(64), nullable=True)

    def __repr__(self):
        return f"<Bitacora {self.evento} {self.creado_en}>"
