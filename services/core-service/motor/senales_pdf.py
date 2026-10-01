"""
Señales del archivo PDF (PRD §21.6): edición posterior a la emisión (PLUS-16)
y contenido activo (PLUS-18).

Se calculan una vez, en la carga (o en el barrido programado para los
documentos custodiados antes de P6), a partir del binario ya verificado, y se
guardan en ``documentos.senales_pdf``. Ninguna señal rechaza el archivo: se
custodia igual, porque es la evidencia de lo que se entregó.

  * **Edición (PLUS-16):** fecha de modificación posterior a la de creación,
    guardados incrementales (sin contar los de una firma digital ni la
    linealización) y un programa editor o procesador de texto conocido. Solo
    pesan en los documentos que el SAT emite electrónicamente
    (``TIPOS_EMITIDOS_SAT``): en un escaneo o un acta, procesar el archivo es
    lo normal y las señales solo se informan.
  * **Contenido activo (PLUS-18, ISO/IEC 27001 A.8.7):** JavaScript, acciones
    automáticas o de ejecución, archivos incrustados, medios enriquecidos y
    formularios XFA, en cualquier tipo.

``revision(tipo, senales)`` traduce lo guardado a los motivos que llevan la
auditoría a revisión humana; el ai-service los recibe en el documento.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import datetime, timedelta
from typing import Any

from pypdf import PdfReader
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

logger = logging.getLogger(__name__)

VERSION = 1

# Documentos que el SAT emite electrónicamente: un retoque es la falsificación
# más común en la revisión de proveedores.
TIPOS_EMITIDOS_SAT = frozenset({"CSF_SAT", "OPINION_CUMPLIMIENTO", "CEDULA_RFC"})

# Una modificación dentro de este margen es la del propio generador al cerrar el archivo.
MARGEN_MODIFICACION = timedelta(minutes=10)

# Editores de PDF y procesadores de texto (en minúsculas, por subcadena del productor o creador).
EDITORES = (
    "ilovepdf", "smallpdf", "pdfescape", "sejda", "foxit phantompdf", "foxit pdf editor", "nitro pro",
    "nitro pdf", "pdf-xchange editor", "pdfelement", "wondershare", "soda pdf", "sodapdf", "pdffiller",
    "dochub", "pdf candy", "adobe acrobat pro", "acrobat pro dc", "adobe acrobat standard", "microsoft word",
    "microsoft® word", "libreoffice", "openoffice", "canva",
)

EDICION_MODIFICADO = "MODIFICADO_DESPUES_DE_EMISION"
EDICION_INCREMENTAL = "GUARDADO_INCREMENTAL"
EDICION_EDITOR = "EDITOR_CONOCIDO"

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


def _texto(valor: Any) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    return texto[:200] or None


def _fecha(lector: PdfReader, atributo: str) -> datetime | None:
    try:
        return getattr(lector.metadata, atributo, None) if lector.metadata else None
    except Exception:  # noqa: BLE001 — una fecha mal formada no es una señal
        return None


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
    """Señales del PDF; None si no es un PDF o no pudo analizarse (no se afirma lo que no se comprobó)."""
    if not contenido.startswith(b"%PDF"):
        return None
    try:
        lector = PdfReader(io.BytesIO(contenido))
        if lector.is_encrypted and not lector.decrypt(""):
            return None  # protegido con contraseña: lo atiende PLUS-02
        metadatos = lector.metadata or {}
        productor = _texto(metadatos.get("/Producer"))
        creador = _texto(metadatos.get("/Creator"))
        creado = _fecha(lector, "creation_date")
        modificado = _fecha(lector, "modification_date")
        linealizado = b"/Linearized" in contenido[:2048]
        firmas = len(re.findall(rb"/ByteRange\s*\[", contenido))
        incrementales = max(contenido.count(b"startxref") - 1 - (1 if linealizado else 0), 0)
        activo = _contenido_activo(lector, contenido)
    except Exception as exc:  # noqa: BLE001 — un PDF dañado lo reporta el Nivel 3 al auditarlo
        logger.warning("No se pudieron analizar las señales del PDF: %s", exc)
        return None

    edicion: list[dict[str, str]] = []
    if creado and modificado:
        try:
            diferencia = modificado - creado
        except TypeError:  # una fecha con zona horaria y otra sin ella
            diferencia = modificado.replace(tzinfo=None) - creado.replace(tzinfo=None)
        if diferencia > MARGEN_MODIFICACION:
            edicion.append({"codigo": EDICION_MODIFICADO,
                            "detalle": f"se modificó el {modificado:%d/%m/%Y %H:%M}, después de crearse el "
                                       f"{creado:%d/%m/%Y %H:%M}"})
    if incrementales and not firmas:
        edicion.append({"codigo": EDICION_INCREMENTAL,
                        "detalle": f"tiene {incrementales} guardado{'s' if incrementales > 1 else ''} posterior"
                                   f"{'es' if incrementales > 1 else ''} a su generación"})
    programa = next((p for p in (productor, creador) if p and any(e in p.lower() for e in EDITORES)), None)
    if programa:
        edicion.append({"codigo": EDICION_EDITOR, "detalle": f"lo generó o guardó «{programa}»"})

    return {
        "version": VERSION,
        "productor": productor,
        "creador": creador,
        "creado": creado.isoformat() if creado else None,
        "modificado": modificado.isoformat() if modificado else None,
        "guardados_incrementales": incrementales,
        "firmas": firmas,
        "linealizado": linealizado,
        "edicion": edicion,
        "contenido_activo": sorted(activo),
    }


def codigos_edicion(tipo_documento: str, senales: dict | None) -> list[str]:
    """Señales de edición que pesan para este tipo (solo los documentos que emite el SAT)."""
    if not senales or tipo_documento not in TIPOS_EMITIDOS_SAT:
        return []
    return [e["codigo"] for e in senales.get("edicion") or []]


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
    if tipo_documento in TIPOS_EMITIDOS_SAT and senales.get("edicion"):
        detalles = "; ".join(e["detalle"] for e in senales["edicion"])
        motivos.append(f"Posible edición del archivo: el SAT emite este documento electrónicamente y el PDF {detalles}.")
    if senales.get("contenido_activo"):
        motivos.append(f"El PDF contiene {descripcion_activo(senales['contenido_activo'])}: "
                       "se recomienda pedir una versión sin contenido activo.")
    return motivos
