"""
Generador de documentos de prueba para los Niveles 3 y 4.

Produce dos versiones del **mismo** documento ficticio, para poder contrastar
las dos rutas del pipeline de extracción con un contenido idéntico:

  * ``constancia_vectorial.pdf`` — PDF generado por software, con capa de texto
    incrustada. Reproduce el caso de la Constancia de Situación Fiscal que se
    descarga del portal del SAT.
  * ``constancia_escaneada.pdf`` — el mismo documento rasterizado y degradado
    para imitar un escaneo de oficina: papel grisáceo con viñeteado, ruido
    gaussiano de sensor, ligera inclinación de alimentación y compresión JPEG
    con pérdida. No lleva capa de texto, de modo que obliga al pipeline a
    resolverlo por OCR.

Los datos son **ficticios** y están rotulados como tales dentro del propio
documento: sirven exclusivamente para probar el motor, no representan a ninguna
constancia real ni emulan un documento oficial válido.

Uso:  python tests/generar_fixtures.py
"""
import os

import cv2
import fitz
import numpy as np

DIRECTORIO_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

# Datos ficticios del documento de prueba.
RFC_PRUEBA = "PLU180514AB3"
RAZON_SOCIAL_PRUEBA = "PLURIONE S.A. DE C.V."
FECHA_EMISION_PRUEBA = "2026-01-15"
FECHA_VENCIMIENTO_PRUEBA = "2027-01-15"

LINEAS = [
    ("DOCUMENTO DE PRUEBA - DATOS FICTICIOS", 15, True),
    ("Generado automaticamente para validar el motor OCR. Sin validez oficial.", 9, False),
    ("", 10, False),
    ("CONSTANCIA DE SITUACION FISCAL", 16, True),
    ("", 10, False),
    ("DATOS DE IDENTIFICACION DEL CONTRIBUYENTE", 11, True),
    (f"RFC: {RFC_PRUEBA}", 12, False),
    (f"Denominacion o Razon Social: {RAZON_SOCIAL_PRUEBA}", 11, False),
    ("Regimen de capital: SOCIEDAD ANONIMA DE CAPITAL VARIABLE", 11, False),
    (f"Fecha de inicio de operaciones: 14 de mayo de 2018", 11, False),
    ("Estatus en el padron: ACTIVO", 11, False),
    ("", 10, False),
    ("DATOS DEL DOMICILIO REGISTRADO", 11, True),
    ("Calle: AVENIDA TECNOLOGICO   Numero exterior: 2909", 11, False),
    ("Colonia: CENTRO   Municipio: CHIHUAHUA   Entidad: CHIHUAHUA", 11, False),
    ("Codigo Postal: 31200", 11, False),
    ("", 10, False),
    ("REGIMENES", 11, True),
    ("Regimen General de Ley Personas Morales   Fecha de alta: 14/05/2018", 11, False),
    ("", 10, False),
    ("VIGENCIA DEL DOCUMENTO", 11, True),
    (f"Fecha de emision: {FECHA_EMISION_PRUEBA}", 11, False),
    (f"Fecha de vencimiento: {FECHA_VENCIMIENTO_PRUEBA}", 11, False),
    ("", 10, False),
    ("Cadena original del sello digital:", 10, True),
    ("||1.0|2026-01-15T09:14:22|PLU180514AB3|CONSTANCIA|31200|CHIHUAHUA||", 8, False),
]


def construir_pdf_vectorial(ruta: str) -> None:
    """Crea el PDF con capa de texto real, que el Nivel 3 resolverá sin OCR."""
    documento = fitz.open()
    pagina = documento.new_page(width=612, height=792)  # Carta

    pagina.draw_rect(fitz.Rect(40, 40, 572, 752), color=(0.15, 0.25, 0.55), width=1.2)

    y = 85
    for texto, tamanio, negrita in LINEAS:
        if texto:
            pagina.insert_text(
                fitz.Point(62, y),
                texto,
                fontsize=tamanio,
                fontname="hebo" if negrita else "helv",
                color=(0.07, 0.09, 0.15),
            )
        y += tamanio + 9

    documento.save(ruta)
    documento.close()


def degradar_como_escaneo(imagen_rgb: np.ndarray, semilla: int = 7) -> np.ndarray:
    """
    Aplica las degradaciones típicas de un escáner de oficina.

    El objetivo no es estropear la imagen por estropearla, sino reproducir los
    tres defectos que de verdad castigan al OCR y que justifican la etapa de
    preprocesamiento: fondo no uniforme, ruido de sensor e inclinación.
    """
    generador = np.random.default_rng(semilla)
    alto, ancho = imagen_rgb.shape[:2]
    imagen = imagen_rgb.astype(np.float32)

    # 1. Papel grisáceo con viñeteado: el centro queda más claro que los bordes.
    eje_y = np.linspace(-1.0, 1.0, alto)[:, None]
    eje_x = np.linspace(-1.0, 1.0, ancho)[None, :]
    vinetado = 1.0 - 0.22 * (eje_x ** 2 + eje_y ** 2)
    imagen *= vinetado[:, :, None]
    imagen *= 0.93  # tono general de papel reciclado

    # 2. Ruido gaussiano del sensor.
    imagen += generador.normal(loc=0.0, scale=9.0, size=imagen.shape)
    imagen = np.clip(imagen, 0, 255).astype(np.uint8)

    # 3. Inclinación de alimentación de 0.7 grados.
    matriz = cv2.getRotationMatrix2D((ancho / 2, alto / 2), 0.7, 1.0)
    imagen = cv2.warpAffine(
        imagen, matriz, (ancho, alto), flags=cv2.INTER_LINEAR,
        borderMode=cv2.BORDER_CONSTANT, borderValue=(216, 214, 210),
    )

    # 4. Compresión JPEG con pérdida, como la que aplica el propio escáner.
    _, codificada = cv2.imencode(".jpg", imagen, [int(cv2.IMWRITE_JPEG_QUALITY), 58])
    return cv2.imdecode(codificada, cv2.IMREAD_COLOR)


def construir_pdf_escaneado(ruta_origen: str, ruta_destino: str, dpi: int = 200) -> None:
    """Rasteriza el PDF vectorial, lo degrada y lo reempaqueta sin capa de texto."""
    with fitz.open(ruta_origen) as origen:
        pagina = origen[0]
        matriz = fitz.Matrix(dpi / 72.0, dpi / 72.0)
        pixmap = pagina.get_pixmap(matrix=matriz, colorspace=fitz.csRGB)
        imagen_rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(
            pixmap.height, pixmap.width, 3
        )
        ancho_pt, alto_pt = pagina.rect.width, pagina.rect.height

    degradada_bgr = degradar_como_escaneo(imagen_rgb[:, :, ::-1].copy())
    exito, codificada = cv2.imencode(".jpg", degradada_bgr, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
    if not exito:
        raise RuntimeError("No fue posible codificar la imagen degradada.")

    destino = fitz.open()
    hoja = destino.new_page(width=ancho_pt, height=alto_pt)
    hoja.insert_image(fitz.Rect(0, 0, ancho_pt, alto_pt), stream=codificada.tobytes())
    destino.save(ruta_destino)
    destino.close()


def main() -> None:
    os.makedirs(DIRECTORIO_FIXTURES, exist_ok=True)
    vectorial = os.path.join(DIRECTORIO_FIXTURES, "constancia_vectorial.pdf")
    escaneada = os.path.join(DIRECTORIO_FIXTURES, "constancia_escaneada.pdf")

    construir_pdf_vectorial(vectorial)
    construir_pdf_escaneado(vectorial, escaneada)

    for ruta in (vectorial, escaneada):
        with fitz.open(ruta) as documento:
            caracteres = sum(len(p.get_text()) for p in documento)
        print(
            f"[fixtures] {os.path.basename(ruta):32s} "
            f"{os.path.getsize(ruta) / 1024:7.1f} KB  "
            f"capa de texto: {caracteres} caracteres"
        )


if __name__ == "__main__":
    main()
