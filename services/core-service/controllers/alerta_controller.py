"""
Controlador de Alertas y Recomendaciones (Módulo 5: RF-18, RF-21, HU-15, HU-16).

Bandeja consolidada de todos los expedientes. Las alertas no se almacenan: se
derivan en cada consulta de la evaluación del semáforo (``motor/cumplimiento``),
de modo que una alerta desaparece en cuanto se corrige el hallazgo y una nueva
aparece en cuanto se produce (un documento que vence hoy, un anexo que falta).
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from config.database import get_db
from controllers.expediente_controller import consultar_expedientes, evaluar_lista
from motor import cumplimiento
from schemas.expediente_schema import AlertaExpedienteResponse

router = APIRouter(prefix="/api/v1/alertas", tags=["Alertas y Recomendaciones"])


@router.get(
    "",
    response_model=list[AlertaExpedienteResponse],
    summary="Alertas vigentes de todos los expedientes, con su recomendación correctiva",
)
def listar_alertas(
    severidad: Optional[str] = Query(None, description="CRITICA, ALTA, MEDIA_ALTA o MEDIA"),
    codigo: Optional[str] = Query(None, description="DOCUMENTO_FALTANTE, ANEXO_FALTANTE, DOCUMENTO_VENCIDO, ..."),
    tipo_expediente: Optional[str] = Query(None, description="JURIDICO, CORPORATIVO o REGULATORIO"),
    expediente_id: Optional[str] = None,
    db: Session = Depends(get_db),
):
    expedientes = consultar_expedientes(db, tipo_expediente=tipo_expediente)
    if expediente_id:
        expedientes = [e for e in expedientes if e.id == expediente_id]
    alertas: list[AlertaExpedienteResponse] = []
    for exp, evaluacion in evaluar_lista(db, expedientes, causa="CONSULTA_ALERTAS"):
        for alerta in evaluacion.alertas:
            if severidad and alerta.severidad != severidad.strip().upper():
                continue
            if codigo and alerta.codigo != codigo.strip().upper():
                continue
            alertas.append(AlertaExpedienteResponse(
                **alerta.__dict__,
                expediente_id=exp.id,
                codigo_expediente=exp.codigo_expediente,
                tipo_expediente=exp.tipo_expediente,
                nombre_expediente=exp.nombre,
                razon_social=exp.titular.razon_social if exp.titular else None,
                rfc=exp.titular.rfc if exp.titular else None,
                estado_expediente=exp.estado_cumplimiento,
            ))
    return sorted(alertas, key=lambda a: cumplimiento.rango_severidad(a.severidad))
