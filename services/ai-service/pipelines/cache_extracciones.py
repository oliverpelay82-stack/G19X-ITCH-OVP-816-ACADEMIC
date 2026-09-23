"""
Caché en memoria del texto extraído por el Nivel 3, indexado por documento.

El OCR de un documento escaneado cuesta segundos por página. Sin caché, cada
turno del chat y cada nueva auditoría sobre el mismo archivo repetiría ese
trabajo. Los documentos de la bóveda son inmutables —su huella SHA-256 se fija
en la ingesta (NOM-151)—, así que el texto de un ``documento_id`` no cambia y
puede reutilizarse sin riesgo de servir contenido obsoleto.

Características:
  * **LRU acotado** a ``CACHE_MAX_DOCUMENTOS`` entradas, para que la memoria no
    crezca sin límite en un servicio de larga duración.
  * **Seguro entre hilos.** FastAPI ejecuta los endpoints síncronos en un pool
    de hilos, de modo que dos peticiones pueden llegar a la vez.
  * **Deduplica extracciones en curso.** Si la auditoría y el chat piden el
    mismo documento al mismo tiempo, la segunda petición espera a la primera en
    lugar de lanzar un segundo OCR.

El caché vive en el proceso: se vacía al reiniciar el servicio, y la siguiente
petición simplemente vuelve a extraer.
"""
from collections import OrderedDict
from threading import Lock
from typing import Any, Callable, Hashable

from config import settings


class CacheExtracciones:
    def __init__(self, capacidad: int) -> None:
        self._capacidad = max(1, capacidad)
        self._entradas: OrderedDict[Hashable, Any] = OrderedDict()
        self._candado = Lock()
        self._candados_por_clave: dict[Hashable, Lock] = {}

    def _leer(self, clave: Hashable) -> tuple[bool, Any]:
        with self._candado:
            if clave in self._entradas:
                self._entradas.move_to_end(clave)
                return True, self._entradas[clave]
            return False, None

    def _guardar(self, clave: Hashable, valor: Any) -> None:
        with self._candado:
            self._entradas[clave] = valor
            self._entradas.move_to_end(clave)
            while len(self._entradas) > self._capacidad:
                self._entradas.popitem(last=False)

    def obtener_o_calcular(self, clave: Hashable, calcular: Callable[[], Any]) -> tuple[Any, bool]:
        """
        Devuelve ``(valor, desde_cache)``. Si la clave no está, ejecuta
        ``calcular`` una sola vez aunque haya peticiones concurrentes.
        Las excepciones de ``calcular`` se propagan y no se guardan.
        """
        encontrado, valor = self._leer(clave)
        if encontrado:
            return valor, True

        with self._candado:
            candado_clave = self._candados_por_clave.setdefault(clave, Lock())

        with candado_clave:
            # Otra petición pudo completar la extracción mientras se esperaba.
            encontrado, valor = self._leer(clave)
            if encontrado:
                return valor, True
            try:
                valor = calcular()
                self._guardar(clave, valor)
                return valor, False
            finally:
                with self._candado:
                    self._candados_por_clave.pop(clave, None)

    def actualizar(self, clave: Hashable, valor: Any) -> None:
        """Reemplaza una entrada (p. ej. cuando termina la lectura completa)."""
        self._guardar(clave, valor)

    def estadisticas(self) -> dict[str, int]:
        with self._candado:
            return {"documentos_en_cache": len(self._entradas), "capacidad": self._capacidad}


cache_texto = CacheExtracciones(settings.CACHE_MAX_DOCUMENTOS)
