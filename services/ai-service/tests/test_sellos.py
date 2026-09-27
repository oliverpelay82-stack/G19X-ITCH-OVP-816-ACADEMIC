"""
Pruebas de los sellos en tinta de color del Nivel 3 (DOC-08: presencia de
sellos), con páginas generadas en la prueba; el OCR usa Tesseract.

  1. Zonas: un sello azul se detecta como SELLO; un renglón impreso en verde
     no es un sello; un gráfico relleno (holograma) no se lee; una página en
     gris o con el papel entintado no tiene zonas.
  2. Un sello denso sobre el texto: la lectura normal pierde la página (la
     segmentación la toma por imagen); con la relectura se recupera el texto,
     incluido el folio. La imagen original no se modifica.
  3. Sello Digital SAT: se detecta en el texto (cadena original, sello digital).

Uso:  cd services/ai-service && python tests/test_sellos.py
"""
import os
import sys

import cv2
import numpy as np
import pytest
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402
from pipelines import extraccion_pipeline, sellos  # noqa: E402

LINEAS = [
    "COMPARECE EL SEÑOR JUAN PEREZ LOPEZ EN SU CARACTER DE ADMINISTRADOR UNICO",
    "DE LA SOCIEDAD INSCRITA EN EL REGISTRO PUBLICO DE COMERCIO BAJO EL FOLIO",
    "MERCANTIL NUMERO 45821 DE FECHA VEINTE DE MAYO DEL AÑO DOS MIL DOS",
    "QUIEN MANIFIESTA QUE SU REPRESENTADA TIENE CAPACIDAD LEGAL PARA OBLIGARSE",
]
_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def _fuente(tamanio: int) -> ImageFont.ImageFont:
    for ruta in ("C:/Windows/Fonts/arial.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamanio)
    return ImageFont.load_default(size=tamanio)


def _pagina(sello_denso: bool = False, titulo_verde: bool = False, holograma: bool = False) -> np.ndarray:
    """Página carta a 300 ppp (recortada) con texto negro y, opcionalmente, marcas de color."""
    imagen = Image.new("RGB", (2550, 1400), "white")
    dibujo = ImageDraw.Draw(imagen)
    for i, linea in enumerate(LINEAS):
        dibujo.text((150, 200 + i * 90), linea, fill="black", font=_fuente(34))
    if titulo_verde:
        dibujo.text((150, 700), "CONSEJO MEXICANO PARA LA ACREDITACION", fill=(40, 150, 60), font=_fuente(40))
    if holograma:
        dibujo.rectangle((2100, 900, 2300, 1150), fill=(210, 160, 40))
    capa = Image.new("RGBA", imagen.size, (0, 0, 0, 0))
    sello = ImageDraw.Draw(capa)
    sello.ellipse((900, 180, 1500, 620), outline=(40, 90, 200, 255), width=10)
    if sello_denso:
        for k in range(0, 600, 14):
            sello.line((900 + k, 180, 900 + k - 200, 620), fill=(60, 110, 210, 170), width=4)
    sello.text((980, 380), "NOTARIA PUBLICA 7", fill=(40, 90, 200, 255), font=_fuente(30))
    imagen = Image.alpha_composite(imagen.convert("RGBA"), capa).convert("RGB")
    return cv2.cvtColor(np.array(imagen), cv2.COLOR_RGB2BGR)


def main(mp: pytest.MonkeyPatch) -> int:
    print("=== SELLOS EN TINTA DE COLOR (NIVEL 3) ===\n")
    _resultados.clear()
    mp.setattr(settings, "OCR_RELEER_SELLOS", True)

    print("[1] Zonas de color")
    zonas = sellos.zonas_de_color(_pagina(titulo_verde=True, holograma=True))
    tipos = sorted((z.tipo or "RENGLON", z.es_grafico) for z in zonas)
    verificar(("SELLO", False) in tipos, "El sello azul se detecta como SELLO", str(tipos))
    verificar(("RENGLON", False) in tipos, "El renglón impreso en verde no se toma por sello")
    verificar(any(z.es_grafico for z in zonas), "El holograma relleno se reconoce como gráfico (no se lee)")
    gris = cv2.cvtColor(cv2.cvtColor(_pagina(), cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    verificar(sellos.zonas_de_color(gris) == [], "Una página en gris no tiene zonas de color")
    amarilla = np.full((1400, 2550, 3), (150, 220, 240), dtype=np.uint8)
    verificar(sellos.zonas_de_color(amarilla) == [], "Si todo el papel está entintado, no se inventan sellos")

    print("\n[2] Sello denso sobre el texto")
    pagina = _pagina(sello_denso=True)
    copia = pagina.copy()
    mp.setattr(settings, "OCR_RELEER_SELLOS", False)
    sin_relectura, _, _, _ = extraccion_pipeline._ocr_sobre_imagen(pagina)
    mp.setattr(settings, "OCR_RELEER_SELLOS", True)
    texto, confianza, palabras, encontrados = extraccion_pipeline._ocr_sobre_imagen(pagina)
    verificar("45821" not in sin_relectura, "Sin la relectura, la segmentación pierde el texto de la página",
              f"{len(sin_relectura.split())} palabras")
    verificar("45821" in texto and "REGISTRO" in texto and "CAPACIDAD" in texto,
              "Con la relectura se recupera el texto, incluido el folio", f"{len(texto.split())} palabras")
    verificar(len(encontrados) == 1 and encontrados[0]["tipo"] == "SELLO" and 0 < encontrados[0]["x0"] < 1,
              "El sello queda registrado con su recuadro normalizado", str(encontrados))
    verificar(np.array_equal(pagina, copia), "La imagen original no se modifica (solo se lee)")
    normal, _, _, sellos_normal = extraccion_pipeline._ocr_sobre_imagen(_pagina())
    verificar("45821" in normal and len(sellos_normal) == 1,
              "Un sello ligero no afecta la lectura y también se registra")

    print("\n[3] Sello Digital SAT")
    verificar(sellos.tiene_sello_digital("Cadena Original Sello: ||1.1|ABC||  Sello Digital: aZx9..."),
              "Se detecta la cadena original / sello digital en el texto")
    verificar(not sellos.tiene_sello_digital("El sello de autorizar del notario."),
              "Un sello notarial mencionado en el texto no es el Sello Digital SAT")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_sellos(monkeypatch):
    assert main(monkeypatch) == 0, "Hay verificaciones en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main(mp))
