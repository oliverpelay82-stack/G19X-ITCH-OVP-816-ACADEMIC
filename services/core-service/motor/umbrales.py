"""
Umbrales de anticipación de las alertas de vencimiento (RF-17, HU-14;
docs/uml/hu14-actividad-umbrales-vencimiento.puml).

Tres días de anticipación, de mayor a menor, uno por severidad de la alerta
«Próximo a vencer»: hasta el primero, Media; hasta el segundo, Media-alta; hasta
el tercero, Alta (PRD §10.3). Rigen también el aviso por correo de la
reevaluación programada (RF-20) y las franjas de la gráfica de vencimientos.

El administrador los cambia desde la interfaz (tabla parametros_sistema); sin
valor guardado rige UMBRALES_ALERTA_VENCIMIENTO (por omisión 30, 15 y 5). Se leen
en cada evaluación, así que un cambio surte efecto en la siguiente consulta.
"""
from __future__ import annotations

import os
from typing import Any

from sqlalchemy.orm import Session

from models.bitacora import EVENTO_ACTUALIZACION_PARAMETRO
from models.parametro import ParametroSistema
from motor import bitacora

CLAVE = "umbrales_vencimiento"
CANTIDAD = 3
MINIMO, MAXIMO = 1, 365


def predeterminados() -> tuple[int, ...]:
    """Los de UMBRALES_ALERTA_VENCIMIENTO; si la variable no trae ninguno válido, 30, 15 y 5."""
    valores = []
    for parte in os.getenv("UMBRALES_ALERTA_VENCIMIENTO", "30,15,5").split(","):
        try:
            valores.append(int(parte))
        except ValueError:
            continue
    return tuple(sorted({v for v in valores if v >= 0}, reverse=True)) or (30, 15, 5)


def vigentes(db: Session) -> tuple[int, ...]:
    fila = db.get(ParametroSistema, CLAVE)
    return tuple(int(v) for v in fila.valor) if fila else predeterminados()


def problema(valores: list[int]) -> str | None:
    """Por qué no se aceptan los valores, en lenguaje llano; None si son válidos."""
    if len(valores) != CANTIDAD:
        return f"Se necesitan exactamente {CANTIDAD} umbrales, uno por severidad de la alerta."
    if any(v < MINIMO or v > MAXIMO for v in valores):
        return f"Cada umbral debe estar entre {MINIMO} y {MAXIMO} días."
    if any(a <= b for a, b in zip(valores, valores[1:])):
        return "Los umbrales deben ir de mayor a menor y ser distintos (por ejemplo, 30, 15 y 5)."
    return None


def estado(db: Session) -> dict[str, Any]:
    fila = db.get(ParametroSistema, CLAVE)
    return {
        "umbrales": list(vigentes(db)),
        "configurado": fila is not None,
        "actualizado_en": fila.actualizado_en if fila else None,
        "actualizado_por": fila.actualizado_por if fila else None,
    }


def guardar(db: Session, valores: list[int], *, usuario: str, ip_origen: str | None = None) -> bool:
    """
    Guarda los umbrales (ya validados con ``problema``) y registra el cambio en la
    bitácora con el valor anterior y el nuevo. Si no cambian, no escribe nada.
    No confirma la transacción.
    """
    anteriores = list(vigentes(db))
    if anteriores == list(valores):
        return False
    fila = db.get(ParametroSistema, CLAVE)
    if fila is None:
        db.add(ParametroSistema(clave=CLAVE, valor=list(valores), actualizado_por=usuario))
    else:
        fila.valor = list(valores)
        fila.actualizado_por = usuario
    bitacora.registrar(
        db, EVENTO_ACTUALIZACION_PARAMETRO, usuario=usuario, ip_origen=ip_origen,
        detalle={"parametro": CLAVE, "anterior": anteriores, "nuevo": list(valores)},
    )
    return True
