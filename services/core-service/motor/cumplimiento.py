"""
Estado consolidado del expediente: semáforo de cumplimiento (RN-01, RN-02, RN-05).

Subir archivos no aprueba un expediente. El estado se deriva de dos fuentes:

  * **Completitud (RIE-01).** Qué tipos de documento exige el catálogo de reglas
    (rules-service) y cuáles están presentes.
  * **Dictámenes.** El último dictamen persistido de cada documento vigente,
    incluida la ratificación humana cuando existe (RN-05: prevalece).

Documento vigente: por cada tipo de documento cuenta el archivo cargado más
recientemente. Los anteriores del mismo tipo quedan sustituidos y no pesan en
el semáforo, aunque sus dictámenes siguen en la bitácora (RN-04: nada se
borra). Así, recargar un comprobante vencido con uno reciente permite que el
expediente se recupere.

Reglas del semáforo, en orden de gravedad:

  1. NO_CONFORME — falta un documento obligatorio de severidad CRÍTICA, o un
     documento vigente tiene dictamen NO_CONFORME (vencido por RCV, titular
     ajeno o alteración RIE-03).
  2. EN_REVISION — falta un obligatorio no crítico, un obligatorio aún no se
     audita, o un documento vigente espera ratificación humana.
  3. CONFORME — todos los obligatorios presentes y todos sus dictámenes
     conformes (automáticos o ratificados por un analista).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from clients import rules_client
from models.bitacora import EVENTO_EVALUACION_REGLAS
from models.dictamen import DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora

CONFORME = "CONFORME"
EN_REVISION = "EN_REVISION"
NO_CONFORME = "NO_CONFORME"
SIN_DICTAMEN = "SIN_DICTAMEN"

INTEGRIDAD_ALTERADO = "ALTERADO"


@dataclass
class EstadoDocumento:
    documento_id: str
    tipo_documento: str
    nombre_archivo_original: str
    obligatorio: bool
    estado: str                        # CONFORME, EN_REVISION, NO_CONFORME o SIN_DICTAMEN
    dictamen_id: str | None = None
    revisado_por_humano: bool = False
    estado_integridad: str = "INTEGRO"


@dataclass
class EvaluacionExpediente:
    estado: str
    porcentaje_completitud: float
    obligatorios: list[dict[str, Any]]
    faltantes: list[str]
    documentos: list[EstadoDocumento]
    motivos: list[str]
    fuente_obligatorios: str
    advertencia: str | None = None
    sustituidos: int = 0


def _ultimos_dictamenes(db: Session, documento_ids: list[str]) -> dict[str, DictamenAuditoria]:
    if not documento_ids:
        return {}
    dictamenes = (
        db.query(DictamenAuditoria)
        .filter(DictamenAuditoria.documento_id.in_(documento_ids))
        .order_by(DictamenAuditoria.creado_en.desc())
        .all()
    )
    ultimos: dict[str, DictamenAuditoria] = {}
    for d in dictamenes:
        ultimos.setdefault(d.documento_id, d)
    return ultimos


def evaluar(
    db: Session,
    expediente: Expediente,
    inventario: rules_client.InventarioObligatorio | None = None,
) -> EvaluacionExpediente:
    """Calcula el semáforo del expediente sin modificar nada."""
    inventario = inventario or rules_client.obtener_documentos_obligatorios()
    requeridos = inventario.documentos

    documentos = (
        db.query(Documento)
        .filter(Documento.expediente_id == expediente.id)
        .order_by(Documento.creado_en.desc())
        .all()
    )
    vigentes: dict[str, Documento] = {}
    for doc in documentos:
        vigentes.setdefault(doc.tipo_documento, doc)
    dictamenes = _ultimos_dictamenes(db, [d.id for d in vigentes.values()])

    estados: list[EstadoDocumento] = []
    for tipo, doc in sorted(vigentes.items()):
        dictamen = dictamenes.get(doc.id)
        if doc.estado_integridad == INTEGRIDAD_ALTERADO:
            estado = NO_CONFORME
        elif dictamen is None:
            estado = SIN_DICTAMEN
        else:
            estado = dictamen.estatus
        estados.append(
            EstadoDocumento(
                documento_id=doc.id,
                tipo_documento=tipo,
                nombre_archivo_original=doc.nombre_archivo_original,
                obligatorio=tipo in requeridos,
                estado=estado,
                dictamen_id=dictamen.id if dictamen else None,
                revisado_por_humano=bool(dictamen and dictamen.revisado_por_humano),
                estado_integridad=doc.estado_integridad or "INTEGRO",
            )
        )

    obligatorios = [
        {"tipo_documento": tipo, **datos, "presente": tipo in vigentes} for tipo, datos in sorted(requeridos.items())
    ]
    faltantes = [o["tipo_documento"] for o in obligatorios if not o["presente"]]
    faltantes_criticos = [o["tipo_documento"] for o in obligatorios if not o["presente"] and o["severidad"] == "CRITICA"]
    presentes = len(obligatorios) - len(faltantes)
    porcentaje = round(presentes / len(obligatorios) * 100, 1) if obligatorios else 100.0

    motivos: list[str] = []
    rechazados = [e for e in estados if e.estado == NO_CONFORME]
    pendientes = [
        e for e in estados
        if e.estado == EN_REVISION or (e.estado == SIN_DICTAMEN and e.obligatorio)
    ]

    if faltantes_criticos:
        motivos.append(f"Faltan documentos obligatorios de severidad crítica: {', '.join(faltantes_criticos)} (RIE-01).")
    for e in rechazados:
        causa = "alteración criptográfica (RIE-03)" if e.estado_integridad == INTEGRIDAD_ALTERADO else "dictamen NO_CONFORME"
        motivos.append(f"{e.tipo_documento} ({e.nombre_archivo_original}): {causa}.")
    faltantes_no_criticos = [t for t in faltantes if t not in faltantes_criticos]
    if faltantes_no_criticos:
        motivos.append(f"Faltan documentos obligatorios: {', '.join(faltantes_no_criticos)}.")
    for e in pendientes:
        causa = "sin auditar" if e.estado == SIN_DICTAMEN else "pendiente de ratificación humana (Nivel 5)"
        motivos.append(f"{e.tipo_documento} ({e.nombre_archivo_original}): {causa}.")

    if faltantes_criticos or rechazados:
        estado_expediente = NO_CONFORME
    elif faltantes_no_criticos or pendientes:
        estado_expediente = EN_REVISION
    else:
        estado_expediente = CONFORME
        motivos.append("Todos los documentos obligatorios están presentes y sus dictámenes son conformes.")

    return EvaluacionExpediente(
        estado=estado_expediente,
        porcentaje_completitud=porcentaje,
        obligatorios=obligatorios,
        faltantes=faltantes,
        documentos=estados,
        motivos=motivos,
        fuente_obligatorios=inventario.fuente,
        advertencia=inventario.advertencia,
        sustituidos=len(documentos) - len(vigentes),
    )


def sincronizar(
    db: Session,
    expediente: Expediente,
    evaluacion: EvaluacionExpediente,
    *,
    causa: str,
    usuario: str = bitacora.USUARIO_SISTEMA,
    ip_origen: str | None = None,
) -> bool:
    """
    Guarda el estado calculado en el expediente. Si el semáforo cambia, deja
    constancia en la bitácora (EVALUACION_REGLAS). No confirma la transacción.
    """
    anterior = expediente.estado_cumplimiento
    # Solo se escribe lo que cambió: una consulta que no altera el semáforo no
    # debe mover la marca actualizado_en del expediente.
    if abs(float(expediente.porcentaje_completitud or 0) - evaluacion.porcentaje_completitud) > 0.001:
        expediente.porcentaje_completitud = evaluacion.porcentaje_completitud
    if anterior == evaluacion.estado:
        return False
    expediente.estado_cumplimiento = evaluacion.estado
    bitacora.registrar(
        db,
        EVENTO_EVALUACION_REGLAS,
        expediente_id=expediente.id,
        usuario=usuario,
        ip_origen=ip_origen,
        detalle={
            "causa": causa,
            "estado_anterior": anterior,
            "estado_nuevo": evaluacion.estado,
            "porcentaje_completitud": evaluacion.porcentaje_completitud,
            "faltantes": evaluacion.faltantes,
            "motivos": evaluacion.motivos,
            "fuente_obligatorios": evaluacion.fuente_obligatorios,
            "advertencia": evaluacion.advertencia,
        },
    )
    return True


def reevaluar(
    db: Session,
    expediente: Expediente,
    *,
    causa: str,
    usuario: str = bitacora.USUARIO_SISTEMA,
    ip_origen: str | None = None,
    inventario: rules_client.InventarioObligatorio | None = None,
) -> EvaluacionExpediente:
    """Evalúa y sincroniza en un solo paso. No confirma la transacción."""
    db.flush()
    evaluacion = evaluar(db, expediente, inventario)
    sincronizar(db, expediente, evaluacion, causa=causa, usuario=usuario, ip_origen=ip_origen)
    return evaluacion
