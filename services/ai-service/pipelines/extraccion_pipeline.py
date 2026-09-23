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

**Corte temprano del OCR.** El OCR cuesta varios segundos por página, y el
texto que excede ``MAX_CARACTERES_CONTEXTO`` se trunca antes de llegar al LLM.
Por eso, salvo que se pida el texto completo, el reconocimiento se detiene al
acumular ese volumen o tras ``MAX_PAGINAS_OCR`` páginas escaneadas. Las páginas
omitidas quedan registradas en la traza y en las observaciones.
"""
from concurrent.futures import ThreadPoolExecutor
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
    paginas_omitidas: list[int] = field(default_factory=list)

    def a_dict(self, incluir_paginas: bool = True) -> dict[str, Any]:
        datos: dict[str, Any] = {
            "texto_extraido": self.texto,
            "metodo_extraccion": self.metodo_extraccion,
            "confidence_score": round(self.confidence_score, 4),
            "total_paginas": self.total_paginas,
            "total_caracteres": self.total_caracteres,
            "paginas_procesadas_con_ocr": self.paginas_ocr,
            "paginas_omitidas_ocr": len(self.paginas_omitidas),
            "extraccion_parcial": bool(self.paginas_omitidas),
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
# Ancho mínimo, en píxeles, para que Tesseract lea con fiabilidad el texto de
# 8-10 pt de un recibo: por debajo, la imagen se amplía antes del OCR.
_ANCHO_MINIMO_OCR = 1800
# Proporción de píxeles negros tras Otsu a partir de la cual el corte global
# falló. Una página de texto queda entre 1 % y 10 % de tinta; una foto con
# sombra o flash deja manchas negras que superan el 30 %.
_MAX_TINTA_OTSU = 0.25


def preprocesar_imagen(imagen_bgr: np.ndarray) -> np.ndarray:
    """
    Acondiciona una página rasterizada para maximizar la exactitud de Tesseract.

    Pasos:
      1. Escala de grises: descarta información cromática que el OCR no usa.
      2. Ampliación de imágenes pequeñas (fotos de recibos, INE o escaneos a
         baja resolución) hasta ``_ANCHO_MINIMO_OCR`` px, con interpolación
         cúbica: Tesseract pierde exactitud con glifos de pocos píxeles.
      3. Filtro bilateral: suaviza el grano conservando los bordes de los glifos.
      4. Binarización de Otsu, que calcula el corte tinta/papel a partir del
         histograma de la página. Es la mejor opción para escaneos con
         iluminación pareja.
      5. Si Otsu deja más de ``_MAX_TINTA_OTSU`` de la página en negro, la
         iluminación es desigual (foto de un recibo con sombra): se repite con
         corrección de contraste CLAHE y umbral adaptativo gaussiano por
         vecindario, que corta tinta/papel según la luz local de cada zona.

    El camino adaptativo solo se activa cuando Otsu falla, porque sobre un
    escaneo limpio CLAHE amplifica el grano y reduce la exactitud (medido:
    98.0 % → 92.7 % en la constancia escaneada de prueba).
    """
    gris = cv2.cvtColor(imagen_bgr, cv2.COLOR_BGR2GRAY)

    alto, ancho = gris.shape
    if ancho < _ANCHO_MINIMO_OCR:
        factor = min(_ANCHO_MINIMO_OCR / ancho, 3.0)
        gris = cv2.resize(gris, (int(ancho * factor), int(alto * factor)), interpolation=cv2.INTER_CUBIC)

    suavizada = cv2.bilateralFilter(gris, d=5, sigmaColor=55, sigmaSpace=55)
    _, binaria = cv2.threshold(suavizada, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    if np.mean(binaria) < 127:
        binaria = cv2.bitwise_not(binaria)

    if float(np.mean(binaria == 0)) > _MAX_TINTA_OTSU:
        contrastada = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gris)
        suavizada = cv2.bilateralFilter(contrastada, d=5, sigmaColor=55, sigmaSpace=55)
        binaria = cv2.adaptiveThreshold(
            suavizada, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 41, 15
        )

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


def _rasterizar(pagina: "fitz.Page") -> np.ndarray:
    """Rasteriza una página PDF a ``OCR_DPI`` ppp y la entrega en BGR para OpenCV."""
    matriz = fitz.Matrix(settings.OCR_DPI / 72.0, settings.OCR_DPI / 72.0)
    pixmap = pagina.get_pixmap(matrix=matriz, colorspace=fitz.csRGB)
    imagen = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
    return cv2.cvtColor(imagen, cv2.COLOR_RGB2BGR)


def _ocr_en_paralelo(imagenes: list[np.ndarray]) -> list[tuple[str, float]]:
    """
    Reconoce varias páginas a la vez y devuelve los resultados en el mismo orden.

    Se usan hilos y no procesos: Tesseract corre como un proceso externo y
    OpenCV libera el GIL, así que los hilos solo esperan y el trabajo real se
    reparte entre los núcleos sin copiar las imágenes entre procesos.
    """
    if len(imagenes) <= 1 or settings.OCR_WORKERS <= 1:
        return [_ocr_sobre_imagen(img) for img in imagenes]
    with ThreadPoolExecutor(max_workers=min(settings.OCR_WORKERS, len(imagenes))) as pool:
        return list(pool.map(_ocr_sobre_imagen, imagenes))


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
    contenido: bytes,
    nombre_archivo: str = "documento",
    forzar_ocr: bool = False,
    texto_completo: bool = False,
) -> ResultadoExtraccion:
    """
    Punto de entrada del Nivel 3: recibe el binario y devuelve texto + confianza.

    :param forzar_ocr: omite la ruta vectorial y rasteriza todas las páginas.
                       Útil para auditar un PDF cuya capa de texto se sospecha
                       discordante respecto de lo que el documento muestra.
    :param texto_completo: desactiva el corte temprano del OCR y reconoce todas
                           las páginas, aunque el excedente no quepa en el
                           contexto del LLM.
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
    omitidas: list[int] = []

    if mime == "application/pdf":
        paginas, total_paginas = _procesar_pdf(contenido, forzar_ocr, texto_completo, omitidas, observaciones)
    else:
        paginas = _procesar_imagen(contenido, observaciones)
        total_paginas = 1

    return _consolidar(paginas, observaciones, total_paginas, omitidas)


def _procesar_pdf(
    contenido: bytes,
    forzar_ocr: bool,
    texto_completo: bool,
    omitidas: list[int],
    observaciones: list[str],
) -> tuple[list[ResultadoPagina], int]:
    paginas: list[ResultadoPagina] = []
    caracteres_acumulados = 0
    paginas_ocr = 0

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

        total_paginas = documento.page_count
        # Páginas escaneadas ya rasterizadas que esperan su turno de OCR.
        pendientes: list[tuple[int, np.ndarray]] = []

        def reconocer_tanda() -> None:
            """Reconoce en paralelo la tanda pendiente y acumula su texto."""
            nonlocal caracteres_acumulados, paginas_ocr
            for numero, (texto_ocr, confianza) in zip(
                [n for n, _ in pendientes], _ocr_en_paralelo([img for _, img in pendientes])
            ):
                paginas.append(
                    ResultadoPagina(
                        numero=numero,
                        metodo="OCR",
                        caracteres=len(texto_ocr),
                        confianza=confianza,
                        texto=texto_ocr,
                    )
                )
                caracteres_acumulados += len(texto_ocr)
                paginas_ocr += 1
            pendientes.clear()

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
                caracteres_acumulados += len(texto_vectorial)
                continue

            # Corte temprano: el texto ya cubre el contexto del LLM, o ya se
            # agotó el presupuesto de páginas escaneadas (contando la tanda
            # que está por reconocerse).
            if not texto_completo and (
                caracteres_acumulados >= settings.MAX_CARACTERES_CONTEXTO
                or paginas_ocr + len(pendientes) >= settings.MAX_PAGINAS_OCR
            ):
                omitidas.append(indice)
                continue

            # Ruta OCR: se rasteriza aquí, en el hilo principal, porque
            # PyMuPDF no es seguro entre hilos; el reconocimiento va en tandas.
            pendientes.append((indice, _rasterizar(pagina)))
            if len(pendientes) >= settings.OCR_WORKERS:
                reconocer_tanda()

        if pendientes:
            reconocer_tanda()

    # Las páginas OCR se agregan por tandas; se restituye el orden del documento.
    paginas.sort(key=lambda p: p.numero)

    if omitidas:
        motivo = (
            f"el texto reconocido ya cubre el contexto del modelo ({settings.MAX_CARACTERES_CONTEXTO} caracteres)"
            if caracteres_acumulados >= settings.MAX_CARACTERES_CONTEXTO
            else f"se alcanzó el máximo de {settings.MAX_PAGINAS_OCR} páginas escaneadas por documento"
        )
        observaciones.append(
            f"Corte temprano del OCR: se omitieron {len(omitidas)} de {total_paginas} páginas "
            f"(de la {omitidas[0]} a la {omitidas[-1]}) porque {motivo}."
        )
    if not paginas:
        observaciones.append("El PDF no contiene páginas legibles.")
    return paginas, total_paginas


def _procesar_imagen(contenido: bytes, observaciones: list[str]) -> list[ResultadoPagina]:
    with Image.open(io.BytesIO(contenido)) as imagen_pil:
        imagen_rgb = np.array(imagen_pil.convert("RGB"))
    texto, confianza = _ocr_sobre_imagen(cv2.cvtColor(imagen_rgb, cv2.COLOR_RGB2BGR))
    observaciones.append("Documento entregado como imagen: resuelto íntegramente por OCR.")
    return [
        ResultadoPagina(numero=1, metodo="OCR", caracteres=len(texto), confianza=confianza, texto=texto)
    ]


def _consolidar(
    paginas: list[ResultadoPagina],
    observaciones: list[str],
    total_paginas: int,
    omitidas: list[int],
) -> ResultadoExtraccion:
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
        total_paginas=total_paginas,
        total_caracteres=len(texto_total),
        paginas_ocr=paginas_ocr,
        requiere_revision_humana=requiere_hitl,
        observaciones=observaciones,
        detalle_paginas=paginas,
        paginas_omitidas=omitidas,
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
