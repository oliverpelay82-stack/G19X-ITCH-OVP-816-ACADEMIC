"""
Pruebas del visor de evidencia (HU-20, RF-13) sin red: el core-service se
simula y los documentos se generan en la prueba.

  1. Información y páginas: número de páginas, método de lectura de cada una y
     página renderizada en JPEG al ancho pedido.
  2. Página con capa de texto: la cita se ubica en su página con un recuadro
     por renglón; una cita unida con «...» se ubica en dos páginas distintas.
  3. Página escaneada: la cita se ubica con las coordenadas del OCR, que se
     guardan para no repetir el reconocimiento.
  4. Honestidad: una frase que no está en el documento no se resalta; una cita
     con errores de OCR se ubica como aproximada; una frase distinta que solo
     comparte el nombre del notario, no.
  5. Una sola lectura: el texto que analiza el Nivel 4 y las palabras que
     resalta el visor salen de la misma llamada a Tesseract; cada página sabe
     dónde empieza en el texto; una lectura de otra versión del Nivel 3 se ignora.

Uso:  cd services/ai-service && python tests/test_visor_documento.py
"""
import hashlib
import os
import sys
import tempfile

import fitz
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import core_client  # noqa: E402
from config import settings  # noqa: E402
from pipelines import extraccion_pipeline, persistencia_texto, repositorio_texto, visor_documento  # noqa: E402
from pipelines.verificacion_contenido import compactar  # noqa: E402

PAGINA_1 = (
    "ESCRITURA PUBLICA NUMERO 18,442. En la ciudad de Chilpancingo, Guerrero, ante mi,\n"
    "Licenciado Juan Perez Lopez, Notario Publico numero 7, comparecen los socios fundadores\n"
    "para constituir la sociedad denominada Constructora Sierra Madre, S.A. de C.V."
)
PAGINA_2 = (
    "CLAUSULA DECIMA. La administracion de la sociedad estara a cargo de un Administrador\n"
    "Unico, con facultades para pleitos y cobranzas y actos de administracion.\n"
    "Doy fe. Lic. Juan Perez Lopez, Notario Publico numero siete."
)
_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def _pdf_vectorial() -> bytes:
    doc = fitz.open()
    for texto in (PAGINA_1, PAGINA_2):
        doc.new_page(width=612, height=792).insert_text((56, 90), texto, fontsize=11)
    return doc.tobytes()


def _pdf_escaneado() -> bytes:
    """La página 2 del PDF vectorial convertida en imagen: sin capa de texto."""
    origen = fitz.open(stream=_pdf_vectorial(), filetype="pdf")
    imagen = origen[1].get_pixmap(matrix=fitz.Matrix(300 / 72, 300 / 72), colorspace=fitz.csGRAY)
    doc = fitz.open()
    doc.new_page(width=612, height=792).insert_image(fitz.Rect(0, 0, 612, 792), pixmap=imagen)
    return doc.tobytes()


def simular_core(mp: pytest.MonkeyPatch, documentos: dict[str, bytes]) -> None:
    mp.setattr(core_client, "verificar_integridad", lambda documento_id: None)
    mp.setattr(core_client, "obtener_metadatos", lambda documento_id: {"id": documento_id, "hash_sha256": f"h-{documento_id}"})
    mp.setattr(core_client, "leer_binario", lambda metadatos: documentos[metadatos["id"]])


def main(mp: pytest.MonkeyPatch) -> int:
    print("=== VISOR DE EVIDENCIA (HU-20, RF-13) ===\n")
    _resultados.clear()
    base = tempfile.mkdtemp(prefix="visor-")
    mp.setattr(settings, "EXTRACCIONES_DB_PATH", os.path.join(base, "visor.sqlite3"))
    visor_documento._binarios.clear()
    simular_core(mp, {"vect": _pdf_vectorial(), "esc": _pdf_escaneado()})

    print("[1] Información y páginas")
    info = visor_documento.info("vect")
    verificar(info["total_paginas"] == 2 and all(p["metodo"] == "VECTORIAL" for p in info["paginas"]),
              "Dos páginas con capa de texto", str([p["metodo"] for p in info["paginas"]]))
    verificar(visor_documento.info("esc")["paginas"][0]["metodo"] == "OCR", "Una página escaneada se lee por OCR")
    jpeg = visor_documento.pagina_jpeg("vect", 1, 800)
    imagen = fitz.Pixmap(jpeg)
    verificar(jpeg[:3] == b"\xff\xd8\xff" and imagen.width == 800, "Página renderizada en JPEG al ancho pedido",
              f"{imagen.width} px · {len(jpeg) // 1024} KB")
    try:
        visor_documento.pagina_jpeg("vect", 9, 800)
        fuera = False
    except IndexError:
        fuera = True
    verificar(fuera, "Una página inexistente se rechaza")

    print("\n[2] Página con capa de texto")
    r = visor_documento.localizar("vect", "Licenciado Juan Pérez López, Notario Público número 7")
    verificar(r.encontrada and r.completa and r.pagina == 1 and r.metodo == "VECTORIAL" and not r.aproximada,
              "La cita se ubica en la página 1, literal", f"página {r.pagina}")
    verificar(len(r.recuadros) == 1 and 0 < r.recuadros[0]["x0"] < r.recuadros[0]["x1"] <= 1,
              "Un recuadro normalizado por renglón", str(r.recuadros))
    r = visor_documento.localizar("vect", "comparecen los socios fundadores para constituir la sociedad")
    verificar(len({round(x["y0"], 3) for x in r.recuadros}) == 2, "Una cita de dos renglones da dos recuadros")
    r = visor_documento.localizar("vect", "ESCRITURA PUBLICA NUMERO 18,442 ... Administrador Unico, con facultades")
    verificar(r.completa and {x["pagina"] for x in r.recuadros} == {1, 2} and r.pagina == 1,
              "Una cita unida con «...» se ubica en sus dos páginas", str(sorted({x["pagina"] for x in r.recuadros})))

    print("\n[3] Página escaneada")
    r = visor_documento.localizar("esc", "con facultades para pleitos y cobranzas y actos de administración")
    verificar(r.encontrada and r.metodo == "OCR" and r.recuadros, "La cita se ubica con las coordenadas del OCR",
              f"{r.metodo} · aproximada={r.aproximada}")
    verificar(persistencia_texto.leer_palabras("h-esc", 1) is not None, "Las palabras reconocidas quedan guardadas")

    print("\n[4] Honestidad de la evidencia")
    r = visor_documento.localizar("vect", "El arrendatario pagará una penalización del diez por ciento")
    verificar(not r.encontrada and not r.recuadros, "Una frase que no está en el documento no se resalta")
    r = visor_documento.localizar("vect", "la administracion de la sociedad estara a cargo de un Administrdor Unico")
    verificar(r.encontrada and r.aproximada and r.pagina == 2, "Una cita con un error de OCR se ubica como aproximada",
              f"página {r.pagina}")
    r = visor_documento.localizar("vect", "Yo Licenciado Juan Perez Lopez, Notario Publico Titular de la Notaria siete")
    verificar(not r.encontrada, "Una frase distinta que solo comparte el nombre del notario no se resalta")
    verificar(not visor_documento.localizar("vect", "Notario").encontrada, "Una cita demasiado corta no se busca")

    print("\n[5] Una sola lectura como fuente de verdad (Nivel 3 versionado)")
    escaneado = _pdf_escaneado()
    texto, traza, _ = repositorio_texto.obtener_por_contenido(escaneado, "escaneado.pdf", usar_cache=False)
    sha = hashlib.sha256(escaneado).hexdigest()
    palabras = persistencia_texto.leer_palabras(sha, 1)
    verificar(palabras is not None and compactar(" ".join(p[4] for p in palabras)) == compactar(texto),
              "El texto analizado y las palabras del visor salen de la misma lectura")
    doble = fitz.open()
    doble.insert_pdf(fitz.open(stream=_pdf_vectorial(), filetype="pdf"), from_page=0, to_page=0)
    doble.insert_pdf(fitz.open(stream=escaneado, filetype="pdf"))
    texto, traza, _ = repositorio_texto.obtener_por_contenido(doble.tobytes(), "hibrido.pdf", usar_cache=False)
    inicio_2 = traza["detalle_paginas"][1]["inicio"]
    verificar(texto.startswith("ESCRITURA") and "Administrador" in texto[inicio_2:inicio_2 + 120]
              and "Administrador" not in texto[:inicio_2],
              "Cada página registra dónde empieza dentro del texto consolidado", f"página 2 desde {inicio_2}")
    verificar(visor_documento._orden_probable(2, "Administrador Unico, con facultades", texto,
                                              traza["detalle_paginas"])[0] == 2,
              "Con esas posiciones, el visor busca primero en la página correcta")
    verificar(persistencia_texto.leer(sha) is not None, "La lectura queda guardada con la versión vigente")
    with pytest.MonkeyPatch.context() as sin_ocr:
        # El reconocimiento de cada página, por tandas o en flujo continuo, pasa por aquí.
        def ocr_prohibido(imagen):
            raise AssertionError("se repitió el OCR de una página ya reconocida")
        sin_ocr.setattr(extraccion_pipeline, "_ocr_sobre_imagen", ocr_prohibido)
        texto_2, _, _ = repositorio_texto.obtener_por_contenido(escaneado, "escaneado.pdf", usar_cache=False,
                                                                 texto_completo=True)
    texto_1, _, _ = repositorio_texto.obtener_por_contenido(escaneado, "escaneado.pdf")
    verificar(texto_2 == texto_1, "Una segunda lectura reutiliza las páginas ya reconocidas: mismo texto, sin OCR")
    mp.setattr(persistencia_texto, "_version", lambda: "n3-9.9|otra-lectura")
    verificar(persistencia_texto.leer(sha) is None and persistencia_texto.leer_palabras(sha, 1) is None,
              "Una lectura de otra versión del Nivel 3 se ignora y el documento se vuelve a leer")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_visor_documento(monkeypatch):
    assert main(monkeypatch) == 0, "Hay verificaciones en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main(mp))
