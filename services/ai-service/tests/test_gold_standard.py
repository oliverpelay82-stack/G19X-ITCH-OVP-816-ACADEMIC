"""
Integridad del Gold Standard (docs/VALIDACION_CUANTITATIVA.md §2): la anotación
está congelada y es coherente con los catálogos del motor. Offline.

  1. gold_standard.json coincide con la huella de gold_standard.sha256 (un
     cambio de la anotación exige un commit propio que actualice la huella).
  2. Cada PDF coincide con la huella anotada.
  3. Cada elemento esperado es una regla RSC de la instantánea del catálogo,
     del tipo registrado del caso; el estatus es uno de los tres del DOC-08.
  4. El tipo esperado es una clave del catálogo del Nivel 4.

Uso:  cd services/ai-service && python -m pytest tests/test_gold_standard.py
"""
import hashlib
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluacion import gold_standard as gs  # noqa: E402
from pipelines.analisis_semantico import TIPOS_DOCUMENTALES  # noqa: E402


def _sha256(ruta: str) -> str:
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _anotacion() -> dict:
    with open(gs.RUTA_ANOTACION, encoding="utf-8") as f:
        return json.load(f)


def test_la_anotacion_esta_congelada():
    with open(gs.RUTA_HUELLA, encoding="utf-8") as f:
        congelada = f.read().split()[0]
    assert _sha256(gs.RUTA_ANOTACION) == congelada


def test_los_documentos_coinciden_con_su_huella():
    for caso in _anotacion()["casos"]:
        assert _sha256(os.path.join(gs.DIRECTORIO_DOCUMENTOS, caso["archivo"])) == caso["sha256_archivo"], caso["id"]


def test_composicion_de_42_casos():
    casos = _anotacion()["casos"]
    assert len(casos) == 42
    assert sum(c["rendicion"] == "ESCANEADO" for c in casos) == 12


def test_coherencia_con_los_catalogos():
    with open(gs.RUTA_CATALOGO, encoding="utf-8") as f:
        reglas = {r["codigo_regla"]: r for r in json.load(f)["reglas"]}
    anotacion = _anotacion()
    assert anotacion["catalogo_reglas_sha256"] == _sha256(gs.RUTA_CATALOGO)
    for caso in anotacion["casos"]:
        esperado = caso["esperado"]
        assert esperado["estatus"] in ("CONFORME", "EN_REVISION", "NO_CONFORME"), caso["id"]
        assert esperado["tipo_documento"] in TIPOS_DOCUMENTALES, caso["id"]
        assert esperado["motivo"], caso["id"]
        for codigo in esperado["elementos"]:
            assert codigo in reglas, (caso["id"], codigo)
            assert reglas[codigo]["tipo_documento"] == caso["tipo_registrado"], (caso["id"], codigo)
