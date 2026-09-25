"""
Persistencia permanente del texto extraído por el Nivel 3 (SQLite).

La llave es la huella SHA-256 del binario, no el ``documento_id``: el contenido
de la bóveda es inmutable (NOM-151), así que el mismo archivo produce siempre el
mismo texto, aunque se cargue dos veces o llegue por el endpoint de extracción
directa. Así un documento ya leído no vuelve a pasar por OCR aunque se reinicie
el servicio o se apague la máquina.

Se guarda por separado la lectura con corte temprano (``completo = 0``) y la
lectura de todas las páginas (``completo = 1``). Una lectura completa nunca se
sobrescribe con una parcial.

SQLite viene incluido en Python, no requiere servidor y mantiene al ai-service
desacoplado de la base de datos de los otros microservicios (DOC-08).

La tabla ``inferencias`` guarda, en la misma base, la respuesta JSON del modelo
por huella de la petición exacta (ver ``clients/groq_client.py``): una
reauditoría del mismo documento no vuelve a consumir tokens de Groq.
"""
from __future__ import annotations

import json
import os
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import Any

from config import settings

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS extracciones (
    sha256        TEXT    NOT NULL,
    forzar_ocr    INTEGER NOT NULL,
    completo      INTEGER NOT NULL,
    texto         TEXT    NOT NULL,
    traza         TEXT    NOT NULL,
    actualizado_en TEXT   NOT NULL,
    PRIMARY KEY (sha256, forzar_ocr)
)
"""

_ESQUEMA_INFERENCIAS = """
CREATE TABLE IF NOT EXISTS inferencias (
    clave      TEXT PRIMARY KEY,   -- SHA-256 de modelo + parámetros + mensajes
    respuesta  TEXT NOT NULL,      -- objeto JSON devuelto por el modelo
    creado_en  TEXT NOT NULL
)
"""

_candado_escritura = Lock()
_inicializada: set[str] = set()


@dataclass
class ExtraccionPersistida:
    texto: str
    traza: dict[str, Any]
    completo: bool


def _conectar() -> sqlite3.Connection:
    ruta = settings.EXTRACCIONES_DB_PATH
    if ruta not in _inicializada:
        os.makedirs(os.path.dirname(ruta) or ".", exist_ok=True)
    conexion = sqlite3.connect(ruta, timeout=10)
    if ruta not in _inicializada:
        conexion.execute("PRAGMA journal_mode=WAL")
        conexion.execute(_ESQUEMA)
        conexion.execute(_ESQUEMA_INFERENCIAS)
        conexion.commit()
        _inicializada.add(ruta)
    return conexion


def leer(sha256: str, forzar_ocr: bool = False) -> ExtraccionPersistida | None:
    """Devuelve la extracción guardada para esa huella, o ``None``."""
    try:
        with closing(_conectar()) as conexion:
            fila = conexion.execute(
                "SELECT texto, traza, completo FROM extracciones WHERE sha256 = ? AND forzar_ocr = ?",
                (sha256, int(forzar_ocr)),
            ).fetchone()
    except sqlite3.Error:
        # La persistencia acelera, pero nunca debe tumbar el análisis.
        return None
    if not fila:
        return None
    return ExtraccionPersistida(texto=fila[0], traza=json.loads(fila[1]), completo=bool(fila[2]))


def guardar(sha256: str, forzar_ocr: bool, texto: str, traza: dict[str, Any], completo: bool) -> None:
    """Guarda la extracción; una lectura completa nunca se reemplaza por una parcial."""
    traza_sin_texto = {k: v for k, v in traza.items() if k != "texto_extraido"}
    try:
        with _candado_escritura, closing(_conectar()) as conexion:
            conexion.execute(
                """
                INSERT INTO extracciones (sha256, forzar_ocr, completo, texto, traza, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT (sha256, forzar_ocr) DO UPDATE SET
                    completo = excluded.completo,
                    texto = excluded.texto,
                    traza = excluded.traza,
                    actualizado_en = excluded.actualizado_en
                WHERE excluded.completo >= extracciones.completo
                """,
                (
                    sha256,
                    int(forzar_ocr),
                    int(completo),
                    texto,
                    json.dumps(traza_sin_texto, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conexion.commit()
    except sqlite3.Error:
        pass


def leer_inferencia(clave: str) -> dict[str, Any] | None:
    """Devuelve la respuesta guardada del modelo para esa petición, o ``None``."""
    try:
        with closing(_conectar()) as conexion:
            fila = conexion.execute("SELECT respuesta FROM inferencias WHERE clave = ?", (clave,)).fetchone()
    except sqlite3.Error:
        return None
    return json.loads(fila[0]) if fila else None


def guardar_inferencia(clave: str, respuesta: dict[str, Any]) -> None:
    """Guarda la respuesta del modelo; la primera respuesta a una petición es la que queda."""
    try:
        with _candado_escritura, closing(_conectar()) as conexion:
            conexion.execute(
                "INSERT OR IGNORE INTO inferencias (clave, respuesta, creado_en) VALUES (?, ?, ?)",
                (clave, json.dumps(respuesta, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
            )
            conexion.commit()
    except sqlite3.Error:
        pass


def estadisticas() -> dict[str, Any]:
    try:
        with closing(_conectar()) as conexion:
            total, completos = conexion.execute(
                "SELECT COUNT(*), COALESCE(SUM(completo), 0) FROM extracciones"
            ).fetchone()
        return {"documentos_persistidos": total, "lecturas_completas": completos}
    except sqlite3.Error as exc:
        return {"error": str(exc)}
