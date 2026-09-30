"""
Entorno offline de la validación cuantitativa (docs/VALIDACION_CUANTITATIVA.md §3).

Ejecuta los endpoints reales del ai-service (auditoría y chat) y el Nivel 3
real sobre los PDF del Gold Standard. Solo sustituye los transportes externos:

  * Groq: ``Casete`` graba cada petición (modo ``grabar``) o la reproduce por su
    huella (modo ``reproducir``); en reproducción, una huella ausente aborta la
    corrida, así que nunca se consumen tokens sin saberlo.
  * core-service: almacén en memoria con los binarios del Gold Standard y los
    dictámenes con la misma forma que los guarda el core.
  * rules-service: vigencia RCV con ``rules-service/motor/vigencia.py`` (puro) y
    criterios RSC de la instantánea del catálogo.

Mientras dura el entorno, la base SQLite del servicio es una temporal, el caché
de texto en memoria empieza vacío, el caché de inferencias del servicio se apaga
(para que las latencias grabadas sean reales) y la lectura completa en segundo
plano no se programa.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
import tempfile
import threading
import time
from collections import deque
from dataclasses import asdict
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import Any
from uuid import uuid4

_SERVICIO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _SERVICIO)

import pytest  # noqa: E402

from clients import core_client, groq_client, rules_client  # noqa: E402
from config import settings  # noqa: E402
from evaluacion import gold_standard as gs  # noqa: E402
from pipelines import analisis_semantico, repositorio_texto  # noqa: E402
from pipelines.cache_extracciones import CacheExtracciones  # noqa: E402

GRABAR, REPRODUCIR = "grabar", "reproducir"
# Presupuesto del grabador: por debajo del límite del plan gratuito de Groq
# (8,000 tokens por minuto) para no depender de los reintentos del SDK.
TOKENS_POR_MINUTO = 7000
_CARACTERES_POR_TOKEN = 3.0


class HuellaAusenteError(RuntimeError):
    """La petición no está en el casete: reproducirla exigiría llamar a Groq."""


def _cargar_vigencia():
    ruta = os.path.join(os.path.dirname(_SERVICIO), "rules-service", "motor", "vigencia.py")
    especificacion = importlib.util.spec_from_file_location("evaluacion_vigencia_rules", ruta)
    modulo = importlib.util.module_from_spec(especificacion)
    # dataclasses resuelve las anotaciones diferidas buscando el módulo en sys.modules.
    sys.modules[especificacion.name] = modulo
    especificacion.loader.exec_module(modulo)
    return modulo


class _Presupuesto:
    """Ventana deslizante de 60 s con los tokens estimados o reales de cada llamada."""

    def __init__(self, limite: int):
        self.limite = limite
        self._llamadas: deque[list[float]] = deque()
        self._candado = threading.Lock()

    def esperar(self, estimado: int) -> list[float]:
        while True:
            with self._candado:
                ahora = time.monotonic()
                while self._llamadas and ahora - self._llamadas[0][0] > 60:
                    self._llamadas.popleft()
                if sum(t for _, t in self._llamadas) + estimado <= self.limite or not self._llamadas:
                    registro = [ahora, float(estimado)]
                    self._llamadas.append(registro)
                    return registro
            time.sleep(1)


class Casete:
    """Respuestas de Groq por huella de la petición exacta."""

    def __init__(self, ruta: str, modo: str):
        if modo not in (GRABAR, REPRODUCIR):
            raise ValueError(f"Modo desconocido: {modo}")
        self.ruta, self.modo = ruta, modo
        self.entradas: dict[str, dict[str, Any]] = {}
        if os.path.exists(ruta):
            with open(ruta, encoding="utf-8") as f:
                self.entradas = json.load(f)["entradas"]
        self._candado = threading.Lock()
        self._presupuesto = _Presupuesto(TOKENS_POR_MINUTO)
        self.consultas: list[dict[str, Any]] = []   # uso de cada llamada de la corrida, en orden
        # Huellas pedidas en reproducción que no estaban grabadas. La excepción basta
        # para abortar, pero se registran por si una capa intermedia la convirtiera en
        # un 500: quien use el entorno debe comprobar que la lista quedó vacía.
        self.faltantes: list[str] = []

    @staticmethod
    def huella(tipo: str, max_tokens: int, temperatura: float, carga: Any) -> str:
        material = json.dumps([tipo, settings.GROQ_MODEL, temperatura, max_tokens, carga], ensure_ascii=False)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def _resolver(self, tipo: str, clave: str, caracteres: int, llamar) -> tuple[Any, dict[str, Any]]:
        comienzo = time.perf_counter()
        with self._candado:
            entrada = self.entradas.get(clave)
        if entrada is None:
            if self.modo == REPRODUCIR:
                with self._candado:
                    self.faltantes.append(clave)
                raise HuellaAusenteError(
                    f"La petición {clave[:16]}… ({tipo}) no está en el casete {os.path.basename(self.ruta)}. "
                    "Cambió el prompt, el modelo, el texto del Nivel 3 o el catálogo: vuelva a grabar."
                )
            registro = self._presupuesto.esperar(int(caracteres / _CARACTERES_POR_TOKEN) + 400)
            inicio = time.perf_counter()
            respuesta = llamar()
            latencia = round((time.perf_counter() - inicio) * 1000)
            uso = getattr(respuesta, "uso", None) or {}
            registro[1] = float(uso.get("total_tokens") or registro[1])
            entrada = {
                "tipo": tipo,
                "respuesta": dict(respuesta) if tipo == "json" else str(respuesta),
                "uso": uso,
                "latencia_ms": latencia,
                "grabado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }
            with self._candado:
                self.entradas[clave] = entrada
        with self._candado:
            # latencia_ms: la de Groq (grabada); en_casete_ms: lo que la petición pasó aquí dentro,
            # espera del presupuesto incluida. La latencia del endpoint se reconstruye con ambas.
            self.consultas.append({"tipo": tipo, "huella": clave, "uso": entrada["uso"],
                                   "latencia_ms": entrada["latencia_ms"],
                                   "en_casete_ms": round((time.perf_counter() - comienzo) * 1000)})
        return entrada["respuesta"], entrada

    def generar_json(self, original, prompt: str, system: str) -> dict[str, Any]:
        clave = self.huella("json", settings.GROQ_MAX_TOKENS, settings.GROQ_TEMPERATURE, [system, prompt])
        respuesta, entrada = self._resolver("json", clave, len(prompt) + len(system),
                                            lambda: original(prompt=prompt, system=system))
        resultado = groq_client.RespuestaJSON(respuesta)
        resultado.uso = dict(entrada["uso"])
        return resultado

    def conversar(self, original, mensajes: list[dict[str, str]], temperatura: float | None = None) -> str:
        efectiva = settings.GROQ_TEMPERATURE if temperatura is None else temperatura
        clave = self.huella("texto", settings.GROQ_MAX_TOKENS, efectiva, mensajes)
        respuesta, entrada = self._resolver("texto", clave, sum(len(m["content"]) for m in mensajes),
                                            lambda: original(mensajes, temperatura))
        resultado = groq_client.RespuestaTexto(respuesta)
        resultado.uso = dict(entrada["uso"])
        return resultado

    def guardar(self) -> None:
        with open(self.ruta, "w", encoding="utf-8", newline="\n") as f:
            json.dump({"version": 1, "modelo": settings.GROQ_MODEL, "entradas": self.entradas}, f,
                      ensure_ascii=False, indent=1, sort_keys=True)
            f.write("\n")


class CoreSimulado:
    """El core-service en memoria: documentos del Gold Standard y dictámenes con la forma del core."""

    def __init__(self, casos: list[dict[str, Any]]):
        self.casos = {c["id"]: c for c in casos}
        self.dictamenes: dict[str, dict[str, Any]] = {}

    def _caso(self, documento_id: str) -> dict[str, Any]:
        if documento_id not in self.casos:
            raise core_client.DocumentoNoEncontradoError(f"Documento con ID '{documento_id}' no encontrado.")
        return self.casos[documento_id]

    def obtener_metadatos(self, documento_id: str) -> dict[str, Any]:
        caso = self._caso(documento_id)
        return {"id": documento_id, "expediente_id": "EXP-GOLD-STANDARD", "nombre_archivo_original": caso["archivo"],
                "tipo_documento": caso["tipo_registrado"], "hash_sha256": caso["sha256_archivo"]}

    def verificar_integridad(self, documento_id: str) -> None:
        self._caso(documento_id)

    def leer_binario(self, metadatos: dict[str, Any]) -> bytes:
        with open(os.path.join(gs.DIRECTORIO_DOCUMENTOS, self._caso(metadatos["id"])["archivo"]), "rb") as f:
            return f.read()

    def registrar_dictamen(self, carga: dict[str, Any]) -> dict[str, Any]:
        """Replica el registro de core-service/controllers/dictamen_controller.py (reglas_aplicadas y representación)."""
        caso = self._caso(carga["documento_id"])
        vigencia = carga.get("vigencia") or {}
        reglas = [{"codigo_regla": "RIE-03", "resultado": "CUMPLE",
                   "detalle": f"Huella SHA-256 verificada contra la registrada en la carga "
                              f"({caso['sha256_archivo'][:16]}…)."}]
        if vigencia and vigencia.get("disponible") is not False:
            reglas += [{k: e.get(k) for k in ("codigo_regla", "resultado", "detalle", "dias_calculados",
                                               "limite_dias", "criterio")}
                       for e in vigencia.get("evaluaciones") or []]
            vigencia_resultado = vigencia.get("resultado") or "SIN_REGLAS"
        else:
            vigencia_resultado = "NO_VERIFICADA"
        reglas += [{"codigo_regla": v.get("codigo_regla"), "nombre_regla": v.get("nombre_regla"),
                    "familia_regla": v.get("familia_regla"), "severidad": v.get("severidad"),
                    "resultado": v.get("resultado"), "detalle": v.get("observacion"), "cita": v.get("cita"),
                    "recomendacion": v.get("recomendacion")}
                   for v in carga.get("verificaciones") or [] if v.get("codigo_regla")]
        dictamen = {
            "id": str(uuid4()), "documento_id": carga["documento_id"], "expediente_id": "EXP-GOLD-STANDARD",
            "estatus": carga["estatus"], "estatus_preliminar": carga["estatus"], "origen": "NIVEL_4",
            "nivel_confianza": carga.get("nivel_confianza"),
            "requiere_revision_humana": carga.get("requiere_revision_humana"),
            "reglas_aplicadas": reglas, "vigencia_resultado": vigencia_resultado,
            "observaciones": carga.get("observaciones") or [],
            "tipo_documento_detectado": carga.get("tipo_documento_detectado"),
            "rfc_detectado": carga.get("rfc_detectado"), "match_titular": carga.get("match_titular"),
            "fecha_emision_extraida": carga.get("fecha_emision"),
            "fecha_vencimiento_extraida": carga.get("fecha_vencimiento"),
            "modelo_utilizado": carga.get("modelo_utilizado"),
            "representacion_legal": carga.get("representacion"), "hash_sha256": caso["sha256_archivo"],
            "revisado_por_humano": False, "justificacion_humana": None, "revisado_por": None, "revisado_en": None,
            "creado_en": datetime.now(timezone.utc).isoformat(),
        }
        self.dictamenes[carga["documento_id"]] = dictamen
        return {"id": dictamen["id"], "estatus": dictamen["estatus"], "estado_expediente": None}

    def ultimo_dictamen(self, documento_id: str) -> dict[str, Any] | None:
        return self.dictamenes.get(documento_id)


class ReglasSimuladas:
    """Criterios RSC de la instantánea del catálogo y vigencia RCV con el motor puro del rules-service."""

    def __init__(self):
        with open(gs.RUTA_CATALOGO, encoding="utf-8") as f:
            self.reglas = json.load(f)["reglas"]
        self._vigencia = _cargar_vigencia()
        self._rcv = [SimpleNamespace(activo=True, **{k: r.get(k) for k in (
            "codigo_regla", "nombre_regla", "familia_regla", "severidad", "tipo_documento", "dias_maximos_vigencia")})
            for r in self.reglas if r["familia_regla"] == "RCV"]

    def criterios_contenido(self, tipo_documento: str | None) -> list[dict[str, Any]]:
        if not tipo_documento:
            return []
        tipo = tipo_documento.strip().upper()
        return [{"codigo_regla": r["codigo_regla"], "nombre_regla": r["nombre_regla"],
                 "familia_regla": r["familia_regla"], "criterio": r["descripcion"],
                 "recomendacion": r["accion"], "severidad": r["severidad"]}
                for r in self.reglas
                if r["familia_regla"] in rules_client.FAMILIAS_CONTENIDO
                and (r.get("tipo_documento") or "").upper() == tipo]

    def evaluar_vigencia(self, tipo_documento: str, fecha_emision: str | None, fecha_vencimiento: str | None,
                         fecha_referencia: date) -> dict[str, Any]:
        resultado = self._vigencia.evaluar(
            self._rcv, tipo_documento=tipo_documento,
            fecha_emision=date.fromisoformat(fecha_emision) if fecha_emision else None,
            fecha_vencimiento=date.fromisoformat(fecha_vencimiento) if fecha_vencimiento else None,
            fecha_referencia=fecha_referencia,
        )
        # Misma forma que la respuesta JSON de POST /api/v1/reglas/evaluar-vigencia.
        return json.loads(json.dumps(asdict(resultado), default=str))


class Entorno:
    """
    Instala las simulaciones mientras dura el bloque ``with`` y las retira al salir.

    ``casos`` son las entradas de gold_standard.json que la corrida necesita; el
    ``id`` de cada caso es su ``documento_id``.
    """

    def __init__(self, casos: list[dict[str, Any]], ruta_casete: str, modo: str = REPRODUCIR):
        self.casete = Casete(ruta_casete, modo)
        self.core = CoreSimulado(casos)
        self.reglas = ReglasSimuladas()
        self._parche = pytest.MonkeyPatch()

    def __enter__(self) -> "Entorno":
        mp = self._parche
        temporal = tempfile.mkdtemp(prefix="plurione-evaluacion-")
        mp.setattr(settings, "EXTRACCIONES_DB_PATH", os.path.join(temporal, "extracciones.sqlite3"))
        mp.setattr(settings, "GROQ_CACHE_INFERENCIAS", False)
        mp.setattr(settings, "COMPLETAR_LECTURA_EN_SEGUNDO_PLANO", False)
        mp.setattr(repositorio_texto, "cache_texto", CacheExtracciones(settings.CACHE_MAX_DOCUMENTOS))
        for nombre in ("obtener_metadatos", "verificar_integridad", "leer_binario", "registrar_dictamen",
                       "ultimo_dictamen"):
            mp.setattr(core_client, nombre, getattr(self.core, nombre))
        mp.setattr(rules_client, "criterios_contenido", self.reglas.criterios_contenido)
        mp.setattr(rules_client, "evaluar_vigencia", self.reglas.evaluar_vigencia)
        generar_json, conversar = groq_client.generar_json, groq_client.conversar
        mp.setattr(groq_client, "generar_json",
                   lambda prompt, system: self.casete.generar_json(generar_json, prompt, system))
        mp.setattr(groq_client, "conversar",
                   lambda mensajes, temperatura=None: self.casete.conversar(conversar, mensajes, temperatura))
        # Fecha de referencia fija del Gold Standard: la vigencia no cambia con el día de la corrida.
        analizar = analisis_semantico.analizar
        mp.setattr(analisis_semantico, "analizar",
                   lambda *a, **k: analizar(*a, **{"fecha_referencia": gs.FECHA_REFERENCIA, **k}))
        return self

    def __exit__(self, *exc) -> None:
        self._parche.undo()
        if self.casete.modo == GRABAR:
            self.casete.guardar()

    def cliente(self):
        from fastapi.testclient import TestClient

        import main
        return TestClient(main.app)

    def version(self) -> dict[str, Any]:
        """Lo que ata una corrida a una versión del motor (§3)."""
        from pipelines import extraccion_pipeline
        with open(gs.RUTA_HUELLA, encoding="utf-8") as f:
            huella_gs = f.read().split()[0]
        return {"modelo": settings.GROQ_MODEL, "version_lectura": extraccion_pipeline.version_lectura(),
                "ocr_workers": settings.OCR_WORKERS, "gold_standard_sha256": huella_gs,
                "casete": os.path.basename(self.casete.ruta), "fecha_referencia": gs.FECHA_REFERENCIA.isoformat()}
