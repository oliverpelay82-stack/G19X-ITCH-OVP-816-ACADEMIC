"""
Pruebas de extremo a extremo del API (P7, Q-b, PRD §21.7; HU-60).

Recorre por HTTP real, como lo hace la interfaz, el flujo completo con dos
titulares: uno con un RFC real (dígito verificador del SAT correcto) y otro
con un RFC ficticio, como los que usarán los agentes de PluriOne:

  salud → titular → expediente → carga del PDF (con folio de seguimiento)
  → carga repetida (409) → vigencia en el rules-service → dictamen del
  Nivel 4 simulado (sin Groq) → ratificación humana → expediente, índice y
  alertas → reportes PDF y Excel → ficha de custodia → cadena de la bitácora
  → el folio en la bitácora y en el registro de los dos servicios.

Aislamiento. Por omisión el script levanta su propio core-service y
rules-service (puertos 8101 y 8102) sobre la base ``plurione_compliance_e2e``,
que recrea en cada corrida, y una bóveda temporal: la bitácora y los
dictámenes son inmutables, así que lo que escribiera en ``plurione_compliance``
se quedaría para siempre junto a los expedientes reales. Con ``--core-url`` y
``--rules-url`` corre contra servicios ya levantados (por ejemplo, un entorno
de aceptación) y lo advierte.

Uso, desde la raíz:  python scripts/e2e_api.py   (termina con código 0 si todo pasa)
"""
from __future__ import annotations

import argparse
import io
import os
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import requests
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

RAIZ = Path(__file__).resolve().parent.parent
SERVICIOS = RAIZ / "services"
BD_E2E = "plurione_compliance_e2e"
TIMEOUT = 30

# BIM011108DJ5: RFC real publicado, con dígito verificador correcto.
# EMP260101AB1: inventado, con formato y fecha válidos y dígito que no coincide.
TITULARES = [
    {"rfc": "BIM011108DJ5", "razon_social": "Grupo Bimbo, S.A.B. de C.V.", "verificacion": "VERIFICADO"},
    {"rfc": "EMP260101AB1", "razon_social": "Empresa Ficticia de Pruebas, S.A. de C.V.",
     "verificacion": "DIGITO_NO_COINCIDE"},
]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


class FallaE2E(AssertionError):
    pass


def comprobar(condicion: bool, mensaje: str) -> None:
    if not condicion:
        raise FallaE2E(mensaje)


class Cliente:
    """Peticiones con folio propio: cada paso puede seguirse en la bitácora y en el registro."""

    def __init__(self, core: str, rules: str):
        self.core, self.rules = core.rstrip("/"), rules.rstrip("/")
        self.sesion = requests.Session()

    def llamar(self, metodo: str, url: str, esperado: int, *, folio: str | None = None, **kwargs) -> requests.Response:
        cabeceras = kwargs.pop("headers", {})
        if folio:
            cabeceras["X-Request-ID"] = folio
        r = self.sesion.request(metodo, url, headers=cabeceras, timeout=TIMEOUT, **kwargs)
        comprobar(r.status_code == esperado,
                  f"{metodo} {url} respondió {r.status_code} (se esperaba {esperado}): {r.text[:400]}")
        return r


# ═══════════════════ Entorno aislado ═══════════════════

def _recrear_bd(nombre: str) -> None:
    conexion = psycopg2.connect(dbname="postgres", user=os.getenv("DB_USER", "postgres"),
                                password=os.getenv("DB_PASSWORD", ""), host=os.getenv("DB_HOST", "127.0.0.1"),
                                port=os.getenv("DB_PORT", "5432"))
    conexion.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    with conexion.cursor() as cursor:
        cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s "
                       "AND pid <> pg_backend_pid()", (nombre,))
        cursor.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
        cursor.execute(f'CREATE DATABASE "{nombre}"')
    conexion.close()


# El rules-service primero: crea sus tablas y precarga el catálogo DOC-05 que el core consulta.
ORDEN_ARRANQUE = ("rules-service", "core-service", "ai-service")


def levantar(puertos: dict[str, int], registros: Path, bd: str = BD_E2E,
             entorno_extra: dict[str, str] | None = None) -> list[tuple[subprocess.Popen, Path]]:
    """
    Levanta los servicios de ``puertos`` sobre la base ``bd`` (recreada) y una
    bóveda temporal. También lo usa scripts/zap_api.py, con el ai-service.
    """
    load_dotenv(SERVICIOS / "core-service" / ".env")
    _recrear_bd(bd)
    entorno = dict(os.environ, DB_NAME=bd, STORAGE_VAULT_PATH=tempfile.mkdtemp(prefix="plurione_boveda_aislada_"),
                   REEVALUACION_INTERVALO_HORAS="0", PYTHONIOENCODING="utf-8")
    if "rules-service" in puertos:
        entorno["RULES_BASE_URL"] = f"http://127.0.0.1:{puertos['rules-service']}"
    if "core-service" in puertos:
        entorno["CORE_BASE_URL"] = f"http://127.0.0.1:{puertos['core-service']}"
    entorno.update(entorno_extra or {})
    entorno.pop("DATABASE_URL", None)
    procesos = []
    for servicio in (s for s in ORDEN_ARRANQUE if s in puertos):
        registro = registros / f"{servicio}.log"
        salida = open(registro, "w", encoding="utf-8")
        proceso = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", str(puertos[servicio])],
            cwd=SERVICIOS / servicio, env=entorno, stdout=salida, stderr=subprocess.STDOUT,
        )
        procesos.append((proceso, registro))
        esperar_salud(f"http://127.0.0.1:{puertos[servicio]}", servicio, proceso, registro)
    return procesos


def esperar_salud(base: str, servicio: str, proceso: subprocess.Popen, registro: Path, segundos: int = 90) -> None:
    limite = time.monotonic() + segundos
    while time.monotonic() < limite:
        if proceso.poll() is not None:
            raise FallaE2E(f"{servicio} terminó al arrancar:\n{registro.read_text(encoding='utf-8')[-2000:]}")
        try:
            if requests.get(f"{base}/api/v1/health", timeout=2).status_code == 200:
                return
        except requests.RequestException:
            pass
        time.sleep(0.5)
    raise FallaE2E(f"{servicio} no respondió en {segundos} s")


def detener(procesos: list[tuple[subprocess.Popen, Path]]) -> None:
    for proceso, _ in procesos:
        proceso.terminate()
    for proceso, _ in procesos:
        try:
            proceso.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proceso.kill()


# ═══════════════════ Datos de prueba ═══════════════════

def pdf_constancia(rfc: str, razon_social: str, emision: date) -> bytes:
    """Constancia de situación fiscal ficticia, generada al vuelo (texto vectorial)."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas

    memoria = io.BytesIO()
    hoja = canvas.Canvas(memoria, pagesize=letter)
    renglones = [
        "CONSTANCIA DE SITUACIÓN FISCAL", f"RFC: {rfc}", f"Denominación o razón social: {razon_social}",
        f"Lugar y fecha de emisión: Ciudad de México, a {emision.isoformat()}",
        "Documento generado para pruebas de extremo a extremo; no tiene validez fiscal.",
        f"Identificador de corrida: {uuid.uuid4()}",
    ]
    for i, renglon in enumerate(renglones):
        hoja.drawString(72, 720 - 18 * i, renglon)
    hoja.save()
    return memoria.getvalue()


# ═══════════════════ Flujo ═══════════════════

def flujo_titular(c: Cliente, datos: dict, hoy: date) -> dict:
    rfc = datos["rfc"]
    titular = c.llamar("POST", f"{c.core}/api/v1/titulares", 201,
                       json={"rfc": rfc, "razon_social": datos["razon_social"], "tipo_persona": "MORAL"}).json()
    comprobar(titular["rfc_verificacion"] == datos["verificacion"],
              f"{rfc}: rfc_verificacion {titular['rfc_verificacion']}, se esperaba {datos['verificacion']}")

    expediente = c.llamar("POST", f"{c.core}/api/v1/expedientes", 201, json={
        "titular_id": titular["id"], "tipo_expediente": "CORPORATIVO", "nombre": f"E2E {rfc}"}).json()
    comprobar(expediente["estado_cumplimiento"] == "NO_CONFORME", "Un expediente vacío no puede ser conforme")

    emision = hoy - timedelta(days=10)
    pdf = pdf_constancia(rfc, datos["razon_social"], emision)
    folio = f"e2e-{uuid.uuid4().hex[:20]}"
    carga = c.llamar("POST", f"{c.core}/api/v1/documentos/upload", 201, folio=folio,
                     data={"expediente_id": expediente["id"], "tipo_documento": "CSF_SAT", "usuario": "e2e"},
                     files={"file": ("constancia.pdf", pdf, "application/pdf")})
    comprobar(carga.headers.get("X-Request-ID") == folio, "El core no devolvió el folio de la carga")
    documento = carga.json()
    # PLUS-01: el mismo archivo en el mismo expediente se rechaza.
    c.llamar("POST", f"{c.core}/api/v1/documentos/upload", 409,
             data={"expediente_id": expediente["id"], "tipo_documento": "CSF_SAT"},
             files={"file": ("constancia.pdf", pdf, "application/pdf")})

    # Nivel 4 simulado: la vigencia la calcula el rules-service, como lo hace el ai-service.
    vigencia = c.llamar("POST", f"{c.rules}/api/v1/reglas/evaluar-vigencia", 200,
                        json={"tipo_documento": "CSF_SAT", "fecha_emision": emision.isoformat()}).json()
    comprobar(c.sesion.get(f"{c.core}/api/v1/health", timeout=TIMEOUT).ok, "core sin salud tras la carga")
    dictamen = c.llamar("POST", f"{c.core}/api/v1/dictamenes", 201, json={
        "documento_id": documento["id"], "estatus": "EN_REVISION", "nivel_confianza": 0.78,
        "requiere_revision_humana": True, "tipo_documento_detectado": "CSF_SAT", "rfc_detectado": rfc,
        "match_titular": True, "fecha_emision": emision.isoformat(), "vigencia": vigencia,
        "observaciones": ["Confianza en la banda de revisión humana (simulado, sin modelo)."],
        "modelo_utilizado": "simulado-e2e", "usuario": "e2e",
    }).json()
    comprobar(dictamen["estatus"] == "EN_REVISION", f"Dictamen registrado con estatus {dictamen['estatus']}")

    ratificado = c.llamar("POST", f"{c.core}/api/v1/dictamenes/{dictamen['id']}/ratificar", 200, json={
        "nuevo_estatus": "CONFORME", "usuario": "analista.e2e",
        "justificacion": "Constancia revisada contra el original: RFC y razón social coinciden.",
    }).json()
    comprobar(ratificado["estatus"] == "CONFORME" and ratificado["estatus_preliminar"] == "EN_REVISION",
              "La ratificación debe conservar el estatus preliminar (RN-05)")
    c.llamar("POST", f"{c.core}/api/v1/dictamenes/{dictamen['id']}/ratificar", 409, json={
        "nuevo_estatus": "NO_CONFORME", "usuario": "analista.e2e", "justificacion": "Segundo intento, debe fallar."})

    evaluacion = c.llamar("GET", f"{c.core}/api/v1/expedientes/{expediente['id']}", 200).json()["evaluacion"]
    estado_doc = next(d for d in evaluacion["documentos"] if d["documento_id"] == documento["id"])
    comprobar(estado_doc["estado"] == "CONFORME", f"La constancia ratificada quedó {estado_doc['estado']}")
    # Faltan el comprobante de domicilio y el acta (obligatorios críticos): no se aprueba.
    comprobar(evaluacion["estado"] == "NO_CONFORME", "Subir un solo documento nunca aprueba el expediente")
    comprobar({"COMP_DOMICILIO", "ACTA_CONSTITUTIVA"} <= set(evaluacion["faltantes"]),
              f"Faltantes inesperados: {evaluacion['faltantes']}")
    indice = evaluacion["indice_cumplimiento"]
    comprobar(indice and indice["cumplidas"] >= 1 and indice["porcentaje"] is not None and indice["bloqueado"],
              f"Índice de cumplimiento inesperado: {indice}")

    alertas = c.llamar("GET", f"{c.core}/api/v1/alertas", 200, params={"expediente_id": expediente["id"]}).json()
    comprobar(any(a["codigo"] == "DOCUMENTO_FALTANTE" and a["tipo_documento"] == "COMP_DOMICILIO" for a in alertas),
              "Falta la alerta del comprobante de domicilio")

    for formato, firma in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        r = c.llamar("GET", f"{c.core}/api/v1/reportes/expedientes/{expediente['id']}", 200, params={"formato": formato})
        comprobar(r.content.startswith(firma), f"El dictamen del expediente en {formato} no es un {formato}")
        r = c.llamar("GET", f"{c.core}/api/v1/reportes/documentos/{documento['id']}/custodia", 200,
                     params={"formato": formato})
        comprobar(r.content.startswith(firma), f"La ficha de custodia en {formato} no es un {formato}")

    eventos = c.llamar("GET", f"{c.core}/api/v1/bitacora", 200,
                       params={"documento_id": documento["id"], "evento": "INGESTA_DOCUMENTO"}).json()
    comprobar(eventos and eventos[0]["detalle"].get("id_peticion") == folio,
              "El evento de la carga no lleva el folio de su petición")
    return {"rfc": rfc, "expediente": expediente["codigo_expediente"], "folio": folio}


def ejecutar(c: Cliente, registros: Path | None) -> list[dict]:
    for base, servicio in ((c.core, "core-service"), (c.rules, "rules-service")):
        salud = c.llamar("GET", f"{base}/api/v1/health", 200).json()
        comprobar(salud.get("status") == "online", f"{servicio} no está en línea: {salud}")

    hoy = date.today()
    resultados = []
    for datos in TITULARES:
        resultados.append(flujo_titular(c, datos, hoy))
        print(f"  [OK] {datos['rfc']} ({datos['verificacion']}): {resultados[-1]['expediente']}")

    for formato, firma in (("pdf", b"%PDF"), ("xlsx", b"PK")):
        r = c.llamar("GET", f"{c.core}/api/v1/reportes/cumplimiento", 200, params={"formato": formato})
        comprobar(r.content.startswith(firma), f"El reporte global en {formato} no es un {formato}")

    cadena = c.llamar("GET", f"{c.core}/api/v1/bitacora/verificar-cadena", 200).json()
    comprobar(cadena["integra"] and cadena["sellada"], f"Cadena de la bitácora comprometida: {cadena['hallazgos']}")

    # El folio de la carga se sigue en el registro de los dos servicios: el core lo propagó al rules-service.
    if registros:
        for servicio in ("core-service", "rules-service"):
            texto = (registros / f"{servicio}.log").read_text(encoding="utf-8")
            for r in resultados:
                comprobar(f'"id_peticion": "{r["folio"]}"' in texto or f'"id_peticion":"{r["folio"]}"' in texto,
                          f"El registro de {servicio} no tiene el folio {r['folio']}")
    print(f"  [OK] Reporte global, cadena íntegra ({cadena['eventos_sellados']} eventos sellados) y folios seguidos")
    return resultados


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--core-url", help="Usar un core-service ya levantado (escribe en su base)")
    parser.add_argument("--rules-url", help="Usar un rules-service ya levantado")
    parser.add_argument("--puerto-core", type=int, default=8101)
    parser.add_argument("--puerto-rules", type=int, default=8102)
    args = parser.parse_args()

    procesos, registros = [], None
    try:
        if args.core_url or args.rules_url:
            comprobar(bool(args.core_url and args.rules_url), "Indique --core-url y --rules-url juntos")
            print("[!] Contra servicios ya levantados: los titulares, expedientes y eventos quedan en su base.")
            cliente = Cliente(args.core_url, args.rules_url)
        else:
            registros = Path(tempfile.mkdtemp(prefix="plurione_e2e_"))
            print(f"[*] Levantando core y rules sobre {BD_E2E} (registros en {registros})")
            procesos = levantar({"core-service": args.puerto_core, "rules-service": args.puerto_rules}, registros)
            cliente = Cliente(f"http://127.0.0.1:{args.puerto_core}", f"http://127.0.0.1:{args.puerto_rules}")
        inicio = time.monotonic()
        ejecutar(cliente, registros)
        print(f"[EXITO] Flujo de extremo a extremo completo en {time.monotonic() - inicio:.1f} s.")
        return 0
    except FallaE2E as exc:
        print(f"[FALLA] {exc}")
        for _, registro in procesos:
            print(f"--- últimas líneas de {registro.name} ---\n{registro.read_text(encoding='utf-8')[-1500:]}")
        return 1
    finally:
        detener(procesos)


if __name__ == "__main__":
    sys.exit(main())
