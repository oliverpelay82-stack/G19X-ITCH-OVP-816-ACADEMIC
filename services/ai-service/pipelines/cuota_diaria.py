"""
PLUS-19 (ESTADO_DEL_DESARROLLO §6.6) — Cuota diaria del proveedor de IA visible.

El plan gratuito de Groq limita el modelo a ``GROQ_TOKENS_POR_DIA`` (200,000)
tokens por día; el 30/09/2026 se agotó sin aviso. Aquí se suman los tokens
que esta instancia consume por día (UTC) en la SQLite del ai-service y se
registra la respuesta 429 por cuota diaria con su tiempo de espera.

  * ``GET /api/v1/health`` informa el estado (``motor_inferencia.cuota_diaria``)
    y la cabecera del frontend lo muestra.
  * Con la cuota agotada, el ciclo de procesamiento diferido (P5) espera en
    lugar de gastar intentos.

Es una **estimación**: solo cuenta lo que consume esta instancia (otra
aplicación con la misma clave no se ve). Cuando Groq informa el uso real en su
429 («Used 199500»), ese valor corrige la cuenta.
"""
from __future__ import annotations

import re
from contextlib import closing
from datetime import datetime, timedelta, timezone
from typing import Any

from config import settings
from pipelines import persistencia_texto

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS uso_diario (
    dia           TEXT PRIMARY KEY,   -- AAAA-MM-DD en UTC
    tokens        INTEGER NOT NULL,
    agotada_hasta TEXT                -- ISO 8601 UTC; nulo si no se ha agotado
)
"""
# «...on tokens per day (TPD): Limit 200000, Used 199500, Requested 1200. Please try again in 5m3.2s.»
_TPD = re.compile(r"tokens per day|\bTPD\b", re.IGNORECASE)
_USADOS = re.compile(r"Used\s+(\d+)", re.IGNORECASE)
_ESPERA = re.compile(r"try again in\s+(?:(\d+)h)?\s*(?:(\d+)m)?\s*(?:([\d.]+)s)?", re.IGNORECASE)


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _conexion():
    conexion = persistencia_texto.conexion()
    conexion.execute(_ESQUEMA)
    return conexion


def _fila(dia: str) -> tuple[int, str | None]:
    with closing(_conexion()) as c:
        fila = c.execute("SELECT tokens, agotada_hasta FROM uso_diario WHERE dia = ?", (dia,)).fetchone()
    return (fila[0], fila[1]) if fila else (0, None)


def _guardar(dia: str, tokens: int, agotada_hasta: str | None) -> None:
    with persistencia_texto.candado_escritura(), closing(_conexion()) as c:
        c.execute("INSERT INTO uso_diario (dia, tokens, agotada_hasta) VALUES (?, ?, ?) ON CONFLICT(dia) DO UPDATE "
                  "SET tokens = excluded.tokens, agotada_hasta = excluded.agotada_hasta", (dia, tokens, agotada_hasta))
        c.commit()


def registrar(tokens: int | None, ahora: datetime | None = None) -> None:
    """Suma los tokens de una llamada real al modelo (las del caché no consumen)."""
    if not tokens:
        return
    dia = (ahora or _ahora()).date().isoformat()
    usados, agotada_hasta = _fila(dia)
    _guardar(dia, usados + int(tokens), agotada_hasta)


def es_cuota_diaria(mensaje: str) -> bool:
    return bool(_TPD.search(mensaje or ""))


def registrar_agotada(mensaje: str, ahora: datetime | None = None) -> None:
    """429 por cuota diaria: marca hasta cuándo esperar y corrige el uso con el que informa Groq."""
    ahora = ahora or _ahora()
    dia = ahora.date().isoformat()
    usados, _ = _fila(dia)
    if (m := _USADOS.search(mensaje)) is not None:
        usados = max(usados, int(m.group(1)))
    espera = timedelta(hours=1)  # sin tiempo indicado, se vuelve a probar en una hora
    if (m := _ESPERA.search(mensaje)) is not None and any(m.groups()):
        horas, minutos, segundos = (float(g) if g else 0.0 for g in m.groups())
        espera = timedelta(hours=horas, minutes=minutos, seconds=segundos)
    _guardar(dia, usados, (ahora + espera).isoformat())


def agotada(ahora: datetime | None = None) -> bool:
    ahora = ahora or _ahora()
    _, hasta = _fila(ahora.date().isoformat())
    return bool(hasta and datetime.fromisoformat(hasta) > ahora)


def estado(ahora: datetime | None = None) -> dict[str, Any]:
    """Estado para el health check: límite, usados, restantes y si está agotada."""
    ahora = ahora or _ahora()
    usados, hasta = _fila(ahora.date().isoformat())
    limite = settings.GROQ_TOKENS_POR_DIA
    vigente = bool(hasta and datetime.fromisoformat(hasta) > ahora)
    return {
        "dia_utc": ahora.date().isoformat(),
        "limite": limite,
        "usados": usados,
        "restantes": max(limite - usados, 0) if limite else None,
        "porcentaje": round(usados / limite * 100, 1) if limite else None,
        "agotada": vigente,
        "disponible_desde": hasta if vigente else None,
        "estimacion": "Solo cuenta lo que consume esta instancia del ai-service.",
    }
