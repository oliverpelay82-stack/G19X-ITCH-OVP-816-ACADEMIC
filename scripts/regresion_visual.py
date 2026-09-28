"""
Regresión visual del frontend (RNF-07: escritorio y portátiles desde 1366x768).

Captura cada vista de la interfaz con los datos reales del entorno local en
1366x768 y 1920x1080, en tema claro y oscuro, y compara píxel a píxel contra
una referencia. Sirve para demostrar que una refactorización del sistema de
diseño no altera la interfaz, o para acotar exactamente dónde la altera.

Requisitos: los tres microservicios y el frontend (`npm run dev`) en marcha,
y Playwright para Python con el canal de Chrome instalado.

Uso (desde la raíz del proyecto):
    python scripts/regresion_visual.py capturar base      # referencia
    python scripts/regresion_visual.py capturar actual    # tras el cambio
    python scripts/regresion_visual.py comparar           # base vs actual
    python scripts/regresion_visual.py comparar base otra # dos corridas cualesquiera

Las capturas quedan en `frontend/.regresion-visual/` (no versionado): dependen
de los datos de la base local y se regeneran en cada corrida.
"""
import sys
from pathlib import Path

from PIL import Image, ImageChops
from playwright.sync_api import Page, sync_playwright

RAIZ = Path(__file__).resolve().parent.parent
SALIDA = RAIZ / "frontend" / ".regresion-visual"
URL = "http://127.0.0.1:5173/"

TAMANOS = [(1366, 768), (1920, 1080)]
TEMAS = ["light", "dark"]
VISTAS = ["Empresas", "Expedientes", "Bóveda", "Alertas", "Reportes", "Reglas"]

# Hoja de estilo solo para la captura: apaga transiciones y el cursor del
# campo de texto. Lo único que cambia entre dos corridas sin que cambie la
# interfaz es la latencia de cada sondeo de salud (de 2 a 4 cifras): se oculta
# y se le fija el ancho, de modo que no desplaza la tira ni cuenta como
# diferencia, y el resto de la tira (estado, puerto, modelo) sí se compara.
CSS_CAPTURA = """
*, *::before, *::after { transition: none !important; animation: none !important; caret-color: transparent !important; }
.health-metric { display: inline-block; min-width: 7ch; visibility: hidden; }
"""

# Diferencia máxima por canal (0-255) que no cuenta como cambio. Los iconos
# SVG compuestos sobre el velo semitransparente del modal varían a veces ±1
# nivel entre corridas sin que cambie nada (ruido del rasterizador); 2 niveles
# lo absorben y siguen delatando el ajuste más sutil de un token de color
# (#78716c -> #716b66 difiere en 7 niveles).
UMBRAL_CANAL = 2

# Mínimo de píxeles distintos para que una captura cuente como cambio. El
# antialiasing de la esquina de un campo de fecha nativo cambia a veces un
# píxel aislado entre corridas; un cambio de diseño real (un borde, un color,
# un desplazamiento) afecta a decenas o cientos. Lo que queda por debajo se
# reporta como RUIDO, a la vista, pero no hace fallar la comparación.
MIN_PIXELES = 5


def _preparar(pagina: Page, tema: str) -> None:
    pagina.add_init_script(f"localStorage.setItem('plurione-theme-v2', '{tema}')")
    pagina.goto(URL)
    pagina.wait_for_load_state("networkidle")
    pagina.add_style_tag(content=CSS_CAPTURA)
    pagina.wait_for_timeout(800)


def _capturar(pagina: Page, ruta: Path, completa: bool = True) -> None:
    pagina.screenshot(path=str(ruta), full_page=completa, animations="disabled")


def _ir_a(pagina: Page, vista: str) -> None:
    pagina.locator("button.nav-item", has_text=vista).first.click()
    pagina.wait_for_load_state("networkidle")
    pagina.wait_for_timeout(600)


def capturar(destino: str) -> None:
    carpeta = SALIDA / destino
    carpeta.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        for ancho, alto in TAMANOS:
            for tema in TEMAS:
                pagina = navegador.new_page(viewport={"width": ancho, "height": alto})
                _preparar(pagina, tema)
                prefijo = f"{ancho}x{alto}_{tema}"
                for vista in VISTAS:
                    _ir_a(pagina, vista)
                    _capturar(pagina, carpeta / f"{prefijo}_{vista}.png")

                # Detalle del expediente: la vista con más densidad de la pestaña.
                _ir_a(pagina, "Expedientes")
                pagina.locator("[aria-expanded]").first.click()
                pagina.wait_for_load_state("networkidle")
                pagina.wait_for_timeout(1200)
                _capturar(pagina, carpeta / f"{prefijo}_expediente_detalle.png")

                # Modal del documento (metadatos, dictamen y visor) desde la Bóveda.
                _ir_a(pagina, "Bóveda")
                pagina.locator("table tbody tr").first.locator("button").last.click()
                pagina.wait_for_load_state("networkidle")
                pagina.wait_for_timeout(2000)
                _capturar(pagina, carpeta / f"{prefijo}_modal_documento.png", completa=False)
                pagina.close()
        navegador.close()
    print(f"{len(list(carpeta.glob('*.png')))} capturas en {carpeta}")


def comparar(referencia: str = "base", nueva_corrida: str = "actual") -> int:
    base, actual, dif = SALIDA / referencia, SALIDA / nueva_corrida, SALIDA / "diferencias"
    dif.mkdir(parents=True, exist_ok=True)
    distintas = 0
    for ref in sorted(base.glob("*.png")):
        nueva = actual / ref.name
        if not nueva.exists():
            print(f"FALTA     {ref.name}")
            distintas += 1
            continue
        a, b = Image.open(ref).convert("RGB"), Image.open(nueva).convert("RGB")
        if a.size != b.size:
            print(f"TAMAÑO    {ref.name}: {a.size} -> {b.size}")
            distintas += 1
            continue
        r, g, bl = ImageChops.difference(a, b).split()
        maximo = ImageChops.lighter(ImageChops.lighter(r, g), bl)  # mayor diferencia de los tres canales
        mapa = maximo.point(lambda v: 255 if v > UMBRAL_CANAL else 0)
        caja = mapa.getbbox()
        if caja is None:
            print(f"IGUAL     {ref.name}")
            continue
        pixeles = mapa.histogram()[255]
        if pixeles < MIN_PIXELES:
            print(f"RUIDO     {ref.name}: {pixeles} px en {caja}")
            continue
        pct = 100 * pixeles / (a.size[0] * a.size[1])
        print(f"DISTINTA  {ref.name}: {pixeles} px ({pct:.3f} %) en {caja}")
        Image.composite(Image.new("RGB", a.size, (220, 38, 38)), b, mapa).save(dif / ref.name)
        distintas += 1
    print(f"\n{distintas} capturas con diferencias (detalle en {dif})")
    return distintas


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "capturar" and sys.argv[2].isidentifier():
        capturar(sys.argv[2])
    elif len(sys.argv) in (2, 4) and sys.argv[1] == "comparar":
        sys.exit(1 if comparar(*sys.argv[2:4]) else 0)
    else:
        print(__doc__)
        sys.exit(2)
