"""
Estado consolidado del expediente: semáforo de cumplimiento (RN-01, RN-02, RN-05)
y alertas con recomendación (RF-18, RF-21).

Subir archivos no aprueba un expediente. El estado se deriva de tres fuentes:

  * **Completitud (RIE-01).** Qué tipos de documento exige el catálogo de reglas
    (rules-service) para el tipo del expediente (RF-06) y cuáles están presentes.
  * **Anexos vinculados (RIE-02).** Si el expediente contiene un documento
    principal con anexos obligatorios (p. ej. un contrato de prestación de
    servicios), esos anexos se vuelven exigibles; la ausencia de uno invalida
    el documento principal.
  * **Dictámenes.** El último dictamen persistido de cada documento vigente,
    incluida la ratificación humana cuando existe (RN-05: prevalece). Las
    fechas que extrajo el dictamen se contrastan con la fecha actual en cada
    evaluación: un documento que era vigente al auditarse y venció después
    pasa a NO_CONFORME sin esperar otra auditoría (RN-02).

Documento vigente: por cada tipo de documento cuenta el archivo cargado más
recientemente. Los anteriores del mismo tipo quedan sustituidos y no pesan en
el semáforo, aunque sus dictámenes siguen en la bitácora (RN-04: nada se
borra). Así, recargar un comprobante vencido con uno reciente permite que el
expediente se recupere.

Reglas del semáforo, en orden de gravedad:

  1. NO_CONFORME — falta un documento obligatorio de severidad CRÍTICA, falta
     un anexo obligatorio de un documento presente (RIE-02), o un documento
     vigente tiene dictamen NO_CONFORME (vencido por RCV, titular ajeno o
     alteración RIE-03) o venció después de auditarse (RN-02).
  2. EN_REVISION — falta un obligatorio no crítico, un obligatorio aún no se
     audita, un documento vigente espera ratificación humana, o un documento
     está próximo a vencer (RCV-01, RF-19: semáforo amarillo).
  3. CONFORME — todos los obligatorios presentes y todos sus dictámenes
     conformes (automáticos o ratificados por un analista).

Las alertas no se guardan en una tabla propia: se derivan de la misma
evaluación, de modo que desaparecen en cuanto se corrige el hallazgo. Cada
cambio de semáforo, con sus alertas, queda en la bitácora (EVALUACION_REGLAS).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy.orm import Session

from clients import rules_client
from config.catalogo import etiqueta_documento
from models.bitacora import EVENTO_EVALUACION_REGLAS
from models.dictamen import ORIGEN_NIVEL_1, DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora

CONFORME = "CONFORME"
EN_REVISION = "EN_REVISION"
NO_CONFORME = "NO_CONFORME"
SIN_DICTAMEN = "SIN_DICTAMEN"

INTEGRIDAD_ALTERADO = "ALTERADO"

# Vigencia recalculada contra la fecha actual (mismos valores que el rules-service).
VIGENTE = "VIGENTE"
PROXIMO_A_VENCER = "PROXIMO_A_VENCER"
VENCIDO = "VENCIDO"
CRITERIO_VENCIMIENTO = "DIAS_PARA_VENCIMIENTO"
CRITERIO_ANTIGUEDAD = "ANTIGUEDAD_DESDE_EMISION"
# Ventana de «próximo a vencer» si el dictamen no registró la de RCV-01 (DOC-05: 30 días).
DIAS_PROXIMO_A_VENCER = 30


def _umbrales_alerta() -> tuple[int, ...]:
    """
    Días de anticipación de las alertas de vencimiento (RF-17, HU-14; por
    defecto 30, 15 y 5), configurables con UMBRALES_ALERTA_VENCIMIENTO.
    """
    valores = []
    for parte in os.getenv("UMBRALES_ALERTA_VENCIMIENTO", "30,15,5").split(","):
        try:
            valores.append(int(parte))
        except ValueError:
            continue
    return tuple(sorted({v for v in valores if v >= 0}, reverse=True)) or (30, 15, 5)


UMBRALES_ALERTA = _umbrales_alerta()

# Códigos de alerta (RF-18). Las severidades son las del catálogo de reglas.
ALERTA_DOCUMENTO_FALTANTE = "DOCUMENTO_FALTANTE"
ALERTA_ANEXO_FALTANTE = "ANEXO_FALTANTE"
ALERTA_DOCUMENTO_VENCIDO = "DOCUMENTO_VENCIDO"
ALERTA_PROXIMO_A_VENCER = "PROXIMO_A_VENCER"
ALERTA_INTEGRIDAD = "INTEGRIDAD_COMPROMETIDA"
ALERTA_DICTAMEN_NO_CONFORME = "DICTAMEN_NO_CONFORME"
ALERTA_REVISION_HUMANA = "PENDIENTE_RATIFICACION"
ALERTA_SIN_AUDITAR = "PENDIENTE_AUDITORIA"
ALERTA_CONTENIDO = "CONTENIDO_NO_LOCALIZADO"

# Resultados de la verificación de contenido (reglas RSC/RDS) que exigen atención.
CONTENIDO_PENDIENTE = ("NO_LOCALIZADO", "NO_VERIFICABLE")

ORDEN_SEVERIDAD = ["CRITICA", "ALTA", "MEDIA_ALTA", "MEDIA", "BAJA"]


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
    # Vigencia a la fecha de la consulta, a partir de las fechas del dictamen.
    vigencia: str | None = None        # VIGENTE, PROXIMO_A_VENCER, VENCIDO; nulo sin fechas
    fecha_caducidad: date | None = None
    dias_para_vencer: int | None = None
    anexo_de: str | None = None        # documento principal si es un anexo exigido (RIE-02)


@dataclass
class Alerta:
    """Hallazgo accionable del expediente con su recomendación correctiva (RF-18, RF-21)."""
    codigo: str
    severidad: str
    titulo: str
    detalle: str
    recomendacion: str
    tipo_documento: str | None = None
    regla: str | None = None
    documento_id: str | None = None


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
    tipo_expediente: str = "CORPORATIVO"
    anexos_faltantes: list[dict[str, str]] = field(default_factory=list)
    alertas: list[Alerta] = field(default_factory=list)


@dataclass
class _Vigencia:
    estado: str
    fecha_caducidad: date
    dias: int
    criterio: str
    limite_dias: int | None
    regla: str | None = None           # regla RCV que fija la caducidad (RCV-01, RCV-02…)


def ultimos_dictamenes(db: Session, documento_ids: list[str]) -> dict[str, DictamenAuditoria]:
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


def vigencia_actual(dictamen: DictamenAuditoria | None, hoy: date) -> _Vigencia | None:
    """
    Recalcula la vigencia del documento a la fecha ``hoy`` con las fechas que
    extrajo su dictamen y los límites de las reglas RCV que se le aplicaron:

      * Fecha de vencimiento declarada (RCV-01): vence ese día; entra en
        «próximo a vencer» dentro de la ventana de RCV-01 (30 días).
      * Caducidad por antigüedad (p. ej. RCV-02, 90 días desde la emisión):
        vence al cumplir el límite; no tiene ventana de «próximo a vencer».

    Si hay varias, prevalece la que vence antes. Sin fechas, devuelve None.
    """
    if dictamen is None:
        return None
    caducidades: list[tuple[date, str, int | None, str | None]] = []
    ventana = DIAS_PROXIMO_A_VENCER
    if dictamen.fecha_vencimiento_extraida:
        caducidades.append((dictamen.fecha_vencimiento_extraida, CRITERIO_VENCIMIENTO, None, "RCV-01"))
    for regla in dictamen.reglas_aplicadas or []:
        limite = regla.get("limite_dias")
        if limite is None:
            continue
        # Los dictámenes previos no guardaban el criterio: RCV-01 es la única
        # regla general por fecha de vencimiento del catálogo (DOC-05).
        criterio = regla.get("criterio") or (
            CRITERIO_VENCIMIENTO if regla.get("codigo_regla") == "RCV-01" else CRITERIO_ANTIGUEDAD
        )
        if criterio == CRITERIO_VENCIMIENTO:
            ventana = int(limite)
        elif dictamen.fecha_emision_extraida:
            caducidades.append((dictamen.fecha_emision_extraida + timedelta(days=int(limite)), CRITERIO_ANTIGUEDAD,
                                int(limite), regla.get("codigo_regla")))
    if not caducidades:
        return None
    fecha, criterio, limite, codigo = min(caducidades, key=lambda c: c[0])
    dias = (fecha - hoy).days
    if dias < 0:
        estado = VENCIDO
    elif criterio == CRITERIO_VENCIMIENTO and dias <= ventana:
        estado = PROXIMO_A_VENCER
    else:
        estado = VIGENTE
    return _Vigencia(estado, fecha, dias, criterio, limite, codigo)


def rango_severidad(severidad: str | None) -> int:
    valor = (severidad or "").upper()
    return ORDEN_SEVERIDAD.index(valor) if valor in ORDEN_SEVERIDAD else len(ORDEN_SEVERIDAD)


def _severidad_por_anticipacion(dias: int) -> str | None:
    """Severidad de la alerta de vencimiento según los umbrales (30, 15, 5 días)."""
    niveles = ["MEDIA", "MEDIA_ALTA", "ALTA"]
    severidad = None
    for i, umbral in enumerate(UMBRALES_ALERTA):
        if dias <= umbral:
            severidad = niveles[min(i, len(niveles) - 1)]
    return severidad


def evaluar(
    db: Session,
    expediente: Expediente,
    inventario: rules_client.InventarioObligatorio | None = None,
    hoy: date | None = None,
) -> EvaluacionExpediente:
    """Calcula el semáforo y las alertas del expediente sin modificar nada."""
    hoy = hoy or date.today()
    tipo_expediente = (expediente.tipo_expediente or "CORPORATIVO").upper()
    inventario = inventario or rules_client.obtener_documentos_obligatorios(tipo_expediente)
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
    dictamenes = ultimos_dictamenes(db, [d.id for d in vigentes.values()])

    # RIE-02: anexos que se vuelven exigibles porque su documento principal está presente.
    anexos_exigidos: dict[str, dict[str, str]] = {}
    for anexo in inventario.anexos:
        tipo = anexo["tipo_documento"]
        if anexo["documento_principal"] in vigentes and tipo not in requeridos and tipo not in anexos_exigidos:
            anexos_exigidos[tipo] = anexo

    estados: list[EstadoDocumento] = []
    vigencias: dict[str, _Vigencia] = {}
    for tipo, doc in sorted(vigentes.items()):
        dictamen = dictamenes.get(doc.id)
        vigencia = vigencia_actual(dictamen, hoy) if doc.estado_integridad != INTEGRIDAD_ALTERADO else None
        if doc.estado_integridad == INTEGRIDAD_ALTERADO:
            estado = NO_CONFORME
        elif dictamen is None:
            estado = SIN_DICTAMEN
        elif vigencia and vigencia.estado == VENCIDO:
            estado = NO_CONFORME   # RN-02: vencido, aunque se auditara (o ratificara) vigente
        else:
            estado = dictamen.estatus
        if vigencia:
            vigencias[doc.id] = vigencia
        estados.append(
            EstadoDocumento(
                documento_id=doc.id,
                tipo_documento=tipo,
                nombre_archivo_original=doc.nombre_archivo_original,
                obligatorio=tipo in requeridos or tipo in anexos_exigidos,
                estado=estado,
                dictamen_id=dictamen.id if dictamen else None,
                revisado_por_humano=bool(dictamen and dictamen.revisado_por_humano),
                estado_integridad=doc.estado_integridad or "INTEGRO",
                vigencia=vigencia.estado if vigencia else None,
                fecha_caducidad=vigencia.fecha_caducidad if vigencia else None,
                dias_para_vencer=vigencia.dias if vigencia else None,
                anexo_de=anexos_exigidos[tipo]["documento_principal"] if tipo in anexos_exigidos else None,
            )
        )

    obligatorios = [
        {"tipo_documento": tipo, **datos, "presente": tipo in vigentes, "documento_principal": None}
        for tipo, datos in sorted(requeridos.items())
    ] + [
        {"tipo_documento": tipo, "codigo_regla": a["codigo_regla"], "severidad": a["severidad"],
         "presente": tipo in vigentes, "documento_principal": a["documento_principal"]}
        for tipo, a in sorted(anexos_exigidos.items())
    ]
    faltantes = [o["tipo_documento"] for o in obligatorios if not o["presente"]]
    faltantes_criticos = [
        o["tipo_documento"] for o in obligatorios
        if not o["presente"] and not o["documento_principal"] and o["severidad"] == "CRITICA"
    ]
    anexos_faltantes = [
        {"tipo_documento": o["tipo_documento"], "documento_principal": o["documento_principal"],
         "codigo_regla": o["codigo_regla"], "severidad": o["severidad"]}
        for o in obligatorios if not o["presente"] and o["documento_principal"]
    ]
    faltantes_no_criticos = [
        t for t in faltantes if t not in faltantes_criticos and t not in {a["tipo_documento"] for a in anexos_faltantes}
    ]
    presentes = len(obligatorios) - len(faltantes)
    porcentaje = round(presentes / len(obligatorios) * 100, 1) if obligatorios else 100.0

    motivos: list[str] = []
    rechazados = [e for e in estados if e.estado == NO_CONFORME]
    pendientes = [
        e for e in estados
        if e.estado == EN_REVISION or (e.estado == SIN_DICTAMEN and e.obligatorio)
    ]
    proximos = [e for e in estados if e.estado != NO_CONFORME and e.vigencia == PROXIMO_A_VENCER]

    if faltantes_criticos:
        motivos.append(f"Faltan documentos obligatorios de severidad crítica: {', '.join(faltantes_criticos)} (RIE-01).")
    for a in anexos_faltantes:
        motivos.append(
            f"{a['documento_principal']} requiere su anexo {a['tipo_documento']}, que no está en el expediente "
            f"({a['codigo_regla']}, RIE-02)."
        )
    for e in rechazados:
        if e.estado_integridad == INTEGRIDAD_ALTERADO:
            causa = "alteración criptográfica (RIE-03)"
        elif e.vigencia == VENCIDO:
            causa = f"vencido desde el {e.fecha_caducidad.isoformat()} (RN-02)"
        elif e.dictamen_id and dictamenes[e.documento_id].origen == ORIGEN_NIVEL_1:
            causa = "archivo protegido con contraseña, no procesable (Nivel 1)"
        else:
            causa = "dictamen NO_CONFORME"
        motivos.append(f"{e.tipo_documento} ({e.nombre_archivo_original}): {causa}.")
    if faltantes_no_criticos:
        motivos.append(f"Faltan documentos obligatorios: {', '.join(faltantes_no_criticos)}.")
    for e in pendientes:
        causa = "sin auditar" if e.estado == SIN_DICTAMEN else "pendiente de ratificación humana (Nivel 5)"
        motivos.append(f"{e.tipo_documento} ({e.nombre_archivo_original}): {causa}.")
    for e in proximos:
        motivos.append(
            f"{e.tipo_documento} ({e.nombre_archivo_original}): vence el {e.fecha_caducidad.isoformat()}, "
            f"en {e.dias_para_vencer} días (RCV-01)."
        )

    if faltantes_criticos or rechazados or anexos_faltantes:
        estado_expediente = NO_CONFORME
    elif faltantes_no_criticos or pendientes or proximos:
        estado_expediente = EN_REVISION
    else:
        estado_expediente = CONFORME
        motivos.append("Todos los documentos obligatorios están presentes y sus dictámenes son conformes.")

    alertas = _alertas(obligatorios, anexos_faltantes, estados, dictamenes, vigencias, vigentes)

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
        tipo_expediente=tipo_expediente,
        anexos_faltantes=anexos_faltantes,
        alertas=alertas,
    )


def _alertas(
    obligatorios: list[dict[str, Any]],
    anexos_faltantes: list[dict[str, str]],
    estados: list[EstadoDocumento],
    dictamenes: dict[str, DictamenAuditoria],
    vigencias: dict[str, _Vigencia],
    vigentes: dict[str, Documento],
) -> list[Alerta]:
    """
    Traduce los hallazgos de la evaluación en alertas accionables: qué pasa,
    por qué y qué hacer para corregirlo (RF-18, RF-21, HU-15, HU-16).
    """
    alertas: list[Alerta] = []

    for o in obligatorios:
        if o["presente"] or o["documento_principal"]:
            continue
        nombre = etiqueta_documento(o["tipo_documento"])
        alertas.append(Alerta(
            codigo=ALERTA_DOCUMENTO_FALTANTE,
            severidad=o["severidad"] or "MEDIA",
            titulo=f"Falta: {nombre}",
            detalle=f"El catálogo de reglas exige este documento para el expediente ({o['codigo_regla']}).",
            recomendacion=(
                f"Solicitar al titular {nombre} y custodiarlo en el expediente. Mientras falte, el expediente "
                "no puede obtener estatus de conforme (RIE-01)."
            ),
            tipo_documento=o["tipo_documento"],
            regla=o["codigo_regla"],
        ))

    for a in anexos_faltantes:
        anexo = etiqueta_documento(a["tipo_documento"])
        principal = etiqueta_documento(a["documento_principal"])
        doc_principal = vigentes.get(a["documento_principal"])
        alertas.append(Alerta(
            codigo=ALERTA_ANEXO_FALTANTE,
            severidad=a["severidad"] or "ALTA",
            titulo=f"Anexo ausente: {anexo}",
            detalle=f"{principal} requiere este anexo; sin él, el documento principal queda invalidado (RIE-02).",
            recomendacion=(
                f"Custodiar en el expediente el documento «{anexo}» vinculado a {principal}"
                + (f" ({doc_principal.nombre_archivo_original})" if doc_principal else "")
                + " y verificar que corresponda a los anexos que ese documento referencia."
            ),
            tipo_documento=a["tipo_documento"],
            regla=a["codigo_regla"],
            documento_id=doc_principal.id if doc_principal else None,
        ))

    for e in estados:
        nombre = etiqueta_documento(e.tipo_documento)
        dictamen = dictamenes.get(e.documento_id)
        vigencia = vigencias.get(e.documento_id)

        if e.estado_integridad == INTEGRIDAD_ALTERADO:
            alertas.append(Alerta(
                codigo=ALERTA_INTEGRIDAD,
                severidad="CRITICA",
                titulo=f"Documento alterado: {nombre}",
                detalle=(
                    f"La huella SHA-256 de «{e.nombre_archivo_original}» ya no coincide con la registrada en la carga "
                    "(RIE-03). El documento está bloqueado."
                ),
                recomendacion=(
                    "Recargar el archivo original desde su fuente (sustituye al alterado) y revisar en la bitácora "
                    "quién tuvo acceso a la bóveda."
                ),
                tipo_documento=e.tipo_documento, regla="RIE-03", documento_id=e.documento_id,
            ))
            continue

        if vigencia and vigencia.estado == VENCIDO:
            if vigencia.criterio == CRITERIO_ANTIGUEDAD and vigencia.limite_dias is not None:
                recomendacion = (
                    f"Solicitar {nombre} con una emisión no mayor a {vigencia.limite_dias} días y custodiarlo: "
                    "sustituye automáticamente al archivo vencido."
                )
            else:
                recomendacion = (
                    f"Gestionar la renovación de {nombre} y custodiar la versión vigente: sustituye "
                    "automáticamente al archivo vencido."
                )
            alertas.append(Alerta(
                codigo=ALERTA_DOCUMENTO_VENCIDO,
                severidad="ALTA",
                titulo=f"Documento vencido: {nombre}",
                detalle=(
                    f"«{e.nombre_archivo_original}» venció el {vigencia.fecha_caducidad.isoformat()} "
                    f"(hace {abs(vigencia.dias)} días)."
                ),
                recomendacion=recomendacion,
                tipo_documento=e.tipo_documento,
                regla=vigencia.regla,
                documento_id=e.documento_id,
            ))
            continue

        if e.estado == NO_CONFORME and dictamen is not None:
            observacion = next((o for o in (dictamen.observaciones or []) if o), None)
            # Un elemento que el documento contradice de forma explícita (p. ej. una
            # opinión 32-D negativa, RSC-OPIN-SENT) trae su cita y la recomendación
            # de su regla: son más precisas que la observación general del modelo.
            incumplida = next(
                (r for r in dictamen.reglas_aplicadas or []
                 if r.get("resultado") == "NO_CUMPLE" and r.get("recomendacion")),
                None,
            )
            if incumplida:
                cita = f" Cita: «{incumplida['cita']}»." if incumplida.get("cita") else ""
                alertas.append(Alerta(
                    codigo=ALERTA_DICTAMEN_NO_CONFORME,
                    severidad="ALTA",
                    titulo=f"Dictamen no conforme: {nombre}",
                    detalle=f"{incumplida.get('detalle') or incumplida.get('nombre_regla')}{cita}",
                    recomendacion=incumplida["recomendacion"],
                    tipo_documento=e.tipo_documento, regla=incumplida.get("codigo_regla"),
                    documento_id=e.documento_id,
                ))
                continue
            if dictamen.origen == ORIGEN_NIVEL_1:
                recomendacion = (
                    "Solicitar al emisor una versión del documento sin contraseña de apertura y custodiarla: "
                    "sustituye a la protegida. Este dictamen no admite ratificación porque su contenido no pudo leerse."
                )
            elif dictamen.match_titular is False:
                recomendacion = (
                    "El RFC del documento no corresponde al titular del expediente: verificar que el documento "
                    "pertenezca a la empresa y custodiar el correcto."
                )
            else:
                recomendacion = (
                    "Revisar las observaciones del dictamen y custodiar una versión corregida del documento; si el "
                    "hallazgo es improcedente, ratificarlo con justificación desde el panel de auditoría (Nivel 5)."
                )
            alertas.append(Alerta(
                codigo=ALERTA_DICTAMEN_NO_CONFORME,
                severidad="ALTA",
                titulo=f"Dictamen no conforme: {nombre}",
                detalle=observacion or "El dictamen del documento es NO_CONFORME.",
                recomendacion=recomendacion,
                tipo_documento=e.tipo_documento, documento_id=e.documento_id,
            ))
            continue

        # Elementos que el catálogo exige al documento y el Nivel 4 no localizó
        # (RSC-01, RDS-02; RF-18: incumplimiento de una cláusula obligatoria).
        # Una ratificación humana los resuelve: el analista ya decidió.
        if dictamen is not None and not dictamen.revisado_por_humano:
            for regla in dictamen.reglas_aplicadas or []:
                if regla.get("resultado") not in CONTENIDO_PENDIENTE:
                    continue
                verificable = regla.get("resultado") == "NO_LOCALIZADO"
                alertas.append(Alerta(
                    codigo=ALERTA_CONTENIDO,
                    severidad=regla.get("severidad") or "MEDIA_ALTA",
                    titulo=f"{regla.get('nombre_regla') or regla.get('codigo_regla')}: "
                           f"{'no localizado' if verificable else 'no verificado'} en {nombre}",
                    detalle=regla.get("detalle") or "El elemento no se localizó en el texto del documento.",
                    recomendacion=regla.get("recomendacion")
                    or "Revisar el documento y, si el elemento falta, solicitar la versión completa al titular.",
                    tipo_documento=e.tipo_documento, regla=regla.get("codigo_regla"), documento_id=e.documento_id,
                ))

        if vigencia and vigencia.dias >= 0:
            severidad = _severidad_por_anticipacion(vigencia.dias)
            if severidad:
                alertas.append(Alerta(
                    codigo=ALERTA_PROXIMO_A_VENCER,
                    severidad=severidad,
                    titulo=f"Próximo a vencer: {nombre}",
                    detalle=(
                        f"«{e.nombre_archivo_original}» vence el {vigencia.fecha_caducidad.isoformat()} "
                        f"({vigencia.dias} días)."
                    ),
                    recomendacion=(
                        f"Iniciar la renovación de {nombre} antes del {vigencia.fecha_caducidad.isoformat()} para "
                        "que el expediente no pase a no conforme."
                    ),
                    tipo_documento=e.tipo_documento, regla="RCV-01", documento_id=e.documento_id,
                ))

        if e.estado == EN_REVISION:
            # El motivo que dio el motor explica por qué el caso espera al analista.
            observaciones_dictamen = dictamen.observaciones if dictamen else []
            motivo = next((o.split(":", 1)[1].strip() for o in observaciones_dictamen or []
                           if o.startswith("Dictamen EN_REVISION:")), None)
            if motivo:
                motivo = motivo[:1].upper() + motivo[1:]
            alertas.append(Alerta(
                codigo=ALERTA_REVISION_HUMANA,
                severidad="MEDIA",
                titulo=f"Pendiente de ratificación: {nombre}",
                detalle=motivo or "El motor no pudo resolver el dictamen de forma automática (confianza o vigencia).",
                recomendacion=(
                    "Un analista debe confirmar o corregir el dictamen con una justificación desde el panel de "
                    "auditoría (Nivel 5, RF-14)."
                ),
                tipo_documento=e.tipo_documento, documento_id=e.documento_id,
            ))
        elif e.estado == SIN_DICTAMEN and e.obligatorio:
            alertas.append(Alerta(
                codigo=ALERTA_SIN_AUDITAR,
                severidad="MEDIA",
                titulo=f"Sin auditar: {nombre}",
                detalle=f"«{e.nombre_archivo_original}» está custodiado pero aún no tiene dictamen.",
                recomendacion="Ejecutar la auditoría con IA del documento desde la Bóveda, o «Auditar pendientes» "
                              "en el expediente (Niveles 3 y 4).",
                tipo_documento=e.tipo_documento, documento_id=e.documento_id,
            ))

    orden = {c: i for i, c in enumerate([
        ALERTA_INTEGRIDAD, ALERTA_DOCUMENTO_FALTANTE, ALERTA_ANEXO_FALTANTE, ALERTA_DOCUMENTO_VENCIDO,
        ALERTA_DICTAMEN_NO_CONFORME, ALERTA_CONTENIDO, ALERTA_PROXIMO_A_VENCER, ALERTA_REVISION_HUMANA,
        ALERTA_SIN_AUDITAR,
    ])}
    return sorted(alertas, key=lambda a: (rango_severidad(a.severidad), orden.get(a.codigo, 99)))


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
    constancia en la bitácora (EVALUACION_REGLAS) con las alertas vigentes.
    No confirma la transacción.
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
            "tipo_expediente": evaluacion.tipo_expediente,
            "porcentaje_completitud": evaluacion.porcentaje_completitud,
            "faltantes": evaluacion.faltantes,
            "anexos_faltantes": evaluacion.anexos_faltantes,
            "motivos": evaluacion.motivos,
            "alertas": [{"codigo": a.codigo, "severidad": a.severidad, "titulo": a.titulo} for a in evaluacion.alertas],
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


class CacheInventarios:
    """Inventario obligatorio por tipo de expediente, consultado una sola vez por petición."""

    def __init__(self) -> None:
        self._por_tipo: dict[str, rules_client.InventarioObligatorio] = {}

    def para(self, expediente: Expediente) -> rules_client.InventarioObligatorio:
        tipo = (expediente.tipo_expediente or "CORPORATIVO").upper()
        if tipo not in self._por_tipo:
            self._por_tipo[tipo] = rules_client.obtener_documentos_obligatorios(tipo)
        return self._por_tipo[tipo]
