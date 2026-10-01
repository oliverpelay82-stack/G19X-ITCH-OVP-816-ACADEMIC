"""
Registro de eventos en la bitácora inmutable (RF-27, protocolo DOC-05 §5.6),
sellados en cadena (P3, PLUS-04 y PLUS-05, PRD §21.3).

La función solo agrega la entrada a la sesión: la confirma la misma transacción
que produjo el evento, de modo que no puede quedar un evento registrado sin su
efecto ni un efecto sin su evento.

Sellado. Cada evento lleva ``secuencia``, ``hash_anterior`` (el ``hash_evento``
del evento previo) y ``hash_evento``: SHA-256 del JSON canónico de su
contenido y de ``hash_anterior``. Los triggers impiden UPDATE y DELETE; el
sello, además, delata una alteración hecha con los triggers desactivados,
porque rompe el hash del evento o su enlace con el siguiente.

  * ``pg_advisory_xact_lock`` serializa los sellos hasta el COMMIT: dos
    transacciones no pueden encadenarse al mismo evento. El índice único de
    ``secuencia`` lo impide de todos modos si el candado no existiera.
  * La fecha del evento la da el reloj de la base (``clock_timestamp()``), en
    la misma zona que la columna: el valor sellado es el que queda guardado.
  * El historial anterior al sellado no se toca (los triggers lo impiden): el
    primer evento sellado es ``SELLO_GENESIS``, con el número de eventos
    previos y la huella de todos ellos, en orden de creación.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from models.bitacora import EVENTO_SELLO_GENESIS, BitacoraAuditoria
from models.sello_tiempo import SelloTiempo
from config import observabilidad

USUARIO_SISTEMA = "SISTEMA"
HASH_INICIAL = "0" * 64
MAX_HALLAZGOS = 20
ALGORITMO = "SHA-256 del JSON canónico (claves ordenadas, UTF-8, sin espacios)"


def _canonico(datos: dict[str, Any]) -> str:
    return json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":"), default=str)


def _fecha(valor: datetime | None) -> str | None:
    return valor.replace(tzinfo=None).isoformat(timespec="microseconds") if valor else None


def huella_evento(e: BitacoraAuditoria) -> str:
    """SHA-256 del contenido del evento y de su enlace con el anterior."""
    contenido = {
        "secuencia": e.secuencia,
        "evento": e.evento,
        "expediente_id": e.expediente_id,
        "documento_id": e.documento_id,
        "dictamen_id": e.dictamen_id,
        "usuario": e.usuario,
        "ip_origen": e.ip_origen,
        "detalle": e.detalle or {},
        "creado_en": _fecha(e.creado_en),
        "hash_anterior": e.hash_anterior,
    }
    return hashlib.sha256(_canonico(contenido).encode("utf-8")).hexdigest()


def _es_postgres(db: Session) -> bool:
    return db.get_bind().dialect.name == "postgresql"


def _ahora(db: Session) -> datetime:
    if _es_postgres(db):
        return db.execute(text("SELECT clock_timestamp()::timestamp")).scalar()
    return datetime.now(timezone.utc).replace(tzinfo=None)


def ultimo_sellado(db: Session) -> BitacoraAuditoria | None:
    return (
        db.query(BitacoraAuditoria)
        .filter(BitacoraAuditoria.secuencia.isnot(None))
        .order_by(BitacoraAuditoria.secuencia.desc())
        .first()
    )


def _previos(db: Session, hasta: datetime | None = None) -> list[BitacoraAuditoria]:
    """Eventos sin sellar (anteriores al sellado), en orden de creación."""
    query = db.query(BitacoraAuditoria).filter(BitacoraAuditoria.secuencia.is_(None))
    if hasta is not None:
        query = query.filter(BitacoraAuditoria.creado_en <= hasta)
    return query.order_by(BitacoraAuditoria.creado_en, BitacoraAuditoria.id).all()


def huella_historial(eventos: list[BitacoraAuditoria]) -> str:
    """Huella acumulada de los eventos previos al sellado: cada paso encadena la del evento siguiente."""
    acumulada = HASH_INICIAL
    for e in eventos:
        acumulada = hashlib.sha256((acumulada + huella_evento(e)).encode("ascii")).hexdigest()
    return acumulada


def _sellar(db: Session, entrada: BitacoraAuditoria, anterior: BitacoraAuditoria | None) -> BitacoraAuditoria:
    entrada.creado_en = _ahora(db)
    entrada.secuencia = anterior.secuencia + 1 if anterior else 1
    entrada.hash_anterior = anterior.hash_evento if anterior else HASH_INICIAL
    entrada.hash_evento = huella_evento(entrada)
    db.add(entrada)
    # Sin autoflush: el siguiente evento de la misma transacción debe ver este.
    db.flush()
    return entrada


def _sellar_genesis(db: Session) -> BitacoraAuditoria:
    previos = _previos(db)
    genesis = BitacoraAuditoria(
        evento=EVENTO_SELLO_GENESIS,
        usuario=USUARIO_SISTEMA,
        detalle={
            "eventos_previos": len(previos),
            "huella_historial_previo": huella_historial(previos),
            "desde": _fecha(previos[0].creado_en) if previos else None,
            "hasta": _fecha(previos[-1].creado_en) if previos else None,
            "algoritmo": ALGORITMO,
        },
    )
    return _sellar(db, genesis, None)


def _con_folio(detalle: dict[str, Any] | None) -> dict[str, Any]:
    folio = observabilidad.actual()
    detalle = dict(detalle or {})
    if folio and "id_peticion" not in detalle:
        detalle["id_peticion"] = folio
    return detalle


def registrar(
    db: Session,
    evento: str,
    *,
    expediente_id: str | None = None,
    documento_id: str | None = None,
    dictamen_id: str | None = None,
    usuario: str = USUARIO_SISTEMA,
    ip_origen: str | None = None,
    detalle: dict[str, Any] | None = None,
) -> BitacoraAuditoria:
    if _es_postgres(db):
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('bitacora_cadena'))"))
    anterior = ultimo_sellado(db) or _sellar_genesis(db)
    entrada = BitacoraAuditoria(
        evento=evento,
        expediente_id=expediente_id,
        documento_id=documento_id,
        dictamen_id=dictamen_id,
        usuario=usuario or USUARIO_SISTEMA,
        ip_origen=ip_origen,
        # El detalle se sella tal como se leerá de la columna JSON. PLUS-21: con el
        # folio de la petición que lo originó (los ciclos programados no lo tienen).
        detalle=json.loads(json.dumps(_con_folio(detalle), default=str)),
    )
    return _sellar(db, entrada, anterior)


def verificar_cadena(db: Session) -> dict[str, Any]:
    """
    Recalcula la cadena completa (PLUS-05): enlace y hash de cada evento
    sellado, secuencia sin huecos, huella del historial previo contra la del
    génesis y eventos sin sellar insertados después del génesis.
    """
    sellados = (
        db.query(BitacoraAuditoria)
        .filter(BitacoraAuditoria.secuencia.isnot(None))
        .order_by(BitacoraAuditoria.secuencia)
        .all()
    )
    hallazgos: list[dict[str, Any]] = []

    def hallazgo(secuencia: int | None, evento_id: str | None, problema: str) -> None:
        hallazgos.append({"secuencia": secuencia, "evento_id": evento_id, "problema": problema})

    sello_tiempo = _verificar_sellos_tiempo(db, {e.secuencia: e for e in sellados}, hallazgo)

    if not sellados:
        previos = _previos(db)
        return {"integra": not hallazgos, "sellada": False, "eventos_sellados": 0, "eventos_previos": len(previos),
                "ultimo_hash": None, "ultima_secuencia": None, "verificado_en": _fecha(_ahora(db)),
                "algoritmo": ALGORITMO, "total_hallazgos": len(hallazgos), "hallazgos": hallazgos[:MAX_HALLAZGOS],
                "sello_tiempo": sello_tiempo}

    esperado, enlace = 1, HASH_INICIAL
    for e in sellados:
        if e.secuencia != esperado:
            hallazgo(e.secuencia, e.id, f"Faltan los eventos {esperado} a {e.secuencia - 1}: fueron borrados.")
        if e.hash_anterior != enlace:
            hallazgo(e.secuencia, e.id, "El enlace con el evento anterior no coincide: la cadena se rompió aquí.")
        if huella_evento(e) != e.hash_evento:
            hallazgo(e.secuencia, e.id, "El contenido del evento no corresponde a su sello: fue alterado.")
        esperado, enlace = e.secuencia + 1, e.hash_evento

    genesis = sellados[0]
    eventos_previos = 0
    if genesis.evento != EVENTO_SELLO_GENESIS or genesis.secuencia != 1:
        hallazgo(genesis.secuencia, genesis.id, "El primer evento sellado no es el génesis de la cadena.")
    else:
        previos = _previos(db, hasta=genesis.creado_en)
        eventos_previos = len(previos)
        datos = genesis.detalle or {}
        if datos.get("eventos_previos") != len(previos) or datos.get("huella_historial_previo") != huella_historial(previos):
            hallazgo(genesis.secuencia, genesis.id,
                     "El historial anterior al sellado ya no coincide con la huella del génesis.")
        intrusos = (
            db.query(BitacoraAuditoria)
            .filter(BitacoraAuditoria.secuencia.is_(None), BitacoraAuditoria.creado_en > genesis.creado_en)
            .order_by(BitacoraAuditoria.creado_en)
            .all()
        )
        for e in intrusos:
            hallazgo(None, e.id, f"Evento {e.evento} sin sellar posterior al génesis: se insertó por fuera del motor.")

    ultimo = sellados[-1]
    return {
        "integra": not hallazgos,
        "sellada": True,
        "eventos_sellados": len(sellados),
        "eventos_previos": eventos_previos,
        "ultimo_hash": ultimo.hash_evento,
        "ultima_secuencia": ultimo.secuencia,
        "verificado_en": _fecha(_ahora(db)),
        "algoritmo": ALGORITMO,
        "total_hallazgos": len(hallazgos),
        "hallazgos": hallazgos[:MAX_HALLAZGOS],
        "sello_tiempo": sello_tiempo,
    }


def _verificar_sellos_tiempo(db: Session, por_secuencia: dict[int, BitacoraAuditoria], hallazgo) -> dict[str, Any] | None:
    """
    P7 (PLUS-22): cada sello de tiempo debe seguir coincidiendo con el eslabón
    que cubrió. Si la cadena se reescribió completa (con los hashes
    recalculados), el enlace no lo delata, pero el sello de la autoridad sí.
    Devuelve el último sello con su resultado, o None si no hay ninguno.
    """
    from motor import sello_tiempo  # importa este módulo: se resuelve al usarse

    sellos = db.query(SelloTiempo).order_by(SelloTiempo.secuencia, SelloTiempo.creado_en).all()
    for s in sellos:
        e = por_secuencia.get(s.secuencia)
        if e is None or e.hash_evento != s.hash_evento:
            hallazgo(s.secuencia, e.id if e else s.evento_id,
                     f"El sello de tiempo del {s.fecha_sello.isoformat(sep=' ', timespec='seconds')} UTC cubre este "
                     "eslabón, pero su huella ya no coincide: la bitácora se reescribió después de esa fecha.")
    if not sellos:
        return None
    ultimo = sellos[-1]
    e = por_secuencia.get(ultimo.secuencia)
    return sello_tiempo.resumen(ultimo, coincide=e is not None and e.hash_evento == ultimo.hash_evento)
