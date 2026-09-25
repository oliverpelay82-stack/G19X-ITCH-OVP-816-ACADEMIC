"""
Regla RIE-03 — Integridad criptográfica del archivo (DOC-05).

Toda lectura de un binario de la bóveda recalcula su SHA-256 y lo compara con
la huella registrada en la carga. Si no coinciden (o el binario desapareció),
el documento se marca ALTERADO, recibe un dictamen NO_CONFORME de origen
RIE-03, el incidente queda en la bitácora y el expediente se reevalúa. A partir
de ese momento el documento queda bloqueado: no se sirve ni se analiza.
"""
from __future__ import annotations

import hashlib
import os

from sqlalchemy.orm import Session

from config.boveda import ruta_en_boveda
from models.bitacora import EVENTO_ALERTA_INTEGRIDAD
from models.dictamen import ORIGEN_RIE_03, DictamenAuditoria
from models.documento import Documento
from models.expediente import Expediente
from motor import bitacora, cumplimiento

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
        motivo = "El binario del documento no se encuentra en la bóveda (posible eliminación no autorizada)."
        _registrar_violacion(db, documento, None, motivo, usuario, ip_origen)
        raise DocumentoAlteradoError(documento, f"[RIE-03] {motivo}")

    with open(ruta, "rb") as archivo:
        contenido = archivo.read()
    hash_actual = hashlib.sha256(contenido).hexdigest()
    if hash_actual != documento.hash_sha256:
        motivo = (
            f"La huella SHA-256 del binario ({hash_actual[:16]}…) no coincide con la registrada en la carga "
            f"({documento.hash_sha256[:16]}…): alteración no autorizada del archivo."
        )
        _registrar_violacion(db, documento, hash_actual, motivo, usuario, ip_origen)
        raise DocumentoAlteradoError(documento, f"[RIE-03] {motivo}")
    return contenido
