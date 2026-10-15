"""
Respaldo diario conjunto de la evidencia, con prueba de restauración (RNF-10).

Un paquete ``respaldo_AAAAMMDD_HHMMSS/`` reúne, en un mismo punto:

  base.dump           pg_dump (formato custom) de plurione_compliance: core y rules.
  boveda.zip          los binarios custodiados (storage_vault).
  extracciones.sqlite3  la SQLite del ai-service, copiada con la API de respaldo de SQLite.
  MANIFIESTO.json     SHA-256 y tamaño de cada pieza, último eslabón de la bitácora
                      antes del volcado y versiones.
  VERIFICACION.json   resultado de la prueba de restauración.

Corre con los servicios en marcha. El orden da la consistencia: primero el
volcado (una instantánea de la base en el instante T) y después la bóveda. La
bóveda solo agrega archivos (el único borrado del core deshace una carga que
nunca llegó a la base), así que lo copiado después de T es un superconjunto:
todo documento del volcado tiene su archivo. Lo mismo vale para la SQLite, que
es una caché indexada por huella.

Prueba de restauración (``verificar``, también al final de ``crear``): restaura
el volcado en una base temporal, recalcula la huella de cada documento contra
boveda.zip (RIE-03), verifica la cadena de la bitácora con el verificar_cadena
del core (PLUS-05) y que contenga el eslabón anotado en el manifiesto, y corre
PRAGMA integrity_check sobre la SQLite. Al terminar borra la base temporal.

Usos, desde la raíz del repositorio:
  python scripts/respaldo.py crear [--destino DIR] [--sin-verificar]
  python scripts/respaldo.py verificar RUTA_DEL_PAQUETE
  python scripts/respaldo.py programar [--hora 02:00] [--quitar]

Variables (las de conexión salen de services/core-service/.env):
  RESPALDO_DIR          destino (por omisión, la carpeta «respaldos» junto al
                        repositorio: los paquetes contienen los originales y no
                        deben quedar dentro del proyecto).
  RESPALDO_SECUNDARIO   segunda copia, dentro de la infraestructura (PRD §12.5).
  RESPALDO_RETENCION    paquetes verificados que se conservan (14).
  PG_BIN                carpeta de pg_dump y pg_restore, si no están en el PATH.
Código de salida 0 solo si el paquete quedó verificado.
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
from dotenv import load_dotenv
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT

RAIZ = Path(__file__).resolve().parent.parent
SERVICIOS = RAIZ / "services"
CORE = SERVICIOS / "core-service"
PIEZA_BASE, PIEZA_BOVEDA, PIEZA_SQLITE = "base.dump", "boveda.zip", "extracciones.sqlite3"
PREFIJO = "respaldo_"
NOMBRE_TAREA = "PluriOne-Respaldo-Motor"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


@dataclass
class Config:
    bd: str
    boveda: Path
    sqlite: Path
    destino: Path
    secundario: Path | None = None
    retencion: int = 14
    bd_restauracion: str = ""
    conexion: dict = field(default_factory=dict)

    def __post_init__(self):
        self.bd_restauracion = self.bd_restauracion or f"{self.bd}_restauracion"


def config_desde_entorno() -> Config:
    load_dotenv(CORE / ".env")
    secundario = os.getenv("RESPALDO_SECUNDARIO", "").strip()
    return Config(
        bd=os.getenv("DB_NAME", "plurione_compliance"),
        boveda=Path(os.getenv("STORAGE_VAULT_PATH") or RAIZ / "storage_vault"),
        sqlite=Path(os.getenv("EXTRACCIONES_DB_PATH") or SERVICIOS / "ai-service" / "data" / PIEZA_SQLITE),
        destino=Path(os.getenv("RESPALDO_DIR") or RAIZ.parent / "respaldos"),
        secundario=Path(secundario) if secundario else None,
        retencion=int(os.getenv("RESPALDO_RETENCION", "14")),
        conexion={"user": os.getenv("DB_USER", "postgres"), "password": os.getenv("DB_PASSWORD", ""),
                  "host": os.getenv("DB_HOST", "127.0.0.1"), "port": os.getenv("DB_PORT", "5432")},
    )


# ═══════════════════ Utilidades ═══════════════════

def sha256_archivo(ruta: Path) -> str:
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(1 << 20), b""):
            h.update(bloque)
    return h.hexdigest()


def binario_pg(nombre: str) -> str:
    """pg_dump o pg_restore: PG_BIN, el PATH o la instalación de PostgreSQL en Windows (la versión mayor más alta)."""
    exe = nombre + (".exe" if os.name == "nt" else "")
    if os.getenv("PG_BIN"):
        return str(Path(os.environ["PG_BIN"]) / exe)
    if shutil.which(nombre):
        return shutil.which(nombre)
    candidatos = sorted(glob.glob(f"C:/Program Files/PostgreSQL/*/bin/{exe}"),
                        key=lambda r: int(Path(r).parent.parent.name) if Path(r).parent.parent.name.isdigit() else 0)
    if candidatos:
        return candidatos[-1]
    raise FileNotFoundError(f"No se encontró {nombre}: agréguelo al PATH o defina PG_BIN.")


def _entorno_pg(cfg: Config) -> dict:
    return dict(os.environ, PGPASSWORD=cfg.conexion.get("password", ""), PGCLIENTENCODING="UTF8")


def _argumentos_pg(cfg: Config) -> list[str]:
    return ["-h", cfg.conexion.get("host", "127.0.0.1"), "-p", str(cfg.conexion.get("port", "5432")),
            "-U", cfg.conexion.get("user", "postgres")]


@contextmanager
def _conectar(cfg: Config, bd: str):
    """Conexión que se cierra al salir (el `with` de psycopg2 solo cierra la transacción)."""
    conexion = psycopg2.connect(dbname=bd, client_encoding="UTF8", **cfg.conexion)
    try:
        yield conexion
    finally:
        conexion.close()


def _ultimo_eslabon(cfg: Config, bd: str) -> dict | None:
    with _conectar(cfg, bd) as conexion, conexion.cursor() as cursor:
        cursor.execute("SELECT secuencia, hash_evento FROM bitacora_auditoria WHERE secuencia IS NOT NULL "
                       "ORDER BY secuencia DESC LIMIT 1")
        fila = cursor.fetchone()
    return {"secuencia": fila[0], "hash_evento": fila[1]} if fila else None


def _version_lectura() -> str | None:
    fuente = SERVICIOS / "ai-service" / "pipelines" / "extraccion_pipeline.py"
    m = re.search(r'^VERSION_PIPELINE\s*=\s*"([^"]+)"', fuente.read_text(encoding="utf-8"), re.M) if fuente.exists() else None
    return m.group(1) if m else None


def _recrear_bd(cfg: Config, nombre: str, crear: bool = True) -> None:
    with _conectar(cfg, "postgres") as conexion:
        conexion.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        with conexion.cursor() as cursor:
            cursor.execute("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = %s "
                           "AND pid <> pg_backend_pid()", (nombre,))
            cursor.execute(f'DROP DATABASE IF EXISTS "{nombre}"')
            if crear:
                cursor.execute(f'CREATE DATABASE "{nombre}"')


# ═══════════════════ crear ═══════════════════

def crear(cfg: Config, verificar_al_final: bool = True) -> tuple[Path, dict | None]:
    """Genera el paquete (y, por omisión, su prueba de restauración). Devuelve la ruta y la verificación."""
    if cfg.bd_restauracion == cfg.bd:
        raise ValueError("La base de restauración no puede ser la base respaldada.")
    cfg.destino.mkdir(parents=True, exist_ok=True)
    marca = datetime.now().strftime("%Y%m%d_%H%M%S")
    final, n = cfg.destino / f"{PREFIJO}{marca}", 1
    while final.exists() or final.with_name(final.name + ".parcial").exists():  # dos respaldos en el mismo segundo
        n += 1
        final = cfg.destino / f"{PREFIJO}{marca}_{n}"
    parcial = final.with_name(final.name + ".parcial")
    parcial.mkdir()

    # 0. El último eslabón ANTES del volcado: la bitácora solo crece, así que la
    #    base restaurada debe contenerlo idéntico (prueba de que no se truncó).
    eslabon = _ultimo_eslabon(cfg, cfg.bd)

    # 1. Instantánea de la base en el instante T.
    subprocess.run([binario_pg("pg_dump"), *_argumentos_pg(cfg), "-Fc", "-f", str(parcial / PIEZA_BASE), cfg.bd],
                   env=_entorno_pg(cfg), check=True, capture_output=True)

    # 2. Bóveda, después del volcado: superconjunto de lo que la base referencia.
    #    Los PDF ya vienen comprimidos: se guardan sin recomprimir.
    archivos_boveda = 0
    with zipfile.ZipFile(parcial / PIEZA_BOVEDA, "w", compression=zipfile.ZIP_STORED) as zf:
        if cfg.boveda.exists():
            for ruta in sorted(p for p in cfg.boveda.rglob("*") if p.is_file()):
                try:
                    zf.write(ruta, ruta.relative_to(cfg.boveda).as_posix())
                    archivos_boveda += 1
                except FileNotFoundError:
                    continue  # una carga que se deshizo mientras se copiaba: nunca llegó a la base

    # 3. SQLite del ai-service: copia consistente aunque el servicio esté escribiendo.
    sqlite_presente = cfg.sqlite.exists()
    if sqlite_presente:
        origen = sqlite3.connect(f"file:{cfg.sqlite.as_posix()}?mode=ro", uri=True)
        copia = sqlite3.connect(parcial / PIEZA_SQLITE)
        with copia:
            origen.backup(copia)
        # La copia hereda el modo WAL: en modo DELETE el paquete es un solo archivo.
        copia.execute("PRAGMA journal_mode=DELETE")
        origen.close()
        copia.close()

    with _conectar(cfg, cfg.bd) as conexion, conexion.cursor() as cursor:
        cursor.execute("SHOW server_version")
        version_pg = cursor.fetchone()[0]
    piezas = {n: {"bytes": (parcial / n).stat().st_size, "sha256": sha256_archivo(parcial / n)}
              for n in (PIEZA_BASE, PIEZA_BOVEDA, PIEZA_SQLITE) if (parcial / n).exists()}
    manifiesto = {
        "formato": 1,
        "creado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "base_de_datos": cfg.bd,
        "postgresql": version_pg,
        "version_lectura": _version_lectura(),
        "eslabon_antes_del_volcado": eslabon,
        "archivos_boveda": archivos_boveda,
        "sqlite_ai_service": sqlite_presente,
        "piezas": piezas,
    }
    (parcial / "MANIFIESTO.json").write_text(json.dumps(manifiesto, ensure_ascii=False, indent=2), encoding="utf-8")
    parcial.rename(final)  # un paquete a medias nunca lleva el nombre definitivo

    resultado = verificar(cfg, final) if verificar_al_final else None
    if resultado and resultado["verificado"]:
        if cfg.secundario:
            cfg.secundario.mkdir(parents=True, exist_ok=True)
            shutil.copytree(final, cfg.secundario / final.name)
            aplicar_retencion(cfg.secundario, cfg.retencion)
        aplicar_retencion(cfg.destino, cfg.retencion)
    return final, resultado


# ═══════════════════ verificar ═══════════════════

def _cadena_restaurada(cfg: Config) -> dict:
    """verificar_cadena del core sobre la base restaurada, en un subproceso (config.database lee DB_NAME al importarse)."""
    entorno = dict(os.environ, DB_NAME=cfg.bd_restauracion, DB_USER=cfg.conexion.get("user", "postgres"),
                   DB_PASSWORD=cfg.conexion.get("password", ""), DB_HOST=cfg.conexion.get("host", "127.0.0.1"),
                   DB_PORT=str(cfg.conexion.get("port", "5432")), PYTHONIOENCODING="utf-8")
    entorno.pop("DATABASE_URL", None)
    codigo = ("import json\nfrom config.database import SessionLocal\nfrom motor.bitacora import verificar_cadena\n"
              "db = SessionLocal()\nprint(json.dumps(verificar_cadena(db), default=str))\ndb.close()\n")
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=CORE, env=entorno, capture_output=True,
                            text=True, encoding="utf-8")
    if salida.returncode != 0:
        raise RuntimeError(f"verificar_cadena falló:\n{salida.stderr[-2000:]}")
    return json.loads(salida.stdout.strip().splitlines()[-1])


def verificar(cfg: Config, paquete: Path) -> dict:
    """Prueba de restauración del paquete. Escribe VERIFICACION.json y devuelve el resultado."""
    if cfg.bd_restauracion == cfg.bd:
        raise ValueError("La base de restauración no puede ser la base respaldada.")
    hallazgos: list[str] = []
    detalle: dict = {}
    manifiesto = json.loads((paquete / "MANIFIESTO.json").read_text(encoding="utf-8"))

    for nombre, meta in manifiesto["piezas"].items():
        ruta = paquete / nombre
        if not ruta.exists():
            hallazgos.append(f"Falta la pieza {nombre}.")
        elif sha256_archivo(ruta) != meta["sha256"]:
            hallazgos.append(f"La huella de {nombre} no coincide con el manifiesto.")
    if hallazgos:
        return _escribir_verificacion(paquete, hallazgos, detalle)

    _recrear_bd(cfg, cfg.bd_restauracion)
    try:
        restauracion = subprocess.run(
            [binario_pg("pg_restore"), *_argumentos_pg(cfg), "--no-owner", "--exit-on-error",
             "-d", cfg.bd_restauracion, str(paquete / PIEZA_BASE)],
            env=_entorno_pg(cfg), capture_output=True, text=True, encoding="utf-8", errors="replace")
        if restauracion.returncode != 0:
            hallazgos.append(f"pg_restore falló: {restauracion.stderr.strip()[-500:]}")
            return _escribir_verificacion(paquete, hallazgos, detalle)

        with _conectar(cfg, cfg.bd_restauracion) as conexion, conexion.cursor() as cursor:
            cursor.execute("SELECT id, hash_sha256, ruta_almacenamiento FROM documentos")
            documentos = cursor.fetchall()
            conteos = {}
            for tabla in ("titulares_expediente", "expedientes", "documentos", "dictamenes_auditoria",
                          "bitacora_auditoria", "reglas_validacion"):
                cursor.execute(f"SELECT count(*) FROM {tabla}")
                conteos[tabla] = cursor.fetchone()[0]
        detalle["conteos"] = conteos

        # RIE-03 sobre lo restaurado: cada documento tiene su archivo y su huella.
        sin_archivo, alterados = [], []
        with zipfile.ZipFile(paquete / PIEZA_BOVEDA) as zf:
            nombres = set(zf.namelist())
            for documento_id, huella, ruta in documentos:
                miembro = Path(ruta.replace("\\", "/")).name
                if miembro not in nombres:
                    sin_archivo.append(documento_id)
                    continue
                h = hashlib.sha256()
                with zf.open(miembro) as f:
                    for bloque in iter(lambda: f.read(1 << 20), b""):
                        h.update(bloque)
                if h.hexdigest() != huella:
                    alterados.append(documento_id)
        detalle["documentos_verificados"] = len(documentos) - len(sin_archivo) - len(alterados)
        if sin_archivo:
            hallazgos.append(f"{len(sin_archivo)} documento(s) sin su archivo en la bóveda: {sin_archivo[:5]}")
        if alterados:
            hallazgos.append(f"{len(alterados)} documento(s) cuya huella no coincide: {alterados[:5]}")

        # Cadena de la bitácora (PLUS-05) y el eslabón anotado antes del volcado.
        cadena = _cadena_restaurada(cfg)
        detalle["cadena"] = {k: cadena.get(k) for k in ("integra", "eventos_sellados", "ultima_secuencia", "ultimo_hash",
                                                         "total_hallazgos")}
        if not cadena.get("integra"):
            hallazgos.append(f"La cadena de la bitácora restaurada no es íntegra ({cadena.get('total_hallazgos')} hallazgos).")
        eslabon = manifiesto.get("eslabon_antes_del_volcado")
        if eslabon:
            with _conectar(cfg, cfg.bd_restauracion) as conexion, conexion.cursor() as cursor:
                cursor.execute("SELECT hash_evento FROM bitacora_auditoria WHERE secuencia = %s", (eslabon["secuencia"],))
                fila = cursor.fetchone()
            if not fila or fila[0] != eslabon["hash_evento"]:
                hallazgos.append(f"La bitácora restaurada no contiene el eslabón {eslabon['secuencia']} anotado antes del volcado.")
    finally:
        _recrear_bd(cfg, cfg.bd_restauracion, crear=False)

    if manifiesto.get("sqlite_ai_service"):
        # immutable: leerla no crea archivos junto a ella ni la modifica.
        conexion = sqlite3.connect(f"file:{(paquete / PIEZA_SQLITE).as_posix()}?mode=ro&immutable=1", uri=True)
        estado = conexion.execute("PRAGMA integrity_check").fetchone()[0]
        conexion.close()
        detalle["sqlite"] = estado
        if estado != "ok":
            hallazgos.append(f"La SQLite del ai-service no pasa integrity_check: {estado}")

    return _escribir_verificacion(paquete, hallazgos, detalle)


def _escribir_verificacion(paquete: Path, hallazgos: list[str], detalle: dict) -> dict:
    resultado = {"verificado": not hallazgos, "verificado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "hallazgos": hallazgos, **detalle}
    (paquete / "VERIFICACION.json").write_text(json.dumps(resultado, ensure_ascii=False, indent=2), encoding="utf-8")
    return resultado


# ═══════════════════ retención y programación ═══════════════════

def _verificado(paquete: Path) -> bool:
    try:
        return json.loads((paquete / "VERIFICACION.json").read_text(encoding="utf-8")).get("verificado") is True
    except (OSError, ValueError):
        return False


def aplicar_retencion(destino: Path, conservar: int) -> list[Path]:
    """
    Conserva los `conservar` paquetes verificados más recientes. Se borran los
    paquetes (verificados o no) anteriores al más antiguo de los conservados;
    los no verificados más recientes se dejan para su revisión. Nunca deja el
    destino sin un paquete verificado.
    """
    paquetes = sorted(p for p in destino.glob(f"{PREFIJO}*") if p.is_dir() and not p.name.endswith(".parcial"))
    verificados = [p for p in paquetes if _verificado(p)]
    if conservar < 1 or len(verificados) <= conservar:
        return []
    corte = verificados[-conservar].name
    borrados = [p for p in paquetes if p.name < corte]
    for p in borrados:
        shutil.rmtree(p)
    return borrados


def programar(hora: str, quitar: bool) -> int:
    """Tarea diaria del sistema. En Windows corre también al encender el equipo si la hora pasó con él apagado."""
    comando = f'"{sys.executable}" "{Path(__file__).resolve()}" crear'
    if os.name != "nt":
        h, m = hora.split(":")
        print("Agregue a crontab (crontab -e):")
        print(f"{int(m)} {int(h)} * * * cd '{RAIZ}' && {comando} >> respaldo.log 2>&1")
        return 0
    if quitar:
        script = f"Unregister-ScheduledTask -TaskName '{NOMBRE_TAREA}' -Confirm:$false"
    else:
        script = (
            f"$accion = New-ScheduledTaskAction -Execute '{sys.executable}' "
            f"-Argument '\"{Path(__file__).resolve()}\" crear' -WorkingDirectory '{RAIZ}'; "
            f"$disparo = New-ScheduledTaskTrigger -Daily -At '{hora}'; "
            "$ajustes = New-ScheduledTaskSettingsSet -StartWhenAvailable -DontStopIfGoingOnBatteries "
            "-AllowStartIfOnBatteries -ExecutionTimeLimit (New-TimeSpan -Hours 2); "
            f"Register-ScheduledTask -TaskName '{NOMBRE_TAREA}' -Action $accion -Trigger $disparo "
            "-Settings $ajustes -Description 'Respaldo diario del Motor de Validación (RNF-10)' -Force | Out-Null"
        )
    salida = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True)
    if salida.returncode != 0:
        print(salida.stderr.strip())
        return 1
    print(f"Tarea «{NOMBRE_TAREA}» {'eliminada' if quitar else f'programada a diario a las {hora}'}.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Respaldo conjunto con prueba de restauración (RNF-10).")
    sub = parser.add_subparsers(dest="accion", required=True)
    p_crear = sub.add_parser("crear")
    p_crear.add_argument("--destino", type=Path)
    p_crear.add_argument("--sin-verificar", action="store_true")
    p_verificar = sub.add_parser("verificar")
    p_verificar.add_argument("paquete", type=Path)
    p_programar = sub.add_parser("programar")
    p_programar.add_argument("--hora", default="02:00")
    p_programar.add_argument("--quitar", action="store_true")
    args = parser.parse_args()

    if args.accion == "programar":
        return programar(args.hora, args.quitar)
    cfg = config_desde_entorno()
    if args.accion == "crear":
        if args.destino:
            cfg.destino = args.destino
        paquete, resultado = crear(cfg, verificar_al_final=not args.sin_verificar)
        print(f"Paquete: {paquete}")
    else:
        paquete, resultado = args.paquete, verificar(cfg, args.paquete)
    if resultado is None:
        print("Sin verificar.")
        return 1
    print(json.dumps(resultado, ensure_ascii=False, indent=2))
    return 0 if resultado["verificado"] else 1


if __name__ == "__main__":
    sys.exit(main())
