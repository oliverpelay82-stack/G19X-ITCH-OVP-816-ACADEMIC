"""
Prueba de los errores de validación (422) en la interfaz.

FastAPI responde un 422 con `detail` como lista de errores
([{"loc": [...], "msg": "..."}]). Intercepta el alta de una regla con esa
respuesta (nada llega al rules-service) y verifica que el aviso y el error
del formulario muestran el mensaje con su campo, y no «[object Object]».

Requisitos: `npm run dev` y los servicios en marcha. Uso, desde la raíz:
python scripts/prueba_error_422.py
"""
import json
import sys

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5173/"
DETALLE = [{"type": "string_too_long", "loc": ["body", "codigo_regla"], "msg": "String should have at most 20 characters", "input": "RDS-04-COMP_DOMICILIO"}]


def main() -> int:
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
        pagina.route(
            "**/api/v1/reglas",
            lambda r: r.fulfill(status=422, content_type="application/json", body=json.dumps({"detail": DETALLE}))
            if r.request.method == "POST" else r.fallback(),
        )
        pagina.goto(URL)
        pagina.wait_for_load_state("networkidle")
        pagina.locator("button.nav-item", has_text="Reglas").first.click()
        pagina.wait_for_timeout(500)
        pagina.locator("button", has_text="Nueva regla").first.click()
        modal = pagina.locator(".modal")
        campos = modal.locator("input:not([type=checkbox]), textarea")
        campos.nth(0).fill("RDS-04")                                   # código base
        campos.nth(1).fill("Regla de prueba")                          # nombre
        campos.nth(2).fill("Criterio de prueba para el error 422.")    # descripción
        campos.nth(4).fill("Revisar")                                  # acción
        modal.locator("button", has_text="Guardar regla").click()
        pagina.wait_for_timeout(1000)
        textos = modal.locator(".form-error").all_inner_texts() + pagina.locator(".toast").all_inner_texts()
        navegador.close()

    print("mensajes mostrados:", textos)
    visibles = " ".join(textos)
    if not textos or "[object Object]" in visibles or "String should have at most 20 characters" not in visibles:
        print("FALLA: el 422 no se muestra como texto legible")
        return 1
    print("OK: el 422 se muestra con su campo y su mensaje")
    return 0


if __name__ == "__main__":
    sys.exit(main())
