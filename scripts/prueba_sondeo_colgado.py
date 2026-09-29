"""
Prueba del sondeo del frontend ante un servicio colgado.

El panel consulta titulares, expedientes, documentos, reglas y la salud de
los tres microservicios cada 15 s. Si un servicio acepta la conexión pero no
responde (p. ej. la base de datos bloqueada), cada ciclo no debe apilar
peticiones sobre las anteriores: el navegador solo abre 6 conexiones por
servidor y las acciones del usuario (cargar, auditar) quedarían en cola.

La prueba intercepta con Playwright GET /titulares del core-service y nunca
responde; durante 40 s (casi tres ciclos) registra cuántas peticiones a esa
ruta quedan pendientes a la vez. Criterio: nunca más de una.

Requisitos: `npm run dev` y los servicios en marcha (solo se intercepta una
ruta; nada se escribe). Uso, desde la raíz: python scripts/prueba_sondeo_colgado.py
"""
import sys
import time

from playwright.sync_api import sync_playwright

URL = "http://127.0.0.1:5173/"
DURACION_S = 40


def main() -> int:
    pendientes = 0
    maximo = 0
    total = 0
    with sync_playwright() as p:
        navegador = p.chromium.launch(channel="chrome")
        pagina = navegador.new_page()
        colgadas = []

        def colgar(ruta):
            nonlocal pendientes, maximo, total
            total += 1
            pendientes += 1
            maximo = max(maximo, pendientes)
            colgadas.append(ruta)  # nunca se responde

        def terminada(peticion):
            nonlocal pendientes
            if peticion.url.endswith("/api/v1/titulares") and peticion.method == "GET":
                pendientes -= 1

        pagina.route("**/api/v1/titulares", colgar)
        pagina.on("requestfailed", terminada)
        pagina.on("requestfinished", terminada)
        pagina.goto(URL)
        fin = time.time() + DURACION_S
        while time.time() < fin:
            pagina.wait_for_timeout(500)
        medido = maximo
        # Se liberan las rutas retenidas antes de cerrar, para no dejar tareas
        # canceladas de Playwright en la salida.
        for ruta in colgadas:
            try:
                ruta.abort()
            except Exception:  # la página ya abortó esa petición por tiempo límite
                pass
        pagina.unroute_all(behavior="ignoreErrors")
        navegador.close()
        maximo = medido

    print(f"peticiones a /titulares en {DURACION_S} s: {total}; máximo pendientes a la vez: {maximo}")
    if maximo > 1:
        print("FALLA: el sondeo apila peticiones sobre un servicio que no responde")
        return 1
    print("OK: nunca hubo más de una petición pendiente")
    return 0


if __name__ == "__main__":
    sys.exit(main())
