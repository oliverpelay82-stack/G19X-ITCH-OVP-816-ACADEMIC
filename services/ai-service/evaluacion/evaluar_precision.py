"""
Suite de precisión del Gold Standard (docs/VALIDACION_CUANTITATIVA.md §4 y §10.2).

Audita los 42 casos con el endpoint real ``POST /api/v1/ai/analisis-semantico``
dentro del entorno offline y compara cada dictamen con la anotación congelada:

  * PE-1, entidades: tipo, RFC, razón social y fechas, con los normalizadores
    del motor (P, R y F1 por campo, micro y macro, y tasa de alucinación).
  * PE-2, elementos RSC: cada par (caso, regla anotada) es una decisión
    presente/omisión; la omisión no detectada es una falsa conformidad.
  * PE-3, personas: firmantes y apoderados por nombre, con la normalización del
    cotejo RN-03, y exactitud del cargo.
  * PE-4, decisiones: matriz 3 × 3 del estatus preliminar, κ, falsa conformidad,
    rechazo indebido, derivación a revisión humana y calibración por banda.
  * CER del OCR de los 12 escaneos contra su texto conocido.

Cada cifra sale con su intervalo (Wilson o *bootstrap* por caso) y se desglosa
por rendición (vectorial / escaneado) para medir el efecto del OCR.

  * ``--modo grabar``: llama a Groq por cada petición que no esté en el casete
    propio ni en el del chat (respaldo) y guarda el casete después de cada caso,
    así que una corrida cortada por la cuota diaria continúa donde quedó.
  * ``--modo reproducir`` (por defecto): no llama a Groq; aborta si falta una huella.

Uso:  cd services/ai-service
      python -m evaluacion.evaluar_precision --modo grabar
      python -m evaluacion.evaluar_precision                  (reproducir)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import re
import sys
import time
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Callable

from evaluacion import entorno  # noqa: I001  (instala los parches antes que el resto del servicio)
from evaluacion import gold_standard as gs
from evaluacion import metricas as m
from evaluacion.medir_chat import DIRECTORIO_RESULTADOS, RUTA_CASETE as RUTA_CASETE_CHAT
from config import settings
from pipelines import repositorio_texto
from pipelines.analisis_semantico import normalizar_fecha, normalizar_razon_social, normalizar_rfc
from pipelines.verificacion_contenido import cita_en_texto

_AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_CASETE = os.path.join(_AQUI, "casetes", "precision.json")
ESTATUS = ("CONFORME", "EN_REVISION", "NO_CONFORME")
RENDICIONES = ("VECTORIAL", "ESCANEADO")
# Bandas de confianza del DOC-08 §6.2, con los mismos umbrales que el dictamen
# (UMBRAL_CONFIANZA_CONFORME y UMBRAL_CONFIANZA_HITL; por omisión 0.85 y 0.70).
_CONFORME, _HITL = settings.UMBRAL_CONFIANZA_CONFORME, settings.UMBRAL_CONFIANZA_HITL
BANDAS = (
    (f"≥ {_CONFORME:.2f}", _CONFORME, 1.01),
    (f"{_HITL:.2f}–{_CONFORME - 0.01:.2f}", _HITL, _CONFORME),
    (f"< {_HITL:.2f}", -0.01, _HITL),
)


class CorridaAbortada(RuntimeError):
    pass


# ── Normalización de las comparaciones ──────────────────────────────
def _tipo(valor: Any) -> str | None:
    return valor.strip().upper() if isinstance(valor, str) and valor.strip() else None


CAMPOS: dict[str, tuple[str, Callable[[Any], Any]]] = {
    # campo de la anotación: (campo de la respuesta, normalizador del motor)
    "tipo_documento": ("tipo_documento_detectado", _tipo),
    "rfc": ("rfc_detectado", normalizar_rfc),
    "razon_social": ("razon_social_detectada", normalizar_razon_social),
    "fecha_emision": ("fecha_emision", normalizar_fecha),
    "fecha_vencimiento": ("fecha_vencimiento", normalizar_fecha),
}

# Copia de core-service/motor/representacion.py (palabras_nombre y mismo_nombre): el
# core no se importa en este proceso (su config.database choca con la del ai-service),
# y PE-3 debe medir con la misma regla con la que el core coteja firmante y apoderado.
_TITULOS = {
    "lic", "licenciado", "licenciada", "ing", "ingeniero", "ingeniera", "cp", "dr", "dra", "doctor", "doctora",
    "sr", "sra", "srita", "senor", "senora", "mtro", "mtra", "maestro", "maestra", "arq", "don", "dona",
}
_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e"}


def _sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def palabras_nombre(nombre: str | None) -> set[str]:
    palabras = re.sub(r"[^a-zñ]+", " ", _sin_acentos(nombre or "")).split()
    return {p for p in palabras if len(p) > 1 and p not in _TITULOS and p not in _PARTICULAS}


def mismo_nombre(a: str | None, b: str | None) -> bool:
    pa, pb = palabras_nombre(a), palabras_nombre(b)
    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return len(corto) >= 2 and corto <= largo


def mismo_cargo(esperado: str | None, extraido: str | None) -> bool:
    """
    El cargo coincide si las palabras de uno están en las del otro, sin acentos y
    sin la vocal final de género («Apoderada legal» y «apoderado» son el mismo
    cargo; «Representante legal» y «Administrador único», no).
    """
    def raices(cargo: str | None) -> set[str]:
        return {re.sub(r"[ao]s?$", "", p) for p in palabras_nombre(cargo)}

    a, b = raices(esperado), raices(extraido)
    return bool(a) and bool(b) and (a <= b or b <= a)


def emparejar_personas(esperadas: list[dict], extraidas: list[dict]) -> tuple[m.Conteo, list[bool]]:
    """Empareja por nombre (cada extraída se usa una vez) y devuelve el conteo y, por pareja, si el cargo coincide."""
    libres = list(extraidas)
    cargos = []
    vp = 0
    for persona in esperadas:
        pareja = next((x for x in libres if mismo_nombre(persona["nombre"], x.get("nombre"))), None)
        if pareja is not None:
            libres.remove(pareja)
            vp += 1
            cargos.append(mismo_cargo(persona.get("cargo"), pareja.get("cargo")))
    return m.Conteo(vp=vp, fp=len(libres), fn=len(esperadas) - vp), cargos


# ── Evaluación de un caso ───────────────────────────────────────────
def evaluar_caso(caso: dict[str, Any], r: dict[str, Any], texto: str) -> dict[str, Any]:
    esperado = caso["esperado"]
    campos = {}
    for campo, (clave, normalizar) in CAMPOS.items():
        valor_esperado, valor_extraido = normalizar(esperado.get(campo)), normalizar(r.get(clave))
        campos[campo] = {"esperado": valor_esperado, "extraido": valor_extraido,
                         "conteo": m.comparar_campo(valor_esperado, valor_extraido).a_dict()}

    verificaciones = {v.get("codigo_regla"): v for v in r.get("verificaciones") or []}
    elementos = {}
    for codigo, presente in esperado.get("elementos", {}).items():
        v = verificaciones.get(codigo)
        resultado = v.get("resultado") if v else "NO_EVALUADA"
        elementos[codigo] = {
            "presente_esperado": presente,
            "resultado": resultado,
            # NO_LOCALIZADO, NO_VERIFICABLE y una regla no evaluada cuentan como omisión,
            # como las trata el dictamen (§4.2).
            "presente_dictaminado": resultado == "CUMPLE",
            "cita_anclada": cita_en_texto(v.get("cita"), texto) if resultado == "CUMPLE" else None,
        }

    personas_extraidas = [p for p in ((r.get("representacion") or {}).get("personas") or []) if p.get("nombre")]
    conteo_personas, cargos = emparejar_personas(esperado.get("personas", []), personas_extraidas)

    cer = None
    if caso["rendicion"] == "ESCANEADO":
        cer = m.cer(caso["texto_referencia"], texto)
    return {
        "id": caso["id"], "caso_base": caso["caso_base"], "rendicion": caso["rendicion"],
        "tipo_registrado": caso["tipo_registrado"],
        "estatus_esperado": esperado["estatus"], "estatus_dictaminado": r.get("estatus_preliminar"),
        "motivo_esperado": esperado.get("motivo"),
        "nivel_confianza": r.get("nivel_confianza"),
        "requiere_revision_humana": r.get("requiere_revision_humana"),
        "observaciones": r.get("observaciones"),
        "campos": campos, "elementos": elementos,
        "personas": {"esperadas": esperado.get("personas", []),
                     "extraidas": [{"nombre": p.get("nombre"), "cargo": p.get("cargo")} for p in personas_extraidas],
                     "conteo": conteo_personas.a_dict(), "cargo_correcto": cargos},
        "cer": round(cer, 4) if cer is not None else None,
    }


# ── Agregados ───────────────────────────────────────────────────────
def _conteo(d: dict[str, Any]) -> m.Conteo:
    return m.Conteo(d["vp"], d["fp"], d["fn"], d["vn"])


def _proporcion(exitos: int, total: int) -> dict[str, Any]:
    return {"exitos": exitos, "total": total, "valor": round(exitos / total, 4) if total else None,
            "ic95": m.wilson(exitos, total)}


def _f1(conteos_por_caso: list[m.Conteo]) -> dict[str, Any]:
    total = m.sumar(conteos_por_caso)
    return {**total.a_dict(), "f1_ic95": m.bootstrap_f1(conteos_por_caso)}


def _conteos_elementos(evaluacion: dict[str, Any], clase_omision: bool) -> m.Conteo:
    """Conteo de un caso para la clase «omisión» (positiva = falta) o «presente»."""
    c = m.Conteo()
    for e in evaluacion["elementos"].values():
        real = (not e["presente_esperado"]) if clase_omision else e["presente_esperado"]
        dicho = (not e["presente_dictaminado"]) if clase_omision else e["presente_dictaminado"]
        c = c + m.Conteo(vp=int(real and dicho), fp=int(dicho and not real), fn=int(real and not dicho),
                         vn=int(not real and not dicho))
    return c


def agregar(evaluaciones: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(evaluaciones)
    if not n:
        return {"casos": 0}

    # PE-1
    por_campo = {}
    for campo in CAMPOS:
        conteos = [_conteo(ev["campos"][campo]["conteo"]) for ev in evaluaciones]
        nulos = [ev for ev in evaluaciones if ev["campos"][campo]["esperado"] is None]
        alucinados = sum(1 for ev in nulos if ev["campos"][campo]["extraido"] is not None)
        por_campo[campo] = {**_f1(conteos), "alucinacion": _proporcion(alucinados, len(nulos))}
    f1s = [c["f1"] for c in por_campo.values() if c["f1"] is not None]
    por_caso_campos = [m.sumar(_conteo(ev["campos"][c]["conteo"]) for c in CAMPOS) for ev in evaluaciones]
    nulos_totales = sum(1 for ev in evaluaciones for c in CAMPOS if ev["campos"][c]["esperado"] is None)
    alucinaciones = sum(1 for ev in evaluaciones for c in CAMPOS
                        if ev["campos"][c]["esperado"] is None and ev["campos"][c]["extraido"] is not None)
    documentos_exactos = sum(1 for ev in evaluaciones
                             if all(ev["campos"][c]["conteo"]["fp"] == ev["campos"][c]["conteo"]["fn"] == 0
                                    for c in CAMPOS))
    entidades = {
        "por_campo": por_campo,
        "micro": _f1(por_caso_campos),
        "f1_macro": round(sum(f1s) / len(f1s), 4) if f1s else None,
        "alucinacion": _proporcion(alucinaciones, nulos_totales),
        "documentos_con_todos_los_campos": _proporcion(documentos_exactos, n),
    }

    # PE-2
    pares = [(ev, codigo, e) for ev in evaluaciones for codigo, e in ev["elementos"].items()]
    cumple = [e for _, _, e in pares if e["resultado"] == "CUMPLE"]
    por_regla = defaultdict(list)
    for ev, codigo, e in pares:
        por_regla[codigo].append(e)
    elementos = {
        "pares": len(pares),
        "omision": _f1([_conteos_elementos(ev, True) for ev in evaluaciones]),
        "presente": _f1([_conteos_elementos(ev, False) for ev in evaluaciones]),
        "abstenciones": sum(1 for _, _, e in pares if e["resultado"] == "NO_VERIFICABLE"),
        "no_evaluadas": sum(1 for _, _, e in pares if e["resultado"] == "NO_EVALUADA"),
        "citas_ancladas": _proporcion(sum(1 for e in cumple if e["cita_anclada"]), len(cumple)),
        "falsas_conformidades": [f"{ev['id']}:{codigo}" for ev, codigo, e in pares
                                 if not e["presente_esperado"] and e["presente_dictaminado"]],
        "omisiones_indebidas": [f"{ev['id']}:{codigo} ({e['resultado']})" for ev, codigo, e in pares
                                if e["presente_esperado"] and not e["presente_dictaminado"]],
        "por_regla": {codigo: {"pares": len(es),
                               "aciertos": sum(1 for e in es if e["presente_esperado"] == e["presente_dictaminado"])}
                      for codigo, es in sorted(por_regla.items())},
    }

    # PE-3
    conteos_personas = [_conteo(ev["personas"]["conteo"]) for ev in evaluaciones if ev["personas"]["esperadas"]
                        or ev["personas"]["extraidas"]]
    cargos = [c for ev in evaluaciones for c in ev["personas"]["cargo_correcto"]]
    personas = {"nombres": _f1(conteos_personas), "cargo": _proporcion(sum(cargos), len(cargos))}

    # PE-4
    matriz = m.matriz_confusion(((ev["estatus_esperado"], ev["estatus_dictaminado"]) for ev in evaluaciones), ESTATUS)
    no_conformes = [ev for ev in evaluaciones if ev["estatus_esperado"] != "CONFORME"]
    no_rechazables = [ev for ev in evaluaciones if ev["estatus_esperado"] != "NO_CONFORME"]
    revision = {
        estatus: _proporcion(sum(1 for ev in evaluaciones if ev["estatus_esperado"] == estatus
                                 and ev["requiere_revision_humana"]),
                             sum(1 for ev in evaluaciones if ev["estatus_esperado"] == estatus))
        for estatus in ESTATUS
    }
    calibracion = {}
    for nombre, desde, hasta in BANDAS:
        banda = [ev for ev in evaluaciones
                 if ev["nivel_confianza"] is not None and desde <= ev["nivel_confianza"] < hasta]
        calibracion[nombre] = _proporcion(sum(1 for ev in banda if ev["estatus_esperado"] == ev["estatus_dictaminado"]),
                                          len(banda))
    decisiones = {
        "matriz": matriz,
        "exactitud": _proporcion(sum(matriz[c][c] for c in ESTATUS), n),
        "f1_macro": m.f1_macro(matriz),
        "kappa": m.kappa_cohen(matriz),
        "falsa_conformidad": _proporcion(sum(1 for ev in no_conformes if ev["estatus_dictaminado"] == "CONFORME"),
                                         len(no_conformes)),
        "rechazo_indebido": _proporcion(sum(1 for ev in no_rechazables if ev["estatus_dictaminado"] == "NO_CONFORME"),
                                        len(no_rechazables)),
        "revision_humana_por_estatus_esperado": revision,
        "derivacion_a_revision": _proporcion(sum(1 for ev in evaluaciones if ev["requiere_revision_humana"]), n),
        "calibracion": calibracion,
        "discrepancias": [{"id": ev["id"], "esperado": ev["estatus_esperado"], "dictaminado": ev["estatus_dictaminado"],
                           "motivo_esperado": ev["motivo_esperado"], "observaciones": ev["observaciones"]}
                          for ev in evaluaciones if ev["estatus_esperado"] != ev["estatus_dictaminado"]],
    }

    cers = [ev["cer"] for ev in evaluaciones if ev["cer"] is not None]
    ocr = {"escaneos": len(cers), "cer_mediana": m.percentil(cers, 50), "cer_maximo": max(cers) if cers else None,
           "por_caso": {ev["id"]: ev["cer"] for ev in evaluaciones if ev["cer"] is not None}}
    return {"casos": n, "entidades": entidades, "elementos": elementos, "personas": personas,
            "decisiones": decisiones, "ocr": ocr}


# ── Corrida ─────────────────────────────────────────────────────────
def evaluar(modo: str) -> dict[str, Any]:
    with open(gs.RUTA_ANOTACION, encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    evaluaciones, auditorias = [], []
    with entorno.Entorno(casos, RUTA_CASETE, modo, respaldos=(RUTA_CASETE_CHAT,)) as e:
        cliente = e.cliente()
        for caso in casos:
            previas = len(e.casete.consultas)
            inicio = time.perf_counter()
            r = cliente.post("/api/v1/ai/analisis-semantico", json={
                "documento_id": caso["id"], "rfc_titular": caso["titular"]["rfc"],
                "razon_social_titular": caso["titular"]["razon_social"], "usuario": "evaluacion",
            })
            pared = (time.perf_counter() - inicio) * 1000
            if e.casete.faltantes:
                raise CorridaAbortada(f"Faltan {len(e.casete.faltantes)} huellas en el casete: vuelva a grabar.")
            if r.status_code != 200 or e.core.diferidos:
                raise CorridaAbortada(f"{caso['id']}: la auditoría respondió {r.status_code} ({r.text[:300]}). "
                                      "Si es la cuota diaria de Groq, vuelva a correr mañana: lo grabado se conserva.")
            if modo == entorno.GRABAR:
                e.casete.guardar()
            respuesta = r.json()
            texto = repositorio_texto.obtener_por_documento(caso["id"], completar_en_fondo=False,
                                                            texto_completo=True).texto
            evaluacion = evaluar_caso(caso, respuesta, texto)
            nuevas = e.casete.consultas[previas:]
            auditorias.append({
                "id": caso["id"], "consultas_groq": len(nuevas),
                "tokens": sum((c["uso"] or {}).get("total_tokens") or 0 for c in nuevas),
                "latencia_ms": round(pared - sum(c["en_casete_ms"] for c in nuevas)
                                     + sum(c["latencia_ms"] for c in nuevas)),
            })
            evaluaciones.append(evaluacion)
            _imprimir(evaluacion, auditorias[-1])
        version = e.version()

    return {
        "etiqueta": "precision",
        "modo": modo,
        "ejecutado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entorno": {**version, "casete": os.path.basename(RUTA_CASETE), "python": platform.python_version(),
                    "sistema": platform.platform(), "procesador": platform.processor()},
        "tokens_totales": sum(a["tokens"] for a in auditorias),
        "total": agregar(evaluaciones),
        "por_rendicion": {r: agregar([ev for ev in evaluaciones if ev["rendicion"] == r]) for r in RENDICIONES},
        # Ablación: los 12 casos base que tienen escaneo, en sus dos rendiciones.
        "pares_vectorial_escaneado": _ablacion(evaluaciones),
        "auditorias": auditorias,
        "casos": evaluaciones,
    }


def _ablacion(evaluaciones: list[dict[str, Any]]) -> dict[str, Any]:
    escaneados = {ev["caso_base"] for ev in evaluaciones if ev["rendicion"] == "ESCANEADO"}
    pares = [ev for ev in evaluaciones if ev["caso_base"] in escaneados]
    return {r: agregar([ev for ev in pares if ev["rendicion"] == r]) for r in RENDICIONES}


def _imprimir(ev: dict[str, Any], auditoria: dict[str, Any]) -> None:
    campos = sum(1 for c in ev["campos"].values() if c["conteo"]["fp"] == c["conteo"]["fn"] == 0)
    elementos = sum(1 for e in ev["elementos"].values() if e["presente_esperado"] == e["presente_dictaminado"])
    marca = "OK " if ev["estatus_esperado"] == ev["estatus_dictaminado"] else "NO "
    print(f"[precisión] {ev['id']:16s} {marca}{ev['estatus_dictaminado'] or '-':12s} "
          f"(esperado {ev['estatus_esperado']:12s}) "
          f"campos {campos}/{len(ev['campos'])} elementos {elementos}/{len(ev['elementos'])} "
          f"{auditoria['tokens']:>6} tokens", flush=True)


def _pct(valor: float | None) -> str:
    return "—" if valor is None else f"{valor * 100:.1f} %"


def _ic(ic: tuple[float, float] | list[float] | None) -> str:
    return "" if not ic else f" ({ic[0] * 100:.0f}–{ic[1] * 100:.0f} %)"


def tabla(resultado: dict[str, Any]) -> str:
    t = resultado["total"]
    ent, ele, per, dec = t["entidades"], t["elementos"], t["personas"], t["decisiones"]
    filas = ["| Campo | P | R | F1 (IC 95 %) | Alucinación |", "|---|---|---|---|---|"]
    for campo, c in ent["por_campo"].items():
        filas.append(f"| {campo} | {_pct(c['precision'])} | {_pct(c['exhaustividad'])} | "
                     f"{_pct(c['f1'])}{_ic(c['f1_ic95'])} "
                     f"| {c['alucinacion']['exitos']}/{c['alucinacion']['total']} |")
    filas.append(f"| **Micro** | {_pct(ent['micro']['precision'])} | {_pct(ent['micro']['exhaustividad'])} | "
                 f"**{_pct(ent['micro']['f1'])}**{_ic(ent['micro']['f1_ic95'])} | "
                 f"{ent['alucinacion']['exitos']}/{ent['alucinacion']['total']} |")
    filas += ["", f"Elementos RSC ({ele['pares']} pares): omisión P {_pct(ele['omision']['precision'])}, "
                  f"R {_pct(ele['omision']['exhaustividad'])}; presente F1 {_pct(ele['presente']['f1'])}; "
                  f"falsas conformidades {len(ele['falsas_conformidades'])}; citas ancladas "
                  f"{ele['citas_ancladas']['exitos']}/{ele['citas_ancladas']['total']}.",
              f"Personas: F1 {_pct(per['nombres']['f1'])}; cargo {per['cargo']['exitos']}/{per['cargo']['total']}.",
              f"Estatus: exactitud {_pct(dec['exactitud']['valor'])}{_ic(dec['exactitud']['ic95'])}, κ "
              f"{dec['kappa']:.3f}, falsa conformidad "
              f"{dec['falsa_conformidad']['exitos']}/{dec['falsa_conformidad']['total']}, "
              f"rechazo indebido {dec['rechazo_indebido']['exitos']}/{dec['rechazo_indebido']['total']}.",
              f"OCR: CER mediano {_pct(t['ocr']['cer_mediana'])}, máximo {_pct(t['ocr']['cer_maximo'])}."]
    return "\n".join(filas)


def main() -> int:
    parser = argparse.ArgumentParser(description="Suite de precisión del Gold Standard (§4 y §10.2).")
    parser.add_argument("--modo", choices=(entorno.GRABAR, entorno.REPRODUCIR), default=entorno.REPRODUCIR)
    args = parser.parse_args()
    # La consola de Windows (cp1252) no imprime κ ni los rangos de las bandas.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    try:
        resultado = evaluar(args.modo)
    except CorridaAbortada as exc:
        print(f"Corrida abortada: {exc}", file=sys.stderr)
        return 1
    os.makedirs(DIRECTORIO_RESULTADOS, exist_ok=True)
    ruta = os.path.join(DIRECTORIO_RESULTADOS, "precision.json")
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print()
    print(tabla(resultado))
    print(f"\nResultado: {ruta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
