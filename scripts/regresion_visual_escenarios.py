"""
Escenarios interactivos de la regresión visual (scripts/regresion_visual.py).

Cubren estados que solo aparecen al interactuar con la interfaz: el
veredicto del Nivel 1 en la ingesta, los filtros de Expedientes, el
historial desplegado (HU-30), el alcance por tipo en una regla nueva, la
ratificación humana del Nivel 5, el visor de evidencia, el panel de
inteligencia documental tras auditar y preguntar, la cadena de custodia
íntegra y comprometida en el historial (P3) y el cotejo del firmante con el
apoderado en el detalle de un contrato, acreditado y no acreditado (P2),
el catálogo de reglas con una familia y una regla desplegadas, las secciones
Evidencia y Registro técnico del panel de IA y la Bóveda con el histórico completo.

Nada de lo que se hace aquí escribe en la base ni consume Groq:
- La ratificación se captura sin enviarla.
- La auditoría y el chat se simulan: Playwright intercepta preparar,
  análisis semántico y chat y responde con DICTAMEN y CHAT, que ejercitan
  todas las ramas del panel. Una auditoría real escribiría un dictamen
  inmutable (y cambiaría el registro que muestran las demás capturas).
- La verificación de la cadena y el cotejo de representación se responden
  con datos fijos (CADENA_*, _cotejo): la base local puede no tener eventos
  sellados ni contratos auditados, y el conteo de sellos crece entre corridas.
- performance.now se fija para que las duraciones del stepper y del chat
  sean deterministas.
"""
import json
from pathlib import Path

from PIL import Image
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


# Turno del chat respondido sin modelo (PLUS-07): la meta dice «datos del dictamen».
CHAT_DICTAMEN = {
    "respuesta": (
        "Según el dictamen del motor, tienen facultades de representación:\n"
        "- **Consejo de administración**: «la administración de la sociedad estará a cargo de un consejo de "
        "administración»"
    ),
    "citas": [
        {
            "texto": "la administración de la sociedad estará a cargo de un consejo de administración",
            "verificada": True,
            "fuente": "documento",
        },
    ],
    "origen_respuesta": "DATOS_DEL_DICTAMEN",
    "modelo_utilizado": None,
    "extraccion_nivel_3": {"lectura_completa": True, "total_paginas": 14, "lectura_completa_en_curso": False},
    "contexto_llm": {
        "estrategia_contexto": "datos_del_dictamen",
        "uso_tokens": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0, "desde_cache": False},
    },
}


# Cadena de custodia (P3). La base local puede no estar sellada todavía y el
# número de eventos sellados crece con cada evento: la verificación se fija
# para que el indicador del historial sea el mismo en todas las corridas.
CADENA_INTEGRA = {
    "integra": True,
    "sellada": True,
    "eventos_sellados": 240,
    "eventos_previos": 43,
    "ultimo_hash": "7d1f0c2a9b8e4f6d3c5a1b2e9f8d7c6b5a4e3d2c1b0a9f8e7d6c5b4a3f2e1d0c",
    "ultima_secuencia": 240,
    "verificado_en": "2026-09-29T12:00:00",
    "algoritmo": "SHA-256 del JSON canónico (claves ordenadas, UTF-8, sin espacios)",
    "total_hallazgos": 0,
    "hallazgos": [],
}
CADENA_COMPROMETIDA = {
    **CADENA_INTEGRA,
    "integra": False,
    "total_hallazgos": 2,
    "hallazgos": [
        {"secuencia": 118, "evento_id": 118, "problema": "hash_evento no coincide con el contenido"},
        {"secuencia": 119, "evento_id": 119, "problema": "hash_anterior no enlaza con el evento previo"},
    ],
}

# Representación legal (P2): el cotejo que el core expone en
# evaluacion.representacion (motor/representacion.py), con y sin coincidencia.
FIRMANTE = {
    "nombre": "JUAN PÉREZ LÓPEZ",
    "cargo": "Apoderado legal",
    "empresa": "GRUPO BIMBO, S.A.B. DE C.V.",
    "cita": "por GRUPO BIMBO, S.A.B. DE C.V., representada por el Lic. Juan Pérez López",
    "cita_verificada": True,
}
APODERADO = {
    "nombre": "JUAN PEREZ LOPEZ",
    "cargo": "Apoderado general",
    "facultades": "Actos de administración",
    "cita": "se otorga poder general para actos de administración a favor de JUAN PEREZ LOPEZ",
    "cita_verificada": True,
    "documento_id": "poder-escenario",
    "tipo_documento": "PODER_NOTARIAL",
    "nombre_archivo_original": "poder_notarial_2025.pdf",
    "vencido": False,
}


def _cotejo(documento_id: str, estado: str) -> dict:
    base = {
        "documento_id": documento_id,
        "tipo_documento": "CONTRATO_SERVICIOS",
        "nombre_archivo_original": "contrato_servicios.pdf",
        "ratificado": False,
        "firmantes": [FIRMANTE],
        "apoderados": [APODERADO],
        "coincidencias": [],
    }
    if estado == "ACREDITADO":
        return {
            **base,
            "estado": "ACREDITADO",
            "coincidencias": [{**APODERADO, "firmante": FIRMANTE["nombre"], "apoderado": APODERADO["nombre"]}],
            "motivo": "JUAN PÉREZ LÓPEZ figura como Apoderado general en el poder notarial «poder_notarial_2025.pdf».",
            "recomendacion": "Confirmar que sus facultades bastan para el acto y ratificar el dictamen del contrato.",
        }
    return {
        **base,
        "estado": "NO_ACREDITADO",
        "apoderados": [{**APODERADO, "nombre": "MARÍA GÓMEZ RUIZ"}],
        "motivo": "JUAN PÉREZ LÓPEZ no figura como apoderado ni representante en el poder notarial o el acta "
        "constitutiva vigentes del expediente.",
        "recomendacion": "Solicitar el poder notarial que acredite las facultades del firmante y custodiarlo.",
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
    cadena = {"respuesta": CADENA_INTEGRA}
    pagina.route("**/api/v1/bitacora/verificar-cadena", lambda ruta: _responder(cadena["respuesta"])(ruta))
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
    # Las otras secciones del panel con el mismo dictamen simulado.
    for seccion, nombre in (("Evidencia", "evidencia"), ("Registro técnico", "registro")):
        pagina.locator(".modal .segmented-item", has_text=seccion).click()
        pagina.wait_for_timeout(300)
        pagina.locator(".modal").click(position={"x": 5, "y": 5})
        h._capturar_modal(pagina, carpeta / f"{prefijo}_panel_{nombre}.png")
    pagina.locator(".modal .segmented-item", has_text="Resultado").click()
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

    # Un turno respondido con los datos del dictamen, sin modelo (PLUS-07): la meta de la
    # respuesta dice su procedencia. Va aparte para no alterar la captura anterior del chat.
    pagina.route("**/api/v1/ai/chat-documento", _responder(CHAT_DICTAMEN))
    pagina.locator("table tbody tr").first.locator("button").last.click()
    h._esperar(pagina, 1500)
    pagina.locator(".modal .segmented-item", has_text="Chat").click()
    pagina.wait_for_timeout(300)
    pagina.locator(".composer textarea").fill("¿Quién tiene facultades de representación?")
    pagina.locator(".composer button[type=submit]").click()
    h._esperar(pagina, 800)
    pagina.locator(".modal").click(position={"x": 5, "y": 5})
    h._capturar_modal(pagina, carpeta / f"{prefijo}_panel_chat_sin_modelo.png")
    h._cerrar_modal(pagina)
    pagina.route("**/api/v1/ai/chat-documento", _responder(CHAT))

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

    # Cadena de custodia comprometida (P3): se pliega y se vuelve a desplegar el
    # historial, que en cada apertura consulta la verificación.
    cadena["respuesta"] = CADENA_COMPROMETIDA
    resumen = pagina.locator("summary", has_text="Historial del expediente")
    resumen.click()
    pagina.wait_for_timeout(200)
    resumen.click()
    h._esperar(pagina, 1200)
    # Solo el indicador: el historial completo es más alto que el viewport.
    indicador = pagina.locator(".exp-historial p[title^='Último sello']")
    _capturar_elemento(pagina, indicador, carpeta / f"{prefijo}_historial_cadena_comprometida.png")

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

    # Bóveda con el histórico completo (la vista entra con solo los vigentes).
    h._ir_a(pagina, "Bóveda")
    pagina.locator(".segmented-item", has_text="Histórico completo").click()
    pagina.wait_for_timeout(300)
    pagina.locator("body").click(position={"x": 5, "y": 5})
    h._capturar(pagina, carpeta / f"{prefijo}_boveda_historico.png")
    h._ir_a(pagina, "Reglas")

    # Catálogo con una familia desplegada y el detalle de su primera regla
    # (la vista entra con las familias plegadas).
    pagina.locator(".group-toggle", has_text="RSC").click()
    pagina.wait_for_timeout(300)
    pagina.locator(".regla-toggle").first.click()
    pagina.wait_for_timeout(300)
    pagina.locator("body").click(position={"x": 5, "y": 5})
    h._capturar(pagina, carpeta / f"{prefijo}_reglas_detalle.png")
    pagina.close()

    _escenarios_representacion(navegador, carpeta, ancho, alto, tema, h)


def _capturar_elemento(pagina: Page, elemento, ruta: Path) -> None:
    """
    Captura solo un bloque de la interfaz. Como en `_capturar_modal`, se toma
    el viewport completo y se recorta después (con `clip`, el antialiasing de
    algunos glifos variaba entre corridas).

    El bloque se lleva siempre a la misma posición entera: 24 px bajo el borde
    del velo si está en un modal, o 120 px bajo el borde de la ventana si no
    (por debajo de la cabecera fija, que lo taparía). Con
    scroll_into_view_if_needed quedaba en una coordenada fraccionaria que
    dependía de la corrida, y el suavizado del texto alternaba entre dos
    estados (el cotejo de P2 daba 24 a 305 px distintos sin cambiar nada).
    """
    elemento.scroll_into_view_if_needed()
    elemento.evaluate(
        """(el) => {
          const velo = el.closest('.modal-overlay')
          const margen = velo ? 24 : 120
          const delta = Math.round(el.getBoundingClientRect().top - (velo ? velo.getBoundingClientRect().top : 0) - margen)
          if (velo) velo.scrollTop = Math.round(velo.scrollTop + delta)
          else window.scrollTo(0, Math.round(window.scrollY + delta))
        }"""
    )
    pagina.wait_for_timeout(250)
    caja = elemento.bounding_box()
    pagina.screenshot(path=str(ruta), animations="disabled")
    x, y = max(int(caja["x"]), 0), max(int(caja["y"]), 0)
    Image.open(ruta).crop((x, y, x + int(caja["width"]), y + int(caja["height"]))).save(ruta)


def _escenarios_representacion(navegador: Browser, carpeta: Path, ancho: int, alto: int, tema: str, h) -> None:
    """
    Cotejo del firmante con el apoderado (P2) en el detalle de un contrato.

    La base local no tiene contratos auditados: en una página aparte se
    presenta el primer documento de la Bóveda como contrato de servicios y se
    responde su evaluación con el cotejo acreditado y el no acreditado. Solo
    se interceptan lecturas; va en su propia página para no alterar las demás
    capturas.
    """
    prefijo = f"{ancho}x{alto}_{tema}_int"
    pagina: Page = navegador.new_page(viewport={"width": ancho, "height": alto})
    pagina.add_init_script("performance.now = () => 1000")
    estado = {"cotejo": "ACREDITADO", "documento_id": None}

    def documentos(ruta):
        lista = ruta.fetch().json()
        if lista:
            lista[0] = {**lista[0], "tipo_documento": "CONTRATO_SERVICIOS"}
            estado["documento_id"] = lista[0]["id"]
        ruta.fulfill(status=200, content_type="application/json", body=json.dumps(lista))

    def expediente(ruta):
        datos = ruta.fetch().json()
        if estado["documento_id"]:
            evaluacion = datos.setdefault("evaluacion", {}) or {}
            evaluacion["representacion"] = [_cotejo(estado["documento_id"], estado["cotejo"])]
            datos["evaluacion"] = evaluacion
        ruta.fulfill(status=200, content_type="application/json", body=json.dumps(datos))

    pagina.route("**/api/v1/documentos", documentos)
    pagina.route("**/api/v1/expedientes/*", expediente)
    h._preparar(pagina, tema)
    h._ir_a(pagina, "Bóveda")
    for cotejo in ("ACREDITADO", "NO_ACREDITADO"):
        estado["cotejo"] = cotejo
        pagina.locator("table tbody tr").first.locator("button").last.click()
        h._esperar(pagina, 2000)
        bloque = pagina.locator(".modal .ia-bloque", has_text="Representación legal")
        _capturar_elemento(pagina, bloque, carpeta / f"{prefijo}_cotejo_{cotejo.lower()}.png")
        h._cerrar_modal(pagina)
    pagina.close()
