"""
Ejecución programada del motor de validación (DOC-02: «ejecución manual o
programada del motor de validación»).

La vigencia de cada documento se recalcula contra la fecha actual (RN-02), pero
solo cuando alguien consulta el expediente. Sin una ejecución programada, un
documento que vence un fin de semana dejaría el semáforo guardado en verde y la
bitácora sin constancia del cambio hasta la siguiente consulta. Esta tarea
reevalúa todos los expedientes cada ``REEVALUACION_INTERVALO_HORAS`` (24 por
defecto; 0 la desactiva) y registra cada cambio de semáforo en la bitácora con
la causa ``REEVALUACION_PROGRAMADA``.

No ejecuta la IA: solo recalcula el semáforo con los dictámenes ya emitidos.

P5 (PLUS-14): antes de reevaluar barre la integridad de toda la bóveda
(``integridad.barrer``), así un archivo alterado que nadie abre se refleja en
el semáforo de ese mismo ciclo. ``BARRIDO_INTEGRIDAD=false`` lo desactiva.
"""
import asyncio
import os
from dataclasses import dataclass

from config.database import SessionLocal
from models.expediente import Expediente
from motor import cumplimiento, integridad

CAUSA = "REEVALUACION_PROGRAMADA"


@dataclass
class ResultadoReevaluacion:
    evaluados: int
    cambios: int
    barrido: integridad.ResultadoBarrido | None = None


def barrido_activo() -> bool:
    """El barrido de integridad corre en cada ciclo salvo con ``BARRIDO_INTEGRIDAD=false``."""
    return os.getenv("BARRIDO_INTEGRIDAD", "true").strip().lower() not in ("false", "0", "no")


def barrer_integridad() -> integridad.ResultadoBarrido:
    """Barrido en su propia sesión: cada alteración se confirma con su dictamen y su evento."""
    db = SessionLocal()
    try:
        return integridad.barrer(db)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def intervalo_horas() -> float:
    """Horas entre ejecuciones; 0 (o un valor inválido o negativo) desactiva la tarea."""
    try:
        return max(float(os.getenv("REEVALUACION_INTERVALO_HORAS", "24")), 0.0)
    except ValueError:
        return 0.0


def reevaluar_todos() -> ResultadoReevaluacion:
    """Barre la integridad de la bóveda y reevalúa y sincroniza todos los expedientes."""
    barrido = barrer_integridad() if barrido_activo() else None
    db = SessionLocal()
    try:
        cache = cumplimiento.CacheInventarios()
        evaluados = cambios = 0
        for expediente in db.query(Expediente).all():
            evaluacion = cumplimiento.evaluar(db, expediente, cache.para(expediente))
            if cumplimiento.sincronizar(db, expediente, evaluacion, causa=CAUSA):
                cambios += 1
            evaluados += 1
        db.commit()
        return ResultadoReevaluacion(evaluados, cambios, barrido)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


async def ciclo(horas: float) -> None:
    """Primera ejecución al arrancar (cubre el tiempo que el servicio estuvo detenido), luego cada `horas`."""
    while True:
        try:
            r = await asyncio.to_thread(reevaluar_todos)
            integridad_txt = (f" Integridad: {r.barrido.revisados} documentos, {r.barrido.alterados} alterados."
                              if r.barrido else "")
            print(f"[core-service] Reevaluación programada: {r.evaluados} expedientes, {r.cambios} cambios de semáforo."
                  f"{integridad_txt}")
        except Exception as exc:  # la tarea no debe detener el servicio; se reintenta en el siguiente ciclo
            print(f"[core-service] Reevaluación programada fallida: {exc}")
        await asyncio.sleep(horas * 3600)
