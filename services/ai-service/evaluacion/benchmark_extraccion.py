"""
Benchmark del RNF-02: extracción y análisis de un documento de hasta 20 páginas
en 25 s o menos (docs/VALIDACION_CUANTITATIVA.md §7.3).

  * Nivel 3 en frío (sin persistencia ni caché: se llama a ``extraer_texto``
    directamente), 5 corridas por documento, mediana y rango, con el tiempo
    acumulado por etapa (rasterizado, preprocesamiento y Tesseract, sumado
    entre los procesos de OCR).
  * Dos configuraciones, cada una en su propio proceso porque el pool de OCR se
    crea al importar: la definitiva (§5.3) y la anterior (núcleos físicos,
    ``spa+eng``; hasta el 02/10/2026 también releía los sellos en tinta de color), sobre la lectura 3.3 de hoy.
  * Documentos: el contrato de 20 páginas vectorial y escaneado (Gold Standard),
    el mismo escaneado a color con un sello en tinta en 1 de cada 4 páginas, y
    las actas reales que se indiquen con ``--actas`` (no se versionan: el
    resultado no guarda sus nombres).
  * RNF-02 completo (``--nivel4 N``): N auditorías reales del contrato escaneado
    por el endpoint, cada una con SQLite y casete nuevos, así que el OCR es en
    frío y la inferencia va a Groq (≈ 7,000 tokens por auditoría).

Uso:  cd services/ai-service
      python -m evaluacion.benchmark_extraccion [--nivel4 3] [--actas RUTA ...]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import time
from typing import Any

_SERVICIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DOCUMENTOS = os.path.join(_SERVICIO, "evaluacion", "gold_standard", "documentos")
DIRECTORIO_RESULTADOS = os.path.join(os.path.dirname(os.path.dirname(_SERVICIO)), "docs", "resultados_validacion")
CORRIDAS = 5
META_MS = 25_000
ESPERA_ENTRE_AUDITORIAS_S = 61

CONFIGURACIONES = {
    # La relectura de sellos en tinta de color, que «anterior» también activaba, se retiró el 02/10/2026.
    "definitiva": {"OCR_WORKERS": str(os.cpu_count() or 2), "OCR_LANG": "spa"},
    "anterior": {"OCR_WORKERS": str(max(1, (os.cpu_count() or 2) // 2)), "OCR_LANG": "spa+eng"},
}


# ── Proceso de medición (una configuración) ─────────────────────────
def _medir_configuracion(documentos: list[dict[str, str]], corridas: int) -> list[dict[str, Any]]:
    sys.path.insert(0, _SERVICIO)
    from pipelines import extraccion_pipeline as ep

    etapas = {"rasterizado": 0.0, "preprocesamiento": 0.0, "tesseract": 0.0}

    def cronometrar(nombre: str, funcion):
        def envoltura(*a, **k):
            inicio = time.perf_counter()
            try:
                return funcion(*a, **k)
            finally:
                etapas[nombre] += (time.perf_counter() - inicio) * 1000
        return envoltura

    ep._rasterizar = cronometrar("rasterizado", ep._rasterizar)
    ep.preprocesar_imagen = cronometrar("preprocesamiento", ep.preprocesar_imagen)
    ep._tesseract = cronometrar("tesseract", ep._tesseract)

    resultados = []
    for documento in documentos:
        with open(documento["ruta"], "rb") as f:
            contenido = f.read()
        tiempos, por_etapa, extraccion = [], [], None
        for _ in range(corridas):
            for k in etapas:
                etapas[k] = 0.0
            inicio = time.perf_counter()
            extraccion = ep.extraer_texto(contenido, texto_completo=True)
            tiempos.append((time.perf_counter() - inicio) * 1000)
            por_etapa.append(dict(etapas))
        resultados.append({
            "documento": documento["nombre"], "paginas": extraccion.total_paginas,
            "paginas_ocr": extraccion.paginas_ocr,
            "metodo": extraccion.metodo_extraccion, "confianza": round(extraccion.confidence_score, 3),
            "corridas_ms": [round(t) for t in tiempos],
            "mediana_ms": round(statistics.median(tiempos)), "min_ms": round(min(tiempos)),
            "max_ms": round(max(tiempos)),
            "etapas_mediana_ms": {k: round(statistics.median(e[k] for e in por_etapa)) for k in etapas},
        })
    return resultados


def _en_subproceso(configuracion: str, documentos: list[dict[str, str]], corridas: int) -> dict[str, Any]:
    entorno = dict(os.environ, PYTHONIOENCODING="utf-8", **CONFIGURACIONES[configuracion])
    salida = subprocess.run(
        [sys.executable, "-m", "evaluacion.benchmark_extraccion", "--proceso", json.dumps(documentos),
         "--corridas", str(corridas)],
        cwd=_SERVICIO, env=entorno, capture_output=True, text=True, encoding="utf-8", timeout=7200,
    )
    if salida.returncode != 0:
        raise RuntimeError(f"La configuración {configuracion} falló:\n{salida.stderr[-2000:]}")
    return json.loads(salida.stdout.strip().splitlines()[-1])


# ── Documento con sellos ────────────────────────────────────────────
def contrato_con_sellos(destino: str) -> str:
    """El contrato de 20 páginas escaneado a color, con un sello en tinta en las páginas 1, 5, 9, 13 y 17."""
    import cv2
    import fitz
    import numpy as np

    from evaluacion import gold_standard as gs

    azar = np.random.default_rng(20261001)
    salida = fitz.open()
    with fitz.open(os.path.join(_DOCUMENTOS, "gs-cont-ext.pdf")) as origen:
        for numero, pagina in enumerate(origen):
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(200 / 72, 200 / 72), colorspace=fitz.csRGB)
            rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
            bgr = rgb[:, :, ::-1].copy()
            if numero % 4 == 0:
                gs._sello(bgr, azar)
            degradada = gs.degradar_como_escaneo(bgr, semilla=20261001 + numero)
            _, jpeg = cv2.imencode(".jpg", degradada, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            hoja = salida.new_page(width=pagina.rect.width, height=pagina.rect.height)
            hoja.insert_image(hoja.rect, stream=jpeg.tobytes())
    salida.save(destino, garbage=3, deflate=True)
    salida.close()
    return destino


# ── RNF-02 completo: Nivel 3 en frío + Nivel 4 con Groq ─────────────
def auditorias_reales(n: int) -> list[dict[str, Any]]:
    from evaluacion import documento_extenso, entorno

    with open(documento_extenso.RUTA_ANOTACION, encoding="utf-8") as f:
        caso = next(c for c in json.load(f)["casos"] if c["rendicion"] == "ESCANEADO")
    resultados = []
    for i in range(n):
        if i:
            time.sleep(ESPERA_ENTRE_AUDITORIAS_S)   # sin contención de cuota (§7.3): un minuto nuevo de Groq
        casete = os.path.join(tempfile.mkdtemp(prefix="plurione-rnf02-"), "casete.json")
        # Sin el presupuesto del grabador: su espera no existe en el servicio y falseaba la latencia.
        with entorno.Entorno([caso], casete, entorno.GRABAR, limitar_tokens=False) as e:
            cliente = e.cliente()
            inicio = time.perf_counter()
            r = cliente.post("/api/v1/ai/analisis-semantico", json={
                "documento_id": caso["id"], "rfc_titular": caso["titular"]["rfc"],
                "razon_social_titular": caso["titular"]["razon_social"], "usuario": "benchmark"})
            total = (time.perf_counter() - inicio) * 1000
            if r.status_code != 200 or e.core.diferidos:
                raise RuntimeError(f"La auditoría respondió {r.status_code}: {r.text[:300]}")
            cuerpo = r.json()
            resultados.append({
                "corrida": i + 1, "total_ms": round(total), "tiempos_ms": cuerpo.get("tiempos_ms"),
                "consultas_groq": len(e.casete.consultas),
                "latencia_groq_ms": [c["latencia_ms"] for c in e.casete.consultas],
                "tokens": sum((c["uso"] or {}).get("total_tokens") or 0 for c in e.casete.consultas),
                "estatus": cuerpo.get("estatus_preliminar"),
            })
        print(f"[RNF-02] auditoría {i + 1}: {resultados[-1]['total_ms']} ms {resultados[-1]['tiempos_ms']} "
              f"({resultados[-1]['tokens']} tokens)", flush=True)
    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark del RNF-02 (§7.3).")
    parser.add_argument("--proceso", help=argparse.SUPPRESS)
    parser.add_argument("--corridas", type=int, default=CORRIDAS)
    parser.add_argument("--actas", nargs="*", default=[], help="Actas reales escaneadas (no se versionan)")
    parser.add_argument("--nivel4", type=int, default=0, help="Auditorías reales con Groq (≈ 7,000 tokens cada una)")
    parser.add_argument("--solo-definitiva", action="store_true")
    parser.add_argument("--sin-nivel3", action="store_true",
                        help="Solo las auditorías de --nivel4 (corrida aparte, por la cuota diaria de Groq)")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if args.proceso:
        print(json.dumps(_medir_configuracion(json.loads(args.proceso), args.corridas)))
        return 0

    temporal = tempfile.mkdtemp(prefix="plurione-rnf02-")
    documentos = [] if args.sin_nivel3 else [
        {"nombre": "Contrato de 20 páginas, vectorial", "ruta": os.path.join(_DOCUMENTOS, "gs-cont-ext.pdf")},
        {"nombre": "Contrato de 20 páginas, escaneado", "ruta": os.path.join(_DOCUMENTOS, "gs-cont-ext-esc.pdf")},
        {"nombre": "Contrato de 20 páginas, escaneado a color con sellos en 5 páginas",
         "ruta": contrato_con_sellos(os.path.join(temporal, "con-sellos.pdf"))},
    ] + [{"nombre": f"Acta real escaneada {chr(65 + i)}", "ruta": ruta} for i, ruta in enumerate(args.actas)]

    configuraciones = () if args.sin_nivel3 else ("definitiva",) if args.solo_definitiva else ("definitiva", "anterior")
    nivel3 = {}
    for configuracion in configuraciones:
        nivel3[configuracion] = _en_subproceso(configuracion, documentos, args.corridas)
        for r in nivel3[configuracion]:
            print(f"[Nivel 3, {configuracion}] {r['documento']}: {r['paginas']} páginas, mediana {r['mediana_ms']} ms "
                  f"({r['min_ms']}–{r['max_ms']}), etapas {r['etapas_mediana_ms']}", flush=True)

    sys.path.insert(0, _SERVICIO)
    from pipelines import extraccion_pipeline
    resultado = {
        "ejecutado_en": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "equipo": {"sistema": platform.platform(), "procesador": platform.processor(),
                   "nucleos_logicos": os.cpu_count(), "python": platform.python_version()},
        "version_lectura": extraccion_pipeline.version_lectura(),
        "configuraciones": {k: CONFIGURACIONES[k] for k in configuraciones},
        "corridas": args.corridas,
        "nivel_3": nivel3,
    }
    if args.nivel4:
        auditorias = auditorias_reales(args.nivel4)
        totales = [a["total_ms"] for a in auditorias]
        resultado["rnf_02"] = {"auditorias": auditorias, "mediana_ms": round(statistics.median(totales)),
                               "meta_ms": META_MS, "cumple": statistics.median(totales) <= META_MS}
        print(f"[RNF-02] mediana {resultado['rnf_02']['mediana_ms']} ms frente a {META_MS} ms: "
              f"{'cumple' if resultado['rnf_02']['cumple'] else 'NO cumple'}")

    os.makedirs(DIRECTORIO_RESULTADOS, exist_ok=True)
    nombre = "rendimiento_rnf02.json" if args.sin_nivel3 else "rendimiento_extraccion.json"
    ruta = os.path.join(DIRECTORIO_RESULTADOS, nombre)
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"Resultado: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
