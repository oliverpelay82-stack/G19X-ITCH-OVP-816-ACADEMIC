"""
Prueba de la carga en lote (RF-02), desde la Bóveda y desde el detalle del expediente.

Levanta su propio core-service y rules-service (puertos 8101 y 8102) sobre la
base ``plurione_compliance_e2e``, recreada en cada corrida, como
scripts/e2e_api.py, y un servidor de Vite en el puerto 5174 que apunta a ellos:
las cargas son reales (Nivel 1, PLUS-01 y bitácora del core), pero nada se
escribe en ``plurione_compliance``.

Bóveda, un lote de cuatro archivos en un expediente que ya custodia «a»:
  a (ya custodiado: el core responde 409), b, c (copia de b) y d (no es un PDF).
Verifica que c y d se marcan y no se envían, que el botón espera el tipo de
cada archivo, que b se custodia y sale de la lista, que a se queda con el
motivo del core, que c sigue marcado aunque b ya salió y que el aviso dice
«en parte». Expediente: dos archivos nuevos se custodian y la lista se vacía, y
un solo archivo sigue el flujo individual. Al final, por la API: cinco
documentos y un evento INGESTA_DOCUMENTO por cada uno.

Requisitos: PostgreSQL y Chrome. Uso, desde la raíz: python scripts/prueba_carga_lote.py
"""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_api import RAIZ, detener, levantar, pdf_constancia  # noqa: E402

CORE = "http://127.0.0.1:8101"
RULES = "http://127.0.0.1:8102"
PUERTO_VITE = 5174
URL = f"http://127.0.0.1:{PUERTO_VITE}/"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

fallas: list[str] = []


def comprobar(condicion: bool, mensaje: str) -> None:
    print(f"{'OK   ' if condicion else 'FALLA'} {mensaje}")
    if not condicion:
        fallas.append(mensaje)


def levantar_vite(registro: Path) -> subprocess.Popen:
    entorno = dict(os.environ, VITE_CORE_URL=f"{CORE}/api/v1", VITE_RULES_URL=f"{RULES}/api/v1",
                   VITE_AI_URL="http://127.0.0.1:8103/api/v1")
    proceso = subprocess.Popen(
        f"npm run dev -- --port {PUERTO_VITE} --strictPort --host 127.0.0.1",
        cwd=RAIZ / "frontend", env=entorno, shell=True,
        stdout=open(registro, "w", encoding="utf-8"), stderr=subprocess.STDOUT,
    )
    limite = time.monotonic() + 60
    while time.monotonic() < limite:
        try:
            if requests.get(URL, timeout=2).ok:
                return proceso
        except requests.RequestException:
            time.sleep(0.5)
    raise RuntimeError(f"Vite no respondió:\n{registro.read_text(encoding='utf-8')[-2000:]}")


def detener_vite(proceso: subprocess.Popen) -> None:
    # npm deja a Vite como proceso hijo: en Windows se termina el árbol completo.
    if os.name == "nt":
        subprocess.run(["taskkill", "/F", "/T", "/PID", str(proceso.pid)], capture_output=True)
    else:
        proceso.terminate()


def preparar_datos(carpeta: Path) -> dict:
    """Titular ficticio, expediente corporativo con «a» ya custodiado y los archivos de los lotes."""
    titular = requests.post(f"{CORE}/api/v1/titulares", json={
        "rfc": "EMP260101AB1", "razon_social": "Empresa Ficticia de Pruebas, S.A. de C.V.", "tipo_persona": "MORAL",
    }, timeout=30)
    titular.raise_for_status()
    expediente = requests.post(f"{CORE}/api/v1/expedientes", json={
        "titular_id": titular.json()["id"], "tipo_expediente": "CORPORATIVO", "nombre": "Prueba de carga en lote",
    }, timeout=30)
    expediente.raise_for_status()
    expediente = expediente.json()

    emision = date.today() - timedelta(days=10)
    archivos = {}
    for nombre in ("a_constancia.pdf", "b_domicilio.pdf", "e_acta.pdf", "f_poder.pdf", "g_estatutos.pdf"):
        archivos[nombre] = carpeta / nombre
        archivos[nombre].write_bytes(pdf_constancia("EMP260101AB1", nombre, emision))
    archivos["c_copia.pdf"] = carpeta / "c_copia.pdf"
    archivos["c_copia.pdf"].write_bytes(archivos["b_domicilio.pdf"].read_bytes())
    archivos["d_falso.pdf"] = carpeta / "d_falso.pdf"
    archivos["d_falso.pdf"].write_bytes(b"Esto no es un PDF.\n")

    previa = requests.post(f"{CORE}/api/v1/documentos/upload", data={
        "expediente_id": expediente["id"], "tipo_documento": "CSF_SAT", "usuario": "prueba-lote"},
        files={"file": ("a_constancia.pdf", archivos["a_constancia.pdf"].read_bytes(), "application/pdf")}, timeout=30)
    previa.raise_for_status()
    return {"expediente": expediente, "archivos": archivos}


def esperar_analisis(raiz, cuantos: int) -> None:
    expect(raiz.locator(".lote-item")).to_have_count(cuantos)
    expect(raiz.locator(".lote-calculando")).to_have_count(0)


def lote_en_boveda(pagina: Page, datos: dict) -> None:
    archivos = datos["archivos"]
    pagina.goto(f"{URL}#/boveda")
    boton = pagina.get_by_role("button", name="Custodiar documento")
    expect(boton).to_be_enabled(timeout=20000)
    boton.click()
    modal = pagina.locator(".modal")
    modal.get_by_label("Expediente destino").select_option(datos["expediente"]["id"])
    modal.locator("input[type=file]").set_input_files(
        [str(archivos[n]) for n in ("a_constancia.pdf", "b_domicilio.pdf", "c_copia.pdf", "d_falso.pdf")])
    esperar_analisis(modal, 4)

    texto = modal.inner_text()
    comprobar("Mismo archivo que «b_domicilio.pdf»" in texto, "Bóveda: la copia de b se marca dentro del lote")
    comprobar("Firma no reconocida" in texto, "Bóveda: el archivo que no es PDF se marca")
    comprobar("2 archivos no se enviarán" in texto and "Elige el tipo de 2 archivos" in texto,
              "Bóveda: la ayuda cuenta los omitidos y los que no tienen tipo")
    enviar = modal.get_by_role("button", name="Custodiar 2 documentos")
    comprobar(enviar.is_disabled(), "Bóveda: sin tipo por omisión, el botón espera a que se elija")

    modal.get_by_label("Tipo de documento de a_constancia.pdf").select_option("CSF_SAT")
    modal.get_by_label("Tipo de documento de b_domicilio.pdf").select_option("COMP_DOMICILIO")
    expect(enviar).to_be_enabled()
    enviar.click()

    expect(pagina.get_by_text("Lote custodiado en parte")).to_be_visible(timeout=20000)
    esperar_analisis(modal, 3)
    nombres = modal.locator(".lote-item .analysis-file-name").all_inner_texts()
    comprobar(nombres == ["a_constancia.pdf", "c_copia.pdf", "d_falso.pdf"],
              f"Bóveda: b salió de la lista y quedan a, c y d ({nombres})")
    fila_a = modal.locator(".lote-item", has=pagina.locator(".analysis-file-name", has_text="a_constancia.pdf"))
    comprobar("is-error" in (fila_a.get_attribute("class") or "") and "ya está custodiado" in fila_a.inner_text(),
              "Bóveda: a se queda con el motivo del core (409)")
    comprobar("Mismo archivo que «b_domicilio.pdf»" in modal.inner_text(),
              "Bóveda: c sigue marcado aunque b ya se custodió")
    comprobar(modal.is_visible(), "Bóveda: con rechazos, el modal sigue abierto")


def lote_en_expediente(pagina: Page, datos: dict) -> None:
    archivos = datos["archivos"]
    pagina.goto(f"{URL}#/expedientes")
    pagina.locator("[aria-expanded]", has_text=datos["expediente"]["codigo_expediente"]).first.click()
    lateral = pagina.locator(".exp-detail-side")
    expect(lateral).to_be_visible(timeout=20000)
    lateral.locator("input[type=file]").set_input_files([str(archivos["e_acta.pdf"]), str(archivos["f_poder.pdf"])])
    esperar_analisis(lateral, 2)
    lateral.get_by_label("Tipo de documento de e_acta.pdf").select_option("ACTA_CONSTITUTIVA")
    lateral.get_by_label("Tipo de documento de f_poder.pdf").select_option("PODER_NOTARIAL")
    lateral.get_by_role("button", name="Custodiar 2 documentos").click()
    expect(pagina.get_by_text("Lote custodiado", exact=True)).to_be_visible(timeout=20000)
    expect(lateral.locator(".lote-item")).to_have_count(0)
    comprobar(True, "Expediente: dos archivos custodiados y la lista vacía")

    # Un solo archivo sigue el flujo individual de siempre: veredicto completo y su aviso.
    # Con los obligatorios completos, la zona de carga se pliega tras un botón.
    otro = lateral.get_by_role("button", name="Custodiar otro documento")
    if otro.count():
        otro.click()
    lateral.locator("input[type=file]").set_input_files(str(archivos["g_estatutos.pdf"]))
    expect(lateral.locator(".analysis-hash")).to_be_visible()
    comprobar(lateral.locator(".lote-item").count() == 0, "Expediente: un solo archivo no entra en modo lote")
    lateral.locator(".dropzone-controls select").select_option("ESTATUTOS_SOCIALES")
    lateral.get_by_role("button", name="Custodiar en bóveda").click()
    expect(pagina.get_by_text("Documento custodiado", exact=True)).to_be_visible(timeout=20000)
    comprobar(True, "Expediente: la carga individual se custodia con su aviso")


def comprobar_api(datos: dict) -> None:
    expediente_id = datos["expediente"]["id"]
    documentos = [d for d in requests.get(f"{CORE}/api/v1/documentos", timeout=30).json()
                  if d["expediente_id"] == expediente_id]
    tipos = sorted(d["tipo_documento"] for d in documentos)
    comprobar(tipos == ["ACTA_CONSTITUTIVA", "COMP_DOMICILIO", "CSF_SAT", "ESTATUTOS_SOCIALES", "PODER_NOTARIAL"],
              f"API: cinco documentos, uno por tipo ({tipos})")
    for d in documentos:
        eventos = requests.get(f"{CORE}/api/v1/bitacora", params={
            "documento_id": d["id"], "evento": "INGESTA_DOCUMENTO"}, timeout=30).json()
        comprobar(len(eventos) == 1, f"API: un evento de ingesta para {d['nombre_archivo_original']}")


def main() -> int:
    registros = Path(tempfile.mkdtemp(prefix="plurione_lote_"))
    procesos = levantar({"rules-service": 8102, "core-service": 8101}, registros)
    vite = None
    try:
        vite = levantar_vite(registros / "vite.log")
        datos = preparar_datos(registros)
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="chrome")
            pagina = navegador.new_page(viewport={"width": 1366, "height": 900})
            errores: list[str] = []
            pagina.on("pageerror", lambda e: errores.append(str(e)))
            lote_en_boveda(pagina, datos)
            lote_en_expediente(pagina, datos)
            comprobar(not errores, f"Sin errores sin capturar en la página ({errores})")
            navegador.close()
        comprobar_api(datos)
    finally:
        if vite:
            detener_vite(vite)
        detener(procesos)
    print(f"\n{'Todo pasó' if not fallas else f'{len(fallas)} fallas'} · registros en {registros}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
