"""
Prueba de seguridad del API con OWASP ZAP (P7, Q-c, PRD §21.7; HU-61).

Corre ``zap-api-scan.py`` (imagen oficial ``zaproxy/zap-stable``) contra el
OpenAPI del core-service, del rules-service y del ai-service: explora cada
operación y lanza el escaneo activo (inyección, XSS, recorrido de rutas,
cabeceras, CORS…).

Aislamiento. El escaneo activo envía miles de peticiones de ataque, que en la
base real dejarían titulares y eventos basura para siempre (la bitácora es
inmutable). El script levanta los tres servicios sobre la base
``plurione_compliance_zap`` (recreada), una bóveda temporal y una SQLite
temporal del ai-service, **sin clave de Groq** (no se consume ni un token).

Criterio: un hallazgo alto (riesgo 3) sin justificación en ``JUSTIFICADOS``
hace fallar la corrida. Los medios y bajos se informan; cada uno se corrige o
se justifica en ``docs/resultados_validacion/seguridad_zap.md``.

Requisitos: Docker y PostgreSQL. Uso, desde la raíz:
    python scripts/zap_api.py [--minutos 10] [--salida docs/resultados_validacion/zap]
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_api  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
IMAGEN = "zaproxy/zap-stable"
BD_ZAP = "plurione_compliance_zap"
PUERTOS = {"core-service": 8201, "rules-service": 8202, "ai-service": 8203}
RIESGO = {3: "Alto", 2: "Medio", 1: "Bajo", 0: "Informativo"}

# Hallazgos altos aceptados por escrito (pluginid → motivo). Vacío: ninguno.
JUSTIFICADOS: dict[str, str] = {}


def _anfitrion() -> tuple[str, list[str]]:
    """En Linux (CI) el contenedor comparte la red del equipo; en Docker Desktop se usa host.docker.internal."""
    if platform.system() == "Linux":
        return "127.0.0.1", ["--network", "host"]
    return "host.docker.internal", []


def escanear(servicio: str, puerto: int, salida: Path, minutos: int) -> dict:
    anfitrion, red = _anfitrion()
    nombre = f"zap_{servicio}"
    comando = [
        "docker", "run", "--rm", *red, "-v", f"{salida}:/zap/wrk:rw", "-u", "root", IMAGEN,
        "zap-api-scan.py", "-t", f"http://{anfitrion}:{puerto}/openapi.json", "-f", "openapi",
        "-J", f"{nombre}.json", "-r", f"{nombre}.html", "-I",
        "-z", f"-config scanner.maxScanDurationInMins={minutos}",
    ]
    print(f"[*] ZAP sobre {servicio} (:{puerto}), escaneo activo de hasta {minutos} min…", flush=True)
    r = subprocess.run(comando, capture_output=True, text=True, encoding="utf-8", errors="replace")
    (salida / f"{nombre}.log").write_text(r.stdout + r.stderr, encoding="utf-8")
    informe = salida / f"{nombre}.json"
    if not informe.exists():
        raise RuntimeError(f"ZAP no produjo el informe de {servicio} (código {r.returncode}):\n{(r.stdout + r.stderr)[-2000:]}")
    return json.loads(informe.read_text(encoding="utf-8"))


def resumir(servicio: str, informe: dict) -> list[dict]:
    hallazgos = []
    for sitio in informe.get("site", []):
        for a in sitio.get("alerts", []):
            hallazgos.append({
                "servicio": servicio, "pluginid": str(a.get("pluginid")), "nombre": a.get("name") or a.get("alert"),
                "riesgo": int(a.get("riskcode", 0)), "confianza": a.get("confidence"),
                "instancias": len(a.get("instances", [])) or int(a.get("count", 0) or 0),
                "ejemplo": (a.get("instances") or [{}])[0].get("uri", ""),
            })
    return hallazgos


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--minutos", type=int, default=10, help="Tope del escaneo activo por servicio, en minutos")
    parser.add_argument("--salida", default=str(RAIZ / "docs" / "resultados_validacion" / "zap"))
    parser.add_argument("--servicios", nargs="*", default=list(PUERTOS))
    args = parser.parse_args()

    salida = Path(args.salida).resolve()
    salida.mkdir(parents=True, exist_ok=True)
    registros = Path(tempfile.mkdtemp(prefix="plurione_zap_"))
    entorno_ai = {
        "GROQ_API_KEY": "", "GROQ_BASE_URL": "http://127.0.0.1:9/sin-proveedor",
        "EXTRACCIONES_DB_PATH": str(registros / "extracciones.sqlite3"), "DIFERIDOS_INTERVALO_MINUTOS": "0",
    }
    # Siempre los tres: el ai-service consulta al core y al rules-service.
    print(f"[*] Levantando los tres servicios sobre {BD_ZAP} (registros en {registros})")
    procesos = e2e_api.levantar(PUERTOS, registros, bd=BD_ZAP, entorno_extra=entorno_ai)
    try:
        hallazgos = []
        for servicio in args.servicios:
            hallazgos += resumir(servicio, escanear(servicio, PUERTOS[servicio], salida, args.minutos))
    finally:
        e2e_api.detener(procesos)

    (salida / "resumen.json").write_text(json.dumps(hallazgos, ensure_ascii=False, indent=2), encoding="utf-8")
    por_riesgo = defaultdict(list)
    for h in sorted(hallazgos, key=lambda h: (-h["riesgo"], h["servicio"], h["nombre"])):
        por_riesgo[h["riesgo"]].append(h)
        print(f"  [{RIESGO[h['riesgo']]}] {h['servicio']}: {h['nombre']} (plugin {h['pluginid']}, "
              f"{h['instancias']} instancias) {h['ejemplo']}")
    altos = [h for h in por_riesgo[3] if h["pluginid"] not in JUSTIFICADOS]
    print(f"[=] Altos: {len(por_riesgo[3])} ({len(altos)} sin justificar) · Medios: {len(por_riesgo[2])} · "
          f"Bajos: {len(por_riesgo[1])} · Informativos: {len(por_riesgo[0])}. Informes en {salida}")
    return 1 if altos else 0


if __name__ == "__main__":
    sys.exit(main())
