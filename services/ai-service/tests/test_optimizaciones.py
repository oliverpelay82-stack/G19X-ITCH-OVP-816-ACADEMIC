"""
Pruebas de las optimizaciones del ai-service, sin servidor ni Groq.

  1. Fragmentos relevantes: una cláusula al final de un documento extenso llega
     al contexto del modelo, sin exceder el presupuesto de caracteres.
  2. Stemming ligero: "acciones" y "acción" se reconocen como el mismo término.
  3. Persistencia SQLite: una lectura completa nunca se sobrescribe con una
     parcial, y los datos sobreviven a una nueva conexión.
  4. Caché LRU: respeta su capacidad y deduplica extracciones concurrentes.
  5. Corte temprano: un PDF escaneado largo solo pasa por OCR hasta cubrir el
     presupuesto, y con texto_completo=True se leen todas las páginas.
  6. Preprocesamiento: una foto con sombra y baja resolución se lee con
     exactitud alta gracias al umbral adaptativo.

Uso:  cd services/ai-service && python tests/test_optimizaciones.py
"""
import difflib
import os
import re
import sys
import tempfile
import threading
import time

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cv2  # noqa: E402
import fitz  # noqa: E402
import numpy as np  # noqa: E402

from config import settings  # noqa: E402
from pipelines import extraccion_pipeline, fragmentos, persistencia_texto  # noqa: E402
from pipelines.cache_extracciones import CacheExtracciones  # noqa: E402

FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def prueba_fragmentos() -> None:
    print("[1] Fragmentos relevantes en un documento extenso")
    relleno = "\n".join(
        f"CLÁUSULA {i}. La sociedad podrá celebrar contratos, adquirir bienes y realizar actos de comercio "
        f"relacionados con su objeto social, conforme a la legislación aplicable número {i}."
        for i in range(1, 400)
    )
    encabezado = "ESCRITURA PÚBLICA NÚMERO 1234. ANTE MÍ, CORREDOR PÚBLICO NÚMERO 6.\n"
    clausula = (
        "ARTÍCULO QUINTO. El CAPITAL SOCIAL mínimo fijo es de $50,000.00 (cincuenta mil pesos), "
        "representado por 500 ACCIONES ordinarias con valor nominal de $100.00 cada una."
    )
    texto = encabezado + relleno + "\n" + clausula + "\n" + relleno[:3000]
    seleccion = fragmentos.seleccionar(texto, "¿Cuál es el capital social de la sociedad?")
    verificar(seleccion.estrategia == "fragmentos", "El documento extenso se resuelve por fragmentos")
    verificar("$50,000.00" in seleccion.texto, "La cláusula del capital social (al 90 %) llega al modelo")
    verificar(seleccion.texto.startswith("ESCRITURA PÚBLICA"), "El encabezado del documento siempre se incluye")
    verificar(
        len(seleccion.texto) <= settings.MAX_CARACTERES_CONTEXTO,
        "El contexto respeta el presupuesto de caracteres",
        f"{len(seleccion.texto)}/{settings.MAX_CARACTERES_CONTEXTO} de {len(texto)}",
    )
    titulos = [f["titulo"] for f in seleccion.fragmentos]
    verificar(any("CAPITAL SOCIAL" in t or "$50,000.00" in t for t in titulos),
              "Cada fragmento lleva un título citable", " | ".join(titulos)[:80])
    corto = fragmentos.seleccionar("Constancia breve con RFC PLU180514AB3.", "rfc")
    verificar(corto.estrategia == "completo", "Un documento corto se envía completo")


def prueba_stemming() -> None:
    print("\n[2] Normalización y stemming ligero")
    verificar(fragmentos.tokenizar("Acciones") == fragmentos.tokenizar("acción"), "acciones == acción")
    verificar(fragmentos.tokenizar("FACULTADES") == fragmentos.tokenizar("facultad"), "facultades == facultad")
    verificar("capital" in fragmentos.tokenizar("¿Cuál es el capital?"), "Se descartan palabras vacías y signos")


def prueba_persistencia() -> None:
    print("\n[3] Persistencia permanente (SQLite)")
    # La ruta original se restaura al salir del bloque, antes de borrar el directorio temporal.
    with tempfile.TemporaryDirectory() as tmp, pytest.MonkeyPatch.context() as mp:
        mp.setattr(settings, "EXTRACCIONES_DB_PATH", os.path.join(tmp, "extracciones.sqlite3"))
        persistencia_texto.guardar("abc", False, "texto parcial", {"total_paginas": 26}, completo=False)
        verificar(persistencia_texto.leer("abc").texto == "texto parcial", "Guarda y recupera una lectura parcial")
        persistencia_texto.guardar("abc", False, "texto completo", {"total_paginas": 26}, completo=True)
        persistencia_texto.guardar("abc", False, "otra parcial", {"total_paginas": 26}, completo=False)
        guardada = persistencia_texto.leer("abc")
        verificar(
            guardada.completo and guardada.texto == "texto completo",
            "Una lectura completa no se sobrescribe con una parcial",
        )
        verificar(persistencia_texto.leer("xyz") is None, "Una huella desconocida devuelve None")


def prueba_cache() -> None:
    print("\n[4] Caché LRU en memoria")
    cache = CacheExtracciones(capacidad=2)
    for clave in ("a", "b", "c"):
        cache.obtener_o_calcular(clave, lambda c=clave: c.upper())
    verificar(cache.estadisticas()["documentos_en_cache"] == 2, "Respeta la capacidad (desaloja el más antiguo)")
    _, desde_cache = cache.obtener_o_calcular("c", lambda: "otra vez")
    verificar(desde_cache, "Un acierto se sirve desde memoria")

    llamadas = []

    def lento():
        llamadas.append(1)
        time.sleep(0.3)
        return "texto"

    hilos = [threading.Thread(target=cache.obtener_o_calcular, args=("doc", lento)) for _ in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join()
    verificar(len(llamadas) == 1, "5 peticiones simultáneas ejecutan una sola extracción", f"{len(llamadas)} llamada(s)")


def _pdf_escaneado(paginas: int) -> bytes:
    with fitz.open(os.path.join(FIXTURES, "constancia_escaneada.pdf")) as fuente, fitz.open() as destino:
        for _ in range(paginas):
            destino.insert_pdf(fuente)
        return destino.tobytes()


def prueba_corte_temprano() -> None:
    print("\n[5] Corte temprano del OCR")
    contenido = _pdf_escaneado(12)
    inicio = time.perf_counter()
    parcial = extraccion_pipeline.extraer_texto(contenido)
    s_parcial = time.perf_counter() - inicio
    verificar(parcial.paginas_omitidas, "Se omiten páginas al cubrir el presupuesto",
              f"OCR en {parcial.paginas_ocr} de {parcial.total_paginas} ({s_parcial:.1f} s)")
    verificar(parcial.paginas_ocr <= settings.MAX_PAGINAS_OCR, "No se excede MAX_PAGINAS_OCR")
    verificar([p.numero for p in parcial.detalle_paginas] == sorted(p.numero for p in parcial.detalle_paginas),
              "Las páginas conservan el orden del documento")
    completo = extraccion_pipeline.extraer_texto(contenido, texto_completo=True)
    verificar(completo.paginas_ocr == 12 and not completo.paginas_omitidas, "texto_completo=True lee todas las páginas")


def prueba_preprocesamiento() -> None:
    print("\n[6] Preprocesamiento de fotos con sombra (umbral adaptativo)")
    with fitz.open(os.path.join(FIXTURES, "constancia_vectorial.pdf")) as d:
        referencia = d[0].get_text()
        pix = d[0].get_pixmap(matrix=fitz.Matrix(110 / 72, 110 / 72), colorspace=fitz.csRGB)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, 3).astype(np.float32)
    alto, ancho = img.shape[:2]
    yy, xx = np.mgrid[0:alto, 0:ancho]
    img = img * (0.45 + 0.55 * ((xx / ancho + yy / alto) / 2))[..., None]
    img += np.random.default_rng(7).normal(0, 9, img.shape)
    foto = cv2.cvtColor(cv2.GaussianBlur(np.clip(img, 0, 255).astype(np.uint8), (3, 3), 0), cv2.COLOR_RGB2BGR)

    texto, confianza = extraccion_pipeline._ocr_sobre_imagen(foto)
    palabras = lambda t: re.findall(r"\w+", t.upper())  # noqa: E731
    exactitud = difflib.SequenceMatcher(None, palabras(texto), palabras(referencia), autojunk=False).ratio()
    verificar(exactitud >= 0.90, "Foto con sombra leída con exactitud alta", f"{exactitud:.1%}, confianza {confianza:.2f}")
    verificar("PLU180514AB3" in texto.replace(" ", ""), "El RFC se recupera de la foto")


def main() -> int:
    print("=== PRUEBAS DE OPTIMIZACIÓN DEL AI-SERVICE ===\n")
    _resultados.clear()
    prueba_fragmentos()
    prueba_stemming()
    prueba_persistencia()
    prueba_cache()
    prueba_corte_temprano()
    prueba_preprocesamiento()
    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_optimizaciones():
    assert main() == 0, "Hay verificaciones de optimización en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    sys.exit(main())
