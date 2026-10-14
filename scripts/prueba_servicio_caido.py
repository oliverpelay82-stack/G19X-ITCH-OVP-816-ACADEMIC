"""
Prueba de las vistas con el core-service caído desde el arranque.

Sin respuesta del core, las listas llegan vacías. Antes, Alertas decía «Sin
alertas vigentes: todos los expedientes cumplen», una afirmación de
cumplimiento falsa, y Empresas, Expedientes y Bóveda decían «aún no hay…».
Solo Reglas distinguía un servicio caído de una lista vacía.

La prueba intercepta con Playwright toda petición al core-service y la aborta
(como un servicio apagado). En Empresas, Expedientes, Bóveda, Alertas y
Reportes comprueba que se muestra «Sistema de expedientes fuera de línea» y
ningún texto de lista vacía ni de cumplimiento.

Requisitos: `npm run dev` en marcha; los servicios no hacen falta (el core se
simula caído y nada se escribe). Uso, desde la raíz:
python scripts/prueba_servicio_caido.py [URL]   (por omisión, http://127.0.0.1:5173/)
"""
import sys

from playwright.sync_api import sync_playwright

URL = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:5173/"
CORE = "**/127.0.0.1:8001/**"
FUERA_DE_LINEA = "Sistema de expedientes fuera de línea"
# Textos que con el core caído afirmarían algo falso.
PROHIBIDOS = (
    "Sin alertas vigentes",
    "Todos los expedientes cumplen",
    "Aún no hay empresas registradas",
    "Aún no hay expedientes aperturados",
    "La bóveda está vacía",
)
VISTAS = ("empresas", "expedientes", "boveda", "alertas", "reportes")


def main() -> int:
    fallos = []
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
        pagina.route(CORE, lambda ruta: ruta.abort("connectionrefused"))
        for vista in VISTAS:
            pagina.goto(f"{URL}#/{vista}")
            try:
                pagina.get_by_text(FUERA_DE_LINEA).first.wait_for(timeout=15000)
                visible = True
            except Exception:  # noqa: BLE001 - se informa como fallo de la vista
                visible = False
            texto = pagina.locator(".app-content").inner_text()
            falsos = [t for t in PROHIBIDOS if t in texto]
            estado = "OK" if visible and not falsos else "FALLA"
            print(f"{estado:6} #/{vista}: fuera de línea {'visible' if visible else 'ausente'}"
                  f"{'; dice: ' + ', '.join(falsos) if falsos else ''}")
            if estado == "FALLA":
                fallos.append(vista)
        navegador.close()

    if fallos:
        print(f"FALLA: {len(fallos)} vistas no distinguen el servicio caído de una lista vacía")
        return 1
    print("OK: todas las vistas dicen que el sistema de expedientes no responde")
    return 0


if __name__ == "__main__":
    sys.exit(main())
