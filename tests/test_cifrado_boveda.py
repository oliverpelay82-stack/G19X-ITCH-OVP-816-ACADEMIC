"""
RNF-04 — Cifrado AES-256 de la bóveda en reposo (docs/uml/rnf04-actividad-cifrado-boveda.puml).

  1. Con BOVEDA_LLAVE, el archivo en disco va cifrado (AES-256-GCM) y no
     contiene el original; la descarga y la verificación RIE-03 devuelven el
     original con la huella registrada.
  2. Un archivo en claro, anterior al cifrado, se sigue leyendo.
  3. Un archivo cifrado alterado (o truncado) dispara RIE-03: ALTERADO, dictamen
     NO_CONFORME y ALERTA_INTEGRIDAD.
  4. Una llave distinta o ausente es un error de configuración (503): el
     documento no se marca, no recibe dictamen y el barrido no registra nada.
  5. Sin llave se guarda en claro y /health lo advierte; una llave mal formada
     no deja arrancar.
  6. scripts/cifrar_boveda.py cifra los archivos en claro cuya huella coincide
     con su nombre y no toca los demás.

Aislamiento: base de datos de pruebas plurione_compliance_test (tests/bd_pruebas.py).
"""
import hashlib
import importlib.util
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import cifrado_boveda  # noqa: E402
from config.boveda import ruta_en_boveda  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.bitacora import BitacoraAuditoria  # noqa: E402
from models.dictamen import ORIGEN_RIE_03, DictamenAuditoria  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import integridad  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)

OTRA_LLAVE = "a1" * 32


def _documento(nombre: str = "csf.pdf") -> tuple[dict, bytes]:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=bd_pruebas.rfc_ficticio("CIF"), razon_social="Cifrado de Prueba S.A. de C.V.",
                                    tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp_id = client.post("/api/v1/expedientes", json={"titular_id": titular_id}).json()["id"]
    contenido = b"%PDF-1.4 original de la prueba de cifrado " + os.urandom(32)
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                    files={"file": (nombre, contenido, "application/pdf")})
    assert r.status_code == 201, r.text
    return r.json(), contenido


def _ruta(doc: dict, nombre: str = "csf.pdf") -> str:
    return ruta_en_boveda(doc["hash_sha256"], nombre)


def _leer(ruta: str) -> bytes:
    with open(ruta, "rb") as archivo:
        return archivo.read()


def _escribir(ruta: str, datos: bytes) -> None:
    with open(ruta, "wb") as archivo:
        archivo.write(datos)


def _estado(doc: dict) -> str:
    return client.get(f"/api/v1/documentos/{doc['id']}").json()["estado_integridad"]


def _alertas(documento_id: str) -> int:
    db = SessionLocal()
    try:
        return db.query(BitacoraAuditoria).filter(BitacoraAuditoria.evento == "ALERTA_INTEGRIDAD",
                                                  BitacoraAuditoria.documento_id == documento_id).count()
    finally:
        db.close()


def _dictamenes_rie03(documento_id: str) -> int:
    db = SessionLocal()
    try:
        return db.query(DictamenAuditoria).filter(DictamenAuditoria.documento_id == documento_id,
                                                  DictamenAuditoria.origen == ORIGEN_RIE_03).count()
    finally:
        db.close()


def test_el_archivo_se_guarda_cifrado_y_se_lee_el_original():
    doc, contenido = _documento()

    almacenado = _leer(_ruta(doc))
    assert almacenado.startswith(cifrado_boveda.CABECERA)
    assert contenido not in almacenado and b"%PDF" not in almacenado
    assert doc["hash_sha256"] == hashlib.sha256(contenido).hexdigest(), "La huella es la del original (RF-03)"

    r = client.get(f"/api/v1/documentos/{doc['id']}/contenido", headers=auth.sistema())
    assert r.status_code == 200 and r.content == contenido
    assert r.headers["X-Hash-SHA256"] == doc["hash_sha256"]
    assert client.get(f"/api/v1/documentos/{doc['id']}/integridad").status_code == 200


def test_cada_archivo_lleva_su_propio_nonce():
    a = cifrado_boveda.cifrar(b"mismo contenido")
    b = cifrado_boveda.cifrar(b"mismo contenido")
    assert a != b
    assert cifrado_boveda.descifrar(a) == cifrado_boveda.descifrar(b) == b"mismo contenido"


def test_un_archivo_en_claro_anterior_se_sigue_leyendo():
    doc, contenido = _documento()
    _escribir(_ruta(doc), contenido)

    assert client.get(f"/api/v1/documentos/{doc['id']}/integridad").status_code == 200
    assert client.get(f"/api/v1/documentos/{doc['id']}/contenido", headers=auth.sistema()).content == contenido
    assert _estado(doc) == integridad.INTEGRO


@pytest.mark.parametrize("alterar", [
    lambda datos: datos[:-1] + bytes([datos[-1] ^ 0x01]),   # un bit de la etiqueta
    lambda datos: datos[:40] + bytes([datos[40] ^ 0x01]) + datos[41:],   # un bit del cifrado
    lambda datos: datos[:20],   # truncado
], ids=["etiqueta", "cifrado", "truncado"])
def test_un_archivo_cifrado_alterado_dispara_rie03(alterar):
    doc, _ = _documento()
    _escribir(_ruta(doc), alterar(_leer(_ruta(doc))))

    r = client.get(f"/api/v1/documentos/{doc['id']}/integridad")

    assert r.status_code == 409 and "RIE-03" in r.json()["detail"]
    assert _estado(doc) == integridad.ALTERADO
    assert _dictamenes_rie03(doc["id"]) == 1 and _alertas(doc["id"]) == 1


def test_una_llave_distinta_no_marca_el_documento(monkeypatch):
    doc, _ = _documento()
    monkeypatch.setenv("BOVEDA_LLAVE", OTRA_LLAVE)

    r = client.get(f"/api/v1/documentos/{doc['id']}/integridad")
    assert r.status_code == 503 and "otra llave" in r.json()["detail"]
    with pytest.raises(cifrado_boveda.LlaveBovedaError):
        db = SessionLocal()
        try:
            integridad.barrer(db)
        finally:
            db.close()

    monkeypatch.delenv("BOVEDA_LLAVE")
    assert client.get(f"/api/v1/documentos/{doc['id']}/contenido", headers=auth.sistema()).status_code == 503

    monkeypatch.undo()
    assert _estado(doc) == integridad.INTEGRO, "Un error de configuración no es una alteración"
    assert _dictamenes_rie03(doc["id"]) == 0 and _alertas(doc["id"]) == 0
    assert client.get(f"/api/v1/documentos/{doc['id']}/integridad").status_code == 200


def test_sin_llave_se_guarda_en_claro_y_health_lo_advierte(monkeypatch):
    def advertencias():
        return client.get("/api/v1/health").json()["advertencias"]

    assert not any("bóveda" in a for a in advertencias())

    monkeypatch.delenv("BOVEDA_LLAVE")
    doc, contenido = _documento()
    assert _leer(_ruta(doc)) == contenido
    assert any("sin cifrar" in a for a in advertencias())

    monkeypatch.setenv("BOVEDA_LLAVE", cifrado_boveda.LLAVE_DEMOSTRACION)
    assert any("llave de demostración" in a for a in advertencias())


@pytest.mark.parametrize("llave", ["corta", "zz" * 32, "ab" * 31])
def test_una_llave_mal_formada_no_deja_arrancar(monkeypatch, llave):
    monkeypatch.setenv("BOVEDA_LLAVE", llave)
    with pytest.raises(cifrado_boveda.LlaveBovedaError, match="64 caracteres"):
        cifrado_boveda.verificar_configuracion()


def _script_cifrar_boveda():
    ruta = os.path.join(bd_pruebas.servicios.RAIZ, "scripts", "cifrar_boveda.py")
    spec = importlib.util.spec_from_file_location("cifrar_boveda", ruta)
    modulo = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modulo)
    return modulo


def test_cifrar_boveda_cifra_los_archivos_en_claro(tmp_path):
    original = b"%PDF-1.4 documento custodiado antes del cifrado"
    huella = hashlib.sha256(original).hexdigest()
    en_claro = tmp_path / f"{huella[:12]}_acta.pdf"
    en_claro.write_bytes(original)
    alterado = tmp_path / f"{huella[:12]}_alterada.pdf"
    alterado.write_bytes(b"%PDF-1.4 contenido manipulado")
    ya_cifrado = tmp_path / "000000000000_previo.pdf"
    ya_cifrado.write_bytes(cifrado_boveda.cifrar(b"previo"))
    script = _script_cifrar_boveda()

    simulado = script.cifrar_boveda(tmp_path, simular=True)
    assert simulado["cifrados"] == [en_claro.name] and en_claro.read_bytes() == original

    resultado = script.cifrar_boveda(tmp_path)

    assert resultado == {"cifrados": [en_claro.name], "ya_cifrados": [ya_cifrado.name],
                         "huella_distinta": [alterado.name]}
    assert cifrado_boveda.descifrar(en_claro.read_bytes()) == original
    assert alterado.read_bytes() == b"%PDF-1.4 contenido manipulado", "Lo alterado se deja para RIE-03"
    assert script.cifrar_boveda(tmp_path)["cifrados"] == [], "Repetirlo no cambia nada"
    assert not list(tmp_path.glob("*.cifrando"))
