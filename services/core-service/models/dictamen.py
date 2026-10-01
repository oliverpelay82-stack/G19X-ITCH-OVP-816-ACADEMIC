"""
Modelo / Entidad DictamenAuditoria.
Mapea la tabla 'dictamenes_auditoria' en PostgreSQL (DOC-08, Tabla 24).

Cada auditoría de un documento deja un dictamen persistido: el del Nivel 4
(IA más reglas RCV del Nivel 2) o el de una violación de integridad RIE-03.
El dictamen conserva el estatus automático original (``estatus_preliminar``)
aunque un analista lo ratifique después (RN-05): la ratificación solo cambia
``estatus`` y registra quién decidió, cuándo y por qué. Un trigger de
PostgreSQL impide borrar dictámenes o reescribir sus datos de origen
(ver ``config.database.init_db``).
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import JSON, Boolean, Column, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import relationship

from config.database import Base

ORIGEN_NIVEL_4 = "NIVEL_4_IA"
ORIGEN_RIE_03 = "RIE-03"
# PDF protegido con contraseña detectado en la carga (PLUS-02, DOC-05 Tabla 1).
ORIGEN_NIVEL_1 = "NIVEL_1"
# P5 (DOC-05, Tabla 1): la lectura no obtuvo texto suficiente; el modelo no se invocó.
ORIGEN_NIVEL_3_ILEGIBLE = "NIVEL_3_ILEGIBLE"


class DictamenAuditoria(Base):
    __tablename__ = "dictamenes_auditoria"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))

    # RESTRICT: un documento con dictámenes no puede borrarse (RN-04).
    documento_id = Column(String(36), ForeignKey("documentos.id", ondelete="RESTRICT"), nullable=False, index=True)
    expediente_id = Column(String(36), ForeignKey("expedientes.id", ondelete="RESTRICT"), nullable=False, index=True)

    # Estatus vigente del dictamen: CONFORME, NO_CONFORME o EN_REVISION.
    estatus = Column(String(20), nullable=False)
    # Estatus que emitió el motor antes de cualquier ratificación humana.
    estatus_preliminar = Column(String(20), nullable=False)
    # Qué produjo el dictamen: el Nivel 4 (IA + reglas) o la regla RIE-03.
    origen = Column(String(30), nullable=False, default=ORIGEN_NIVEL_4)

    nivel_confianza = Column(Float, nullable=True)
    requiere_revision_humana = Column(Boolean, nullable=False, default=False)

    # Reglas evaluadas con su resultado: [{codigo_regla, resultado, detalle}].
    reglas_aplicadas = Column(JSON, nullable=False, default=list)
    # Resultado consolidado de las reglas RCV (VIGENTE, VENCIDO, INDETERMINADO…).
    vigencia_resultado = Column(String(30), nullable=True)
    observaciones = Column(JSON, nullable=False, default=list)

    tipo_documento_detectado = Column(String(50), nullable=True)
    rfc_detectado = Column(String(13), nullable=True)
    match_titular = Column(Boolean, nullable=True)
    fecha_emision_extraida = Column(Date, nullable=True)
    fecha_vencimiento_extraida = Column(Date, nullable=True)
    modelo_utilizado = Column(String(100), nullable=True)
    # P2 (RSC-02, HU-37): firmantes de un contrato o apoderados de un poder o
    # acta, con su cita: {"rol": "FIRMANTES"|"APODERADOS", "personas": [...]}.
    # El cotejo RN-03 se calcula con estos datos en cada evaluación.
    representacion_legal = Column(JSON, nullable=True)
    # P5 (protocolo de auditoría del DOC-05): con qué lectura del Nivel 3 y con qué
    # instrucciones al modelo se emitió el dictamen, para poder reproducirlo.
    version_lectura = Column(String(160), nullable=True)
    version_instrucciones = Column(String(40), nullable=True)

    # Huella del archivo al momento de la evaluación (protocolo DOC-05 §5.6).
    hash_sha256 = Column(String(64), nullable=False)

    # Nivel 5 — ratificación humana (RF-14, RN-05).
    revisado_por_humano = Column(Boolean, nullable=False, default=False)
    justificacion_humana = Column(Text, nullable=True)
    revisado_por = Column(String(100), nullable=True)
    revisado_en = Column(DateTime, nullable=True)

    creado_en = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    documento = relationship("Documento")

    def __repr__(self):
        return f"<Dictamen {self.estatus} doc={self.documento_id}>"
