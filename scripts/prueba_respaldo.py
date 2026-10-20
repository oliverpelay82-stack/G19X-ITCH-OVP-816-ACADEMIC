"""
Prueba del respaldo conjunto y de su prueba de restauración (RNF-10).

Levanta core y rules (puertos 8101 y 8102) sobre ``plurione_compliance_e2e``,
recreada, con una bóveda propia, como scripts/e2e_api.py: nada se escribe en
``plurione_compliance``. Carga documentos por HTTP y registra un dictamen, y
con los servicios en marcha:

  1. crear: el paquete queda verificado, con cada documento restaurado contra
     su archivo, la cadena de la bitácora íntegra y la SQLite en buen estado.
  2. Un archivo alterado dentro de boveda.zip (con el manifiesto rehecho para
     que la huella de la pieza coincida) se detecta por documento (RIE-03).
  3. Un archivo que falta en la bóveda se detecta.
  4. Una pieza modificada después del respaldo no coincide con el manifiesto.
  5. Un eslabón del manifiesto que no está en la bitácora restaurada se detecta.
  5b. RNF-04: la bóveda va cifrada en el paquete y, sin BOVEDA_LLAVE, la
     verificación no puede comprobar los documentos y lo dice.
  6. Retención: con RESPALDO_RETENCION=2 quedan los dos paquetes verificados
     más recientes, y la segunda copia recibe los mismos.
  7. La base de restauración se borra al terminar.

Uso, desde la raíz: python scripts/prueba_respaldo.py   (código 0 si todo pasa)
"""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
import respaldo  # noqa: E402
import sesion_api  # noqa: E402
from e2e_api import BD_E2E, detener, levantar, pdf_constancia  # noqa: E402

CORE = "http://127.0.0.1:8101/api/v1"

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

fallas: list[str] = []


def comprobar(condicion: bool, mensaje: str) -> None:
    print(f"{'OK   ' if condicion else 'FALLA'} {mensaje}")
    if not condicion:
        fallas.append(mensaje)


def poblar() -> int:
    """Titular ficticio, expediente, tres documentos y un dictamen. Devuelve cuántos documentos hay."""
    from datetime import date, timedelta

    api = sesion_api.sesion(CORE, "VALIDADOR")  # Módulo 7: la cuenta de demostración del validador
    titular = api.post(f"{CORE}/titulares", json={
        "rfc": "EMP260101AB1", "razon_social": "Empresa Ficticia de Pruebas, S.A. de C.V.", "tipo_persona": "MORAL"},
        timeout=30).json()
    expediente = api.post(f"{CORE}/expedientes", json={
        "titular_id": titular["id"], "tipo_expediente": "CORPORATIVO", "nombre": "Prueba de respaldo"}, timeout=30).json()
    emision = date.today() - timedelta(days=5)
    ids = []
    for tipo in ("CSF_SAT", "COMP_DOMICILIO", "ACTA_CONSTITUTIVA"):
        r = api.post(f"{CORE}/documentos/upload", data={"expediente_id": expediente["id"], "tipo_documento": tipo},
                          files={"file": (f"{tipo.lower()}.pdf", pdf_constancia("EMP260101AB1", tipo, emision),
                                          "application/pdf")}, timeout=30)
        r.raise_for_status()
        ids.append(r.json()["id"])
    # Solo el ai-service registra dictámenes: token SISTEMA firmado con la clave de los servicios aislados.
    api.post(f"{CORE}/dictamenes", headers=sesion_api.cabeceras_sistema(secreto=sesion_api.SECRETO_AISLADO), json={
        "documento_id": ids[0], "estatus": "EN_REVISION", "nivel_confianza": 0.8, "requiere_revision_humana": True,
        "tipo_documento_detectado": "CSF_SAT", "rfc_detectado": "EMP260101AB1", "match_titular": True,
        "observaciones": ["Dictamen simulado para la prueba de respaldo."], "modelo_utilizado": "simulado",
    }, timeout=30).raise_for_status()
    return len(ids)


def rehacer_manifiesto(paquete: Path) -> None:
    """Simula a quien altera una pieza y rehace el manifiesto para que su huella coincida."""
    ruta = paquete / "MANIFIESTO.json"
    manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
    for nombre in manifiesto["piezas"]:
        manifiesto["piezas"][nombre]["sha256"] = respaldo.sha256_archivo(paquete / nombre)
    ruta.write_text(json.dumps(manifiesto), encoding="utf-8")


def reescribir_zip(paquete: Path, cambiar) -> None:
    """Reescribe boveda.zip aplicando `cambiar(nombre, datos)` → datos nuevos, o None para omitir el archivo."""
    origen = paquete / respaldo.PIEZA_BOVEDA
    temporal = origen.with_suffix(".tmp")
    with zipfile.ZipFile(origen) as entrada, zipfile.ZipFile(temporal, "w") as salida:
        for nombre in entrada.namelist():
            datos = cambiar(nombre, entrada.read(nombre))
            if datos is not None:
                salida.writestr(nombre, datos)
    temporal.replace(origen)


def copia(paquete: Path, carpeta: Path, sufijo: str) -> Path:
    destino = carpeta / f"{paquete.name}_{sufijo}"
    shutil.copytree(paquete, destino)
    return destino


def main() -> int:
    trabajo = Path(tempfile.mkdtemp(prefix="plurione_respaldo_"))
    boveda = trabajo / "boveda"
    boveda.mkdir()
    sqlite_ai = trabajo / "extracciones.sqlite3"
    with sqlite3.connect(sqlite_ai) as c:
        c.execute("CREATE TABLE extracciones (sha256 TEXT PRIMARY KEY, texto TEXT)")
        c.execute("INSERT INTO extracciones VALUES ('abc', 'texto de prueba')")
    c.close()

    # RNF-04: la verificación descifra la bóveda con la misma llave que usa el core aislado.
    os.environ["BOVEDA_LLAVE"] = sesion_api.ENTORNO_AISLADO["BOVEDA_LLAVE"]
    procesos = levantar({"rules-service": 8102, "core-service": 8101}, trabajo,
                        entorno_extra={"STORAGE_VAULT_PATH": str(boveda)})
    try:
        documentos = poblar()
        base = respaldo.config_desde_entorno()
        cfg = respaldo.Config(bd=BD_E2E, boveda=boveda, sqlite=sqlite_ai, destino=trabajo / "respaldos",
                              secundario=trabajo / "secundario", retencion=2, conexion=base.conexion)

        # 1. Respaldo con los servicios en marcha.
        paquete, resultado = respaldo.crear(cfg)
        comprobar(resultado["verificado"], f"crear: paquete verificado ({resultado['hallazgos']})")
        comprobar(resultado.get("documentos_verificados") == documentos,
                  f"crear: {documentos} documentos restaurados con su huella ({resultado.get('documentos_verificados')})")
        comprobar(resultado.get("cadena", {}).get("integra") is True and resultado["cadena"]["eventos_sellados"] > 0,
                  "crear: la cadena de la bitácora restaurada es íntegra")
        comprobar(resultado.get("sqlite") == "ok", "crear: la SQLite del ai-service pasa integrity_check")
        comprobar((cfg.secundario / paquete.name / "VERIFICACION.json").exists(), "crear: la segunda copia recibe el paquete")

        pruebas = trabajo / "alterados"
        pruebas.mkdir()

        # 2. Un archivo alterado dentro de la bóveda respaldada.
        p = copia(paquete, pruebas, "alterado")
        primero = zipfile.ZipFile(p / respaldo.PIEZA_BOVEDA).namelist()[0]
        reescribir_zip(p, lambda n, d: d + b"%alterado" if n == primero else d)
        rehacer_manifiesto(p)
        r = respaldo.verificar(cfg, p)
        comprobar(not r["verificado"] and any("huella no coincide" in h for h in r["hallazgos"]),
                  "verificar: un archivo alterado en la bóveda se detecta por documento")

        # 3. Un archivo que falta.
        p = copia(paquete, pruebas, "falta")
        reescribir_zip(p, lambda n, d: None if n == primero else d)
        rehacer_manifiesto(p)
        r = respaldo.verificar(cfg, p)
        comprobar(not r["verificado"] and any("sin su archivo" in h for h in r["hallazgos"]),
                  "verificar: un documento sin su archivo se detecta")

        # 4. Una pieza modificada sin rehacer el manifiesto.
        p = copia(paquete, pruebas, "pieza")
        with open(p / respaldo.PIEZA_BASE, "ab") as f:
            f.write(b"\0")
        r = respaldo.verificar(cfg, p)
        comprobar(not r["verificado"] and any("no coincide con el manifiesto" in h for h in r["hallazgos"]),
                  "verificar: una pieza modificada no coincide con el manifiesto")

        # 5. Un eslabón que la bitácora restaurada no contiene.
        p = copia(paquete, pruebas, "eslabon")
        ruta = p / "MANIFIESTO.json"
        manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
        manifiesto["eslabon_antes_del_volcado"]["hash_evento"] = "0" * 64
        ruta.write_text(json.dumps(manifiesto), encoding="utf-8")
        r = respaldo.verificar(cfg, p)
        comprobar(not r["verificado"] and any("eslabón" in h for h in r["hallazgos"]),
                  "verificar: un eslabón ausente de la bitácora restaurada se detecta")

        # 5b. RNF-04: la bóveda viaja cifrada y la llave no va en el paquete.
        with zipfile.ZipFile(paquete / respaldo.PIEZA_BOVEDA) as zf:
            cifrados = all(respaldo.cifrado_boveda.esta_cifrado(zf.read(n)) for n in zf.namelist())
        comprobar(cifrados, "RNF-04: los archivos de boveda.zip van cifrados")
        p = copia(paquete, pruebas, "sin_llave")
        llave = os.environ.pop("BOVEDA_LLAVE")
        try:
            r = respaldo.verificar(cfg, p)
        finally:
            os.environ["BOVEDA_LLAVE"] = llave
        comprobar(not r["verificado"] and any("BOVEDA_LLAVE" in h for h in r["hallazgos"]),
                  "RNF-04: sin la llave, la verificación lo dice en vez de dar por buenos los documentos")

        # 6. Retención: dos paquetes más; quedan los dos verificados más recientes.
        segundo, _ = respaldo.crear(cfg)
        tercero, _ = respaldo.crear(cfg)
        quedan = sorted(x.name for x in cfg.destino.iterdir())
        comprobar(quedan == [segundo.name, tercero.name], f"retención: quedan los dos más recientes ({quedan})")
        quedan2 = sorted(x.name for x in cfg.secundario.iterdir())
        comprobar(quedan2 == [segundo.name, tercero.name], f"retención: también en la segunda copia ({quedan2})")

        # 7. La base temporal no queda.
        with respaldo._conectar(cfg, "postgres") as conexion, conexion.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s", (cfg.bd_restauracion,))
            comprobar(cursor.fetchone() is None, "la base de restauración se borra al terminar")
    finally:
        detener(procesos)
    print(f"\n{'Todo pasó' if not fallas else f'{len(fallas)} fallas'} · trabajo en {trabajo}")
    return 1 if fallas else 0


if __name__ == "__main__":
    sys.exit(main())
