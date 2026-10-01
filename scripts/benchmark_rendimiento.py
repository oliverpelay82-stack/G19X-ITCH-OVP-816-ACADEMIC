"""
Benchmark de rendimiento del core (docs/VALIDACION_CUANTITATIVA.md §7.2 y §7.4).

RNF-01 (evaluación determinista de un expediente completo, p95 ≤ 2 s):
  * Expedientes jurídicos sintéticos de 3, 8 y 15 documentos, cada uno con su
    dictamen, el anexo del contrato (RIE-02) y un contrato cuyo firmante se
    coteja con el apoderado del poder (RN-03).
  * 5 peticiones de calentamiento y 100 medidas, secuenciales, de
    ``GET /api/v1/expedientes/{id}``; la misma serie con una lectura OCR del
    contrato escaneado de 20 páginas en curso (los procesos de OCR que usa una
    auditoría), y ``motor/cumplimiento.reevaluar`` dentro del proceso para
    separar el costo de red.
  * ``GET /api/v1/expedientes`` con 30 expedientes, como estrés.

RNF-03 (≥ 50 peticiones simultáneas sin degradación ni pérdida):
  * 50 peticiones liberadas a la vez por una barrera, en tres escenarios:
    ``GET /health``, ``GET /expedientes/{id}`` sobre 10 expedientes y 50 cargas
    de documentos distintos en 10 expedientes; cada uno contra su serie
    secuencial de 50 (degradación = p95 concurrente / p95 secuencial).
  * Pérdida de transacciones: documentos creados = cargas con 201, eventos
    INGESTA_DOCUMENTO = cargas aceptadas y cadena de la bitácora íntegra.

Aislamiento: levanta su propio core y rules (puertos 8111 y 8112) sobre
``plurione_compliance_bench``, recreada en cada corrida, como scripts/e2e_api.py.
No llama a Groq: los dictámenes se registran como lo hace el ai-service.

Uso, desde la raíz:  python scripts/benchmark_rendimiento.py
"""
from __future__ import annotations

import argparse
import io
import json
import os
import platform
import statistics
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_api import SERVICIOS, detener, levantar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
BD_BENCH = "plurione_compliance_bench"
RESULTADOS = RAIZ / "docs" / "resultados_validacion" / "rendimiento.json"
DOCUMENTO_EXTENSO = SERVICIOS / "ai-service" / "evaluacion" / "gold_standard" / "documentos" / "gs-cont-ext-esc.pdf"
TIMEOUT = 60
CALENTAMIENTO, MEDIDAS, SIMULTANEAS = 5, 100, 50
META_P95_MS = 2000

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TITULAR = {"rfc": "PLU180514AB3", "razon_social": "PLURIONE S.A. DE C.V.", "tipo_persona": "MORAL"}
APODERADA = "María Elena Ruiz Soto"
# Composición de cada expediente jurídico: los obligatorios (contrato con su anexo, NDA y
# poder) y, para llegar al tamaño, otros tipos del DOC-02. Cada tipo una sola vez: una
# segunda carga del mismo tipo es una versión (RN-04) y no agranda la evaluación.
_TIPOS = ["CONTRATO_SERVICIOS", "ANEXO_CONTRATO", "PODER_NOTARIAL", "ACUERDO_CONFIDENCIALIDAD",
          "CONVENIO_MODIFICATORIO", "DICTAMEN_PERICIAL", "CSF_SAT", "OPINION_CUMPLIMIENTO", "COMP_DOMICILIO",
          "ACTA_CONSTITUTIVA", "ESTATUTOS_SOCIALES", "ACTA_ASAMBLEA", "AVISO_PRIVACIDAD", "ESTADO_CUENTA",
          "CEDULA_RFC"]
COMPOSICION = {3: _TIPOS[:3], 8: _TIPOS[:8], 15: _TIPOS[:15]}


def _ms(inicio: float) -> float:
    return (time.perf_counter() - inicio) * 1000


def _percentil(valores: list[float], p: float) -> float:
    ordenados = sorted(valores)
    posicion = (len(ordenados) - 1) * p / 100
    abajo, arriba = int(posicion), min(int(posicion) + 1, len(ordenados) - 1)
    return ordenados[abajo] + (ordenados[arriba] - ordenados[abajo]) * (posicion - abajo)


def resumen(latencias: list[float]) -> dict[str, float]:
    return {"n": len(latencias), "p50_ms": round(_percentil(latencias, 50), 1),
            "p95_ms": round(_percentil(latencias, 95), 1), "p99_ms": round(_percentil(latencias, 99), 1),
            "max_ms": round(max(latencias), 1), "media_ms": round(statistics.fmean(latencias), 1)}


def pdf(titulo: str) -> bytes:
    """PDF vectorial ficticio y único (su huella no se repite: PLUS-01 rechazaría un duplicado)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    memoria = io.BytesIO()
    hoja = canvas.Canvas(memoria, pagesize=letter)
    for i, renglon in enumerate(["DOCUMENTO DE PRUEBA - DATOS FICTICIOS", titulo, f"RFC: {TITULAR['rfc']}",
                                 f"Identificador: {uuid.uuid4()}"]):
        hoja.drawString(72, 720 - 18 * i, renglon)
    hoja.save()
    return memoria.getvalue()


class Banco:
    def __init__(self, core: str, rules: str):
        self.core, self.rules = core, rules
        self.sesion = requests.Session()

    def _ok(self, r: requests.Response, esperado: int) -> dict:
        if r.status_code != esperado:
            raise RuntimeError(f"{r.request.method} {r.url} respondió {r.status_code}: {r.text[:300]}")
        return r.json()

    def titular(self) -> str:
        return self._ok(self.sesion.post(f"{self.core}/api/v1/titulares", json=TITULAR, timeout=TIMEOUT), 201)["id"]

    def expediente(self, titular_id: str, nombre: str, tipo: str = "JURIDICO") -> str:
        return self._ok(self.sesion.post(f"{self.core}/api/v1/expedientes", timeout=TIMEOUT, json={
            "titular_id": titular_id, "tipo_expediente": tipo, "nombre": nombre}), 201)["id"]

    def cargar(self, expediente_id: str, tipo: str, sesion: requests.Session | None = None) -> requests.Response:
        return (sesion or self.sesion).post(
            f"{self.core}/api/v1/documentos/upload", timeout=TIMEOUT,
            data={"expediente_id": expediente_id, "tipo_documento": tipo, "usuario": "benchmark"},
            files={"file": (f"{tipo.lower()}.pdf", pdf(tipo), "application/pdf")})

    def dictaminar(self, documento_id: str, tipo: str, hoy: date) -> None:
        emision = hoy - timedelta(days=15)
        vigencia = self._ok(self.sesion.post(f"{self.rules}/api/v1/reglas/evaluar-vigencia", timeout=TIMEOUT, json={
            "tipo_documento": tipo, "fecha_emision": emision.isoformat()}), 200)
        representacion = None
        if tipo == "CONTRATO_SERVICIOS":
            representacion = {"rol": "FIRMANTES", "personas": [
                {"nombre": APODERADA, "cargo": "Apoderada legal", "cita": f"{APODERADA}, Apoderada legal",
                 "cita_verificada": True, "empresa": TITULAR["razon_social"]}]}
        elif tipo == "PODER_NOTARIAL":
            representacion = {"rol": "APODERADOS", "personas": [
                {"nombre": APODERADA, "cargo": "Apoderada", "cita": f"poder general a favor de {APODERADA}",
                 "cita_verificada": True, "facultades": "pleitos y cobranzas, actos de administración"}]}
        self._ok(self.sesion.post(f"{self.core}/api/v1/dictamenes", timeout=TIMEOUT, json={
            "documento_id": documento_id, "estatus": "CONFORME", "nivel_confianza": 0.92,
            "requiere_revision_humana": False, "tipo_documento_detectado": tipo, "rfc_detectado": TITULAR["rfc"],
            "match_titular": True, "fecha_emision": emision.isoformat(), "vigencia": vigencia,
            "observaciones": ["Dictamen sintético del benchmark (sin modelo)."], "modelo_utilizado": "benchmark",
            "representacion": representacion, "usuario": "benchmark"}), 201)

    def poblar(self, titular_id: str, tamano: int, nombre: str, hoy: date) -> str:
        expediente_id = self.expediente(titular_id, nombre)
        for tipo in COMPOSICION[tamano]:
            documento = self._ok(self.cargar(expediente_id, tipo), 201)
            self.dictaminar(documento["id"], tipo, hoy)
        return expediente_id

    def medir_get(self, url: str, n: int = MEDIDAS) -> list[float]:
        for _ in range(CALENTAMIENTO):
            self._ok(self.sesion.get(url, timeout=TIMEOUT), 200)
        latencias = []
        for _ in range(n):
            inicio = time.perf_counter()
            self._ok(self.sesion.get(url, timeout=TIMEOUT), 200)
            latencias.append(_ms(inicio))
        return latencias


# ═══════════════════ RNF-01 ═══════════════════

_REEVALUAR_EN_PROCESO = r"""
import json, sys, time
from config.database import SessionLocal
from models.expediente import Expediente
from motor import cumplimiento
ids, calentamiento, medidas = json.loads(sys.argv[1]), int(sys.argv[2]), int(sys.argv[3])
resultado = {}
db = SessionLocal()
for expediente_id in ids:
    latencias = []
    for i in range(calentamiento + medidas):
        expediente = db.get(Expediente, expediente_id)
        inicio = time.perf_counter()
        cumplimiento.reevaluar(db, expediente, causa="BENCHMARK", usuario="benchmark")
        if i >= calentamiento:
            latencias.append((time.perf_counter() - inicio) * 1000)
        db.rollback()   # nada queda escrito: solo se mide la evaluación y la sincronización
    resultado[expediente_id] = latencias
db.close()
print(json.dumps(resultado))
"""

_OCR_EN_CURSO = r"""
import sys
from pipelines import extraccion_pipeline
contenido = open(sys.argv[1], "rb").read()
while True:
    extraccion_pipeline.extraer_texto(contenido, "contrato.pdf", forzar_ocr=True, texto_completo=True)
"""


def reevaluar_en_proceso(entorno: dict[str, str], ids: list[str]) -> dict[str, list[float]]:
    salida = subprocess.run([sys.executable, "-c", _REEVALUAR_EN_PROCESO, json.dumps(ids), str(CALENTAMIENTO),
                             str(MEDIDAS)], cwd=SERVICIOS / "core-service", env=entorno, capture_output=True,
                            text=True, encoding="utf-8", timeout=1800)
    if salida.returncode != 0:
        raise RuntimeError(f"reevaluar en proceso falló:\n{salida.stderr[-2000:]}")
    return json.loads(salida.stdout.strip().splitlines()[-1])


def rnf01(b: Banco, titular_id: str, hoy: date, entorno: dict[str, str]) -> dict:
    expedientes = {tamano: b.poblar(titular_id, tamano, f"Benchmark {tamano} documentos", hoy)
                   for tamano in COMPOSICION}
    for tamano, expediente_id in expedientes.items():
        respuesta = b.sesion.get(f"{b.core}/api/v1/expedientes/{expediente_id}", timeout=TIMEOUT)
        evaluacion = b._ok(respuesta, 200)["evaluacion"]
        if len(evaluacion["documentos"]) != tamano:
            raise RuntimeError(f"El expediente de {tamano} evalúa {len(evaluacion['documentos'])} documentos")
        cotejos = [c["estado"] for c in evaluacion.get("representacion") or []]
        if "ACREDITADO" not in cotejos:
            raise RuntimeError(f"El expediente de {tamano} no cotejó al firmante con el apoderado (RN-03): {cotejos}")
        print(f"  expediente de {tamano}: {len(evaluacion['documentos'])} documentos, estado {evaluacion['estado']}, "
              f"cotejo RN-03: {cotejos}")

    resultado = {"consulta": {}, "consulta_con_ocr": {}, "en_proceso": {}}
    for tamano, expediente_id in expedientes.items():
        resultado["consulta"][tamano] = resumen(b.medir_get(f"{b.core}/api/v1/expedientes/{expediente_id}"))
        print(f"  GET expediente de {tamano} documentos: {resultado['consulta'][tamano]}")

    en_proceso = reevaluar_en_proceso(entorno, list(expedientes.values()))
    for tamano, expediente_id in expedientes.items():
        resultado["en_proceso"][tamano] = resumen(en_proceso[expediente_id])
        print(f"  reevaluar en proceso, {tamano} documentos: {resultado['en_proceso'][tamano]}")

    # Con una lectura OCR de 20 páginas en curso, como durante una auditoría escaneada.
    ocr = subprocess.Popen([sys.executable, "-c", _OCR_EN_CURSO, str(DOCUMENTO_EXTENSO)],
                           cwd=SERVICIOS / "ai-service", env=dict(os.environ, PYTHONIOENCODING="utf-8"),
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        time.sleep(8)   # que el pool de OCR ya esté ocupando los núcleos
        for tamano, expediente_id in expedientes.items():
            resultado["consulta_con_ocr"][tamano] = resumen(b.medir_get(f"{b.core}/api/v1/expedientes/{expediente_id}"))
            print(f"  GET con OCR en curso, {tamano} documentos: {resultado['consulta_con_ocr'][tamano]}")
    finally:
        ocr.kill()
        ocr.wait()

    # Estrés: el listado con 30 expedientes (los 3 medidos más 27 de 3 documentos).
    for i in range(27):
        b.poblar(titular_id, 3, f"Benchmark relleno {i + 1}", hoy)
    resultado["listado_30"] = resumen(b.medir_get(f"{b.core}/api/v1/expedientes", n=30))
    print(f"  GET /expedientes con 30: {resultado['listado_30']}")
    resultado["cumple"] = all(r["p95_ms"] <= META_P95_MS for grupo in ("consulta", "consulta_con_ocr")
                              for r in resultado[grupo].values())
    return resultado


# ═══════════════════ RNF-03 ═══════════════════

def _simultaneas(funciones: list) -> tuple[list[float], list[int]]:
    """Ejecuta las funciones a la vez, liberadas por una barrera; devuelve latencias y códigos."""
    barrera = threading.Barrier(len(funciones))

    def correr(funcion):
        sesion = requests.Session()
        barrera.wait()
        inicio = time.perf_counter()
        try:
            codigo = funcion(sesion).status_code
        except requests.RequestException:
            codigo = 0
        return _ms(inicio), codigo

    with ThreadPoolExecutor(max_workers=len(funciones)) as ejecutor:
        resultados = list(ejecutor.map(correr, funciones))
    return [r[0] for r in resultados], [r[1] for r in resultados]


def _secuenciales(funciones: list) -> tuple[list[float], list[int]]:
    sesion = requests.Session()
    latencias, codigos = [], []
    for funcion in funciones:
        inicio = time.perf_counter()
        codigos.append(funcion(sesion).status_code)
        latencias.append(_ms(inicio))
    return latencias, codigos


def _escenario(nombre: str, secuencial: tuple[list[float], list[int]], simultaneo: tuple[list[float], list[int]],
               esperado: int) -> dict:
    sec, sim = resumen(secuencial[0]), resumen(simultaneo[0])
    r = {"secuencial": sec, "simultaneo": sim,
         "degradacion_p95": round(sim["p95_ms"] / sec["p95_ms"], 2) if sec["p95_ms"] else None,
         "respuestas_5xx": sum(1 for c in simultaneo[1] + secuencial[1] if c >= 500),
         "sin_respuesta": sum(1 for c in simultaneo[1] if c == 0),
         "respuestas_esperadas": sum(1 for c in simultaneo[1] if c == esperado)}
    print(f"  {nombre}: secuencial p95 {sec['p95_ms']} ms, simultáneo p95 {sim['p95_ms']} ms "
          f"(×{r['degradacion_p95']}), 5xx {r['respuestas_5xx']}, "
          f"{r['respuestas_esperadas']}/{SIMULTANEAS} con {esperado}")
    return r


def rnf03(b: Banco, titular_id: str, hoy: date) -> dict:
    core = b.core
    salud = [lambda s: s.get(f"{core}/api/v1/health", timeout=TIMEOUT)] * SIMULTANEAS
    resultado = {"health": _escenario("50 × GET /health", _secuenciales(salud), _simultaneas(salud), 200)}

    consultados = [b.poblar(titular_id, 3, f"Benchmark concurrencia {i + 1}", hoy) for i in range(10)]
    consultas = [lambda s, e=consultados[i % 10]: s.get(f"{core}/api/v1/expedientes/{e}", timeout=TIMEOUT)
                 for i in range(SIMULTANEAS)]
    resultado["consulta"] = _escenario("50 × GET /expedientes/{id}", _secuenciales(consultas),
                                       _simultaneas(consultas), 200)

    # Cargas: 50 secuenciales en 10 expedientes y 50 simultáneas en otros 10.
    destinos_sec = [b.expediente(titular_id, f"Benchmark cargas secuenciales {i + 1}") for i in range(10)]
    destinos_sim = [b.expediente(titular_id, f"Benchmark cargas simultáneas {i + 1}") for i in range(10)]
    eventos_antes = _eventos_ingesta(b)
    cargas_sec = [lambda s, e=destinos_sec[i % 10]: b.cargar(e, "CONTRATO_SERVICIOS", s) for i in range(SIMULTANEAS)]
    cargas_sim = [lambda s, e=destinos_sim[i % 10]: b.cargar(e, "CONTRATO_SERVICIOS", s) for i in range(SIMULTANEAS)]
    secuencial = _secuenciales(cargas_sec)
    simultaneo = _simultaneas(cargas_sim)
    resultado["cargas"] = _escenario("50 cargas", secuencial, simultaneo, 201)

    aceptadas = sum(1 for c in secuencial[1] + simultaneo[1] if c == 201)
    # Filas en la base, versiones incluidas: la evaluación solo lista la versión vigente de cada tipo.
    documentos = _documentos_en_bd(destinos_sec + destinos_sim)
    eventos = _eventos_ingesta(b) - eventos_antes
    cadena = b._ok(b.sesion.get(f"{core}/api/v1/bitacora/verificar-cadena", timeout=TIMEOUT), 200)
    resultado["transacciones"] = {"cargas_aceptadas": aceptadas, "documentos_creados": documentos,
                                  "eventos_ingesta": eventos, "cadena_integra": cadena.get("integra"),
                                  "cadena_sellada": cadena.get("sellada"),
                                  "eventos_sellados": cadena.get("eventos_sellados")}
    print(f"  transacciones: {resultado['transacciones']}")
    t = resultado["transacciones"]
    resultado["cumple"] = (
        all(resultado[e]["respuestas_5xx"] == 0 and resultado[e]["sin_respuesta"] == 0
            for e in ("health", "consulta", "cargas"))
        and t["cargas_aceptadas"] == t["documentos_creados"] == t["eventos_ingesta"] == 2 * SIMULTANEAS
        and bool(t["cadena_integra"]) and resultado["consulta"]["simultaneo"]["p95_ms"] <= META_P95_MS
    )
    return resultado


def _documentos_en_bd(expedientes: list[str]) -> int:
    import psycopg2

    conexion = psycopg2.connect(dbname=BD_BENCH, user=os.getenv("DB_USER", "postgres"),
                                password=os.getenv("DB_PASSWORD", ""), host=os.getenv("DB_HOST", "127.0.0.1"),
                                port=os.getenv("DB_PORT", "5432"))
    with conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM documentos WHERE expediente_id = ANY(%s)", (expedientes,))
        total = cursor.fetchone()[0]
    conexion.close()
    return total


def _eventos_ingesta(b: Banco) -> int:
    return len(b._ok(b.sesion.get(f"{b.core}/api/v1/bitacora", timeout=TIMEOUT,
                                  params={"evento": "INGESTA_DOCUMENTO", "limite": 500}), 200))


def _equipo() -> dict:
    datos = {"sistema": platform.platform(), "procesador": platform.processor(), "nucleos_logicos": os.cpu_count(),
             "python": platform.python_version()}
    try:
        import psutil
        datos["ram_gb"] = round(psutil.virtual_memory().total / 2**30, 1)
    except ImportError:
        pass
    try:
        version = subprocess.run(["psql", "--version"], capture_output=True, text=True, timeout=10).stdout.strip()
        datos["postgresql_cliente"] = version or None
    except (OSError, subprocess.SubprocessError):
        pass
    return datos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--puerto-core", type=int, default=8111)
    parser.add_argument("--puerto-rules", type=int, default=8112)
    args = parser.parse_args()
    registros = Path(tempfile.mkdtemp(prefix="plurione_bench_"))
    print(f"[*] Levantando core y rules sobre {BD_BENCH} (registros en {registros})")
    procesos = levantar({"core-service": args.puerto_core, "rules-service": args.puerto_rules}, registros, bd=BD_BENCH)
    try:
        b = Banco(f"http://127.0.0.1:{args.puerto_core}", f"http://127.0.0.1:{args.puerto_rules}")
        entorno = dict(os.environ, DB_NAME=BD_BENCH, RULES_BASE_URL=b.rules, PYTHONIOENCODING="utf-8")
        entorno.pop("DATABASE_URL", None)
        hoy = date.today()
        titular_id = b.titular()
        inicio = time.monotonic()
        print("[RNF-01] Evaluación determinista")
        r1 = rnf01(b, titular_id, hoy, entorno)
        print("[RNF-03] Concurrencia")
        r3 = rnf03(b, titular_id, hoy)
        resultado = {"ejecutado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                     "equipo": _equipo(), "base": BD_BENCH, "servicios": "locales (uvicorn, un proceso por servicio)",
                     "duracion_s": round(time.monotonic() - inicio, 1), "rnf_01": r1, "rnf_03": r3}
        RESULTADOS.parent.mkdir(parents=True, exist_ok=True)
        RESULTADOS.write_text(json.dumps(resultado, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"[*] RNF-01 {'cumple' if r1['cumple'] else 'NO cumple'}; "
              f"RNF-03 {'cumple' if r3['cumple'] else 'NO cumple'}")
        print(f"[*] Resultado: {RESULTADOS}")
        return 0
    finally:
        detener(procesos)


if __name__ == "__main__":
    sys.exit(main())
