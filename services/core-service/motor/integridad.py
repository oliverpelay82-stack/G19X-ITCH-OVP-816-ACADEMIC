"""
Regla RIE-03 — Integridad criptográfica del archivo (DOC-05).

Toda lectura de un binario de la bóveda recalcula su SHA-256 y lo compara con
la huella registrada en la carga. Si no coinciden (o el binario desapareció),
el documento se marca ALTERADO, recibe un dictamen NO_CONFORME de origen
RIE-03, el incidente queda en la bitácora y el expediente se reevalúa. A partir
de ese momento el documento queda bloqueado: no se sirve ni se analiza.

P5 (PLUS-14): además de al leerse, toda la bóveda se verifica en el barrido
programado (``barrer``), para que un archivo alterado que nadie abre también
se detecte; cada barrido deja su constancia sellada en la bitácora.
"""
from __future__ import annotations

import hashlib
import os
import time
from dataclasses import dataclass

from sqlalchemy.orm import Session

from config.boveda import ruta_en_boveda
from models.bitacora import EVENTO_ALERTA_INTEGRIDAD, EVENTO_VERIFICACION_INTEGRIDAD
from models.dictamen import ORIGEN_RIE_03, DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora, cumplimiento, senales_pdf

INTEGRO = "INTEGRO"
ALTERADO = "ALTERADO"


class DocumentoAlteradoError(Exception):
    """La huella del binario no coincide con la registrada (RIE-03)."""

    def __init__(self, documento: Documento, mensaje: str):
        super().__init__(mensaje)
        self.documento = documento


def ruta_binario(documento: Documento) -> str:
    """
    Ruta del binario en la bóveda actual. Se reconstruye con la convención de
    nombrado y no se toma de ``ruta_almacenamiento``, que guarda la ruta
    absoluta del entorno donde se cargó (local o contenedor).
    """
    ruta = ruta_en_boveda(documento.hash_sha256, documento.nombre_archivo_original)
    if not os.path.isfile(ruta) and documento.ruta_almacenamiento and os.path.isfile(documento.ruta_almacenamiento):
        return documento.ruta_almacenamiento
    return ruta


def huella_actual(documento: Documento) -> str | None:
    """SHA-256 del binario tal como está hoy en la bóveda (None si ya no está). Solo lee: no registra nada."""
    ruta = ruta_binario(documento)
    if not os.path.isfile(ruta):
        return None
    huella = hashlib.sha256()
    with open(ruta, "rb") as archivo:
        for bloque in iter(lambda: archivo.read(1 << 20), b""):
            huella.update(bloque)
    return huella.hexdigest()


MOTIVO_SIN_BINARIO = "El binario del documento no se encuentra en la bóveda (posible eliminación no autorizada)."


def _motivo_discrepancia(hash_actual: str, hash_registrado: str) -> str:
    return (
        f"La huella SHA-256 del binario ({hash_actual[:16]}…) no coincide con la registrada en la carga "
        f"({hash_registrado[:16]}…): alteración no autorizada del archivo."
    )


def _registrar_violacion(
    db: Session, documento: Documento, hash_actual: str | None, motivo: str, usuario: str, ip_origen: str | None
) -> None:
    documento.estado_integridad = ALTERADO
    reglas = [{"codigo_regla": "RIE-03", "resultado": "NO_CUMPLE", "detalle": motivo}]
    dictamen = DictamenAuditoria(
        documento_id=documento.id,
        expediente_id=documento.expediente_id,
        estatus=cumplimiento.NO_CONFORME,
        estatus_preliminar=cumplimiento.NO_CONFORME,
        origen=ORIGEN_RIE_03,
        nivel_confianza=None,
        requiere_revision_humana=False,
        reglas_aplicadas=reglas,
        vigencia_resultado=None,
        observaciones=[motivo, "Documento bloqueado: se requiere recargar el archivo original."],
        hash_sha256=documento.hash_sha256,
    )
    db.add(dictamen)
    db.flush()
    bitacora.registrar(
        db,
        EVENTO_ALERTA_INTEGRIDAD,
        expediente_id=documento.expediente_id,
        documento_id=documento.id,
        dictamen_id=dictamen.id,
        usuario=usuario,
        ip_origen=ip_origen,
        detalle={
            "regla": "RIE-03",
            "motivo": motivo,
            "hash_registrado": documento.hash_sha256,
            "hash_actual": hash_actual,
        },
    )
    expediente = db.query(Expediente).filter(Expediente.id == documento.expediente_id).first()
    if expediente:
        cumplimiento.reevaluar(db, expediente, causa="ALERTA_INTEGRIDAD", usuario=usuario, ip_origen=ip_origen)
    db.commit()


def leer_verificado(
    db: Session, documento: Documento, usuario: str = bitacora.USUARIO_SISTEMA, ip_origen: str | None = None
) -> bytes:
    """
    Devuelve el binario solo si su huella coincide con la registrada.
    Ante una discrepancia registra el incidente y lanza ``DocumentoAlteradoError``.
    """
    if documento.estado_integridad == ALTERADO:
        raise DocumentoAlteradoError(
            documento,
            f"[RIE-03] El documento '{documento.id}' está bloqueado: se detectó una alteración de su "
            "binario en una verificación anterior.",
        )

    ruta = ruta_binario(documento)
    if not os.path.isfile(ruta):
        _registrar_violacion(db, documento, None, MOTIVO_SIN_BINARIO, usuario, ip_origen)
        raise DocumentoAlteradoError(documento, f"[RIE-03] {MOTIVO_SIN_BINARIO}")

    with open(ruta, "rb") as archivo:
        contenido = archivo.read()
    hash_actual = hashlib.sha256(contenido).hexdigest()
    if hash_actual != documento.hash_sha256:
        motivo = _motivo_discrepancia(hash_actual, documento.hash_sha256)
        _registrar_violacion(db, documento, hash_actual, motivo, usuario, ip_origen)
        raise DocumentoAlteradoError(documento, f"[RIE-03] {motivo}")
    return contenido


# ── P5 (PLUS-14): barrido programado de integridad ─────────────────────


@dataclass
class ResultadoBarrido:
    revisados: int
    alterados: int
    duracion_ms: int


def _calcular_senales(documento: Documento) -> int:
    """
    P6 (PLUS-16, PLUS-18): señales del PDF de un documento custodiado antes de
    P6. Se leen del binario cuya huella acaba de comprobarse; un PDF que no
    puede analizarse queda marcado para no releerlo en cada barrido.
    """
    try:
        with open(documento.ruta_almacenamiento, "rb") as f:
            calculadas = senales_pdf.analizar(f.read())
    except OSError:
        return 0
    documento.senales_pdf = calculadas or {"version": senales_pdf.VERSION, "no_analizable": True}
    return 1


def barrer(db: Session) -> ResultadoBarrido:
    """
    Recalcula la huella de todos los documentos íntegros de la bóveda. Una
    discrepancia o un binario ausente se registra igual que en una lectura
    (dictamen RIE-03, ALERTA_INTEGRIDAD y reevaluación del expediente), con la
    nota de que lo detectó el barrido. Al final sella la constancia
    VERIFICACION_INTEGRIDAD. Solo lee los binarios: no los sirve ni llama a la IA.
    """
    inicio = time.perf_counter()
    revisados = alterados = senales_calculadas = 0
    ids = [i for (i,) in db.query(Documento.id).filter(Documento.estado_integridad == INTEGRO).all()]
    for documento_id in ids:
        documento = db.get(Documento, documento_id)
        if documento is None or documento.estado_integridad != INTEGRO:
            continue  # otra lectura lo marcó mientras avanzaba el barrido
        revisados += 1
        hash_actual = huella_actual(documento)
        if hash_actual == documento.hash_sha256:
            if documento.senales_pdf is None and documento.mime_type == "application/pdf":
                senales_calculadas += _calcular_senales(documento)
            continue
        motivo = MOTIVO_SIN_BINARIO if hash_actual is None else _motivo_discrepancia(hash_actual, documento.hash_sha256)
        _registrar_violacion(
            db, documento, hash_actual, f"{motivo} Detectado en el barrido programado de integridad.",
            bitacora.USUARIO_SISTEMA, None,
        )
        alterados += 1
    duracion_ms = round((time.perf_counter() - inicio) * 1000)
    bitacora.registrar(
        db,
        EVENTO_VERIFICACION_INTEGRIDAD,
        detalle={"origen": "BARRIDO_PROGRAMADO", "documentos_revisados": revisados,
                 "alterados": alterados, "duracion_ms": duracion_ms,
                 **({"senales_calculadas": senales_calculadas} if senales_calculadas else {})},
    )
    db.commit()
    return ResultadoBarrido(revisados, alterados, duracion_ms)
