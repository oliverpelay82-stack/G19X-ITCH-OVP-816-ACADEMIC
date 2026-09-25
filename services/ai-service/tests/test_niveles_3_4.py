"""
Suite de verificación de los Niveles 3 y 4 del pipeline (DOC-05).

Comprueba, contra el servicio levantado en el puerto 8003:

  1. El health check reporta Groq Cloud, su modelo y el motor OCR.
  2. La ruta vectorial resuelve un PDF con capa de texto sin invocar OCR.
  3. La ruta OCR recupera el contenido de un escaneo degradado con confianza
     suficiente, tras el preprocesamiento con OpenCV.
  4. Un PDF con cabecera válida pero cuerpo corrupto se rechaza con 400 y no
     con un error interno.
  5. El Nivel 4 dictamina CONFORME cuando el RFC del documento coincide con el
     del titular y el documento está vigente.
  6. El Nivel 4 dictamina NO_CONFORME cuando el RFC no pertenece al titular.
  7. El endpoint conversacional responde preguntas sobre el documento.

Uso:  python tests/test_niveles_3_4.py
      (requiere: uvicorn main:app --port 8003 y GROQ_API_KEY configurada)
"""
import json
import os
import sys
import time

import requests

BASE = os.getenv("AI_SERVICE_URL", "http://127.0.0.1:8003").rstrip("/")
API = f"{BASE}/api/v1"
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

RFC_TITULAR = "PLU180514AB3"
RAZON_SOCIAL_TITULAR = "PLURIONE S.A. DE C.V."
RFC_AJENO = "XAXX010101000"

_resultados: list[tuple[bool, str, str]] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> bool:
    _resultados.append((bool(condicion), titulo, detalle))
    marca = "[ OK ]" if condicion else "[FALLA]"
    print(f"  {marca} {titulo}" + (f"  -> {detalle}" if detalle else ""))
    return bool(condicion)


def extraer(nombre_fixture: str, **campos) -> dict:
    ruta = os.path.join(FIXTURES, nombre_fixture)
    with open(ruta, "rb") as archivo:
        respuesta = requests.post(
            f"{API}/ai/extraer-texto",
            files={"file": (nombre_fixture, archivo, "application/pdf")},
            data={k: str(v).lower() for k, v in campos.items()},
            timeout=600,
        )
    respuesta.raise_for_status()
    return respuesta.json()


def main() -> int:
    if not os.path.isdir(FIXTURES):
        print("No existen los documentos de prueba. Ejecute antes: python tests/generar_fixtures.py")
        return 1

    print("=== VERIFICACION DE LOS NIVELES 3 Y 4 DEL PIPELINE (DOC-05) ===\n")

    # ── 1. Health check ─────────────────────────────────────────────
    print("[1] Health check del ai-service y sus dependencias")
    salud = requests.get(f"{API}/health", timeout=30).json()
    verificar(salud["status"] == "online", "El servicio responde", f"puerto {salud['puerto']}")
    verificar(
        salud["motor_inferencia"]["modelo_disponible"],
        "Modelo de lenguaje disponible en Groq",
        salud["motor_inferencia"]["modelo_requerido"],
    )
    verificar(
        salud["motor_ocr"]["disponible"],
        "Motor OCR operativo",
        f"Tesseract {salud['motor_ocr'].get('version')} "
        f"({', '.join(salud['motor_ocr'].get('idiomas_disponibles', []))})",
    )
    modelo = salud["motor_inferencia"]["modelo_requerido"]

    # ── 2. Nivel 3: ruta vectorial ──────────────────────────────────
    print("\n[2] Nivel 3 - Ruta vectorial (PDF con capa de texto)")
    vectorial = extraer("constancia_vectorial.pdf")
    verificar(
        vectorial["metodo_extraccion"] == "VECTORIAL",
        "Resuelto sin invocar OCR",
        f"metodo={vectorial['metodo_extraccion']}",
    )
    verificar(
        vectorial["paginas_procesadas_con_ocr"] == 0,
        "Ninguna pagina requirio rasterizado",
    )
    verificar(
        RFC_TITULAR in vectorial["texto_extraido"],
        "El RFC aparece en el texto recuperado",
        RFC_TITULAR,
    )

    # ── 3. Nivel 3: ruta OCR ────────────────────────────────────────
    print("\n[3] Nivel 3 - Ruta OCR con preprocesamiento (escaneo degradado)")
    inicio = time.time()
    escaneado = extraer("constancia_escaneada.pdf")
    duracion = time.time() - inicio
    verificar(
        escaneado["metodo_extraccion"] == "OCR",
        "Derivado automaticamente a OCR",
        f"{duracion:.1f}s",
    )
    verificar(
        escaneado["confidence_score"] >= 0.70,
        "Confianza por encima del umbral de gobernanza humana",
        f"score={escaneado['confidence_score']}",
    )
    verificar(
        RFC_TITULAR in escaneado["texto_extraido"],
        "El RFC se recupero pese a la degradacion del escaneo",
    )
    cobertura = escaneado["total_caracteres"] / max(vectorial["total_caracteres"], 1)
    verificar(
        cobertura >= 0.90,
        "Cobertura de texto respecto del original vectorial",
        f"{cobertura:.1%}",
    )

    # El OCR debe reconstruir los renglones a partir de la estructura de bloques
    # que reporta Tesseract. Si los concatena en una sola linea, el titulo del
    # documento queda pegado al encabezado del apartado siguiente y el Nivel 4
    # pierde la senal que le permite clasificarlo.
    renglones_ocr = [l for l in escaneado["texto_extraido"].split("\n") if l.strip()]
    renglones_vec = [l for l in vectorial["texto_extraido"].split("\n") if l.strip()]
    verificar(
        len(renglones_ocr) >= len(renglones_vec) * 0.8,
        "El OCR conserva la estructura de renglones del documento",
        f"{len(renglones_ocr)} renglones frente a {len(renglones_vec)} del vectorial",
    )
    verificar(
        any(l.strip() == "CONSTANCIA DE SITUACION FISCAL" for l in renglones_ocr),
        "El titulo del documento queda aislado en su propio renglon",
    )

    # ── 4. Robustez ante un PDF corrupto ────────────────────────────
    print("\n[4] Nivel 3 - Rechazo controlado de un PDF corrupto")
    corrupto = b"%PDF-1.4\n% archivo truncado, sin arbol de objetos\n"
    respuesta = requests.post(
        f"{API}/ai/extraer-texto",
        files={"file": ("corrupto.pdf", corrupto, "application/pdf")},
        timeout=120,
    )
    verificar(
        respuesta.status_code == 400,
        "Devuelve 400 y no un error interno",
        f"HTTP {respuesta.status_code}",
    )

    # ── 5. Nivel 4: dictamen CONFORME ───────────────────────────────
    print(f"\n[5] Nivel 4 - Analisis semantico con titular coincidente (modelo {modelo})")
    inicio = time.time()
    conforme = requests.post(
        f"{API}/ai/analisis-semantico",
        json={
            "texto": escaneado["texto_extraido"],
            "rfc_titular": RFC_TITULAR,
            "razon_social_titular": RAZON_SOCIAL_TITULAR,
        },
        timeout=900,
    ).json()
    duracion = time.time() - inicio
    verificar(
        conforme.get("rfc_detectado") == RFC_TITULAR,
        "RFC extraido por el modelo",
        f"{conforme.get('rfc_detectado')}  [{duracion:.1f}s]",
    )
    verificar(conforme.get("match_titular") is True, "Coincidencia de titularidad confirmada")
    verificar(
        conforme.get("tipo_documento_detectado") == "CONSTANCIA_SITUACION_FISCAL",
        "Tipo documental clasificado correctamente sobre texto de OCR",
        str(conforme.get("tipo_documento_detectado")),
    )
    verificar(
        conforme.get("estatus_preliminar") == "CONFORME",
        "Estatus preliminar dictaminado",
        conforme.get("estatus_preliminar", ""),
    )
    verificar(
        conforme.get("fecha_vencimiento") is not None,
        "Fecha de vencimiento localizada",
        str(conforme.get("fecha_vencimiento")),
    )

    # ── 6. Nivel 4: dictamen NO_CONFORME ────────────────────────────
    print("\n[6] Nivel 4 - Analisis semantico con titular ajeno")
    no_conforme = requests.post(
        f"{API}/ai/analisis-semantico",
        json={"texto": escaneado["texto_extraido"], "rfc_titular": RFC_AJENO},
        timeout=900,
    ).json()
    verificar(no_conforme.get("match_titular") is False, "Discrepancia de titularidad detectada")
    verificar(
        no_conforme.get("estatus_preliminar") == "NO_CONFORME",
        "Estatus preliminar dictaminado",
        no_conforme.get("estatus_preliminar", ""),
    )

    # ── 7. Chat documental ──────────────────────────────────────────
    print("\n[7] Nivel 4 - Consulta conversacional sobre el documento")
    inicio = time.time()
    chat = requests.post(
        f"{API}/ai/chat-documento",
        json={
            "texto": escaneado["texto_extraido"],
            "pregunta": "Cual es el codigo postal del domicilio fiscal registrado?",
        },
        timeout=900,
    ).json()
    duracion = time.time() - inicio
    verificar(
        "31200" in chat.get("respuesta", ""),
        "La respuesta cita el dato correcto del documento",
        f"[{duracion:.1f}s] {chat.get('respuesta', '')[:90]}",
    )

    # ── Resumen ─────────────────────────────────────────────────────
    aprobadas = sum(1 for ok, _, _ in _resultados if ok)
    total = len(_resultados)
    print("\n" + "=" * 62)
    print(f"RESULTADO: {aprobadas}/{total} comprobaciones aprobadas")
    if aprobadas < total:
        print("\nComprobaciones fallidas:")
        for ok, titulo, detalle in _resultados:
            if not ok:
                print(f"  - {titulo} ({detalle})")
    print("=" * 62)

    # Se deja la evidencia en disco para adjuntarla al expediente documental.
    evidencia = os.path.join(FIXTURES, "evidencia_niveles_3_4.json")
    with open(evidencia, "w", encoding="utf-8") as archivo:
        json.dump(
            {
                "health": salud,
                "extraccion_vectorial": {k: v for k, v in vectorial.items() if k != "texto_extraido"},
                "extraccion_ocr": {k: v for k, v in escaneado.items() if k != "texto_extraido"},
                "analisis_conforme": conforme,
                "analisis_no_conforme": no_conforme,
                "chat": chat,
            },
            archivo,
            indent=2,
            ensure_ascii=False,
        )
    print(f"Evidencia guardada en: {evidencia}")

    return 0 if aprobadas == total else 1


def test_niveles_3_4():
    """Suite en vivo: se omite si el ai-service no está levantado en AI_SERVICE_URL."""
    import pytest

    try:
        requests.get(f"{API}/health", timeout=3)
    except requests.RequestException:
        pytest.skip(f"ai-service no disponible en {BASE}; esta suite requiere el servicio y GROQ_API_KEY")
    assert main() == 0, "Hay verificaciones de los Niveles 3 y 4 en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    sys.exit(main())
