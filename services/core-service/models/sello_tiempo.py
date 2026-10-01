"""
Modelo / Entidad SelloTiempo (P7, PLUS-22, PRD §21.7).

Sello de tiempo RFC 3161 que una autoridad externa emitió sobre el
``hash_evento`` de un eslabón de la bitácora. La tabla solo admite
inserciones: un trigger rechaza UPDATE y DELETE (``config.database``).
Se guarda el token DER completo para que cualquiera lo verifique con
``openssl ts -verify`` sin depender del motor.
"""
from datetime import datetime, timezone
import uuid

from sqlalchemy import BigInteger, Column, DateTime, LargeBinary, String

from config.database import Base


class SelloTiempo(Base):
    __tablename__ = "sellos_tiempo"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    # Eslabón cubierto: su secuencia, su identificador y la huella que viajó a la autoridad.
    secuencia = Column(BigInteger, nullable=False, index=True)
    evento_id = Column(String(36), nullable=False)
    hash_evento = Column(String(64), nullable=False)
    autoridad = Column(String(255), nullable=False)
    politica = Column(String(100), nullable=True)
    numero_serie = Column(String(80), nullable=False)
    fecha_sello = Column(DateTime, nullable=False)           # genTime del sello, en UTC
    token_der = Column(LargeBinary, nullable=False)          # TimeStampToken (CMS SignedData)
    origen = Column(String(20), nullable=False)               # PROGRAMADO o A_DEMANDA
    creado_en = Column(DateTime, nullable=False, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None))

    def __repr__(self):
        return f"<SelloTiempo secuencia={self.secuencia} {self.fecha_sello}>"
