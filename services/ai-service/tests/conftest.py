"""
Aislamiento común de las pruebas del ai-service con pytest.

Cada prueba usa una SQLite temporal propia: las respuestas simuladas del modelo
que el caché del chat guarda (PLUS-10) y los textos de documentos de prueba
nunca llegan a ``services/ai-service/data/``, la base de desarrollo.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import settings  # noqa: E402


@pytest.fixture(autouse=True)
def _sqlite_temporal(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "EXTRACCIONES_DB_PATH", str(tmp_path / "extracciones.sqlite3"))
