"""
Escenarios interactivos de la regresión visual (scripts/regresion_visual.py).

Cubren estados que solo aparecen al interactuar con la interfaz: el
veredicto del Nivel 1 en la ingesta, los filtros de Expedientes, el
historial desplegado (HU-30), el alcance por tipo en una regla nueva, la
ratificación humana del Nivel 5, el visor de evidencia y el panel de
inteligencia documental tras auditar y preguntar.

Nada de lo que se hace aquí escribe en la base ni consume Groq:
- La ratificación se captura sin enviarla.
- La auditoría y el chat se simulan: Playwright intercepta preparar,
  análisis semántico y chat y responde con DICTAMEN y CHAT, que ejercitan
  todas las ramas del panel. Una auditoría real escribiría un dictamen
  inmutable (y cambiaría el registro que muestran las demás capturas).
- performance.now se fija para que las duraciones del stepper y del chat
  sean deterministas.
"""
import json
from pathlib import Path

from playwright.sync_api import Browser, Page

PREPARAR = {
    "extraccion_nivel_3": {"metodo_extraccion": "OCR", "total_paginas": 14, "paginas_omitidas_ocr": 0},
    "fuente_texto": "DISCO",
}

DICTAMEN = {
    "estatus_preliminar": "EN_REVISION",
    "nivel_confianza": 0.78,
    "umbral_confianza_conforme": 0.85,
    "umbral_confianza_hitl": 0.7,
    "requiere_revision_humana": True,
    "observaciones": [
        "Dictamen EN_REVISION: confianza por debajo del umbral y un elemento de contenido sin localizar.",
        "El sello notarial de la página 3 cruza parte del texto.",
    ],
    "rfc_detectado": None,
    "rfc_estructura_valida": None,
    "match_titular": None,
    "razon_social_detectada": "GRUPO BIMBO, S.A.B. DE C.V.",
    "titularidad": "RAZON_SOCIAL",
    "tipo_documento_detectado": "ACTA_CONSTITUTIVA",
    "tipo_coincide": True,
    "fecha_emision": "2002-05-14",
    "fecha_vencimiento": None,
    "vigencia_nivel_2": {"disponible": True, "resultado": None, "evaluaciones": []},
    "verificaciones": [
        {
            "codigo_regla": "RSC-ACTA-ADMON",
            "nombre_regla": "Administración y facultades de representación",
            "resultado": "CUMPLE",
            "cita": "la administración de la sociedad estará a cargo de un consejo de administración",
        },
        {
            "codigo_regla": "RSC-ACTA-ESCR",
            "nombre_regla": "Escritura pública y notario",
            "resultado": "CUMPLE",
            "cita": "escritura pública número 12,345",
        },
        {
            "codigo_regla": "RSC-ACTA-RPC",
            "nombre_regla": "Inscripción en el Registro Público de Comercio",
            "resultado": "NO_LOCALIZADO",
            "observacion": "No se localizó la boleta de inscripción.",
            "recomendacion": "Solicitar la boleta o constancia de inscripción en el Registro Público.",
        },
        {
            "codigo_regla": "RDS-01",
            "nombre_regla": "Criterio dinámico",
            "resultado": "NO_VERIFICABLE",
            "observacion": "Texto ilegible en la zona del sello.",
        },
    ],
    "recomendaciones": ["Solicitar la boleta o constancia de inscripción en el Registro Público."],
    "sellos": [
        {"pagina": 3, "x": 0.1, "y": 0.2, "ancho": 0.2, "alto": 0.2},
        {"pagina": 3, "x": 0.5, "y": 0.6, "ancho": 0.2, "alto": 0.2},
        {"pagina": 9, "x": 0.1, "y": 0.1, "ancho": 0.2, "alto": 0.2},
    ],
    "sello_digital_sat": True,
    "extraccion_nivel_3": {
        "lectura_completa": False,
        "paginas_omitidas_ocr": 2,
        "total_paginas": 14,
        "lectura_completa_en_curso": True,
    },
    "contexto_llm": {"estrategia_contexto": "inicio"},
    "modelo_utilizado": "qwen/qwen3.8-27b",
    "tiempos_ms": {"inferencia": 1234},
    "persistencia": {"guardado": True},
}

CHAT = {
    "respuesta": (
        "El acta designa un **consejo de administración**: «la administración de la sociedad estará a cargo "
        "de un consejo de administración». También afirma «el capital social es de cien millones»."
    ),
    "citas": [
        {
            "texto": "la administración de la sociedad estará a cargo de un consejo de administración",
            "verificada": True,
            "fuente": "documento",
        },
        {"texto": "el capital social es de cien millones", "verificada": False, "fuente": "documento"},
    ],
    "extraccion_nivel_3": {
        "lectura_completa": False,
        "paginas_omitidas_ocr": 2,
        "total_paginas": 14,
        "lectura_completa_en_curso": False,
    },
    "contexto_llm": {
        "estrategia_contexto": "fragmentos",
        "fragmentos_relevantes": [
            {"posicion_pct": 12, "puntaje": 3.1, "titulo": "Cláusula octava", "inicio": "La administración de la sociedad", "pagina": 4},
            {"posicion_pct": 40, "puntaje": 2.2, "titulo": "Capital social", "inicio": "El capital social", "pagina": 6},
        ],
    },
    "modelo_utilizado": "qwen/qwen3.8-27b",
}


def _responder(datos: dict):
    return lambda ruta: ruta.fulfill(status=200, content_type="application/json", body=json.dumps(datos))


def _archivos_ingesta(carpeta: Path) -> tuple[Path, Path]:
    """Un PDF mínimo con firma válida y un archivo sin firma reconocida (Nivel 1, en el navegador)."""
    carpeta.mkdir(parents=True, exist_ok=True)
    pdf = carpeta / "prueba.pdf"
    pdf.write_bytes(b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF\n")
    invalido = carpeta / "prueba.txt"
    invalido.write_bytes(b"no soy un pdf")
    return pdf, invalido


def capturar_escenarios(navegador: Browser, carpeta: Path, ancho: int, alto: int, tema: str, h) -> None:
    """
    `h` es el módulo regresion_visual (sus ayudantes de preparación, navegación
    y captura), para no duplicar la lógica de determinismo.
    """
    prefijo = f"{ancho}x{alto}_{tema}_int"
    pagina: Page = navegador.new_page(viewport={"width": ancho, "height": alto})
    pagina.add_init_script("performance.now = () => 1000")
    pagina.route("**/api/v1/ai/documentos/*/preparar", _responder(PREPARAR))
    pagina.route("**/api/v1/ai/analisis-semantico", _responder(DICTAMEN))
    pagina.route("**/api/v1/ai/chat-documento", _responder(CHAT))
    h._preparar(pagina, tema)
    pdf, invalido = _archivos_ingesta(h.SALIDA / "_archivos")

    # Ingesta: veredicto del Nivel 1 con un PDF válido y con un archivo sin firma reconocida.
    h._ir_a(pagina, "Bóveda")
    pagina.locator("button", has_text="Custodiar documento").first.click()
    for nombre, archivo in (("pdf", pdf), ("invalido", invalido)):
        pagina.locator(".modal input[type=file]").set_input_files(str(archivo))
        pagina.wait_for_timeout(800)
        h._capturar_modal(pagina, carpeta / f"{prefijo}_ingesta_{nombre}.png")
    h._cerrar_modal(pagina)

    # Visor de evidencia abierto sobre el segundo documento (modal xl).
    pagina.locator("table tbody tr").nth(1).locator("button").last.click()
    h._esperar(pagina, 1500)
    pagina.locator("button", has_text="Ver documento").click()
    h._esperar(pagina, 2500)
    h._capturar(pagina, carpeta / f"{prefijo}_visor.png", completa=False)
    h._cerrar_modal(pagina)

    # Ratificación humana (Nivel 5), sin enviarla: vacía, inválida y válida.
    pagina.locator("table tbody tr").first.locator("button").last.click()
    h._esperar(pagina, 2000)
    resolver = pagina.locator("button", has_text="Resolver revisión humana")
    if resolver.count():
        resolver.click()
        pagina.wait_for_timeout(300)
        pagina.locator(".modal").click(position={"x": 5, "y": 5})
        h._capturar_modal(pagina, carpeta / f"{prefijo}_ratificacion_vacia.png")
        area = pagina.locator(".ratificacion textarea")
        for nombre, texto in (("invalida", "corto"), ("valida", "Se cotejó el acta con el registro público.")):
            area.fill(texto)
            area.blur()
            pagina.wait_for_timeout(200)
            h._capturar_modal(pagina, carpeta / f"{prefijo}_ratificacion_{nombre}.png")
        pagina.locator(".ratificacion button", has_text="Cancelar").click()
    else:
        print(f"  {prefijo}: el primer documento no tiene ratificación pendiente; se omite ese escenario")

    # Panel de inteligencia documental tras una auditoría y un turno de chat simulados.
    pagina.locator("button", has_text="Auditar documento").click()
    h._esperar(pagina, 1500)
    pagina.locator(".modal").click(position={"x": 5, "y": 5})
    h._capturar_modal(pagina, carpeta / f"{prefijo}_panel_auditoria.png")
    pagina.locator(".modal .segmented-item", has_text="Chat").click()
    pagina.wait_for_timeout(300)
    pagina.locator(".composer textarea").fill("¿Quién administra la sociedad?")
    pagina.locator(".composer button[type=submit]").click()
    h._esperar(pagina, 800)
    pagina.locator(".citation").first.click()
    h._esperar(pagina, 2500)
    pagina.locator(".modal").click(position={"x": 5, "y": 5})
    h._capturar_modal(pagina, carpeta / f"{prefijo}_panel_chat.png")
    h._cerrar_modal(pagina)

    # Expedientes con filtros activos («Limpiar filtros» a la vista) e historial desplegado (HU-30).
    h._ir_a(pagina, "Expedientes")
    pagina.locator(".select-inline select").first.select_option("CORPORATIVO")
    pagina.locator("input[type=date]").first.fill("2026-09-01")
    pagina.wait_for_timeout(400)
    pagina.locator("body").click(position={"x": 5, "y": 5})
    h._capturar(pagina, carpeta / f"{prefijo}_expedientes_filtros.png")
    pagina.locator("button", has_text="Limpiar filtros").click()
    pagina.locator("[aria-expanded]").first.click()
    h._esperar(pagina, 800)
    pagina.locator("summary", has_text="Historial del expediente").click()
    h._esperar(pagina, 1200)
    ver_todo = pagina.locator("button", has_text="Ver todo")
    if ver_todo.count():
        ver_todo.click()
        pagina.wait_for_timeout(500)
    h._capturar(pagina, carpeta / f"{prefijo}_historial.png")

    # Regla nueva con alcance por tipo documental (selector de tipos y ayuda del anexo).
    h._ir_a(pagina, "Reglas")
    pagina.locator("button", has_text="Nueva regla").first.click()
    pagina.locator(".modal input").first.fill("RDS-09")
    pagina.locator(".checkbox-field", has_text="Aplica a todo").locator("input").uncheck()
    pagina.locator(".modal .chip", has_text="Contrato").first.click()
    pagina.wait_for_timeout(400)
    pagina.locator(".modal").click(position={"x": 5, "y": 5})
    h._capturar_modal(pagina, carpeta / f"{prefijo}_regla_por_tipo.png")
    h._cerrar_modal(pagina)
    pagina.close()
