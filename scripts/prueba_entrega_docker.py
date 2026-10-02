"""
Prueba de entrega: el sistema tal como lo recibirá PluriOne (RNF-11).

Clona el último commit en una carpeta temporal (lo que no está comprometido
no viaja), lo levanta con ``docker compose up --build`` en un proyecto propio
(``plurione_entrega``, con su base y sus volúmenes nuevos) y recorre el flujo
con datos ficticios:

  salud de los tres servicios y del frontend → empresa con RFC ficticio →
  expediente → carga de una constancia → auditoría → chat → semáforo (un
  expediente incompleto nunca se aprueba) → cadena de la bitácora → reportes
  PDF y Excel → ficha de custodia.

Sin ``--con-ia`` no usa la clave del proveedor: comprueba que la auditoría
responde 503 con la instrucción para configurarla. Con ``--con-ia`` toma
``GROQ_API_KEY`` del entorno o de ``services/ai-service/.env`` y hace una
auditoría y una pregunta reales (unos pocos miles de tokens); la clave solo se
escribe en el ``.env`` del clon temporal.

Al terminar baja los contenedores, borra sus volúmenes y el clon, salvo con
``--conservar``. Los puertos de docker-compose.yml (5433, 8001 a 8003 y 5173)
deben estar libres: detenga antes los servicios locales.

Uso, desde la raíz:  python scripts/prueba_entrega_docker.py [--con-ia] [--conservar]
Código 0 si todo pasa.
"""
from __future__ import annotations

import argparse
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import requests
from dotenv import dotenv_values

sys.path.insert(0, str(Path(__file__).resolve().parent))
from e2e_api import RAIZ, pdf_constancia  # noqa: E402

PROYECTO = "plurione_entrega"
PUERTOS = (5433, 8001, 8002, 8003, 5173)
B = {"core": "http://127.0.0.1:8001/api/v1", "rules": "http://127.0.0.1:8002/api/v1", "ai": "http://127.0.0.1:8003/api/v1"}
FRONTEND = "http://127.0.0.1:5173/"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

fallas: list[str] = []


def comprobar(condicion: bool, mensaje: str) -> None:
    print(f"{'OK   ' if condicion else 'FALLA'} {mensaje}", flush=True)
    if not condicion:
        fallas.append(mensaje)


def puertos_ocupados() -> list[int]:
    ocupados = []
    for puerto in PUERTOS:
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", puerto)) == 0:
                ocupados.append(puerto)
    return ocupados


def clave_ia() -> str:
    clave = os.getenv("GROQ_API_KEY") or dotenv_values(RAIZ / "services" / "ai-service" / ".env").get("GROQ_API_KEY")
    if not clave:
        raise SystemExit("--con-ia necesita GROQ_API_KEY en el entorno o en services/ai-service/.env")
    return clave


def compose(clon: Path, *args: str, salida=None) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", "compose", "-p", PROYECTO, *args], cwd=clon, stdout=salida, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace")


def esperar_servicios(segundos: int = 180) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        try:
            if all(requests.get(f"{u}/health", timeout=3).ok for u in B.values()) and requests.get(FRONTEND, timeout=3).ok:
                return
        except requests.RequestException:
            pass
        time.sleep(2)
    raise RuntimeError(f"Los servicios no respondieron en {segundos} s")


def recorrer(con_ia: bool) -> None:
    salud_ai = requests.get(f"{B['ai']}/health", timeout=15).json()
    comprobar(salud_ai.get("capacidades_operativas") is con_ia,
              f"ai-service {'operativo con' if con_ia else 'degradado sin'} clave de IA")
    comprobar(len(requests.get(f"{B['rules']}/reglas", timeout=15).json()) > 0, "catálogo de reglas precargado")

    rfc, razon = "EMP260101AB1", "Empresa Ficticia de Pruebas, S.A. de C.V."
    titular = requests.post(f"{B['core']}/titulares", timeout=15,
                            json={"rfc": rfc, "razon_social": razon, "tipo_persona": "MORAL"})
    comprobar(titular.status_code == 201, f"empresa con RFC ficticio ({titular.status_code})")
    expediente = requests.post(f"{B['core']}/expedientes", timeout=15,
                               json={"titular_id": titular.json()["id"], "tipo_expediente": "CORPORATIVO"}).json()
    carga = requests.post(f"{B['core']}/documentos/upload", timeout=30,
                          data={"expediente_id": expediente["id"], "tipo_documento": "CSF_SAT"},
                          files={"file": ("constancia.pdf", pdf_constancia(rfc, razon, date.today() - timedelta(days=5)),
                                          "application/pdf")})
    comprobar(carga.status_code == 201, f"carga de una constancia ficticia ({carga.status_code})")
    documento = carga.json()

    auditoria = requests.post(f"{B['ai']}/ai/analisis-semantico", timeout=180, json={
        "documento_id": documento["id"], "rfc_titular": rfc, "razon_social_titular": razon, "usuario": "prueba-entrega"})
    if con_ia:
        cuerpo = auditoria.json()
        comprobar(auditoria.status_code == 200 and (cuerpo.get("persistencia") or {}).get("guardado") is True,
                  f"auditoría real guardada ({auditoria.status_code}: {cuerpo.get('estatus_preliminar')})")
        chat = requests.post(f"{B['ai']}/ai/chat-documento", timeout=120,
                             json={"documento_id": documento["id"], "pregunta": "¿Cuál es el RFC del documento?"})
        comprobar(chat.status_code == 200 and rfc in chat.json().get("respuesta", ""), "el chat responde con el RFC")
    else:
        comprobar(auditoria.status_code == 503 and "no está configurado" in auditoria.json().get("detail", ""),
                  "sin clave, la auditoría responde 503 con la instrucción para configurarla")

    evaluacion = requests.get(f"{B['core']}/expedientes/{expediente['id']}", timeout=15).json()["evaluacion"]
    comprobar(evaluacion["estado"] != "CONFORME", f"un expediente incompleto no se aprueba ({evaluacion['estado']})")
    cadena = requests.get(f"{B['core']}/bitacora/verificar-cadena", timeout=15).json()
    comprobar(cadena["integra"], f"cadena de la bitácora íntegra ({cadena['eventos_sellados']} eventos)")
    for formato, firma in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        r = requests.get(f"{B['core']}/reportes/expedientes/{expediente['id']}", params={"formato": formato}, timeout=60)
        comprobar(r.ok and r.content.startswith(firma), f"reporte del expediente en {formato}")
    r = requests.get(f"{B['core']}/reportes/documentos/{documento['id']}/custodia", params={"formato": "pdf"}, timeout=60)
    comprobar(r.ok and r.content.startswith(b"%PDF"), "ficha de custodia en pdf")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prueba de entrega en Docker desde un clon limpio.")
    parser.add_argument("--con-ia", action="store_true", help="auditoría y chat reales con la clave de IA")
    parser.add_argument("--conservar", action="store_true", help="no bajar los contenedores ni borrar el clon")
    args = parser.parse_args()

    ocupados = puertos_ocupados()
    if ocupados:
        print(f"Puertos ocupados {ocupados}: detenga los servicios locales antes de la prueba.")
        return 2
    pendientes = subprocess.run(["git", "status", "--porcelain"], cwd=RAIZ, capture_output=True, text=True).stdout
    if pendientes.strip():
        print("Aviso: hay cambios sin comprometer; la prueba usa el último commit.\n")

    trabajo = Path(tempfile.mkdtemp(prefix="plurione_entrega_"))
    clon = trabajo / "motor"
    registro = trabajo / "docker.log"
    try:
        subprocess.run(["git", "clone", "-q", str(RAIZ), str(clon)], check=True)
        commit = subprocess.run(["git", "log", "--oneline", "-1"], cwd=clon, capture_output=True, text=True).stdout.strip()
        print(f"Clon limpio de {commit}")
        if args.con_ia:
            (clon / ".env").write_text(f"GROQ_API_KEY={clave_ia()}\n", encoding="utf-8")
        inicio = time.monotonic()
        with open(registro, "w", encoding="utf-8") as salida:
            construccion = compose(clon, "up", "-d", "--build", salida=salida)
        comprobar(construccion.returncode == 0, f"docker compose up --build ({time.monotonic() - inicio:.0f} s)")
        if construccion.returncode == 0:
            esperar_servicios()
            recorrer(args.con_ia)
    except Exception as exc:  # noqa: BLE001 — se reporta y se limpia igual
        comprobar(False, f"error inesperado: {exc}")
    finally:
        if args.conservar:
            print(f"\nSe conservan los contenedores ({PROYECTO}) y el clon en {clon}")
        else:
            compose(clon, "down", "-v", salida=subprocess.DEVNULL) if clon.exists() else None
            shutil.rmtree(trabajo, ignore_errors=True)
    if fallas:
        print(f"\n{len(fallas)} fallas" + ("" if args.conservar else " (registro de Docker borrado; repita con --conservar)"))
        return 1
    print("\nTodo pasó")
    return 0


if __name__ == "__main__":
    sys.exit(main())
