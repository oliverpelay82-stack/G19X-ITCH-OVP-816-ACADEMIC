"""
Excepción «Procesamiento diferido» (DOC-05, Tabla 1; P5).

Si el proveedor de IA no responde tras sus 3 intentos (los del SDK,
``GROQ_MAX_RETRIES`` más el primero), la auditoría no se pierde: entra en una
cola de la SQLite del ai-service y un ciclo en segundo plano la reintenta sola,
con espera creciente (de 15 min a 24 h) y hasta ``DIFERIDOS_MAX_INTENTOS``.

  * Las auditorías vencidas se procesan de una en una; si el proveedor sigue
    sin responder, el ciclo se detiene hasta la siguiente vuelta en lugar de
    insistir con las demás (cuida la cuota por minuto y la diaria).
  * Cada cambio se avisa al core (``/documentos/{id}/procesamiento-diferido``),
    que muestra la alerta «Procesamiento diferido» en el expediente; al
    guardarse el dictamen, el core la retira.
  * Un documento que ya no existe o que quedó alterado (RIE-03) sale de la
    cola: no hay nada que reintentar.

La cola guarda solo la petición de la auditoría (documento, titular y
usuario), nunca el texto del documento.
"""
from __future__ import annotations

import json
import threading
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from config import settings
from pipelines import persistencia_texto

ESPERA_INICIAL = timedelta(minutes=15)
ESPERA_MAXIMA = timedelta(hours=24)

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS auditorias_diferidas (
    documento_id    TEXT PRIMARY KEY,
    peticion        TEXT NOT NULL,      -- JSON: documento, titular y usuario de la auditoría
    intentos        INTEGER NOT NULL,   -- intentos fallidos, contando el original
    proximo_intento TEXT NOT NULL,      -- ISO 8601, UTC
    ultimo_error    TEXT NOT NULL,
    creado_en       TEXT NOT NULL
)
"""


@dataclass
class Diferida:
    documento_id: str
    peticion: dict[str, Any]
    intentos: int
    proximo_intento: datetime
    ultimo_error: str

    @property
    def agotada(self) -> bool:
        return self.intentos >= settings.DIFERIDOS_MAX_INTENTOS

    def aviso(self) -> dict[str, Any]:
        """Cuerpo del aviso al core (ProcesamientoDiferidoRequest)."""
        return {
            "motivo": self.ultimo_error[:500] or "El servicio de IA no respondió.",
            "intentos": self.intentos,
            "max_intentos": settings.DIFERIDOS_MAX_INTENTOS,
            "proximo_intento": None if self.agotada else self.proximo_intento.isoformat(),
            "agotado": self.agotada,
        }


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def espera(intentos: int) -> timedelta:
    """15 min tras el primer fallo; el doble en cada uno, sin pasar de 24 h."""
    return min(ESPERA_INICIAL * (2 ** max(intentos - 1, 0)), ESPERA_MAXIMA)


def _conexion():
    conexion = persistencia_texto.conexion()
    conexion.execute(_ESQUEMA)
    return conexion


def _fila(fila) -> Diferida:
    documento_id, peticion, intentos, proximo, error = fila
    return Diferida(documento_id, json.loads(peticion), intentos, datetime.fromisoformat(proximo), error)


def obtener(documento_id: str) -> Diferida | None:
    with closing(_conexion()) as c:
        fila = c.execute(
            "SELECT documento_id, peticion, intentos, proximo_intento, ultimo_error FROM auditorias_diferidas "
            "WHERE documento_id = ?", (documento_id,)).fetchone()
    return _fila(fila) if fila else None


def registrar_fallo(peticion: dict[str, Any], error: str) -> Diferida:
    """Encola la auditoría o, si ya estaba, suma un intento fallido y aleja el siguiente."""
    documento_id = peticion["documento_id"]
    previa = obtener(documento_id)
    intentos = (previa.intentos if previa else 0) + 1
    diferida = Diferida(documento_id, peticion, intentos, _ahora() + espera(intentos), error)
    with persistencia_texto.candado_escritura(), closing(_conexion()) as c:
        c.execute(
            "INSERT INTO auditorias_diferidas (documento_id, peticion, intentos, proximo_intento, ultimo_error, creado_en) "
            "VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(documento_id) DO UPDATE SET peticion = excluded.peticion, "
            "intentos = excluded.intentos, proximo_intento = excluded.proximo_intento, "
            "ultimo_error = excluded.ultimo_error",
            (documento_id, json.dumps(peticion), intentos, diferida.proximo_intento.isoformat(), error,
             _ahora().isoformat()))
        c.commit()
    return diferida


def quitar(documento_id: str) -> None:
    with persistencia_texto.candado_escritura(), closing(_conexion()) as c:
        c.execute("DELETE FROM auditorias_diferidas WHERE documento_id = ?", (documento_id,))
        c.commit()


def vencidas(ahora: datetime | None = None) -> list[Diferida]:
    """Auditorías cuyo siguiente intento ya llegó, de la más antigua a la más reciente."""
    with closing(_conexion()) as c:
        filas = c.execute(
            "SELECT documento_id, peticion, intentos, proximo_intento, ultimo_error FROM auditorias_diferidas "
            "WHERE proximo_intento <= ? ORDER BY proximo_intento", ((ahora or _ahora()).isoformat(),)).fetchall()
    return [_fila(f) for f in filas]


def procesar_vencidas(
    auditar: Callable[[dict[str, Any]], Any],
    avisar: Callable[[str, dict[str, Any]], None],
    error_proveedor: type[Exception],
    sin_reintento: tuple[type[Exception], ...] = (),
    ahora: datetime | None = None,
) -> dict[str, int]:
    """
    Una vuelta del ciclo. ``auditar`` repite la auditoría completa (y persiste
    su dictamen); ``avisar`` informa al core. Se detiene en cuanto el proveedor
    vuelve a fallar.
    """
    resumen = {"auditadas": 0, "reprogramadas": 0, "agotadas": 0, "descartadas": 0}
    for diferida in vencidas(ahora):
        try:
            auditar(diferida.peticion)
        except error_proveedor as exc:
            nueva = registrar_fallo(diferida.peticion, str(exc))
            avisar(nueva.documento_id, nueva.aviso())
            if nueva.agotada:
                quitar(nueva.documento_id)
                resumen["agotadas"] += 1
            else:
                resumen["reprogramadas"] += 1
            break  # el proveedor sigue sin responder: las demás esperan a la siguiente vuelta
        except sin_reintento:
            quitar(diferida.documento_id)
            resumen["descartadas"] += 1
        else:
            quitar(diferida.documento_id)
            resumen["auditadas"] += 1
    return resumen


def iniciar_ciclo(paso: Callable[[], dict[str, int]]) -> threading.Event | None:
    """Hilo en segundo plano que llama a ``paso`` cada ``DIFERIDOS_INTERVALO_MINUTOS``; 0 lo desactiva."""
    minutos = settings.DIFERIDOS_INTERVALO_MINUTOS
    if minutos <= 0:
        return None
    detener = threading.Event()

    def bucle() -> None:
        while not detener.wait(minutos * 60):
            try:
                resumen = paso()
                if any(resumen.values()):
                    print(f"[ai-service] Procesamiento diferido: {resumen}")
            except Exception as exc:  # noqa: BLE001 - el ciclo no debe detener el servicio
                print(f"[ai-service] Ciclo de procesamiento diferido fallido: {exc}")

    threading.Thread(target=bucle, name="procesamiento-diferido", daemon=True).start()
    return detener
