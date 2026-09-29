"""
Prueba de una carga que falla, desde la Bóveda y desde el detalle del expediente.

Intercepta POST /documentos/upload con un 500 (nada llega al core-service ni
se escribe en la base) y verifica en los dos contextos que:
- no queda una promesa rechazada sin capturar en la consola, y
- el archivo elegido se conserva para poder reintentar.

Requisitos: `npm run dev` y los servicios en marcha, con al menos un
expediente. Uso, desde la raíz: python scripts/prueba_carga_fallida.py
"""
import json
import sys
import tempfile
from pathlib import Path

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5173/"


def main() -> int:
    carpeta = Path(tempfile.mkdtemp(prefix="plurione_carga_"))
    pdf = carpeta / "prueba.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    fallas = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        for contexto in ("Bóveda", "Expediente"):
            pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
            errores = []
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            pagina.on("console", lambda m: errores.append(m.text) if m.type == "error" and "Uncaught" in m.text else None)
            pagina.route(
                "**/api/v1/documentos/upload",
                lambda r: r.fulfill(status=500, content_type="application/json", body=json.dumps({"detail": "fallo simulado"})),
            )
            pagina.goto(URL)
            pagina.wait_for_load_state("networkidle")
            if contexto == "Bóveda":
                pagina.locator("button.nav-item", has_text="Bóveda").first.click()
                pagina.wait_for_timeout(500)
                pagina.locator("button", has_text="Custodiar documento").first.click()
                pagina.locator(".modal select").last.select_option(index=1)  # expediente destino
                raiz = pagina.locator(".modal")
            else:
                pagina.locator("button.nav-item", has_text="Expedientes").first.click()
                pagina.wait_for_timeout(500)
                pagina.locator("[aria-expanded]").first.click()
                pagina.wait_for_timeout(1000)
                raiz = pagina.locator(".exp-detail-side")
            raiz.locator("input[type=file]").set_input_files(str(pdf))
            pagina.wait_for_timeout(600)
            raiz.locator("button", has_text="Custodiar en bóveda").click()
            pagina.wait_for_timeout(1200)
            conserva = raiz.locator(".analysis-file-name", has_text="prueba.pdf").count() == 1
            ok = conserva and not errores
            fallas += not ok
            print(f"{'OK   ' if ok else 'FALLA'} {contexto}: archivo conservado={conserva}; errores sin capturar={errores}")
            pagina.close()
        navegador.close()
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
