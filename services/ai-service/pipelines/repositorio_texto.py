"""
Punto único de acceso al texto de un documento (Nivel 3 con memoria y disco).

Orden de resolución para un ``documento_id``:

  1. **Memoria** — caché LRU del proceso (0 ms).
  2. **Persistencia** — SQLite por huella SHA-256; sobrevive a reinicios.
  3. **Extracción** — Nivel 3 (vectorial + OCR paralelo con corte temprano).
     El resultado se guarda en disco y en memoria: ese documento no vuelve a
     pasar por OCR.

Si el corte temprano dejó páginas sin leer, la lectura de todas las páginas se
programa en un hilo de fondo. La petición actual responde con la lectura
parcial, y cuando la completa termina reemplaza a la parcial en memoria y en
disco, de modo que la búsqueda de fragmentos pasa a abarcar el documento entero
(capital social, comisario o firmas en las últimas páginas).
"""
from __future__ import annotations

import hashlib
import traceback
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, replace
from threading import Lock
from typing import Any

from clients import core_client
from config import settings
from pipelines import extraccion_pipeline, persistencia_texto
from pipelines.cache_extracciones import cache_texto


@dataclass(frozen=True)
class TextoDocumento:
    texto: str
    metadatos: dict[str, Any] | None
    traza: dict[str, Any]            # métricas del Nivel 3 (sin el texto)
    completo: bool                   # True si se leyeron todas las páginas
    sha256: str
    fuente: str = "extraccion"       # 'memoria' | 'persistencia' | 'extraccion'


# La lectura completa es CPU-intensiva (ya usa OCR_WORKERS hilos por dentro):
# se hace de un documento a la vez.
_ejecutor_fondo = ThreadPoolExecutor(max_workers=1, thread_name_prefix="lectura-completa")
_en_curso: set[tuple[str, bool]] = set()
_candado = Lock()


def _traza(extraccion: extraccion_pipeline.ResultadoExtraccion) -> dict[str, Any]:
    datos = extraccion.a_dict(incluir_paginas=True)
    datos.pop("texto_extraido", None)
    return datos


def _extraer(contenido: bytes, nombre: str, forzar_ocr: bool, texto_completo: bool, sha256: str):
    extraccion = extraccion_pipeline.extraer_texto(
        contenido=contenido, nombre_archivo=nombre, forzar_ocr=forzar_ocr, texto_completo=texto_completo
    )
    traza = _traza(extraccion)
    completo = not extraccion.paginas_omitidas
    persistencia_texto.guardar(sha256, forzar_ocr, extraccion.texto, traza, completo)
    return extraccion.texto, traza, completo


# ── Documentos de la bóveda ─────────────────────────────────────────
def obtener_por_documento(documento_id: str, forzar_ocr: bool = False) -> TextoDocumento:
    """
    Devuelve el texto del documento sin repetir nunca un OCR ya hecho.

    Propaga ``DocumentoNoEncontradoError``, ``FormatoNoSoportadoError`` y
    ``MotorOcrNoDisponibleError`` para que el controlador los traduzca a HTTP.
    """
    clave = (documento_id, forzar_ocr)
    fuente_calculada = ["extraccion"]

    def resolver() -> TextoDocumento:
        metadatos = core_client.obtener_metadatos(documento_id)
        sha256 = metadatos.get("hash_sha256", "")
        guardada = persistencia_texto.leer(sha256, forzar_ocr) if sha256 else None
        if guardada:
            fuente_calculada[0] = "persistencia"
            return TextoDocumento(guardada.texto, metadatos, guardada.traza, guardada.completo, sha256)
        contenido = core_client.leer_binario(metadatos)
        sha256 = sha256 or hashlib.sha256(contenido).hexdigest()
        texto, traza, completo = _extraer(
            contenido, metadatos.get("nombre_archivo_original", "documento"), forzar_ocr, False, sha256
        )
        return TextoDocumento(texto, metadatos, traza, completo, sha256)

    documento, desde_memoria = cache_texto.obtener_o_calcular(clave, resolver)
    documento = replace(documento, fuente="memoria" if desde_memoria else fuente_calculada[0])

    if not documento.completo and settings.COMPLETAR_LECTURA_EN_SEGUNDO_PLANO:
        _programar_lectura_completa(documento_id, forzar_ocr, documento)
    return documento


def lectura_completa_en_curso(documento_id: str, forzar_ocr: bool = False) -> bool:
    with _candado:
        return (documento_id, forzar_ocr) in _en_curso


def _programar_lectura_completa(documento_id: str, forzar_ocr: bool, parcial: TextoDocumento) -> None:
    clave = (documento_id, forzar_ocr)
    with _candado:
        if clave in _en_curso:
            return
        _en_curso.add(clave)
    _ejecutor_fondo.submit(_leer_completo, clave, parcial)


def _leer_completo(clave: tuple[str, bool], parcial: TextoDocumento) -> None:
    documento_id, forzar_ocr = clave
    try:
        contenido = core_client.leer_binario(parcial.metadatos or {"id": documento_id})
        texto, traza, _ = _extraer(
            contenido,
            (parcial.metadatos or {}).get("nombre_archivo_original", "documento"),
            forzar_ocr,
            True,
            parcial.sha256,
        )
        cache_texto.actualizar(clave, replace(parcial, texto=texto, traza=traza, completo=True))
        print(f"[ai-service] Lectura completa lista: {documento_id} ({traza['total_paginas']} páginas).")
    except Exception:  # noqa: BLE001 - un fallo de fondo no debe tumbar el servicio
        print(f"[ai-service] AVISO: falló la lectura completa de {documento_id}:\n{traceback.format_exc()}")
    finally:
        with _candado:
            _en_curso.discard(clave)


# ── Archivos sueltos (endpoint /ai/extraer-texto) ───────────────────
def obtener_por_contenido(
    contenido: bytes,
    nombre: str,
    forzar_ocr: bool = False,
    texto_completo: bool = False,
    usar_cache: bool = True,
) -> tuple[str, dict[str, Any], str]:
    """
    Extrae un archivo que no necesariamente está en la bóveda, reutilizando la
    persistencia por huella SHA-256. Devuelve (texto, traza, fuente).
    """
    sha256 = hashlib.sha256(contenido).hexdigest()
    if usar_cache:
        guardada = persistencia_texto.leer(sha256, forzar_ocr)
        if guardada and (guardada.completo or not texto_completo):
            return guardada.texto, guardada.traza, "persistencia"
    texto, traza, _ = _extraer(contenido, nombre, forzar_ocr, texto_completo, sha256)
    return texto, traza, "extraccion"


def estadisticas() -> dict[str, Any]:
    with _candado:
        en_curso = len(_en_curso)
    return {**cache_texto.estadisticas(), **persistencia_texto.estadisticas(), "lecturas_completas_en_curso": en_curso}
