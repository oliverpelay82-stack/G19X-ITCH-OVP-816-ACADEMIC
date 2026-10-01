"""
Persistencia permanente del texto extraído por el Nivel 3 (SQLite).

La llave es la huella SHA-256 del binario, no el ``documento_id``: el contenido
de la bóveda es inmutable (NOM-151), así que el mismo archivo produce siempre el
mismo texto, aunque se cargue dos veces o llegue por el endpoint de extracción
directa. Así un documento ya leído no vuelve a pasar por OCR aunque se reinicie
el servicio o se apague la máquina.

Se guarda por separado la lectura con corte temprano (``completo = 0``) y la
lectura de todas las páginas (``completo = 1``). Una lectura completa nunca se
sobrescribe con una parcial de la misma versión.

Cada lectura lleva la versión del Nivel 3 que la produjo
(``extraccion_pipeline.version_lectura``). Una lectura de otra versión se
ignora y el documento se vuelve a leer: el texto que analiza el Nivel 4 y las
palabras con coordenadas que usa el visor provienen siempre de la misma lectura.

SQLite viene incluido en Python, no requiere servidor y mantiene al ai-service
desacoplado de la base de datos de los otros microservicios (DOC-08).

La tabla ``inferencias`` guarda, en la misma base, la respuesta JSON del modelo
por huella de la petición exacta (ver ``clients/groq_client.py``): una
reauditoría del mismo documento no vuelve a consumir tokens de Groq.

La tabla ``fichas_documento`` guarda, por huella del binario, los datos que la
última auditoría extrajo y verificó (T0, PLUS-07): con ellos el chat responde las
preguntas factuales sin llamar al modelo.
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
    version       TEXT    NOT NULL DEFAULT '',
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

_ESQUEMA_FICHAS = """
CREATE TABLE IF NOT EXISTS fichas_documento (
    sha256       TEXT PRIMARY KEY,   -- huella del binario auditado
    dictamen_id  TEXT NOT NULL,      -- dictamen del core que produjo la ficha
    ficha        TEXT NOT NULL,      -- JSON: datos extraídos y verificaciones con su cita
    creado_en    TEXT NOT NULL
)
"""

_ESQUEMA_PALABRAS = """
CREATE TABLE IF NOT EXISTS palabras_ocr (
    sha256     TEXT    NOT NULL,
    pagina     INTEGER NOT NULL,   -- 1-based
    palabras   TEXT    NOT NULL,   -- [[x0, y0, x1, y1, texto, renglón], ...] normalizadas a [0, 1]
    creado_en  TEXT    NOT NULL,
    version    TEXT    NOT NULL DEFAULT '',
    texto      TEXT,                -- texto de la página (misma lectura que las palabras)
    confianza  REAL,
    sellos     TEXT,                -- [{"tipo", "x0", "y0", "x1", "y1"}, ...]
    PRIMARY KEY (sha256, pagina)
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
        conexion.execute(_ESQUEMA_PALABRAS)
        conexion.execute(_ESQUEMA_FICHAS)
        # Migración de bases previas a la versión en la llave: sus filas quedan
        # con versión vacía, que no coincide con ninguna, y se releen.
        for tabla in ("extracciones", "palabras_ocr"):
            columnas = {c[1] for c in conexion.execute(f"PRAGMA table_info({tabla})")}
            if "version" not in columnas:
                conexion.execute(f"ALTER TABLE {tabla} ADD COLUMN version TEXT NOT NULL DEFAULT ''")
        columnas = {c[1] for c in conexion.execute("PRAGMA table_info(palabras_ocr)")}
        for columna, tipo in (("texto", "TEXT"), ("confianza", "REAL"), ("sellos", "TEXT")):
            if columna not in columnas:
                conexion.execute(f"ALTER TABLE palabras_ocr ADD COLUMN {columna} {tipo}")
        conexion.commit()
        _inicializada.add(ruta)
    return conexion


def conexion() -> sqlite3.Connection:
    """Conexión a la base del ai-service con sus tablas creadas (la usa la cola de diferidos, P5)."""
    return _conectar()


def candado_escritura() -> Lock:
    """Candado que serializa las escrituras en la base del ai-service."""
    return _candado_escritura


def _version() -> str:
    from pipelines.extraccion_pipeline import version_lectura  # import diferido: evita el ciclo con el pipeline

    return version_lectura()


def leer(sha256: str, forzar_ocr: bool = False) -> ExtraccionPersistida | None:
    """Devuelve la extracción guardada para esa huella por la versión vigente del Nivel 3, o ``None``."""
    try:
        with closing(_conectar()) as conexion:
            fila = conexion.execute(
                "SELECT texto, traza, completo FROM extracciones WHERE sha256 = ? AND forzar_ocr = ? AND version = ?",
                (sha256, int(forzar_ocr), _version()),
            ).fetchone()
    except sqlite3.Error:
        # La persistencia acelera, pero nunca debe tumbar el análisis.
        return None
    if not fila:
        return None
    return ExtraccionPersistida(texto=fila[0], traza=json.loads(fila[1]), completo=bool(fila[2]))


def guardar(sha256: str, forzar_ocr: bool, texto: str, traza: dict[str, Any], completo: bool) -> None:
    """Guarda la extracción; una lectura completa nunca se reemplaza por una parcial de la misma versión."""
    traza_sin_texto = {k: v for k, v in traza.items() if k != "texto_extraido"}
    try:
        with _candado_escritura, closing(_conectar()) as conexion:
            conexion.execute(
                """
                INSERT INTO extracciones (sha256, forzar_ocr, completo, texto, traza, actualizado_en, version)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT (sha256, forzar_ocr) DO UPDATE SET
                    completo = excluded.completo,
                    texto = excluded.texto,
                    traza = excluded.traza,
                    actualizado_en = excluded.actualizado_en,
                    version = excluded.version
                WHERE excluded.completo >= extracciones.completo OR excluded.version != extracciones.version
                """,
                (
                    sha256,
                    int(forzar_ocr),
                    int(completo),
                    texto,
                    json.dumps(traza_sin_texto, ensure_ascii=False),
                    datetime.now(timezone.utc).isoformat(),
                    _version(),
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


def guardar_ficha(sha256: str, dictamen_id: str, ficha: dict[str, Any]) -> None:
    """Ficha de la última auditoría del binario; una auditoría nueva la sustituye."""
    try:
        with _candado_escritura, closing(_conectar()) as conexion:
            conexion.execute(
                "INSERT OR REPLACE INTO fichas_documento (sha256, dictamen_id, ficha, creado_en) VALUES (?, ?, ?, ?)",
                (sha256, dictamen_id, json.dumps(ficha, ensure_ascii=False), datetime.now(timezone.utc).isoformat()),
            )
            conexion.commit()
    except sqlite3.Error:
        pass


def leer_ficha(sha256: str) -> dict[str, Any] | None:
    """Devuelve ``{"dictamen_id", "ficha"}`` o ``None``."""
    try:
        with closing(_conectar()) as conexion:
            fila = conexion.execute(
                "SELECT dictamen_id, ficha FROM fichas_documento WHERE sha256 = ?", (sha256,)
            ).fetchone()
    except sqlite3.Error:
        return None
    return {"dictamen_id": fila[0], "ficha": json.loads(fila[1])} if fila else None


def leer_palabras(sha256: str, pagina: int) -> list[list[Any]] | None:
    """Palabras con recuadro de una página escaneada, de la versión vigente del Nivel 3."""
    with closing(_conectar()) as conexion:
        fila = conexion.execute(
            "SELECT palabras FROM palabras_ocr WHERE sha256 = ? AND pagina = ? AND version = ?",
            (sha256, pagina, _version()),
        ).fetchone()
    return json.loads(fila[0]) if fila else None


def guardar_palabras(
    sha256: str,
    pagina: int,
    palabras: list[list[Any]],
    texto: str | None = None,
    confianza: float | None = None,
    sellos: list[dict[str, Any]] | None = None,
) -> None:
    """Guarda el reconocimiento de una página escaneada: palabras con recuadro, texto, confianza y sellos."""
    with _candado_escritura, closing(_conectar()) as conexion:
        conexion.execute(
            "INSERT OR REPLACE INTO palabras_ocr "
            "(sha256, pagina, palabras, creado_en, version, texto, confianza, sellos) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (sha256, pagina, json.dumps(palabras, ensure_ascii=False), datetime.now(timezone.utc).isoformat(),
             _version(), texto, confianza, json.dumps(sellos or [], ensure_ascii=False)),
        )
        conexion.commit()


def paginas_reconocidas(sha256: str) -> dict[int, tuple[str, float, list[list[Any]], list[dict[str, Any]]]]:
    """
    Páginas escaneadas de ese archivo ya reconocidas por la versión vigente del
    Nivel 3 (por una lectura parcial previa o por el visor): (texto, confianza,
    palabras, sellos). La lectura completa las reutiliza en lugar de repetir su OCR.
    """
    try:
        with closing(_conectar()) as conexion:
            filas = conexion.execute(
                "SELECT pagina, texto, confianza, palabras, sellos FROM palabras_ocr "
                "WHERE sha256 = ? AND version = ? AND texto IS NOT NULL",
                (sha256, _version()),
            ).fetchall()
    except sqlite3.Error:
        return {}
    return {
        pagina: (texto, float(confianza or 0.0), json.loads(palabras), json.loads(sellos or "[]"))
        for pagina, texto, confianza, palabras, sellos in filas
    }


def estadisticas() -> dict[str, Any]:
    try:
        with closing(_conectar()) as conexion:
            total, completos = conexion.execute(
                "SELECT COUNT(*), COALESCE(SUM(completo), 0) FROM extracciones"
            ).fetchone()
        return {"documentos_persistidos": total, "lecturas_completas": completos}
    except sqlite3.Error as exc:
        return {"error": str(exc)}
