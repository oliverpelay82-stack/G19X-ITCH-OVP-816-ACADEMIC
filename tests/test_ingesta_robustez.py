"""
Robustez de la ingesta del core-service (Nivel 1):

1. La lectura del archivo está acotada: nunca se piden más de 15 MB + 1 byte,
   así que un archivo enorme no entra completo a memoria, y se rechaza con 400.
2. La ingesta no bloquea el servicio: mientras una carga espera al
   rules-service (reevaluación del semáforo), /health sigue respondiendo.

Aislamiento: base de datos de pruebas plurione_compliance_test y bóveda
temporal (tests/bd_pruebas.py).
"""
import io
import os
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
# La reevaluación programada correría al arrancar el lifespan y competiría con
# la medición de latencia; esta prueba no la necesita.
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from controllers import documento_controller  # noqa: E402
from models.expediente import Expediente  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()

MAX = documento_controller.MAX_FILE_SIZE_BYTES
INVENTARIO = rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)


def _expediente(codigo: str, rfc: str) -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Titular {codigo} S.A. de C.V.", tipo_persona="MORAL", categoria="PROVEEDOR")
        db.add(titular)
        db.flush()
        expediente = Expediente(titular_id=titular.id, codigo_expediente=codigo, estado_cumplimiento="EN_REVISION", porcentaje_completitud=0.0)
        db.add(expediente)
        db.commit()
        return expediente.id
    finally:
        db.close()


class _ArchivoEspia(io.BytesIO):
    """Registra cuántos bytes se piden en cada lectura."""

    def __init__(self, datos: bytes):
        super().__init__(datos)
        self.pedidos: list[int] = []

    def read(self, n: int = -1) -> bytes:
        self.pedidos.append(n)
        return super().read(n)


def test_lectura_acotada_al_limite_del_nivel_1():
    espia = _ArchivoEspia(b"%PDF-" + b"0" * (MAX + 1024 * 1024))
    contenido = documento_controller._leer_acotado(espia)
    assert len(contenido) == MAX + 1, len(contenido)
    assert espia.pedidos and all(0 < n <= MAX + 1 for n in espia.pedidos), espia.pedidos


def test_archivo_mayor_al_limite_se_rechaza_con_400():
    os.makedirs(BOVEDA, exist_ok=True)
    rules_client.obtener_documentos_obligatorios = lambda *_: INVENTARIO
    exp_id = _expediente("EXP-TEST-GRANDE", "GRA010101AAA")
    try:
        res = TestClient(app).post(
            "/api/v1/documentos/upload",
            data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
            files={"file": ("enorme.pdf", b"%PDF-" + b"0" * (MAX + 1024), "application/pdf")},
        )
        assert res.status_code == 400, res.text
        assert "tamaño máximo" in res.json()["detail"]
    finally:
        bd_pruebas.limpiar_boveda(BOVEDA)


def test_ingesta_no_bloquea_el_servicio():
    espera = 1.5

    def lento(*_):
        time.sleep(espera)  # el rules-service tarda en responder
        return INVENTARIO

    os.makedirs(BOVEDA, exist_ok=True)
    rules_client.obtener_documentos_obligatorios = lento
    exp_id = _expediente("EXP-TEST-CONCURRENTE", "CON010101AAA")
    respuestas = {}
    try:
        with TestClient(app) as cliente:  # un solo bucle de eventos para las dos peticiones
            carga = threading.Thread(
                target=lambda: respuestas.setdefault(
                    "carga",
                    cliente.post(
                        "/api/v1/documentos/upload",
                        data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                        files={"file": ("csf.pdf", b"%PDF-1.4 concurrente", "application/pdf")},
                    ),
                )
            )
            inicio_carga = time.perf_counter()
            carga.start()
            time.sleep(0.4)  # la carga ya está esperando al rules-service
            inicio = time.perf_counter()
            salud = cliente.get("/api/v1/health")
            latencia = time.perf_counter() - inicio
            carga.join()
            duracion_carga = time.perf_counter() - inicio_carga
        # La carga debe haber ocurrido de verdad (si fallara al instante, no probaría nada).
        assert respuestas["carga"].status_code == 201, respuestas["carga"].text
        assert duracion_carga >= espera, duracion_carga
        assert salud.status_code == 200
        assert latencia < 0.6, f"/health tardó {latencia:.2f} s: la ingesta bloqueó el bucle de eventos"
    finally:
        rules_client.obtener_documentos_obligatorios = lambda *_: INVENTARIO
        bd_pruebas.limpiar_boveda(BOVEDA)


if __name__ == "__main__":
    for prueba in (test_lectura_acotada_al_limite_del_nivel_1, test_archivo_mayor_al_limite_se_rechaza_con_400, test_ingesta_no_bloquea_el_servicio):
        prueba()
        print(f"PASÓ: {prueba.__name__}")
