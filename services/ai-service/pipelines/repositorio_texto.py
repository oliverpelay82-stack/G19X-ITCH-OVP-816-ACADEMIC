"""
Punto único de acceso al texto de un documento (Nivel 3 con memoria y disco).

Orden de resolución para un ``documento_id``:

  1. **Memoria** — caché LRU del proceso (0 ms).
  2. **Persistencia** — SQLite por huella SHA-256; sobrevive a reinicios.
  3. **Extracción** — Nivel 3 (vectorial + OCR paralelo con corte temprano).
     El resultado se guarda en disco y en memoria: ese documento no vuelve a
     pasar por OCR.

**La auditoría lee el documento completo** (``texto_completo=True``): la
verificación de contenido busca elementos que pueden estar en cualquier página
(la inscripción en el Registro Público o las facultades del administrador, al
final de un acta). Esa lectura queda en memoria y en disco, así que después el
chat, las citas y el visor trabajan sobre todas las páginas sin repetir el OCR.

Si el chat abre un documento que nadie ha auditado, responde de inmediato con la
lectura parcial (corte temprano) y programa la completa en un hilo de fondo;
cuando termina, reemplaza a la parcial en memoria y en disco. Un candado por
documento evita que la auditoría y la lectura de fondo reconozcan las mismas
páginas dos veces.
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
# Un candado por documento para la lectura completa: la de la auditoría y la de
# fondo del chat se esperan entre sí y la segunda reutiliza el resultado.
_candados_lectura: dict[tuple[str, bool], Lock] = {}


def _candado_lectura(clave: tuple[str, bool]) -> Lock:
    with _candado:
        return _candados_lectura.setdefault(clave, Lock())


def _traza(extraccion: extraccion_pipeline.ResultadoExtraccion) -> dict[str, Any]:
    datos = extraccion.a_dict(incluir_paginas=True)
    datos.pop("texto_extraido", None)
    return datos


def _extraer(contenido: bytes, nombre: str, forzar_ocr: bool, texto_completo: bool, sha256: str):
    # Las páginas escaneadas que ya reconoció una lectura parcial o el visor no
    # vuelven a pasar por OCR (solo si son de esta misma versión del Nivel 3).
    extraccion = extraccion_pipeline.extraer_texto(
        contenido=contenido, nombre_archivo=nombre, forzar_ocr=forzar_ocr, texto_completo=texto_completo,
        paginas_conocidas=persistencia_texto.paginas_reconocidas(sha256) if sha256 and not forzar_ocr else None,
    )
    traza = _traza(extraccion)
    completo = not extraccion.paginas_omitidas
    persistencia_texto.guardar(sha256, forzar_ocr, extraccion.texto, traza, completo)
    # Las palabras con coordenadas de cada página escaneada, de esta misma
    # lectura: el visor resalta exactamente el texto que se analizó.
    for pagina in extraccion.detalle_paginas:
        if pagina.palabras:
            persistencia_texto.guardar_palabras(
                sha256, pagina.numero, pagina.palabras, pagina.texto, pagina.confianza, pagina.sellos
            )
    return extraccion.texto, traza, completo


# ── Documentos de la bóveda ─────────────────────────────────────────
def obtener_por_documento(
    documento_id: str, forzar_ocr: bool = False, completar_en_fondo: bool = True, texto_completo: bool = False
) -> TextoDocumento:
    """
    Devuelve el texto del documento sin repetir nunca un OCR ya hecho.

    :param completar_en_fondo: si la lectura es parcial, programa la de todas
        las páginas en segundo plano (la usa el chat).
    :param texto_completo: si la lectura es parcial, lee ahora todas las
        páginas antes de responder (la usa la auditoría).

    Antes de servir cualquier texto —incluso desde memoria o disco— el
    core-service verifica la integridad del binario (RIE-03): un texto extraído
    de un archivo que después fue alterado no debe volver a analizarse.

    Propaga ``DocumentoNoEncontradoError``, ``DocumentoAlteradoError``,
    ``CoreNoDisponibleError``, ``FormatoNoSoportadoError`` y
    ``MotorOcrNoDisponibleError`` para que el controlador los traduzca a HTTP.
    """
    core_client.verificar_integridad(documento_id)
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

    if texto_completo and not documento.completo:
        return _completar(clave, documento)
    if completar_en_fondo and not documento.completo and settings.COMPLETAR_LECTURA_EN_SEGUNDO_PLANO:
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


def _completar(clave: tuple[str, bool], parcial: TextoDocumento) -> TextoDocumento:
    """
    Lectura de todas las páginas de un documento leído parcialmente. Si otra
    petición la está haciendo, espera y reutiliza su resultado (ya persistido).
    """
    documento_id, forzar_ocr = clave
    with _candado_lectura(clave):
        guardada = persistencia_texto.leer(parcial.sha256, forzar_ocr) if parcial.sha256 else None
        if guardada and guardada.completo:
            completo = replace(parcial, texto=guardada.texto, traza=guardada.traza, completo=True,
                               fuente="persistencia")
        else:
            contenido = core_client.leer_binario(parcial.metadatos or {"id": documento_id})
            texto, traza, _ = _extraer(
                contenido,
                (parcial.metadatos or {}).get("nombre_archivo_original", "documento"),
                forzar_ocr,
                True,
                parcial.sha256,
            )
            completo = replace(parcial, texto=texto, traza=traza, completo=True, fuente="extraccion")
        cache_texto.actualizar(clave, replace(completo, fuente=parcial.fuente))
        return completo


def _leer_completo(clave: tuple[str, bool], parcial: TextoDocumento) -> None:
    documento_id, _ = clave
    try:
        completo = _completar(clave, parcial)
        print(f"[ai-service] Lectura completa lista: {documento_id} ({completo.traza['total_paginas']} páginas).")
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
