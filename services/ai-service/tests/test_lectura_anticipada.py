"""
RNF-02 — Lectura anticipada y prioridad del OCR (ESTADO_DEL_DESARROLLO §6.9), sin red ni OCR real.

  1. El pool de OCR atiende primero las páginas de primer plano (auditoría,
     chat, visor) y después las de fondo; entre iguales, en orden de llegada.
  2. Promover un turno de fondo sube sus páginas pendientes a primer plano.
  3. La auditoría de un documento sin leer lo lee completo de una vez: sin la
     lectura parcial previa (6 páginas en tandas y una barrera).
  4. ``anticipar`` lee el documento de fondo una sola vez; una segunda petición
     mientras sigue en curso no programa otra, y con LECTURA_ANTICIPADA=false no
     programa nada. Después, la auditoría encuentra el texto completo guardado.
  5. Si la auditoría llega mientras la lectura anticipada sigue, la promueve y
     espera esa misma lectura (sin repetir el OCR).
  6. El endpoint responde 202 al instante.
"""
import hashlib
import threading
import time

import pytest

import sesion

import main
from clients import core_client
from config import settings
from pipelines import extraccion_pipeline as ep
from pipelines import repositorio_texto
from pipelines.cache_extracciones import CacheExtracciones

DOC_ID = "doc-anticipada-001"
CONTENIDO = b"%PDF-1.4 acta anticipada"


# ── 1 y 2. Pool con prioridad ───────────────────────────────────────
def _pool_detenido():
    """Pool de un hilo ocupado hasta que se libere: lo encolado después espera su turno."""
    pool = ep._PoolPrioritario(1)
    liberar = threading.Event()
    pool.submit(liberar.wait)
    time.sleep(0.05)
    return pool, liberar


def test_el_primer_plano_pasa_antes_que_el_fondo():
    pool, liberar = _pool_detenido()
    orden: list[str] = []
    fondo = ep.Turno(ep.FONDO)
    with ep.en_turno(fondo):
        a = pool.submit(orden.append, "fondo-1")
        b = pool.submit(orden.append, "fondo-2")
    c = pool.submit(orden.append, "auditoria")
    liberar.set()
    for f in (a, b, c):
        f.result(timeout=5)
    assert orden == ["auditoria", "fondo-1", "fondo-2"]
    pool.shutdown()


def test_promover_sube_las_paginas_pendientes_de_un_turno():
    pool, liberar = _pool_detenido()
    orden: list[str] = []
    fondo = ep.Turno(ep.FONDO)
    with ep.en_turno(ep.Turno(ep.FONDO)):
        otro = pool.submit(orden.append, "otro-documento")
    with ep.en_turno(fondo):
        a = pool.submit(orden.append, "pagina-1")
        b = pool.submit(orden.append, "pagina-2")
    fondo.prioridad = ep.PRIMER_PLANO
    pool.reordenar()
    liberar.set()
    for f in (otro, a, b):
        f.result(timeout=5)
    assert orden == ["pagina-1", "pagina-2", "otro-documento"]
    pool.shutdown()


def test_el_pool_entrega_las_excepciones_y_cancela_al_cerrar():
    pool, liberar = _pool_detenido()
    pendiente = pool.submit(lambda: "nunca")
    pool.shutdown()
    liberar.set()
    assert pendiente.cancelled()
    pool = ep._PoolPrioritario(1)
    with pytest.raises(ZeroDivisionError):
        pool.submit(lambda: 1 / 0).result(timeout=5)
    pool.shutdown()


# ── 3 a 6. Repositorio y endpoint ───────────────────────────────────
class _Lecturas(list):
    """Lecturas del Nivel 3 simulado (texto_completo de cada una) y la pausa que las retiene."""

    def __init__(self):
        super().__init__()
        self.pausa = threading.Event()
        self.pausa.set()


@pytest.fixture
def lecturas(monkeypatch):
    """Simula el core y el Nivel 3; devuelve la lista de lecturas (texto_completo de cada una)."""
    registro = _Lecturas()
    sha = hashlib.sha256(CONTENIDO).hexdigest()
    monkeypatch.setattr(repositorio_texto, "cache_texto", CacheExtracciones(16))
    monkeypatch.setattr(core_client, "verificar_integridad", lambda _id: None)
    monkeypatch.setattr(core_client, "obtener_metadatos",
                        lambda _id: {"id": _id, "hash_sha256": sha, "nombre_archivo_original": "acta.pdf"})
    monkeypatch.setattr(core_client, "leer_binario", lambda _m: CONTENIDO)

    def extraer_texto(contenido, forzar_ocr=False, texto_completo=False, paginas_conocidas=None):
        registro.append(texto_completo)
        registro.pausa.wait(timeout=10)
        return ep.ResultadoExtraccion(
            texto="ACTA CONSTITUTIVA ... 26 páginas", metodo_extraccion="OCR", confidence_score=0.9,
            total_paginas=26, total_caracteres=31, paginas_ocr=26 if texto_completo else 6,
            requiere_revision_humana=False, paginas_omitidas=[] if texto_completo else list(range(7, 27)),
        )

    monkeypatch.setattr(ep, "extraer_texto", extraer_texto)
    return registro


def _esperar_fin_de_fondo(documento_id: str, segundos: float = 10) -> None:
    limite = time.time() + segundos
    while repositorio_texto.lectura_completa_en_curso(documento_id) and time.time() < limite:
        time.sleep(0.02)


def test_la_auditoria_lee_completo_de_una_vez(lecturas):
    documento = repositorio_texto.obtener_por_documento(DOC_ID, completar_en_fondo=False, texto_completo=True)
    assert documento.completo and lecturas == [True], "Sin lectura parcial previa"


def test_anticipar_lee_una_vez_y_la_auditoria_encuentra_el_texto(lecturas):
    lecturas.pausa.clear()
    assert repositorio_texto.anticipar(DOC_ID) is True
    assert repositorio_texto.anticipar(DOC_ID) is False, "Una segunda petición no programa otra lectura"
    lecturas.pausa.set()
    _esperar_fin_de_fondo(DOC_ID)
    documento = repositorio_texto.obtener_por_documento(DOC_ID, completar_en_fondo=False, texto_completo=True)
    assert documento.completo and documento.fuente in ("memoria", "persistencia")
    assert lecturas == [True], "La auditoría no repite el OCR"


def test_con_la_lectura_anticipada_apagada_no_se_programa(lecturas, monkeypatch):
    monkeypatch.setattr(settings, "LECTURA_ANTICIPADA", False)
    assert repositorio_texto.anticipar(DOC_ID) is False
    assert lecturas == []


def test_la_auditoria_promueve_la_lectura_de_fondo_y_la_espera(lecturas, monkeypatch):
    promovidos: list[ep.Turno] = []
    original = ep.promover
    monkeypatch.setattr(ep, "promover", lambda turno: (promovidos.append(turno), original(turno)))
    lecturas.pausa.clear()
    assert repositorio_texto.anticipar(DOC_ID)
    limite = time.time() + 5
    while not lecturas and time.time() < limite:
        time.sleep(0.02)

    resultado: list = []
    hilo = threading.Thread(target=lambda: resultado.append(
        repositorio_texto.obtener_por_documento(DOC_ID, completar_en_fondo=False, texto_completo=True)))
    hilo.start()
    time.sleep(0.2)
    assert len(promovidos) == 1 and promovidos[0].prioridad == ep.PRIMER_PLANO
    lecturas.pausa.set()
    hilo.join(timeout=10)
    _esperar_fin_de_fondo(DOC_ID)
    assert resultado and resultado[0].completo
    assert lecturas == [True], "La auditoría esperó la lectura de fondo en lugar de repetirla"


def test_el_endpoint_responde_202_al_instante(lecturas):
    lecturas.pausa.clear()
    inicio = time.perf_counter()
    r = sesion.cliente(main.app).post(f"/api/v1/ai/documentos/{DOC_ID}/anticipar")
    assert r.status_code == 202 and r.json() == {"documento_id": DOC_ID, "programada": True}
    assert time.perf_counter() - inicio < 2
    lecturas.pausa.set()
    _esperar_fin_de_fondo(DOC_ID)
