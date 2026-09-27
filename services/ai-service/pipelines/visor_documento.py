"""
Visor de evidencia (HU-20, RF-13): páginas del documento y ubicación de una cita.

El dictamen y el chat sustentan cada hallazgo con una cita literal. El visor
lleva al analista a la página donde está y la resalta, para que confirme el
hallazgo sobre el documento original y no solo sobre el texto extraído.

  * ``info`` — número de páginas y cómo se lee cada una (capa vectorial u OCR).
  * ``pagina_jpeg`` — la página renderizada desde el binario verificado (RIE-03).
  * ``localizar`` — página y recuadros de una cita. En una página con capa de
    texto se usan las palabras de PyMuPDF; en una escaneada, las del OCR con su
    recuadro (``extraccion_pipeline.palabras_ocr``), guardadas en SQLite para no
    repetir el reconocimiento. La comparación literal es la misma que valida las
    citas (``verificacion_contenido.compactar``). Si el OCR de la imagen difiere
    del texto analizado, se resalta la zona más parecida y se marca como
    aproximada; si no hay una zona suficientemente parecida, no se resalta nada.

Solo se lee el binario a través del core-service: cada petición verifica su
huella (RIE-03), así que el visor nunca muestra un archivo alterado.
"""
from __future__ import annotations

import io
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from threading import Lock
from typing import Any

import fitz  # PyMuPDF
import numpy as np
from PIL import Image

from clients import core_client
from config import settings
from pipelines import extraccion_pipeline, persistencia_texto
from pipelines.verificacion_contenido import MIN_CARACTERES_CITA, compactar, fragmentos_de_cita, partes_de_cita

ANCHO_MINIMO_PX = 400
ANCHO_MAXIMO_PX = 2000
MIN_CARACTERES_PARTE = 6
# Ubicación aproximada: fracción mínima de las palabras de la cita que debe
# aparecer junta en la página, y palabras mínimas para intentarla.
UMBRAL_APROXIMADA = 0.85
MIN_PALABRAS_APROXIMADA = 4

_binarios: OrderedDict[str, tuple[str, bytes]] = OrderedDict()
_candado = Lock()
_MAX_BINARIOS = 6


@dataclass
class Documento:
    sha256: str
    contenido: bytes
    es_pdf: bool


@dataclass
class Localizacion:
    encontrada: bool
    pagina: int | None = None
    recuadros: list[dict[str, Any]] = field(default_factory=list)
    metodo: str | None = None
    paginas_revisadas: int = 0
    completa: bool = False       # se ubicaron todos los fragmentos de la cita
    aproximada: bool = False     # algún fragmento se ubicó por semejanza, no literal

    def a_dict(self) -> dict[str, Any]:
        return {
            "encontrada": self.encontrada,
            "pagina": self.pagina,
            "recuadros": self.recuadros,
            "metodo": self.metodo,
            "paginas_revisadas": self.paginas_revisadas,
            "completa": self.completa,
            "aproximada": self.aproximada,
        }


def _documento(documento_id: str) -> Documento:
    """Binario verificado del documento; se reutiliza en memoria mientras su huella no cambie."""
    core_client.verificar_integridad(documento_id)
    metadatos = core_client.obtener_metadatos(documento_id)
    sha256 = metadatos.get("hash_sha256", "")
    with _candado:
        previo = _binarios.get(documento_id)
        if previo and previo[0] == sha256:
            _binarios.move_to_end(documento_id)
            contenido = previo[1]
        else:
            contenido = None
    if contenido is None:
        contenido = core_client.leer_binario(metadatos)
        with _candado:
            _binarios[documento_id] = (sha256, contenido)
            while len(_binarios) > _MAX_BINARIOS:
                _binarios.popitem(last=False)
    mime = extraccion_pipeline.detectar_mime(contenido)
    return Documento(sha256, contenido, mime == "application/pdf")


def _abrir_pdf(contenido: bytes) -> fitz.Document:
    try:
        return fitz.open(stream=contenido, filetype="pdf")
    except Exception as exc:  # PyMuPDF lanza su propia jerarquía de errores
        raise extraccion_pipeline.FormatoNoSoportadoError(
            f"El PDF tiene la firma correcta pero no pudo abrirse: {exc}"
        ) from exc


def _es_vectorial(pagina: fitz.Page) -> bool:
    return len(pagina.get_text("text").strip()) >= settings.UMBRAL_CARACTERES_PAGINA


def info(documento_id: str) -> dict[str, Any]:
    doc = _documento(documento_id)
    if not doc.es_pdf:
        with Image.open(io.BytesIO(doc.contenido)) as imagen:
            ancho, alto = imagen.size
        return {"total_paginas": 1, "paginas": [{"numero": 1, "ancho": ancho, "alto": alto, "metodo": "OCR"}]}
    with _abrir_pdf(doc.contenido) as pdf:
        paginas = [
            {"numero": i, "ancho": p.rect.width, "alto": p.rect.height,
             "metodo": "VECTORIAL" if _es_vectorial(p) else "OCR"}
            for i, p in enumerate(pdf, start=1)
        ]
    return {"total_paginas": len(paginas), "paginas": paginas}


CALIDAD_JPEG = 82


def pagina_jpeg(documento_id: str, numero: int, ancho_px: int) -> bytes:
    """
    La página ``numero`` (desde 1) como JPEG de ``ancho_px`` píxeles de ancho.
    Un escaneo en PNG pesa más de 1 MB por página; en JPEG, una décima parte,
    sin pérdida visible de legibilidad.
    """
    ancho_px = max(ANCHO_MINIMO_PX, min(ancho_px, ANCHO_MAXIMO_PX))
    doc = _documento(documento_id)
    if not doc.es_pdf:
        if numero != 1:
            raise IndexError("Una imagen tiene una sola página.")
        with Image.open(io.BytesIO(doc.contenido)) as imagen:
            imagen = imagen.convert("RGB")
            alto_px = round(imagen.height * ancho_px / imagen.width)
            salida = io.BytesIO()
            imagen.resize((ancho_px, alto_px), Image.LANCZOS).save(salida, format="JPEG", quality=CALIDAD_JPEG)
        return salida.getvalue()
    with _abrir_pdf(doc.contenido) as pdf:
        if not 1 <= numero <= pdf.page_count:
            raise IndexError(f"El documento tiene {pdf.page_count} páginas.")
        pagina = pdf[numero - 1]
        zoom = ancho_px / pagina.rect.width
        return pagina.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("jpg", jpg_quality=CALIDAD_JPEG)


# ── Localización de citas ───────────────────────────────────────────
def _palabras_vectoriales(pagina: fitz.Page) -> list[list[Any]]:
    ancho, alto = pagina.rect.width, pagina.rect.height
    return [
        [x0 / ancho, y0 / alto, x1 / ancho, y1 / alto, texto, f"{bloque}-{linea}"]
        for x0, y0, x1, y1, texto, bloque, linea, _ in pagina.get_text("words")
    ]


def _palabras_escaneadas(doc: Documento, pdf: fitz.Document | None, numeros: list[int]) -> dict[int, list[list[Any]]]:
    """
    Palabras con recuadro de varias páginas escaneadas. Las ya reconocidas salen
    de SQLite; las demás se rasterizan aquí (PyMuPDF no es seguro entre hilos) y
    se reconocen en paralelo, dentro del tope de OCR_WORKERS del pool compartido.
    """
    resultado: dict[int, list[list[Any]]] = {}
    imagenes: dict[int, np.ndarray] = {}
    for numero in numeros:
        guardadas = persistencia_texto.leer_palabras(doc.sha256, numero)
        if guardadas is not None:
            resultado[numero] = guardadas
        elif pdf is not None:
            imagenes[numero] = extraccion_pipeline._rasterizar(pdf[numero - 1])
        else:
            with Image.open(io.BytesIO(doc.contenido)) as original:
                imagenes[numero] = np.array(original.convert("L"))
    if imagenes:
        with ThreadPoolExecutor(max_workers=settings.OCR_WORKERS) as hilos:
            reconocidas = dict(zip(imagenes, hilos.map(extraccion_pipeline.reconocer_pagina, imagenes.values())))
        # Se guarda también el texto y la confianza: la lectura completa de la
        # auditoría reutiliza estas páginas en lugar de repetir su OCR.
        for numero, (texto, confianza, palabras, sellos_pagina) in reconocidas.items():
            persistencia_texto.guardar_palabras(doc.sha256, numero, palabras, texto, confianza, sellos_pagina)
            resultado[numero] = palabras
    return resultado


def _recuadros(palabras: list[list[Any]], indices: set[int], numero: int, aproximada: bool) -> list[dict[str, Any]]:
    """Un recuadro por renglón que abarca las palabras indicadas."""
    renglones: dict[str, list[float]] = {}
    for i in sorted(indices):
        x0, y0, x1, y1, _, renglon = palabras[i]
        r = renglones.setdefault(renglon, [x0, y0, x1, y1])
        r[0], r[1], r[2], r[3] = min(r[0], x0), min(r[1], y0), max(r[2], x1), max(r[3], y1)
    return [
        {"pagina": numero, "x0": round(r[0], 4), "y0": round(r[1], 4), "x1": round(r[2], 4),
         "y1": round(r[3], 4), "aproximada": aproximada}
        for r in sorted(renglones.values(), key=lambda r: (r[1], r[0]))
    ]


def _buscar_exacta(parte: str, palabras: list[list[Any]], numero: int) -> list[dict[str, Any]] | None:
    """La parte aparece literalmente (misma comparación que valida las citas)."""
    compacto, dueno = [], []
    for i, palabra in enumerate(palabras):
        c = compactar(str(palabra[4]))
        compacto.append(c)
        dueno.extend([i] * len(c))
    inicio = "".join(compacto).find(parte)
    if inicio < 0:
        return None
    return _recuadros(palabras, set(dueno[inicio:inicio + len(parte)]), numero, aproximada=False)


def _buscar_aproximada(tokens: list[str], palabras: list[list[Any]]) -> tuple[float, set[int]]:
    """
    Mejor ventana de palabras de la página que contiene la mayoría de las
    palabras de la cita. Cubre el caso en que el OCR de la imagen difiere del
    texto analizado (un escaneo reconocido de nuevo no siempre da el mismo texto).
    """
    pagina = [(i, compactar(str(p[4]))) for i, p in enumerate(palabras)]
    pagina = [(i, t) for i, t in pagina if t]
    # Cada palabra de la cita se compara una sola vez contra toda la página:
    # posiciones (en `pagina`) de las palabras parecidas a cada una.
    parecidas = [{j for j, (_, t) in enumerate(pagina) if _palabras_parecidas(token, t)} for token in tokens]
    largo = len(tokens) + 2
    mejor, indices = 0.0, set()
    for inicio in range(max(1, len(pagina) - len(tokens) + 1)):
        ventana = set(range(inicio, min(inicio + largo, len(pagina))))
        en_ventana = [p & ventana for p in parecidas]
        puntaje = sum(1 for p in en_ventana if p) / len(tokens)
        if puntaje > mejor:
            mejor, indices = puntaje, {pagina[min(p)][0] for p in en_ventana if p}
    return mejor, indices


def _palabras_parecidas(a: str, b: str) -> bool:
    """
    Iguales, una contenida en la otra (el OCR une «Ejecutivo-Tesorero» en una
    sola palabra) o con una sola letra de diferencia en palabras largas.
    """
    if a == b:
        return True
    corta, larga = sorted((a, b), key=len)
    if len(corta) >= 4 and corta in larga:
        return True
    if len(corta) < 5 or len(larga) - len(corta) > 2:
        return False
    comparador = SequenceMatcher(None, a, b)
    return comparador.real_quick_ratio() >= 0.85 and comparador.quick_ratio() >= 0.85 and comparador.ratio() >= 0.85


def _orden_probable(
    total: int, cita: str, texto_extraido: str | None, paginas_texto: list[dict[str, Any]] | None = None
) -> list[int]:
    """
    Páginas ordenadas de la más a la menos probable. Con las posiciones de
    página de la extracción (``detalle_paginas[].inicio``) se sabe en qué
    página del texto analizado está cada fragmento, y esas van primero; sin
    ellas, se estima por la posición relativa de la cita en el texto.
    """
    partes = partes_de_cita(cita)
    if not texto_extraido or not partes:
        return list(range(1, total + 1))
    exactas: list[int] = []
    if paginas_texto:
        tramos = sorted((p["inicio"], p["pagina"]) for p in paginas_texto if "inicio" in p)
        for i, (inicio, numero) in enumerate(tramos):
            fin = tramos[i + 1][0] if i + 1 < len(tramos) else len(texto_extraido)
            tramo = compactar(texto_extraido[inicio:fin])
            if any(parte in tramo for parte in partes) and numero not in exactas:
                exactas.append(numero)
    estimada = exactas[0] if exactas else 1
    if not exactas:
        completo = compactar(texto_extraido)
        posicion = completo.find(partes[0])
        if posicion >= 0 and completo:
            estimada = min(total, int(posicion / len(completo) * total) + 1)
    return sorted(range(1, total + 1), key=lambda n: (n not in exactas, abs(n - estimada), n))


def localizar(
    documento_id: str,
    cita: str,
    texto_extraido: str | None = None,
    paginas_texto: list[dict[str, Any]] | None = None,
) -> Localizacion:
    """
    Ubica cada fragmento de la cita (el modelo puede unir con «...» fragmentos
    de páginas distintas). Primero se busca el fragmento literal; si no aparece
    en ninguna página, la ventana de palabras más parecida (al menos
    ``UMBRAL_APROXIMADA`` de sus palabras), marcada como aproximada. La
    localización es ``completa`` solo si se ubicaron todos los fragmentos.
    """
    fragmentos = [(c, t) for c, t in fragmentos_de_cita(cita or "") if len(c) >= MIN_CARACTERES_PARTE]
    # La misma regla que valida las citas: una palabra suelta no es evidencia.
    if not fragmentos or max(len(c) for c, _ in fragmentos) < MIN_CARACTERES_CITA:
        return Localizacion(encontrada=False)
    doc = _documento(documento_id)
    ubicados: dict[str, int] = {}
    recuadros: list[dict[str, Any]] = []
    metodos: set[str] = set()
    leidas: dict[int, tuple[list[list[Any]], str]] = {}

    def revisar(numero: int, palabras: list[list[Any]], metodo: str) -> None:
        leidas[numero] = (palabras, metodo)
        for compacta, _ in fragmentos:
            if compacta not in ubicados and (encontrados := _buscar_exacta(compacta, palabras, numero)):
                ubicados[compacta] = numero
                recuadros.extend(encontrados)
                metodos.add(metodo)

    def completos() -> bool:
        return all(c in ubicados for c, _ in fragmentos)

    if not doc.es_pdf:
        revisar(1, _palabras_escaneadas(doc, None, [1])[1], "OCR")
    else:
        with _abrir_pdf(doc.contenido) as pdf:
            orden = _orden_probable(pdf.page_count, cita, texto_extraido, paginas_texto)
            vectoriales = [n for n in orden if _es_vectorial(pdf[n - 1])]
            escaneadas = [n for n in orden if n not in vectoriales]
            # Primero las páginas con capa de texto (instantáneas); después las
            # escaneadas, por tandas de OCR_WORKERS páginas, de la más probable a la menos.
            for numero in vectoriales:
                if completos():
                    break
                revisar(numero, _palabras_vectoriales(pdf[numero - 1]), "VECTORIAL")
            tanda = max(1, settings.OCR_WORKERS)
            for i in range(0, len(escaneadas), tanda):
                if completos():
                    break
                for numero, palabras in sorted(_palabras_escaneadas(doc, pdf, escaneadas[i:i + tanda]).items()):
                    revisar(numero, palabras, "OCR")

    for compacta, tokens in fragmentos:
        if compacta in ubicados or len(tokens) < MIN_PALABRAS_APROXIMADA:
            continue
        candidatos = [(*_buscar_aproximada(tokens, palabras), numero) for numero, (palabras, _) in leidas.items()]
        mejor = max(candidatos, key=lambda r: r[0], default=None)
        if mejor and mejor[0] >= UMBRAL_APROXIMADA:
            _, indices, numero = mejor
            ubicados[compacta] = numero
            recuadros.extend(_recuadros(leidas[numero][0], indices, numero, aproximada=True))
            metodos.add(leidas[numero][1])

    if not recuadros:
        return Localizacion(encontrada=False, paginas_revisadas=len(leidas))
    orden = sorted(recuadros, key=lambda r: (r["pagina"], r["y0"], r["x0"]))
    primera = next((ubicados[c] for c, _ in fragmentos if c in ubicados), orden[0]["pagina"])
    return Localizacion(
        encontrada=True, pagina=primera, recuadros=orden, metodo="+".join(sorted(metodos)),
        paginas_revisadas=len(leidas), completa=completos(), aproximada=any(r["aproximada"] for r in orden),
    )
