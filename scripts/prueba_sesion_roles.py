"""
Prueba de la sesión y los roles en el navegador (Módulo 7: RF-25, RF-26, HU-05,
HU-06 y HU-31; PRD §5.1 y §5.2).

Levanta core, rules y ai-service aislados (puertos 8101 a 8103) sobre la base
``plurione_compliance_e2e``, recreada en cada corrida, con las cuentas de
demostración (scripts/sesion_api.py), y un Vite en el 5174 que apunta a ellos.
El ai-service va sin clave de IA: nada consume tokens.

Etapas (por omisión, todas):
  diseno    pantalla de acceso en claro, oscuro y móvil; una pregunta a la vez
            con su secuencia de pasos; mostrar contraseña y estado de los
            servicios.
  acceso    pasos vacíos, cambiar de correo, credenciales incorrectas, menú por
            rol, recarga, cierre de
            sesión, ruta ajena, token rechazado y contraseña temporal.
  permisos  el auditor solo lee; el validador opera sin pausar reglas.
  mfa       alta del segundo factor con QR, código erróneo, inicio de sesión con
            código y baja.
  usuarios  alta de una cuenta de consulta, asignación de un expediente,
            desactivar y reactivar, y la consulta ve su semáforo.
  visor     la página del documento llega con el token (blob).

Uso, desde la raíz:
    python scripts/prueba_sesion_roles.py [etapa …] [--capturas CARPETA]
Requisitos: PostgreSQL y Chrome. Código 0 si todo pasa.
"""
from __future__ import annotations

import argparse
import sys
import tempfile
import uuid
from pathlib import Path

import requests
from playwright.sync_api import Page, expect, sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sesion_api  # noqa: E402
from e2e_api import detener, detener_vite, levantar, levantar_vite, pdf_constancia  # noqa: E402

PUERTOS = {"rules-service": 8102, "core-service": 8101, "ai-service": 8103}
CORE_BASE, RULES_BASE, AI_BASE = (f"http://127.0.0.1:{PUERTOS[s]}" for s in ("core-service", "rules-service", "ai-service"))
CORE = f"{CORE_BASE}/api/v1"
PUERTO_VITE = 5174
URL = f"http://127.0.0.1:{PUERTO_VITE}/"
ETAPAS = ("diseno", "acceso", "permisos", "mfa", "usuarios", "visor")
CLAVE = {rol: clave for rol, (_, clave) in sesion_api.CUENTAS_DEMO.items()}
CORREO = {rol: correo for rol, (correo, _) in sesion_api.CUENTAS_DEMO.items()}

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

fallas: list[str] = []
capturas: Path | None = None


def ok(condicion: bool, mensaje: str) -> None:
    print(("OK    " if condicion else "FALLA ") + mensaje, flush=True)
    if not condicion:
        fallas.append(mensaje)


def captura(page: Page, nombre: str) -> None:
    if capturas:
        page.screenshot(path=str(capturas / f"{nombre}.png"))


def admin() -> dict[str, str]:
    return sesion_api.cabeceras(CORE_BASE, "ADMIN")


def entrar(page: Page, correo: str, clave: str) -> None:
    page.goto(URL)
    page.get_by_role("textbox", name="Correo", exact=True).fill(correo)
    page.get_by_role("button", name="Continuar").click()
    page.get_by_label("Contraseña", exact=True).fill(clave)
    page.get_by_role("button", name="Iniciar sesión").click()


def entrar_rol(page: Page, rol: str) -> None:
    entrar(page, CORREO[rol], CLAVE[rol])


def salir(page: Page) -> None:
    page.locator(".menu-usuario-boton").click()
    page.get_by_role("menuitem", name="Cerrar sesión").click()
    expect(page.get_by_role("heading", name="¿Cuál es tu correo?")).to_be_visible()


def menu(page: Page) -> list[str]:
    return [t.strip() for t in page.locator(".sidebar-nav .nav-label").all_inner_texts()]


def cambiar_temporal(page: Page, temporal: str, definitiva: str) -> None:
    expect(page.get_by_role("heading", name="Cambia tu contraseña")).to_be_visible()
    page.get_by_label("Contraseña temporal").fill(temporal)
    page.locator("input[autocomplete=new-password]").first.fill(definitiva)
    page.get_by_label("Repite la contraseña nueva").fill(definitiva)
    page.get_by_role("button", name="Guardar contraseña").click()


def cuenta_temporal(rol: str, prefijo: str) -> str:
    correo = f"{prefijo}-{uuid.uuid4().hex[:6]}@example.com"
    r = requests.post(f"{CORE}/usuarios", headers=admin(), timeout=30, json={
        "email": correo, "nombre_completo": f"Cuenta {prefijo}", "rol": rol, "contrasena_temporal": "Temporal-2026"})
    r.raise_for_status()
    return correo


def expediente_de_prueba() -> dict:
    rfc = "USR" + "010101" + uuid.uuid4().hex[:3].upper()
    t = requests.post(f"{CORE}/titulares", headers=admin(), timeout=30,
                      json={"rfc": rfc, "razon_social": f"Asignada {rfc} S.A.", "tipo_persona": "MORAL"})
    t.raise_for_status()
    e = requests.post(f"{CORE}/expedientes", headers=admin(), timeout=30,
                      json={"titular_id": t.json()["id"], "nombre": f"Proveedor {rfc}"})
    e.raise_for_status()
    return e.json()


def expediente_con_documento() -> tuple[dict, str]:
    from datetime import date

    exp = expediente_de_prueba()
    nombre = f"csf_m7_{uuid.uuid4().hex[:4]}.pdf"
    r = requests.post(f"{CORE}/documentos/upload", headers=admin(), timeout=30,
                      data={"expediente_id": exp["id"], "tipo_documento": "CSF_SAT"},
                      files={"file": (nombre, pdf_constancia("USR010101AB1", "Asignada S.A.", date.today()),
                                      "application/pdf")})
    r.raise_for_status()
    return exp, nombre


def abrir_documento(page: Page, exp: dict, nombre: str) -> None:
    page.goto(URL + "#/expedientes/" + exp["codigo_expediente"])
    page.get_by_role("button", name=nombre).click()
    expect(page.locator(".modal")).to_be_visible()


# ═══════════════════ Etapas ═══════════════════

def etapa_diseno(page: Page) -> None:
    for tema in ("light", "dark"):
        page.set_viewport_size({"width": 1366, "height": 768})
        page.goto(URL)
        page.evaluate("t => localStorage.setItem('plurione-theme-v2', t)", tema)
        page.reload()
        expect(page.get_by_role("heading", name="¿Cuál es tu correo?")).to_be_visible()
        expect(page.locator(".acceso-estado")).to_contain_text("Servicios en línea")
        page.wait_for_timeout(900)  # el paso termina de entrar (Motion) antes de la captura
        captura(page, f"acceso_{tema}")
        page.set_viewport_size({"width": 390, "height": 844})
        page.wait_for_timeout(300)
        captura(page, f"acceso_movil_{tema}")
        ok(page.locator(".acceso-paso-nombre:visible").all_inner_texts() == ["Correo"],
           f"diseño ({tema}): en móvil solo se nombra el paso actual")
        ok(page.evaluate("document.documentElement.scrollWidth <= window.innerWidth"),
           f"diseño ({tema}): sin desplazamiento horizontal en móvil")
        page.set_viewport_size({"width": 1366, "height": 768})
        ok(page.locator(".acceso-paso.is-actual").inner_text().strip().endswith("Correo"),
           f"diseño ({tema}): el primer paso es el correo")
        # Un correo inexistente: no suma intentos fallidos a ninguna cuenta (el bloqueo es real).
        page.get_by_role("textbox", name="Correo", exact=True).fill("diseno-sin-cuenta@example.com")
        page.keyboard.press("Enter")
        expect(page.get_by_role("heading", name="Escribe tu contraseña")).to_be_visible()
        expect(page.locator(".acceso-cuenta")).to_contain_text("diseno-sin-cuenta@example.com")
        ok(page.locator(".acceso-paso.is-hecho").count() == 1, f"diseño ({tema}): Enter avanza y el correo queda hecho")
        page.get_by_label("Contraseña", exact=True).fill("mala-clave-123")
        page.get_by_role("button", name="Mostrar contraseña").click()
        ok(page.get_by_label("Contraseña", exact=True).get_attribute("type") == "text",
           f"diseño ({tema}): mostrar contraseña")
        captura(page, f"acceso_contrasena_{tema}")
        page.get_by_role("button", name="Iniciar sesión").click()
        expect(page.locator(".acceso-alerta--error")).to_be_visible()
        captura(page, f"acceso_error_{tema}")
    page.evaluate("() => localStorage.setItem('plurione-theme-v2', 'light')")


def etapa_acceso(page: Page) -> None:
    page.set_viewport_size({"width": 1366, "height": 768})
    page.goto(URL)
    expect(page.get_by_role("heading", name="¿Cuál es tu correo?")).to_be_visible()
    page.get_by_role("button", name="Continuar").click()
    expect(page.locator(".acceso-alerta--error")).to_have_text("Escribe tu correo.")
    page.get_by_role("textbox", name="Correo", exact=True).fill("otra-cuenta@example.com")
    page.get_by_role("button", name="Continuar").click()
    page.get_by_role("button", name="Iniciar sesión").click()
    expect(page.locator(".acceso-alerta--error")).to_have_text("Escribe tu contraseña.")
    ok(True, "acceso: cada paso vacío dice qué falta, sin llamar al servidor")
    page.get_by_role("button", name="Cambiar de correo").click()
    expect(page.get_by_role("heading", name="¿Cuál es tu correo?")).to_be_visible()
    ok(page.get_by_role("textbox", name="Correo", exact=True).input_value() == "otra-cuenta@example.com",
       "acceso: cambiar de correo vuelve al primer paso con lo escrito")
    entrar(page, CORREO["VALIDADOR"], "mal-contrasena-123")
    expect(page.locator(".acceso-alerta--error")).to_have_text("Correo o contraseña incorrectos.")
    ok(True, "acceso: credenciales malas muestran el mensaje del core")

    entrar_rol(page, "VALIDADOR")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(menu(page) == ["Empresas", "Expedientes", "Bóveda", "Alertas", "Reportes", "Reglas"],
       f"acceso: menú del validador sin Usuarios ({menu(page)})")
    ok("Responsable de cumplimiento" in page.locator(".menu-usuario-rol").inner_text(), "acceso: rol en la cabecera")
    page.reload()
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(True, "acceso: la sesión sobrevive a una recarga")
    salir(page)
    ok(True, "acceso: cerrar sesión vuelve al inicio")

    entrar_rol(page, "CONSULTA")
    expect(page.locator(".app-title")).to_have_text("Mis expedientes")
    ok(menu(page) == ["Mis expedientes"], f"acceso: la consulta solo ve Mis expedientes ({menu(page)})")
    page.goto(URL + "#/reglas")
    expect(page).to_have_url(URL + "#/mis-expedientes")
    expect(page.locator(".app-title")).to_have_text("Mis expedientes")
    ok(True, "acceso: una ruta ajena lleva al inicio del rol")
    ok(page.locator("[aria-haspopup='dialog']").count() == 0, "acceso: la consulta no tiene la paleta de búsqueda")
    salir(page)

    entrar_rol(page, "ADMIN")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok("Usuarios" in menu(page), "acceso: el administrador ve Usuarios")
    # Un token que el servidor ya no acepta: la siguiente petición cierra la sesión.
    page.evaluate("""() => {
        const s = JSON.parse(sessionStorage.getItem('plurione.sesion'))
        s.token = s.token.slice(0, -4) + 'AAAA'
        sessionStorage.setItem('plurione.sesion', JSON.stringify(s))
    }""")
    page.reload()
    expect(page.get_by_role("heading", name="¿Cuál es tu correo?")).to_be_visible()
    expect(page.locator(".acceso-alerta--aviso")).to_contain_text("Tu sesión expiró")
    ok(True, "acceso: un token rechazado cierra la sesión con el aviso")

    correo = cuenta_temporal("AUDITOR", "temporal")
    entrar(page, correo, "Temporal-2026")
    cambiar_temporal(page, "Temporal-2026", "Definitiva-2026")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(True, "acceso: la contraseña temporal se cambia antes de entrar")
    salir(page)


def etapa_permisos(page: Page) -> None:
    exp, nombre = expediente_con_documento()
    page.set_viewport_size({"width": 1366, "height": 768})
    entrar_rol(page, "AUDITOR")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    expect(page.locator(".exp-card, .data-table").first).to_be_visible()
    ok(page.get_by_role("button", name="Aperturar expediente").count() == 0, "permisos: el auditor no apertura expedientes")
    abrir_documento(page, exp, nombre)
    modal = page.locator(".modal")
    ok(modal.get_by_role("button", name="Auditar documento").count() == 0, "permisos: el auditor no audita")
    ok(modal.get_by_role("tab", name="Chat").count() == 0 and modal.get_by_text("Chat", exact=True).count() == 0,
       "permisos: el auditor no tiene el chat")
    expect(modal.get_by_text("Este documento aún no se audita.")).to_have_count(1)
    ok(modal.get_by_text("audítalo").count() == 0, "permisos: el auditor ve que falta auditar, sin que se le pida")
    page.keyboard.press("Escape")
    ok(page.locator(".exp-lateral-bloque", has_text="Custodiar documento").count() == 0,
       "permisos: el auditor no custodia documentos")
    page.goto(URL + "#/reglas")
    expect(page.get_by_label("Buscar reglas")).to_be_visible()
    ok(page.locator("button.switch").count() == 0 and page.get_by_role("button", name="Nueva regla").count() == 0
       and page.get_by_role("button", name="Nuevo tipo de documento").count() == 0,
       "permisos: el auditor ve las reglas sin pausar ni dar de alta")
    page.goto(URL + "#/boveda")
    expect(page.get_by_label("Buscar en la bóveda")).to_be_visible()
    ok(page.get_by_role("button", name="Custodiar documento").count() == 0, "permisos: el auditor no custodia desde la Bóveda")
    page.goto(URL + "#/empresas")
    expect(page.get_by_label("Buscar empresas")).to_be_visible()
    ok(page.get_by_role("button", name="Alta de empresa").count() == 0, "permisos: el auditor no registra empresas")
    salir(page)

    entrar_rol(page, "VALIDADOR")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(page.get_by_role("button", name="Aperturar expediente").count() >= 1, "permisos: el validador apertura expedientes")
    abrir_documento(page, exp, nombre)
    ok(page.locator(".modal").get_by_role("button", name="Auditar documento").count() == 1, "permisos: el validador audita")
    page.keyboard.press("Escape")
    page.goto(URL + "#/reglas")
    expect(page.get_by_label("Buscar reglas")).to_be_visible()
    ok(page.get_by_role("button", name="Nueva regla").count() == 0 and page.locator("button.switch").count() == 0
       and page.get_by_role("button", name="Nuevo tipo de documento").count() == 1,
       "permisos: el validador da de alta tipos de documento, pero no pausa reglas")
    page.goto(URL + "#/boveda")
    expect(page.get_by_label("Buscar en la bóveda")).to_be_visible()
    ok(page.get_by_role("button", name="Custodiar documento").count() >= 1, "permisos: el validador custodia desde la Bóveda")
    page.goto(URL + "#/empresas")
    expect(page.get_by_label("Buscar empresas")).to_be_visible()
    ok(page.get_by_role("button", name="Alta de empresa").count() >= 1, "permisos: el validador registra empresas")
    salir(page)


def etapa_mfa(page: Page) -> None:
    import pyotp

    page.set_viewport_size({"width": 1366, "height": 768})
    correo = cuenta_temporal("VALIDADOR", "mfa")
    entrar(page, correo, "Temporal-2026")
    cambiar_temporal(page, "Temporal-2026", "Definitiva-2026")
    expect(page.locator(".app-title")).to_have_text("Expedientes")

    page.locator(".menu-usuario-boton").click()
    page.get_by_role("menuitem", name="Verificación en dos pasos").click()
    page.locator(".modal").get_by_label("Contraseña").fill("Definitiva-2026")
    page.get_by_role("button", name="Continuar").click()
    qr = page.locator(".mfa-qr img")
    expect(qr).to_be_visible()
    ok(qr.get_attribute("src").startswith("data:image/png"), "mfa: el código QR se dibuja en el navegador")
    secreto = page.locator(".modal .copy-chip .mono").inner_text().strip()
    totp = pyotp.TOTP(secreto)
    page.locator(".modal").get_by_label("Código de 6 dígitos").fill("000000" if totp.now() != "000000" else "111111")
    page.get_by_role("button", name="Activar").click()
    expect(page.locator(".modal .form-error")).to_be_visible()
    ok(True, "mfa: un código equivocado no activa")
    page.locator(".modal").get_by_label("Código de 6 dígitos").fill(totp.now())
    page.get_by_role("button", name="Activar").click()
    expect(page.locator(".modal")).to_have_count(0)
    page.locator(".menu-usuario-boton").click()
    expect(page.locator(".menu-usuario-estado")).to_have_text("Activa")
    page.keyboard.press("Escape")
    ok(True, "mfa: activada con el código de la app")
    salir(page)

    entrar(page, correo, "Definitiva-2026")
    expect(page.get_by_role("heading", name="Verificación en dos pasos")).to_be_visible()
    page.get_by_label("Código de verificación").fill(totp.now())
    page.get_by_role("button", name="Verificar").click()
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(True, "mfa: el inicio de sesión pide y acepta el código")

    page.locator(".menu-usuario-boton").click()
    page.get_by_role("menuitem", name="Verificación en dos pasos").click()
    page.locator(".modal").get_by_label("Contraseña").fill("Definitiva-2026")
    page.locator(".modal").get_by_label("Código de 6 dígitos").fill(totp.now())
    page.get_by_role("button", name="Desactivar").click()
    expect(page.locator(".modal")).to_have_count(0)
    salir(page)
    entrar(page, correo, "Definitiva-2026")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    ok(True, "mfa: desactivada, vuelve a entrar solo con la contraseña")
    salir(page)


def etapa_usuarios(page: Page) -> None:
    exp = expediente_de_prueba()
    page.set_viewport_size({"width": 1366, "height": 768})
    entrar_rol(page, "ADMIN")
    page.locator(".sidebar-nav").get_by_text("Usuarios").click()
    expect(page.locator(".app-title")).to_have_text("Usuarios")
    expect(page.get_by_text(CORREO["VALIDADOR"], exact=True)).to_be_visible()
    ok(True, "usuarios: el administrador ve la lista de cuentas")

    correo = f"consulta-{uuid.uuid4().hex[:6]}@example.com"
    page.get_by_role("button", name="Nueva cuenta").click()
    page.get_by_label("Nombre completo").fill("Cliente de Prueba")
    page.get_by_label("Correo institucional").fill(correo)
    page.locator(".rol-opcion", has_text="Consulta").click()
    ok(page.get_by_role("radio", name="Consulta").is_checked(), "usuarios: el rol se elige con su tarjeta")
    expect(page.locator(".rol-alcance")).to_contain_text("semáforo")
    crear = page.get_by_role("button", name="Crear cuenta")
    page.locator(".modal input.mono").fill("corta")
    ok(crear.is_disabled() and page.locator(".requisito.is-ok").count() == 0, "usuarios: una contraseña débil no deja crear")
    page.get_by_role("button", name="Generar contraseña segura").click()
    generada = page.locator(".modal input.mono").input_value()
    ok(len(generada) == 14 and page.locator(".requisito.is-ok").count() == 3 and crear.is_enabled(),
       f"usuarios: la contraseña generada cumple los tres requisitos ({len(generada)} caracteres)")
    page.locator(".modal input.mono").fill("Temporal-2026")
    crear.click()
    fila = page.locator("tr", has_text=correo)
    expect(fila).to_contain_text("Contraseña temporal")
    ok(True, "usuarios: alta con contraseña temporal")

    fila.get_by_role("button", name="Expedientes").click()
    page.locator(".modal").get_by_label("Buscar expedientes").fill(exp["codigo_expediente"])
    page.locator(".asignacion-opcion", has_text=exp["codigo_expediente"]).locator("input").check()
    page.get_by_role("button", name="Guardar asignación (1)").click()
    expect(page.locator(".modal")).to_have_count(0)
    ok(True, "usuarios: expediente asignado a la cuenta")

    fila.get_by_role("button", name="Editar").click()
    page.get_by_role("button", name="Desactivar cuenta").click()
    expect(page.get_by_role("button", name="Reactivar cuenta")).to_be_visible()
    expect(fila).to_contain_text("Desactivada")
    page.get_by_role("button", name="Reactivar cuenta").click()
    expect(page.get_by_role("button", name="Desactivar cuenta")).to_be_visible()
    page.keyboard.press("Escape")
    expect(page.locator(".modal")).to_have_count(0)
    ok(True, "usuarios: desactivar y reactivar desde Editar")
    captura(page, "usuarios")
    salir(page)

    entrar(page, correo, "Temporal-2026")
    cambiar_temporal(page, "Temporal-2026", "Definitiva-2026")
    expect(page.locator(".app-title")).to_have_text("Mis expedientes")
    expect(page.locator("tbody tr", has_text=exp["codigo_expediente"])).to_contain_text("No conforme")
    ok(True, "usuarios: la consulta ve el semáforo del expediente asignado")
    salir(page)


def etapa_visor(page: Page) -> None:
    exp, nombre = expediente_con_documento()
    page.set_viewport_size({"width": 1366, "height": 768})
    entrar_rol(page, "AUDITOR")
    expect(page.locator(".app-title")).to_have_text("Expedientes")
    abrir_documento(page, exp, nombre)
    page.get_by_role("button", name="Ver documento").click()
    imagen = page.locator(".visor-pagina img")
    expect(imagen).to_be_visible(timeout=60000)
    src = imagen.get_attribute("src")
    ancho = imagen.evaluate("i => i.naturalWidth")
    ok(src.startswith("blob:") and ancho > 0, f"visor: la página llega con el token y se pinta ({src[:12]}, {ancho} px)")
    captura(page, "visor")
    page.keyboard.press("Escape")
    salir(page)


# ═══════════════════ Arranque ═══════════════════

def main() -> int:
    global capturas
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("etapas", nargs="*", help=f"por omisión, todas: {', '.join(ETAPAS)}")
    parser.add_argument("--capturas", help="carpeta donde guardar capturas de cada etapa")
    args = parser.parse_args()
    etapas = args.etapas or list(ETAPAS)
    desconocidas = set(etapas) - set(ETAPAS)
    if desconocidas:
        parser.error(f"etapas desconocidas: {', '.join(sorted(desconocidas))}")
    if args.capturas:
        capturas = Path(args.capturas).resolve()
        capturas.mkdir(parents=True, exist_ok=True)

    registros = Path(tempfile.mkdtemp(prefix="plurione_sesion_roles_"))
    entorno_ai = {"GROQ_API_KEY": "", "EXTRACCIONES_DB_PATH": str(registros / "extracciones.sqlite3"),
                  "DIFERIDOS_INTERVALO_MINUTOS": "0"}
    print(f"[*] Levantando los tres servicios y Vite (registros en {registros})")
    procesos = levantar(PUERTOS, registros, entorno_extra=entorno_ai)
    vite = None
    errores_consola: list[str] = []
    try:
        vite = levantar_vite(registros / "vite.log", PUERTO_VITE, CORE_BASE, RULES_BASE, AI_BASE)
        with sync_playwright() as p:
            navegador = p.chromium.launch(channel="chrome")
            page = navegador.new_page()
            page.on("console", lambda m: errores_consola.append(m.text) if m.type == "error" else None)
            for etapa in ETAPAS:
                if etapa in etapas:
                    try:
                        globals()[f"etapa_{etapa}"](page)
                    except Exception as exc:  # noqa: BLE001 — una etapa rota no impide las demás
                        captura(page, f"falla_{etapa}")
                        ok(False, f"{etapa}: {type(exc).__name__}: {str(exc).splitlines()[0][:300]}")
            navegador.close()
    finally:
        if vite:
            detener_vite(vite)
        detener(procesos)

    # Los 401 y 403 esperados (token rechazado, credenciales malas) los anota el navegador como errores de red.
    reales = [e for e in errores_consola if "401" not in e and "403" not in e and "Failed to load resource" not in e]
    ok(not reales, f"consola sin errores de la interfaz ({reales[:3]})")
    print("\nTodo pasó" if not fallas else f"\n{len(fallas)} fallas")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
