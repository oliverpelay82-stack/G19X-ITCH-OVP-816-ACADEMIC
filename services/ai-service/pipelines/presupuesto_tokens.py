"""
Presupuesto local de tokens por minuto — T4, PLUS-11 (PRD §21.4).

Groq limita el plan gratuito a ``GROQ_TOKENS_POR_MINUTO`` (8,000). La auditoría
de un documento largo consume hasta ≈ 7,000 tokens en segundos; un turno de chat
inmediatamente después excede el límite y el SDK espera y reintenta. Este módulo
lleva la cuenta de los tokens que el proceso gastó en los últimos 60 segundos
(``groq_client`` registra cada llamada real con su uso) para que el chat pueda
decidir, antes de llamar, si su petición cabe o si debe acotar su contexto.

Es una cuenta por proceso: no conoce el consumo de otras instancias del servicio
con la misma clave de Groq. Con ``GROQ_TOKENS_POR_MINUTO=0`` queda desactivado.
"""
from __future__ import annotations

import threading
import time
from collections import deque
from typing import Callable

from config import settings

VENTANA_SEGUNDOS = 60
# Caracteres por token medidos en la línea base del chat (español, prompt de
# ≈ 9,700 caracteres → ≈ 2,900 tokens): VALIDACION_CUANTITATIVA.md §10.1.
CARACTERES_POR_TOKEN = 3.3
# Tokens que se reservan para la respuesta al estimar una petición.
RESERVA_RESPUESTA = 300
# Margen bajo el límite del proveedor.
MARGEN = 0.95


class Presupuesto:
    def __init__(self, reloj: Callable[[], float] = time.monotonic):
        self._reloj = reloj
        self._consumos: deque[tuple[float, int]] = deque()
        self._candado = threading.Lock()

    @property
    def limite(self) -> int:
        return int(settings.GROQ_TOKENS_POR_MINUTO * MARGEN)

    def activo(self) -> bool:
        return settings.GROQ_TOKENS_POR_MINUTO > 0

    def registrar(self, tokens: int | None) -> None:
        if tokens:
            with self._candado:
                self._consumos.append((self._reloj(), int(tokens)))

    def usados(self) -> int:
        with self._candado:
            ahora = self._reloj()
            while self._consumos and ahora - self._consumos[0][0] >= VENTANA_SEGUNDOS:
                self._consumos.popleft()
            return sum(t for _, t in self._consumos)

    def cabe(self, estimado: int) -> bool:
        return not self.activo() or self.usados() + estimado <= self.limite

    def vaciar(self) -> None:
        with self._candado:
            self._consumos.clear()


def estimar(mensajes: list[dict[str, str]]) -> int:
    """Tokens estimados de una petición de chat: su texto más la reserva de la respuesta."""
    caracteres = sum(len(m.get("content") or "") for m in mensajes)
    return int(caracteres / CARACTERES_POR_TOKEN) + RESERVA_RESPUESTA


presupuesto = Presupuesto()
