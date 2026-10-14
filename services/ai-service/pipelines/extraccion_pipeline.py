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
from concurrent.futures import FIRST_COMPLETED, Future, wait
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any
import heapq
import io
import itertools
import re
import threading

import cv2
import fitz  # PyMuPDF
import numpy as np
import pytesseract
from PIL import Image, UnidentifiedImageError

from config import settings
from pipelines import sellos

pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD

# ── Pool de OCR con prioridad (RNF-02) ──────────────────────────────
PRIMER_PLANO = 0   # auditoría, chat y visor: alguien espera la respuesta
FONDO = 1          # lectura anticipada y lectura completa del chat


class Turno:
    """
    Prioridad de las páginas de una lectura. Es mutable: si una auditoría pide
    un documento que se está leyendo de fondo, ``promover`` sube sus páginas
    pendientes a primer plano sin repetir el OCR.
    """

    __slots__ = ("prioridad",)

    def __init__(self, prioridad: int = PRIMER_PLANO):
        self.prioridad = prioridad


_TURNO_PRIMER_PLANO = Turno(PRIMER_PLANO)
_turno_actual: ContextVar[Turno] = ContextVar("turno_ocr", default=_TURNO_PRIMER_PLANO)


@contextmanager
def en_turno(turno: Turno):
    """Las páginas que se envíen al pool dentro del bloque llevan la prioridad de ``turno``."""
    token = _turno_actual.set(turno)
    try:
        yield turno
    finally:
        _turno_actual.reset(token)


class _PoolPrioritario:
    """
    Pool único de OCR para todo el proceso, con OCR_WORKERS hilos: el total de
    reconocimientos simultáneos queda acotado al procesador (con un pool por
    petición, tres auditorías lanzaban 3 × OCR_WORKERS Tesseract y la memoria
    crecía con cada una). Cada hilo toma la página de mayor prioridad y, entre
    iguales, la más antigua: lo que espera una persona pasa antes que la
    lectura anticipada, que solo usa el procesador libre.
    """

    def __init__(self, hilos: int):
        self._cola: list[list[Any]] = []
        self._orden = itertools.count()
        self._condicion = threading.Condition()
        self._cerrado = False
        for n in range(hilos):
            threading.Thread(target=self._trabajar, name=f"ocr_{n}", daemon=True).start()

    def submit(self, funcion, *args) -> Future:
        futuro: Future = Future()
        turno = _turno_actual.get()
        with self._condicion:
            if self._cerrado:
                raise RuntimeError("El pool de OCR está cerrado.")
            heapq.heappush(self._cola, [turno.prioridad, next(self._orden), turno, futuro, funcion, args])
            self._condicion.notify()
        return futuro

    def map(self, funcion, elementos) -> list[Any]:
        futuros = [self.submit(funcion, e) for e in elementos]
        return [f.result() for f in futuros]

    def reordenar(self) -> None:
        """Recalcula el orden de la cola tras promover un turno."""
        with self._condicion:
            for entrada in self._cola:
                entrada[0] = entrada[2].prioridad
            heapq.heapify(self._cola)

    def shutdown(self) -> None:
        with self._condicion:
            self._cerrado = True
            for *_, futuro, _f, _a in self._cola:
                futuro.cancel()
            self._cola.clear()
            self._condicion.notify_all()

    def _trabajar(self) -> None:
        while True:
            with self._condicion:
                while not self._cola and not self._cerrado:
                    self._condicion.wait()
                if self._cerrado:
                    return
                *_, futuro, funcion, args = heapq.heappop(self._cola)
            if not futuro.set_running_or_notify_cancel():
                continue
            try:
                futuro.set_result(funcion(*args))
            except BaseException as exc:  # noqa: BLE001 - se entrega al que espera el resultado
                futuro.set_exception(exc)


_POOL_OCR = _PoolPrioritario(settings.OCR_WORKERS)


def turno_actual() -> Turno:
    return _turno_actual.get()


def promover(turno: Turno) -> None:
    """Pasa a primer plano las páginas pendientes de una lectura de fondo."""
    if turno.prioridad != PRIMER_PLANO:
        turno.prioridad = PRIMER_PLANO
        _POOL_OCR.reordenar()


def cerrar() -> None:
    """Apagado del servicio: descarta los reconocimientos en cola sin esperarlos."""
    _POOL_OCR.shutdown()

# Firmas binarias aceptadas, idénticas a las del Nivel 1 en core-service.
FIRMAS_MAGICAS: dict[str, list[bytes]] = {
    "application/pdf": [b"%PDF-"],
    "image/jpeg": [b"\xff\xd8\xff"],
    "image/png": [b"\x89PNG\r\n\x1a\n"],
}


class FormatoNoSoportadoError(ValueError):
    """El binario recibido no es un PDF, JPEG o PNG válido."""


class TiempoOcrExcedidoError(FormatoNoSoportadoError):
    """Una página excedió OCR_TIMEOUT_PAGINA_SEGUNDOS: el archivo no se puede leer (400)."""


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
    # Palabras del OCR con su recuadro, de la misma lectura que produjo `texto`
    # (vacío en páginas vectoriales, cuyas palabras da PyMuPDF al vuelo).
    palabras: list[list[Any]] = field(default_factory=list)
    inicio: int = 0        # posición de la página dentro del texto consolidado
    # Siempre vacío desde que se retiró la lectura de sellos en tinta de color
    # (PRD §21.8); se conserva por el contrato de la API y la columna de SQLite.
    sellos: list[dict[str, Any]] = field(default_factory=list)


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
    sello_digital_sat: bool = False      # el texto incluye el Sello Digital SAT (DOC-08)

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
            "sello_digital_sat": self.sello_digital_sat,
            "paginas_con_sello": [p.numero for p in self.detalle_paginas if p.sellos],
        }
        if incluir_paginas:
            datos["detalle_paginas"] = [
                {
                    "pagina": p.numero,
                    "metodo": p.metodo,
                    "caracteres": p.caracteres,
                    "confianza": round(p.confianza, 4),
                    "inicio": p.inicio,
                    "sellos": p.sellos,
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


def _normalizar_iluminacion(gris: np.ndarray) -> np.ndarray:
    """
    Divide la página entre su fondo estimado para emparejar la iluminación.

    Un escaneo con iluminación desigual (bordes más oscuros que el centro) hace
    que el corte global de Otsu pinte de negro las esquinas y borre el texto que
    cae en ellas, sin llegar a la proporción de tinta que activa el camino
    adaptativo (medido: 22.8 % de tinta en una página cuyo encabezado se perdió).
    El fondo es de baja frecuencia: se estima con un cierre morfológico, que
    borra el texto, sobre la página reducida a 1/8 y se amplía de vuelta, así el
    paso cuesta milisegundos a 300 ppp. Sobre papel parejo el cociente es ≈ 1 y
    la página no cambia.
    """
    alto, ancho = gris.shape
    if min(alto, ancho) < 64:
        return gris
    reducida = cv2.resize(gris, (max(1, ancho // 8), max(1, alto // 8)), interpolation=cv2.INTER_AREA)
    k = max(7, (min(reducida.shape) // 20) | 1)
    fondo = cv2.morphologyEx(reducida, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (k, k)))
    fondo = cv2.GaussianBlur(fondo, (0, 0), k / 3)
    fondo = cv2.resize(fondo, (ancho, alto), interpolation=cv2.INTER_LINEAR)
    return cv2.divide(gris, fondo, scale=255)


def preprocesar_imagen(imagen: np.ndarray) -> np.ndarray:
    """
    Acondiciona una página rasterizada para maximizar la exactitud de Tesseract.

    Acepta la página ya en escala de grises (2D, como la entrega ``_rasterizar``)
    o en BGR (3 canales, como llegan las fotos JPEG/PNG).

    Pasos:
      1. Escala de grises: descarta información cromática que el OCR no usa.
         Después se empareja la iluminación (``_normalizar_iluminacion``): sin
         ese paso, los bordes oscuros de un escaneo desigual se binarizaban en
         negro y se perdía el texto de las esquinas.
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
    gris = imagen if imagen.ndim == 2 else cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = _normalizar_iluminacion(gris)

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


def _tesseract(binaria: np.ndarray, psm: int = 3) -> dict[str, list[Any]]:
    try:
        return pytesseract.image_to_data(
            binaria,
            lang=settings.OCR_LANG,
            config=f"--oem 3 --psm {psm}",
            output_type=pytesseract.Output.DICT,
            timeout=settings.OCR_TIMEOUT_PAGINA_SEGUNDOS,
        )
    except RuntimeError as exc:
        # pytesseract mata el proceso al vencer el tiempo y lo informa así.
        if "timeout" not in str(exc).lower():
            raise
        raise TiempoOcrExcedidoError(
            f"Una página tardó más de {settings.OCR_TIMEOUT_PAGINA_SEGUNDOS:g} s en el reconocimiento de texto: "
            "el archivo puede estar dañado o ser demasiado complejo para leerlo."
        ) from exc
    except pytesseract.TesseractNotFoundError as exc:
        raise MotorOcrNoDisponibleError(
            f"Tesseract no es ejecutable en la ruta configurada "
            f"({settings.TESSERACT_CMD}). Instale Tesseract OCR o defina TESSERACT_CMD."
        ) from exc


def _palabras(datos: dict[str, list[Any]], ancho: int, alto: int, desplazamiento=(0, 0, 1, 1)) -> list[list[Any]]:
    """
    Palabras de una lectura de Tesseract: ``[x0, y0, x1, y1, texto, renglón,
    confianza]``, con el recuadro normalizado a la página. ``desplazamiento``
    (x0, y0, ancho, alto de un recorte, normalizados) ubica en la página las
    palabras leídas en un recorte.
    """
    ox, oy, ow, oh = desplazamiento
    palabras = []
    for i, texto in enumerate(datos["text"]):
        texto = (texto or "").strip()
        if not texto:
            continue
        clave = "-".join(str(datos[k][i]) for k in ("block_num", "par_num", "line_num"))
        try:
            confianza = float(datos["conf"][i]) / 100.0
        except (TypeError, ValueError):
            confianza = -1.0
        x, y = datos["left"][i], datos["top"][i]
        x1, y1 = x + datos["width"][i], y + datos["height"][i]
        palabras.append([
            ox + ow * x / ancho, oy + oh * y / alto, ox + ow * x1 / ancho, oy + oh * y1 / alto,
            texto, clave, confianza,
        ])
    return palabras


def _confianza(palabras: list[list[Any]]) -> float:
    # Tesseract marca con -1 los bloques sin estimación de confianza.
    valores = [p[6] for p in palabras if p[6] >= 0]
    return sum(valores) / len(valores) if valores else 0.0


def _texto_por_bloques(palabras: list[list[Any]]) -> str:
    """
    Texto en el orden de Tesseract: bloque, párrafo y renglón. Sin saltos de
    línea, el título del documento queda pegado al encabezado del apartado
    siguiente y se pierde la señal que permite reconocer de qué documento se
    trata (una constancia fiscal leída en un solo renglón se confunde con una
    identificación oficial).
    """
    renglones: dict[tuple[int, ...], list[str]] = {}
    for p in palabras:
        renglones.setdefault(tuple(int(n) for n in p[5].split("-")), []).append(p[4])
    return "\n".join(" ".join(renglones[clave]) for clave in sorted(renglones))


def _ocr_sobre_imagen(imagen: np.ndarray) -> tuple[str, float, list[list[Any]], list[dict[str, Any]]]:
    """
    Preprocesa la imagen (gris o BGR), ejecuta Tesseract y devuelve el texto,
    su confianza promedio, las palabras con su recuadro normalizado a [0, 1]
    (``[x0, y0, x1, y1, texto, renglón]``) y la lista de sellos de la página,
    siempre vacía desde que se retiró la detección de sellos en tinta de color
    (se conserva por la columna ``sellos`` de la persistencia). Texto y
    palabras salen de la misma lectura: lo que analiza el Nivel 4 y lo que
    resalta el visor coinciden.
    """
    binaria = preprocesar_imagen(imagen)
    palabras = _palabras(_tesseract(binaria), binaria.shape[1], binaria.shape[0])
    return _texto_por_bloques(palabras), _confianza(palabras), [p[:6] for p in palabras], []


def reconocer_pagina(imagen: np.ndarray) -> tuple[str, float, list[list[Any]], list[dict[str, Any]]]:
    """
    Texto, confianza y palabras con recuadro de una página que la extracción no
    leyó (corte temprano): los pide el visor de evidencia. Es la misma función
    de OCR que la extracción, por el pool compartido, así que el resultado es
    idéntico y la lectura completa puede reutilizarlo.
    """
    return _POOL_OCR.submit(_ocr_sobre_imagen, imagen).result()


# Versión del Nivel 3. Forma parte de la llave de la persistencia: si cambia el
# preprocesamiento o la configuración del OCR, los documentos se vuelven a leer
# en lugar de servir un texto de otra lectura (el visor y el dictamen verían
# documentos distintos). Súbase al modificar cualquier paso de la extracción.
# 3.3: normalización de la iluminación antes de la binarización (_normalizar_iluminacion).
VERSION_PIPELINE = "3.3"


@lru_cache(maxsize=1)
def version_lectura() -> str:
    """Huella de todo lo que determina el texto: pipeline, Tesseract, idiomas y resolución."""
    try:
        tesseract = str(pytesseract.get_tesseract_version())
    except Exception:  # noqa: BLE001 - sin Tesseract la versión simplemente no incluye el dato
        tesseract = "no-disponible"
    # «sin-sellos» se conserva tal cual al retirar la lectura de sellos en tinta de
    # color (que estaba apagada): el texto no cambia, así que las extracciones
    # guardadas y la versión de lectura de los dictámenes siguen siendo válidas.
    return f"n3-{VERSION_PIPELINE}|tesseract-{tesseract}|{settings.OCR_LANG}|{settings.OCR_DPI}dpi|sin-sellos"


def _rasterizar(pagina: "fitz.Page") -> np.ndarray:
    """
    Rasteriza una página PDF a ``OCR_DPI`` ppp en escala de grises (8 MB por
    hoja carta a 300 ppp), que al OCR le basta: la diferencia media frente a
    convertir después con OpenCV es de 0.03 niveles por píxel. Una página que a
    esa resolución excedería OCR_MAX_MEGAPIXELES_PAGINA se rasteriza a menos ppp,
    con su misma proporción; las de tamaño normal no cambian.
    """
    escala = settings.OCR_DPI / 72.0
    pixeles = pagina.rect.width * pagina.rect.height * escala * escala
    tope = settings.OCR_MAX_MEGAPIXELES_PAGINA * 1_000_000
    if tope > 0 and pixeles > tope:
        escala *= (tope / pixeles) ** 0.5
    matriz = fitz.Matrix(escala, escala)
    pixmap = pagina.get_pixmap(matrix=matriz, colorspace=fitz.csGRAY)
    return np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width)


def _ocr_en_paralelo(imagenes: list[np.ndarray]) -> list[tuple[str, float, list[list[Any]], list[dict[str, Any]]]]:
    """
    Reconoce varias páginas a la vez y devuelve los resultados en el mismo orden.

    Se usan hilos y no procesos: Tesseract corre como un proceso externo y
    OpenCV libera el GIL, así que los hilos solo esperan y el trabajo real se
    reparte entre los núcleos sin copiar las imágenes entre procesos. El pool
    es el compartido del proceso (``_POOL_OCR``).
    """
    return _POOL_OCR.map(_ocr_sobre_imagen, imagenes)


# Lectura completa en flujo continuo: páginas rasterizadas que pueden esperar su
# OCR por cada hilo del pool. Con 2, cada hilo tiene siempre la siguiente
# página lista al terminar la suya, y la memoria queda acotada (≈ 8 MB por hoja
# a 300 ppp: 16 páginas en vuelo con 8 hilos).
_EN_VUELO_POR_TRABAJADOR = 2


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
    forzar_ocr: bool = False,
    texto_completo: bool = False,
    paginas_conocidas: dict[int, tuple[str, float, list[list[Any]]]] | None = None,
) -> ResultadoExtraccion:
    """
    Punto de entrada del Nivel 3: recibe el binario y devuelve texto + confianza.

    :param forzar_ocr: omite la ruta vectorial y rasteriza todas las páginas.
                       Útil para auditar un PDF cuya capa de texto se sospecha
                       discordante respecto de lo que el documento muestra.
    :param texto_completo: desactiva el corte temprano del OCR y reconoce todas
                           las páginas, aunque el excedente no quepa en el
                           contexto del LLM.
    :param paginas_conocidas: páginas escaneadas ya reconocidas por esta misma
                           versión del Nivel 3 (``persistencia_texto.paginas_reconocidas``):
                           se reutilizan en lugar de repetir su OCR.
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
        paginas, total_paginas = _procesar_pdf(
            contenido, forzar_ocr, texto_completo, omitidas, observaciones, paginas_conocidas or {}
        )
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
    paginas_conocidas: dict[int, tuple[str, float, list[list[Any]]]] | None = None,
) -> tuple[list[ResultadoPagina], int]:
    paginas_conocidas = paginas_conocidas or {}
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
        # Lectura parcial: páginas escaneadas ya rasterizadas que esperan su tanda
        # de OCR (el corte temprano se decide con el texto de cada tanda).
        pendientes: list[tuple[int, np.ndarray]] = []
        # Lectura completa: páginas ya enviadas al pool que aún no se recogen.
        en_vuelo: dict[int, Future] = {}
        tope_en_vuelo = _EN_VUELO_POR_TRABAJADOR * max(1, settings.OCR_WORKERS)

        def agregar_ocr(numero: int, resultado: tuple[str, float, list[list[Any]], list[dict[str, Any]]]) -> None:
            nonlocal caracteres_acumulados, paginas_ocr
            texto_ocr, confianza, palabras, sellos_pagina = resultado
            paginas.append(ResultadoPagina(
                numero=numero, metodo="OCR", caracteres=len(texto_ocr), confianza=confianza,
                texto=texto_ocr, palabras=palabras, sellos=sellos_pagina,
            ))
            caracteres_acumulados += len(texto_ocr)
            paginas_ocr += 1

        def reconocer_tanda() -> None:
            """Reconoce en paralelo la tanda pendiente y acumula su texto."""
            for (numero, _), resultado in zip(pendientes, _ocr_en_paralelo([img for _, img in pendientes])):
                agregar_ocr(numero, resultado)
            pendientes.clear()

        def recoger_terminadas() -> None:
            """Espera a que termine al menos una página en vuelo y recoge todas las terminadas."""
            terminadas, _ = wait(en_vuelo.values(), return_when=FIRST_COMPLETED)
            for numero in [n for n, f in en_vuelo.items() if f in terminadas]:
                agregar_ocr(numero, en_vuelo.pop(numero).result())

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

            # Página ya reconocida por esta versión del Nivel 3: se reutiliza.
            if indice in paginas_conocidas:
                agregar_ocr(indice, paginas_conocidas[indice])
                continue

            # Ruta OCR: se rasteriza aquí, en el hilo principal, porque PyMuPDF
            # no es seguro entre hilos.
            if texto_completo:
                # Flujo continuo (RNF-02): la página entra al pool en cuanto se
                # rasteriza y cada proceso toma la siguiente al terminar la suya,
                # sin esperar a la más lenta de una tanda. El texto de cada página
                # es el mismo que por tandas: misma función y mismos parámetros.
                try:
                    if len(en_vuelo) >= tope_en_vuelo:
                        recoger_terminadas()
                    en_vuelo[indice] = _POOL_OCR.submit(_ocr_sobre_imagen, _rasterizar(pagina))
                except BaseException:
                    for futuro in en_vuelo.values():
                        futuro.cancel()
                    raise
                continue
            pendientes.append((indice, _rasterizar(pagina)))
            if len(pendientes) >= settings.OCR_WORKERS:
                reconocer_tanda()

        if pendientes:
            reconocer_tanda()
        try:
            while en_vuelo:
                recoger_terminadas()
        finally:
            for futuro in en_vuelo.values():
                futuro.cancel()

    # Las páginas OCR se agregan al terminar; se restituye el orden del documento.
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


def abrir_imagen(contenido: bytes) -> Image.Image:
    """
    Imagen JPEG o PNG del documento, ya decodificada (``load``). Como en el PDF,
    una imagen con la firma correcta puede venir truncada o dañada, y PIL solo
    lo descubre al decodificarla: es un dato del documento, no un fallo del
    motor (400, no un error interno). También se rechaza la que excede el límite
    de píxeles de PIL (bomba de descompresión), que en memoria pesaría varios GB.
    La usan la extracción y el visor; se cierra con ``with``. Una imagen de más de
    OCR_MAX_MEGAPIXELES_PAGINA se reduce con su misma proporción (un JPEG ya se
    decodifica reducido, con ``draft``).
    """
    try:
        imagen = Image.open(io.BytesIO(contenido))
        tope = settings.OCR_MAX_MEGAPIXELES_PAGINA * 1_000_000
        factor = (tope / (imagen.width * imagen.height)) ** 0.5 if tope > 0 and imagen.width * imagen.height > tope else 1
        if factor < 1:
            imagen.draft(imagen.mode, (int(imagen.width * factor), int(imagen.height * factor)))
        imagen.load()
        if factor < 1 and imagen.width * imagen.height > tope:
            factor = (tope / (imagen.width * imagen.height)) ** 0.5
            imagen = imagen.resize((max(1, int(imagen.width * factor)), max(1, int(imagen.height * factor))),
                                   Image.LANCZOS)
        return imagen
    except Image.DecompressionBombError as exc:
        raise FormatoNoSoportadoError(f"La imagen excede el tamaño máximo que admite el OCR: {exc}") from exc
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise FormatoNoSoportadoError(
            f"La imagen tiene la firma correcta pero está truncada o dañada: {exc}"
        ) from exc


def _procesar_imagen(contenido: bytes, observaciones: list[str]) -> list[ResultadoPagina]:
    with abrir_imagen(contenido) as imagen_pil:
        imagen_rgb = np.array(imagen_pil.convert("RGB"))
    # También por el pool compartido, para que cuente dentro del tope de OCR_WORKERS.
    texto, confianza, palabras, sellos_pagina = _POOL_OCR.submit(
        _ocr_sobre_imagen, cv2.cvtColor(imagen_rgb, cv2.COLOR_RGB2BGR)
    ).result()
    observaciones.append("Documento entregado como imagen: resuelto íntegramente por OCR.")
    return [
        ResultadoPagina(
            numero=1, metodo="OCR", caracteres=len(texto), confianza=confianza, texto=texto, palabras=palabras,
            sellos=sellos_pagina,
        )
    ]


def _consolidar(
    paginas: list[ResultadoPagina],
    observaciones: list[str],
    total_paginas: int,
    omitidas: list[int],
) -> ResultadoExtraccion:
    # Posición de cada página en el texto consolidado: permite saber en qué
    # página está una cita sin insertar marcas que alterarían el texto analizado.
    posicion = 0
    for p in paginas:
        p.inicio = posicion
        if p.texto:
            posicion += len(p.texto) + 2  # separador "\n\n"
    texto_total = "\n\n".join(p.texto for p in paginas if p.texto)
    recorte = len(texto_total) - len(texto_total.lstrip())
    texto_total = texto_total.strip()
    for p in paginas:
        p.inicio = max(0, p.inicio - recorte)
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
        sello_digital_sat=sellos.tiene_sello_digital(texto_total),
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
