"""
Modelo / Entidad ParametroSistema.
Mapea la tabla 'parametros_sistema' en PostgreSQL: parámetros de operación que el
administrador cambia desde la interfaz sin tocar el código ni el .env (HU-14).
"""
from datetime import datetime, timezone

from sqlalchemy import JSON, Column, DateTime, String

from config.database import Base


class ParametroSistema(Base):
    """
    Un parámetro por clave (hoy, «umbrales_vencimiento»). Sin fila, rige el valor
    por omisión de su variable de entorno. Cada cambio queda además en la bitácora
    sellada con el valor anterior y el nuevo (RF-27): esta tabla solo guarda el vigente.
    """
    __tablename__ = "parametros_sistema"

    clave = Column(String(50), primary_key=True)
    valor = Column(JSON, nullable=False)
    actualizado_en = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    # Correo de la cuenta que hizo el último cambio.
    actualizado_por = Column(String(150), nullable=True)

    def __repr__(self):
        return f"<ParametroSistema(clave='{self.clave}', valor={self.valor})>"
