"""
Prueba de la lectura anticipada (RNF-02, PRD §21.9) por HTTP, sin el modelo ni tokens.

Levanta core, rules y ai-service aislados (puertos 8101 a 8103, base
``plurione_compliance_e2e`` recreada, bóveda y SQLite temporales) y recorre:

  1. Custodiar un documento escaneado → ``/anticipar`` responde 202 al instante →
     la lectura termina de fondo → ``/preparar`` (la auditoría) encuentra el
     texto completo en memoria, en milisegundos.
  2. Custodiar otro → ``/anticipar`` → ``/preparar`` de inmediato: la auditoría
     promueve la lectura de fondo y la espera, sin leer dos veces.

Usa los escaneos del Gold Standard, así que corre en cualquier clon. Código 0 si
todo pasa. Uso, desde la raíz:  python scripts/prueba_lectura_anticipada.py
"""
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import e2e_api as e2e  # noqa: E402
import sesion_api  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
DOCUMENTOS = RAIZ / "services" / "ai-service" / "evaluacion" / "gold_standard" / "documentos"
CORE, AI = "http://127.0.0.1:8101/api/v1", "http://127.0.0.1:8103/api/v1"
# Lo que tarda resolver el texto de un documento que ya se leyó de fondo.
MAXIMO_TRAS_ANTICIPAR_MS = 1500


def main() -> int:
    registros = Path(tempfile.mkdtemp(prefix="plurione_lectura_anticipada_"))
    procesos = e2e.levantar(
        {"rules-service": 8102, "core-service": 8101, "ai-service": 8103}, registros,
        entorno_extra={"EXTRACCIONES_DB_PATH": str(registros / "extracciones.sqlite3"), "PYTHONUNBUFFERED": "1"},
    )
    registro_ai = registros / "ai-service.log"
    api = sesion_api.sesion(CORE, "VALIDADOR")  # Módulo 7: la cuenta de demostración del validador
    fallas: list[str] = []

    def comprobar(condicion: bool, mensaje: str) -> None:
        print(f"{'OK   ' if condicion else 'FALLA'} {mensaje}")
        if not condicion:
            fallas.append(mensaje)

    try:
        titular = api.post(f"{CORE}/titulares", json={
            "rfc": "ANT010101AB1", "razon_social": "LECTURA ANTICIPADA PRUEBA S.A. DE C.V.", "tipo_persona": "MORAL",
        }, timeout=30).json()
        expediente = api.post(f"{CORE}/expedientes", json={"titular_id": titular["id"]}, timeout=30).json()

        def custodiar(nombre: str, tipo: str) -> str:
            r = api.post(f"{CORE}/documentos/upload", data={"expediente_id": expediente["id"], "tipo_documento": tipo},
                              files={"file": (nombre, (DOCUMENTOS / nombre).read_bytes(), "application/pdf")}, timeout=60)
            assert r.status_code == 201, r.text
            return r.json()["id"]

        def lecturas_listas() -> int:
            return registro_ai.read_text(encoding="utf-8", errors="ignore").count("Lectura anticipada lista")

        # 1. Custodiar → anticipar → la auditoría encuentra el texto listo.
        contrato = custodiar("gs-cont-ext-esc.pdf", "CONTRATO_SERVICIOS")
        inicio = time.perf_counter()
        r = api.post(f"{AI}/ai/documentos/{contrato}/anticipar", timeout=30)
        comprobar(r.status_code == 202 and r.json().get("programada") is True,
                  f"/anticipar responde 202 en {(time.perf_counter() - inicio) * 1000:.0f} ms")
        comprobar(api.post(f"{AI}/ai/documentos/{contrato}/anticipar", timeout=30).json().get("programada") is False,
                  "una segunda petición del mismo documento no programa otra lectura")
        limite = time.monotonic() + 300
        while lecturas_listas() < 1 and time.monotonic() < limite:
            time.sleep(0.5)
        comprobar(lecturas_listas() >= 1, f"la lectura de fondo termina ({time.perf_counter() - inicio:.1f} s)")
        inicio = time.perf_counter()
        p = api.post(f"{AI}/ai/documentos/{contrato}/preparar", timeout=300).json()
        ms = (time.perf_counter() - inicio) * 1000
        comprobar(ms < MAXIMO_TRAS_ANTICIPAR_MS and p["fuente_texto"] in ("memoria", "persistencia"),
                  f"la auditoría encuentra el texto listo ({ms:.0f} ms, {p['fuente_texto']}, "
                  f"{p['extraccion_nivel_3'].get('total_paginas')} páginas)")

        # 2. Auditar en cuanto se custodia: promueve la lectura de fondo y la espera.
        acta = custodiar("gs-acta-03-esc.pdf", "ACTA_CONSTITUTIVA")
        api.post(f"{AI}/ai/documentos/{acta}/anticipar", timeout=30)
        inicio = time.perf_counter()
        p = api.post(f"{AI}/ai/documentos/{acta}/preparar", timeout=300).json()
        comprobar(p["extraccion_nivel_3"].get("total_paginas", 0) > 0,
                  f"la auditoría inmediata espera la lectura de fondo ({time.perf_counter() - inicio:.1f} s, {p['fuente_texto']})")
        time.sleep(1)
        log = registro_ai.read_text(encoding="utf-8", errors="ignore")
        comprobar("Traceback" not in log and "AVISO: falló" not in log, "sin errores en el registro del ai-service")
    finally:
        e2e.detener(procesos)
    print("\nTodo pasó" if not fallas else f"\n{len(fallas)} fallas")
    return 0 if not fallas else 1


if __name__ == "__main__":
    sys.exit(main())
