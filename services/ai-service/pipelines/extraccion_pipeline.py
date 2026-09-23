"""
Nivel 3 del pipeline de validación (DOC-05) — Extracción de texto híbrida.

La estrategia es de dos rutas con selección automática por página:

  1. **Ruta vectorial.** La mayoría de los documentos fiscales mexicanos
     (Constancia de Situación Fiscal, Opinión de Cumplimiento) se descargan del
     portal del SAT como PDF generados por software, con una capa de texto
     incrustada. PyMuPDF la lee directamente: es exacta, instantánea y no
     introduce ruido.

  2. **Ruta OCR con preprocesamiento.** Cuando una página rinde menos caracteres
     que ``UMBRAL_CARACTERES_PAGINA`` se asume que es un escaneo o una fotografía
     y se rasteriza a ``OCR_DPI`` ppp para pasarla por Tesseract. Antes del
     reconocimiento se aplica una cadena de limpieza con OpenCV —escala de
     grises, reducción de ruido y binarización de Otsu— porque Tesseract opera
     sobre imágenes binarias y su exactitud cae de forma abrupta con fondos
     sombreados, sellos o iluminación desigual.

El resultado incluye un *confidence score* homogéneo en el rango [0.0, 1.0] que
es el insumo que decide, más adelante, si el expediente puede resolverse en
automático o debe escalar al Nivel 5 (gobernanza humana).
"""
from dataclasses import dataclass, field
from typing import Any
import io
import re

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image

from config import settings

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# Firmas binarias aceptadas, idénticas a las del Nivel 1 en core-service.
FIRMAS_MAGICAS: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}


class FormatoNoSoportadoError(ValueError):
    """El binario recibido no es un PDF, JPEG o PNG válido."""


class MotorOcrNoDisponibleError(RuntimeError):
    """Tesseract no está instalado o no es ejecutable en esta máquina."""


@dataclass
class ResultadoPagina:
    """Traza por página: permite auditar qué ruta resolvió cada hoja."""
    numero: int
    metodo: str            # 'VECTORIAL' | 'OCR'
    caracteres: int
    confianza: float
    texto: str = ""


@dataclass
class ResultadoExtraccion:
    """Salida completa del Nivel 3."""
    texto: str
    metodo_extraccion: str          # 'VECTORIAL' | 'OCR' | 'HIBRIDO'
    confidence_score: float
    total_paginas: int
    total_caracteres: int
    paginas_ocr: int
    requiere_revision_humana: bool
    observaciones: list[str] = field(default_factory=list)
    detalle_paginas: list[ResultadoPagina] = field(default_factory=list)

    def a_dict(self, incluir_paginas: bool = True) -> dict[str, Any]:
        datos: dict[str, Any] = {
            "texto_extraido": self.texto,
            "metodo_extraccion": self.metodo_extraccion,
            "confidence_score": round(self.confidence_score, 4),
            "total_paginas": self.total_paginas,
            "total_caracteres": self.total_caracteres,
            "paginas_procesadas_con_ocr": self.paginas_ocr,
            "requiere_revision_humana": self.requiere_revision_humana,
            "umbral_confianza_hitl": settings.UMBRAL_CONFIANZA_HITL,
            "observaciones": self.observaciones,
        }
        if incluir_paginas:
            datos["detalle_paginas"] = [
                {
                    "pagina": p.numero,
                    "metodo": p.metodo,
                    "caracteres": p.caracteres,
                    "confianza": round(p.confianza, 4),
                }
                for p in self.detalle_paginas
            ]
        return datos


# ── Preprocesamiento de imagen ──────────────────────────────────────
def preprocesar_imagen(imagen_bgr: np.ndarray) -> np.ndarray:
    """
    Acondiciona una página rasterizada para maximizar la exactitud de Tesseract.

    Pasos: conversión a escala de grises (descarta información cromática que el
    OCR no utiliza), filtro bilateral (suaviza el grano del escaneo conservando
    los bordes de los glifos) y umbralización de Otsu, que calcula de forma
    automática el punto de corte óptimo entre tinta y papel a partir del
    histograma de la propia página, sin necesidad de calibrarlo por documento.
    """
    gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)
    suavizada = cv2.bilateralFilter(gris, d=5, sigmaColor=55, sigmaSpace=55)
    _, binaria = cv2.threshold(suavizada, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    # Tesseract espera texto oscuro sobre fondo claro. Si Otsu dejó la página
    # mayoritariamente oscura (documento con fondo invertido), se corrige.
    if np.mean(binaria) < 127:
        binaria = cv2.bitwise_not(binaria)
    return binaria


def _ocr_sobre_imagen(imagen_bgr: np.ndarray) -> tuple[str, float]:
    """Ejecuta Tesseract sobre una imagen ya preprocesada y promedia su confianza."""
    binaria = preprocesar_imagen(imagen_bgr)
    try:
        datos = pytesseract.image_to_data(
            binaria,
            lang=settings.OCR_LANG,
            config="--oem 3 --psm 3",
            output_type=pytesseract.Output.DICT,
        )
    except pytesseract.TesseractNotFoundError as exc:
        raise MotorOcrNoDisponibleError(
            f"Tesseract no es ejecutable en la ruta configurada "
            f"({settings.TESSERACT_CMD}). Instale Tesseract OCR o defina TESSERACT_CMD."
        ) from exc

    # Tesseract sitúa cada palabra en un bloque, un párrafo y un renglón. Esa
    # estructura se reconstruye en lugar de concatenar las palabras seguidas:
    # sin saltos de línea, el título del documento queda pegado al encabezado
    # del apartado siguiente y se pierde la señal que permite reconocer de qué
    # documento se trata. En una constancia fiscal, "CONSTANCIA DE SITUACION
    # FISCAL" seguido de "DATOS DE IDENTIFICACION DEL CONTRIBUYENTE" en un solo
    # renglón induce a confundirla con una identificación oficial.
    renglones: dict[tuple[int, int, int], list[str]] = {}
    confianzas: list[float] = []
    for indice, texto in enumerate(datos["text"]):
        texto = (texto or "").strip()
        if not texto:
            continue
        clave = (
            datos["block_num"][indice],
            datos["par_num"][indice],
            datos["line_num"][indice],
        )
        renglones.setdefault(clave, []).append(texto)
        try:
            valor = float(datos["conf"][indice])
        except (TypeError, ValueError):
            continue
        # Tesseract marca con -1 los bloques sin estimación de confianza.
        if valor >= 0:
            confianzas.append(valor / 100.0)

    # Las claves vienen en orden de lectura, pero se ordenan de forma explícita
    # para no depender de que el diccionario preserve el orden de inserción.
    lineas = [" ".join(renglones[clave]) for clave in sorted(renglones)]
    texto_pagina = "\n".join(lineas)
    confianza = sum(confianzas) / len(confianzas) if confianzas else 0.0
    return texto_pagina, confianza


# ── Heurística de calidad de la capa vectorial ──────────────────────
def _confianza_vectorial(texto: str) -> float:
    """
    Estima la calidad de un texto leído de la capa vectorial.

    No hay una confianza nativa que reportar —la lectura es exacta por
    construcción—, pero sí puede degradarse cuando el PDF trae fuentes con
    codificación rota, lo que produce cadenas con exceso de caracteres no
    imprimibles. La métrica penaliza esa proporción sobre una base alta.
    """
    if not texto.strip():
        return 0.0
    utiles = len(re.findall(r"[0-9A-Za-zÁÉÍÓÚáéíóúÑñÜü.,:;/()%$#\-\s]", texto))
    proporcion = utiles / len(texto)
    return round(min(0.99, 0.80 + 0.19 * proporcion), 4)


def detectar_mime(contenido: bytes) -> str:
    """Identifica el formato por firma binaria, sin confiar en la extensión."""
    for mime, firmas in FIRMAS_MAGICAS.items():
        if any(contenido.startswith(firma) for firma in firmas):
            return mime
    raise FormatoNoSoportadoError(
        "El archivo no corresponde a un PDF, JPEG o PNG válido (firma binaria desconocida)."
    )


# ── Orquestador del Nivel 3 ─────────────────────────────────────────
def extraer_texto(
    contenido: bytes, nombre_archivo: str = "documento", forzar_ocr: bool = False
) -> ResultadoExtraccion:
    """
    Punto de entrada del Nivel 3: recibe el binario y devuelve texto + confianza.

    :param forzar_ocr: omite la ruta vectorial y rasteriza todas las páginas.
                       Útil para auditar un PDF cuya capa de texto se sospecha
                       discordante respecto de lo que el documento muestra.
    """
    if not contenido:
        raise FormatoNoSoportadoError("El archivo recibido está vacío.")
    if len(contenido) > settings.MAX_FILE_SIZE_BYTES:
        limite_mb = settings.MAX_FILE_SIZE_BYTES // (1024 * 1024)
        raise FormatoNoSoportadoError(
            f"El archivo supera el límite de {limite_mb} MB establecido en el Nivel 1."
        )

    mime = detectar_mime(contenido)
    observaciones: list[str] = []

    if mime == "application/pdf":
        paginas = _procesar_pdf(contenido, forzar_ocr, observaciones)
    else:
        paginas = _procesar_imagen(contenido, observaciones)

    return _consolidar(paginas, observaciones)


def _procesar_pdf(contenido: bytes, forzar_ocr: bool, observaciones: list[str]) -> list[ResultadoPagina]:
    paginas: list[ResultadoPagina] = []

    # Un archivo puede traer la cabecera %PDF- correcta y aun así tener el
    # cuerpo truncado o el árbol de objetos destruido; PyMuPDF solo lo detecta
    # al abrir el flujo, y eso es un dato del documento, no un fallo del motor.
    try:
        documento = fitz.open(stream=contenido, filetype="pdf")
    except (fitz.FileDataError, RuntimeError) as exc:
        raise FormatoNoSoportadoError(
            f"El PDF tiene la firma correcta pero su estructura interna está "
            f"corrupta o incompleta: {exc}"
        ) from exc

    with documento:
        if documento.is_encrypted and not documento.authenticate(""):
            raise FormatoNoSoportadoError(
                "El PDF está protegido con contraseña; no es posible extraer su contenido."
            )

        for indice, pagina in enumerate(documento, start=1):
            texto_vectorial = "" if forzar_ocr else pagina.get_text("text").strip()

            if len(texto_vectorial) >= settings.UMBRAL_CARACTERES_PAGINA:
                paginas.append(
                    ResultadoPagina(
                        numero=indice,
                        metodo="VECTORIAL",
                        caracteres=len(texto_vectorial),
                        confianza=_confianza_vectorial(texto_vectorial),
                        texto=texto_vectorial,
                    )
                )
                continue

            # Ruta OCR: se rasteriza la página a la resolución configurada.
            matriz = fitz.Matrix(settings.OCR_DPI / 72.0, settings.OCR_DPI / 72.0)
            pixmap = pagina.get_pixmap(matrix=matriz, colorspace=fitz.csRGB)
            imagen = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
                pixmap.height, pixmap.width, 3
            )
            texto_ocr, confianza = _ocr_sobre_imagen(cv2.cvtColor(imagen, cv2.COLOR_RGB2BGR))

            paginas.append(
                ResultadoPagina(
                    numero=indice,
                    metodo="OCR",
                    caracteres=len(texto_ocr),
                    confianza=confianza,
                    texto=texto_ocr,
                )
            )

    if not paginas:
        observaciones.append("El PDF no contiene páginas legibles.")
    return paginas


def _procesar_imagen(contenido: bytes, observaciones: list[str]) -> list[ResultadoPagina]:
    with Image.open(io.BytesIO(contenido)) as imagen_pil:
        imagen_rgb = np.array(imagen_pil.convert("RGB"))
    texto, confianza = _ocr_sobre_imagen(cv2.cvtColor(imagen_rgb, cv2.COLOR_RGB2BGR))
    observaciones.append("Documento entregado como imagen: resuelto íntegramente por OCR.")
    return [
        ResultadoPagina(numero=1, metodo="OCR", caracteres=len(texto), confianza=confianza, texto=texto)
    ]


def _consolidar(paginas: list[ResultadoPagina], observaciones: list[str]) -> ResultadoExtraccion:
    texto_total = "\n\n".join(p.texto for p in paginas if p.texto).strip()
    paginas_ocr = sum(1 for p in paginas if p.metodo == "OCR")
    paginas_vectoriales = len(paginas) - paginas_ocr

    if paginas_ocr and paginas_vectoriales:
        metodo = "HIBRIDO"
    elif paginas_ocr:
        metodo = "OCR"
    else:
        metodo = "VECTORIAL"

    # La confianza global se pondera por caracteres: una portada escaneada de
    # veinte palabras no debe arrastrar la confianza de un anexo vectorial extenso.
    peso_total = sum(max(p.caracteres, 1) for p in paginas) or 1
    confianza = (
        sum(p.confianza * max(p.caracteres, 1) for p in paginas) / peso_total if paginas else 0.0
    )

    if not texto_total:
        confianza = 0.0
        observaciones.append(
            "No se recuperó texto alguno: el documento puede estar en blanco, "
            "severamente degradado o ser una imagen sin contenido textual."
        )

    requiere_hitl = confianza < settings.UMBRAL_CONFIANZA_HITL
    if requiere_hitl:
        observaciones.append(
            f"Confianza de extracción ({confianza:.2f}) por debajo del umbral "
            f"{settings.UMBRAL_CONFIANZA_HITL:.2f}: se escala al Nivel 5 (revisión humana)."
        )

    return ResultadoExtraccion(
        texto=texto_total,
        metodo_extraccion=metodo,
        confidence_score=confianza,
        total_paginas=len(paginas),
        total_caracteres=len(texto_total),
        paginas_ocr=paginas_ocr,
        requiere_revision_humana=requiere_hitl,
        observaciones=observaciones,
        detalle_paginas=paginas,
    )


def diagnostico_ocr() -> dict[str, Any]:
    """Reporta la disponibilidad de Tesseract para el health check."""
    try:
        version = str(pytesseract.get_tesseract_version())
        idiomas = pytesseract.get_languages(config="")
        return {
            "disponible": True,
            "version": version,
            "idiomas_disponibles": idiomas,
            "idioma_configurado": settings.OCR_LANG,
            "tessdata_prefix": settings.TESSDATA_PREFIX,
            "dpi_rasterizado": settings.OCR_DPI,
        }
    except Exception as exc:
        return {
            "disponible": False,
            "detalle": f"Tesseract no disponible en {settings.TESSERACT_CMD}: {exc}",
            "idioma_configurado": settings.OCR_LANG,
        }
