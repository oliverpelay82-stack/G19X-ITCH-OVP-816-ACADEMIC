"""
Contenido activo del archivo PDF (PRD §21.6, PLUS-18; ISO/IEC 27001 A.8.7):
JavaScript, acciones automáticas o de ejecución, archivos incrustados, medios
enriquecidos y formularios XFA, en cualquier tipo de documento.

Se calcula una vez, en la carga (o en el barrido programado para los
documentos custodiados antes de P6), a partir del binario ya verificado, y se
guarda en ``documentos.senales_pdf``. No rechaza el archivo: se custodia igual,
porque es la evidencia de lo que se entregó.

Las señales de edición (PLUS-16: fechas de modificación, guardados
incrementales y programa editor) se retiraron el 02/10/2026: ningún documento
de la especificación las pide, y un documento de prueba hecho con un
procesador de texto quedaba en revisión por «posible edición». Las que ya
estén guardadas en ``senales_pdf["edicion"]`` se ignoran.

``revision(tipo, senales)`` traduce lo guardado a los motivos que llevan la
auditoría a revisión humana; el ai-service los recibe en el documento.
"""
from __future__ import annotations

import io
import logging
import re
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

logger = logging.getLogger(__name__)

# 2: solo contenido activo (sin las señales de edición de la versión 1).
VERSION = 2

ACTIVO_JAVASCRIPT = "JAVASCRIPT"
ACTIVO_ACCION = "ACCION_AUTOMATICA"
ACTIVO_EJECUCION = "EJECUCION_DE_PROGRAMA"
ACTIVO_ADJUNTO = "ARCHIVO_INCRUSTADO"
ACTIVO_MEDIOS = "MEDIOS_ENRIQUECIDOS"
ACTIVO_XFA = "FORMULARIO_XFA"

_NOMBRE_ACTIVO = {
    ACTIVO_JAVASCRIPT: "JavaScript",
    ACTIVO_ACCION: "una acción que se ejecuta sola al abrir o recorrer el archivo",
    ACTIVO_EJECUCION: "una orden para ejecutar otro programa",
    ACTIVO_ADJUNTO: "archivos incrustados",
    ACTIVO_MEDIOS: "medios enriquecidos (Flash o video incrustado)",
    ACTIVO_XFA: "un formulario XFA dinámico",
}


def _resolver(valor: Any) -> Any:
    return valor.get_object() if isinstance(valor, IndirectObject) else valor


def _acciones(accion: Any, encontradas: set[str], profundidad: int = 0) -> None:
    """Clasifica una acción PDF (y sus encadenadas en /Next)."""
    accion = _resolver(accion)
    if not isinstance(accion, DictionaryObject) or profundidad > 8:
        return
    tipo = accion.get("/S")
    if tipo == "/JavaScript" or "/JS" in accion:
        encontradas.add(ACTIVO_JAVASCRIPT)
    elif tipo in ("/Launch", "/ImportData"):
        encontradas.add(ACTIVO_EJECUCION)
    siguiente = _resolver(accion.get("/Next"))
    for item in (siguiente if isinstance(siguiente, ArrayObject) else [siguiente]):
        _acciones(item, encontradas, profundidad + 1)


def _contenido_activo(lector: PdfReader, contenido: bytes) -> set[str]:
    encontradas: set[str] = set()
    raiz = _resolver(lector.trailer.get("/Root"))
    if isinstance(raiz, DictionaryObject):
        nombres = _resolver(raiz.get("/Names"))
        if isinstance(nombres, DictionaryObject):
            if "/JavaScript" in nombres:
                encontradas.add(ACTIVO_JAVASCRIPT)
            if "/EmbeddedFiles" in nombres:
                encontradas.add(ACTIVO_ADJUNTO)
        apertura = _resolver(raiz.get("/OpenAction"))
        if isinstance(apertura, DictionaryObject):
            encontradas.add(ACTIVO_ACCION)
            _acciones(apertura, encontradas)
        if "/AA" in raiz:
            encontradas.add(ACTIVO_ACCION)
        formulario = _resolver(raiz.get("/AcroForm"))
        if isinstance(formulario, DictionaryObject) and "/XFA" in formulario:
            encontradas.add(ACTIVO_XFA)
    for pagina in lector.pages:
        if "/AA" in pagina:
            encontradas.add(ACTIVO_ACCION)
        for anotacion in _resolver(pagina.get("/Annots")) or []:
            anotacion = _resolver(anotacion)
            if not isinstance(anotacion, DictionaryObject):
                continue
            subtipo = anotacion.get("/Subtype")
            if subtipo == "/FileAttachment":
                encontradas.add(ACTIVO_ADJUNTO)
            elif subtipo in ("/RichMedia", "/Movie", "/Screen"):
                encontradas.add(ACTIVO_MEDIOS)
            if "/AA" in anotacion:
                encontradas.add(ACTIVO_ACCION)
            _acciones(anotacion.get("/A"), encontradas)
    # Respaldo sobre los bytes sin comprimir (objetos fuera del árbol que se recorrió).
    if re.search(rb"/S\s*/JavaScript|/JS\s*[(<\[]", contenido):
        encontradas.add(ACTIVO_JAVASCRIPT)
    if re.search(rb"/S\s*/Launch", contenido):
        encontradas.add(ACTIVO_EJECUCION)
    return encontradas


def analizar(contenido: bytes) -> dict[str, Any] | None:
    """Contenido activo del PDF; None si no es un PDF o no pudo analizarse (no se afirma lo que no se comprobó)."""
    if not contenido.startswith(b"%PDF"):
        return None
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted and not lector.decrypt(""):
            return None  # protegido con contraseña: lo atiende PLUS-02
        activo = _contenido_activo(lector, contenido)
    except Exception as exc:  # noqa: BLE001 — un PDF dañado lo reporta el Nivel 3 al auditarlo
        logger.warning("No se pudieron analizar las señales del PDF: %s", exc)
        return None
    return {"version": VERSION, "contenido_activo": sorted(activo)}


def descripcion_activo(codigos: list[str]) -> str:
    return ", ".join(_NOMBRE_ACTIVO.get(c, c) for c in codigos)


def revision(tipo_documento: str, senales: dict | None) -> list[str]:
    """
    Motivos, en lenguaje llano, por los que la auditoría de este documento debe
    quedar en revisión humana. Vacío si el archivo no tiene señales que pesen.
    """
    if not senales:
        return []
    motivos: list[str] = []
    if senales.get("contenido_activo"):
        motivos.append(f"El PDF contiene {descripcion_activo(senales['contenido_activo'])}: "
                       "se recomienda pedir una versión sin contenido activo.")
    return motivos
