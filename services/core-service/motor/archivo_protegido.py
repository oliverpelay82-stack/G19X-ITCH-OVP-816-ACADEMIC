"""
PLUS-02 — PDF protegido con contraseña detectado en el Nivel 1 (DOC-05, Tabla 1).

«Archivo protegido con contraseña: el Nivel 1 detecta que el archivo no puede
abrirse ni procesarse. Rojo: archivo protegido, no procesable.» El archivo se
custodia igual (es la evidencia de lo que se entregó) y recibe un dictamen
NO_CONFORME de origen NIVEL_1 que no admite ratificación: se corrige cargando
una versión sin contraseña, que lo sustituye como versión vigente de su tipo.
"""
from __future__ import annotations

import io
import logging

from pypdf import PasswordType, PdfReader
from sqlalchemy.orm import Session

from models.bitacora import EVENTO_ARCHIVO_PROTEGIDO
from models.dictamen import ORIGEN_NIVEL_1, DictamenAuditoria
from models.documento import Documento
from motor import bitacora, cumplimiento

logger = logging.getLogger(__name__)

MOTIVO = (
    "Archivo protegido, no procesable: el PDF exige una contraseña de apertura y su contenido no puede "
    "leerse (DOC-05, Nivel 1)."
)
ADVERTENCIA = (
    "El PDF está protegido con contraseña: quedó custodiado como NO_CONFORME. Solicite al emisor una "
    "versión sin contraseña de apertura y cárguela para sustituirlo."
)


def pdf_protegido(contenido: bytes) -> bool:
    """
    True solo si el PDF exige contraseña de apertura. Un PDF cifrado con
    contraseña de propietario (restricciones de impresión o copia) se abre con
    la contraseña vacía y es procesable: no cuenta. Si la estructura no puede
    analizarse, no se afirma una protección que no se comprobó; el Nivel 3 lo
    reportará al auditarlo.
    """
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if not lector.is_encrypted:
            return False
        return lector.decrypt("") == PasswordType.NOT_DECRYPTED
    except Exception as exc:  # noqa: BLE001 — cualquier falla de pypdf equivale a «no comprobado»
        logger.warning("No se pudo comprobar si el PDF está protegido: %s", exc)
        return False


def registrar(db: Session, documento: Documento, usuario: str, ip_origen: str | None) -> DictamenAuditoria:
    """Dictamen NO_CONFORME de origen NIVEL_1 y evento ARCHIVO_PROTEGIDO, en la transacción de la carga."""
    dictamen = DictamenAuditoria(
        documento_id=documento.id,
        expediente_id=documento.expediente_id,
        estatus=cumplimiento.NO_CONFORME,
        estatus_preliminar=cumplimiento.NO_CONFORME,
        origen=ORIGEN_NIVEL_1,
        nivel_confianza=None,
        requiere_revision_humana=False,
        reglas_aplicadas=[{"codigo_regla": "NIVEL_1", "resultado": "NO_CUMPLE", "detalle": MOTIVO}],
        vigencia_resultado=None,
        observaciones=[MOTIVO, "Se requiere una versión del documento sin contraseña de apertura."],
        hash_sha256=documento.hash_sha256,
    )
    db.add(dictamen)
    db.flush()
    bitacora.registrar(
        db,
        EVENTO_ARCHIVO_PROTEGIDO,
        expediente_id=documento.expediente_id,
        documento_id=documento.id,
        dictamen_id=dictamen.id,
        usuario=usuario,
        ip_origen=ip_origen,
        detalle={"motivo": MOTIVO, "hash_sha256": documento.hash_sha256,
                 "nombre_archivo_original": documento.nombre_archivo_original},
    )
    return dictamen
