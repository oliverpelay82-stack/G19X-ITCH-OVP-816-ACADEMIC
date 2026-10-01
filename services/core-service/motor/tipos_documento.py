"""
RF-09 — Tipos de documento declarados por reglas dinámicas (RDS-01).

El catálogo base de 22 tipos (config/catalogo.py, DOC-02) no es una lista
cerrada: un tipo nuevo se declara con una regla RDS en el rules-service, que
los publica en GET /reglas/tipos-documento. Este módulo los consulta con una
caché breve para:

  * admitirlos en la carga (solo los activos), y
  * registrar su nombre en el catálogo, para que alertas, motivos y reportes
    digan «Permiso de Impacto Ambiental» y no el código.

Si el rules-service no responde se conserva lo último conocido y no se vuelve
a preguntar hasta que vence la caché; los tipos base nunca dependen de él.
"""
from __future__ import annotations

import threading
import time
from typing import Any

from clients import rules_client
from config import catalogo

# Segundos que se reutiliza la consulta al rules-service.
TTL_SEGUNDOS = 60.0

_declarados: dict[str, dict[str, Any]] = {}
_consultado_en: float | None = None
_candado = threading.Lock()


def tipos_declarados(forzar: bool = False) -> dict[str, dict[str, Any]]:
    """Tipos declarados que no son del catálogo base, por código, con su nombre y si están activos."""
    global _declarados, _consultado_en
    with _candado:
        vigente = _consultado_en is not None and time.monotonic() - _consultado_en < TTL_SEGUNDOS
        if vigente and not forzar:
            return _declarados
    lista = rules_client.tipos_documento_declarados()
    with _candado:
        _consultado_en = time.monotonic()
        if lista is not None:
            _declarados = {
                t["tipo_documento"].upper(): t for t in lista
                if t["tipo_documento"].upper() not in catalogo.TIPOS_DOCUMENTO
            }
            catalogo.registrar_nombres_declarados({codigo: t["nombre"] for codigo, t in _declarados.items()})
        return _declarados


def tipo_admitido(tipo: str) -> bool:
    """La carga admite los tipos del catálogo base y los declarados activos."""
    if tipo in catalogo.TIPOS_DOCUMENTO:
        return True
    if not catalogo.FORMATO_CODIGO_TIPO.match(tipo):
        return False
    # Un tipo recién declarado aún no está en la caché: se pregunta de nuevo.
    declarado = tipos_declarados().get(tipo) or tipos_declarados(forzar=True).get(tipo)
    return bool(declarado and declarado.get("activo"))


def refrescar_si_hay_desconocidos(tipos: set[str]) -> None:
    """Antes de redactar alertas y reportes: actualiza los nombres si aparece un tipo fuera del catálogo base."""
    if any(t and t.upper() not in catalogo.TIPOS_DOCUMENTO and t.upper() != "OTRO" for t in tipos):
        tipos_declarados()
