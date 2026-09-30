"""
Medición del chat documental (docs/VALIDACION_CUANTITATIVA.md §6).

Audita los 6 documentos de la batería (el estado del sistema necesita su
dictamen) y hace las 30 preguntas y las 2 conversaciones contra el endpoint
real ``POST /api/v1/ai/chat-documento``, dentro del entorno offline.

  * ``--modo grabar``: llama a Groq por cada petición que el casete no tenga
    (tokens y latencias reales) y la guarda.
  * ``--modo reproducir``: no llama a Groq; aborta si falta una huella.

Por turno registra tokens, latencia, citas y si la respuesta acierta. La
latencia del endpoint se reconstruye igual en ambos modos: tiempo de la
petición, menos lo que pasó dentro del casete (incluida la espera del
presupuesto de tokens), más la latencia de Groq grabada.

Uso:  cd services/ai-service
      python -m evaluacion.medir_chat --etiqueta base --modo grabar
      python -m evaluacion.medir_chat --etiqueta base            (reproducir)
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from evaluacion import entorno  # noqa: I001  (instala los parches antes que el resto del servicio)
from evaluacion import bateria_chat as bateria
from evaluacion import documento_extenso
from evaluacion import gold_standard as gs
from evaluacion import metricas

_AQUI = os.path.dirname(os.path.abspath(__file__))
RUTA_CASETE = os.path.join(_AQUI, "casetes", "chat.json")
DIRECTORIO_RESULTADOS = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_AQUI))), "docs",
                                     "resultados_validacion")
LIMITE_TPM = 8000


class CorridaAbortada(RuntimeError):
    pass


BATERIAS = {
    # nombre: (anotación, documentos, preguntas sueltas, conversaciones)
    "corta": (gs.RUTA_ANOTACION, bateria.DOCUMENTOS, bateria.PREGUNTAS, bateria.CONVERSACIONES),
    "extensa": (documento_extenso.RUTA_ANOTACION, bateria.DOCUMENTOS_EXTENSOS, bateria.PREGUNTAS_EXTENSAS, []),
}


def _casos(ruta: str, documentos: tuple[str, ...]) -> list[dict[str, Any]]:
    with open(ruta, encoding="utf-8") as f:
        casos = json.load(f)["casos"]
    return [c for c in casos if c["id"] in documentos]


def _peticion(e: entorno.Entorno, cliente, ruta: str, cuerpo: dict[str, Any]) -> tuple[dict[str, Any], dict]:
    previas = len(e.casete.consultas)
    inicio = time.perf_counter()
    r = cliente.post(ruta, json=cuerpo)
    pared = (time.perf_counter() - inicio) * 1000
    if e.casete.faltantes:
        raise CorridaAbortada(f"Faltan {len(e.casete.faltantes)} huellas en el casete: vuelva a grabar.")
    if r.status_code != 200:
        raise CorridaAbortada(f"{ruta} respondió {r.status_code}: {r.text[:300]}")
    nuevas = e.casete.consultas[previas:]
    medicion = {
        "consultas_groq": len(nuevas),
        "tokens": {k: sum((c["uso"] or {}).get(k) or 0 for c in nuevas)
                   for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
        "latencia_groq_ms": [c["latencia_ms"] for c in nuevas],
        # Consultas en serie (el chat hace una): tiempo local + latencia de Groq.
        "latencia_endpoint_ms": round(pared - sum(c["en_casete_ms"] for c in nuevas)
                                      + sum(c["latencia_ms"] for c in nuevas)),
    }
    return r.json(), medicion


def _turno(e, cliente, pregunta: bateria.Pregunta, historial: list[dict[str, str]]) -> dict[str, Any]:
    cuerpo = {"documento_id": pregunta.documento, "pregunta": pregunta.pregunta, "historial": historial}
    respuesta, medicion = _peticion(e, cliente, "/api/v1/ai/chat-documento", cuerpo)
    citas = respuesta.get("citas") or []
    return {
        "documento": pregunta.documento,
        "pregunta": pregunta.pregunta,
        "categoria": pregunta.categoria,
        "ruta_prevista": pregunta.ruta_prevista,
        "turnos_previos": len(historial),
        "respuesta": respuesta.get("respuesta"),
        "acierta": bateria.acierta(respuesta.get("respuesta") or "", pregunta),
        "citas": len(citas),
        "citas_verificadas": sum(1 for c in citas if c.get("verificada")),
        "origen_respuesta": respuesta.get("origen_respuesta", "MODELO"),
        "caracteres_de_contexto": respuesta.get("caracteres_de_contexto"),
        **medicion,
    }


def _resumen(turnos: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(turnos)
    con_modelo = [t for t in turnos if t["consultas_groq"]]
    tokens = [t["tokens"]["total_tokens"] for t in turnos]
    tokens_modelo = [t["tokens"]["total_tokens"] for t in con_modelo]
    aciertos = sum(t["acierta"] for t in turnos)
    citas = sum(t["citas"] for t in turnos)
    verificadas = sum(t["citas_verificadas"] for t in turnos)
    promedio = sum(tokens) / n if n else None
    return {
        "turnos": n,
        "tokens_promedio": round(promedio, 1) if promedio is not None else None,
        "tokens_promedio_con_modelo": round(sum(tokens_modelo) / len(tokens_modelo), 1) if tokens_modelo else 0,
        "prompt_promedio": round(sum(t["tokens"]["prompt_tokens"] for t in turnos) / n, 1) if n else None,
        "completion_promedio": round(sum(t["tokens"]["completion_tokens"] for t in turnos) / n, 1) if n else None,
        "tokens_totales": sum(tokens),
        "turnos_por_minuto": round(LIMITE_TPM / promedio, 2) if promedio else None,
        "sin_modelo": sum(1 for t in turnos if not t["consultas_groq"]),
        "latencia_p50_ms": metricas.percentil([t["latencia_endpoint_ms"] for t in turnos], 50),
        "latencia_p95_ms": metricas.percentil([t["latencia_endpoint_ms"] for t in turnos], 95),
        "aciertos": aciertos,
        "exactitud": round(aciertos / n, 4) if n else None,
        "exactitud_ic95": metricas.wilson(aciertos, n),
        "citas": citas,
        "citas_verificadas": verificadas,
        "proporcion_citas_verificadas": round(verificadas / citas, 4) if citas else None,
    }


def medir(etiqueta: str, modo: str, nombre_bateria: str = "corta") -> dict[str, Any]:
    ruta_anotacion, documentos, preguntas, conversaciones = BATERIAS[nombre_bateria]
    casos = _casos(ruta_anotacion, documentos)
    auditorias, turnos = [], []
    with entorno.Entorno(casos, RUTA_CASETE, modo) as e:
        cliente = e.cliente()
        for caso in casos:
            respuesta, medicion = _peticion(e, cliente, "/api/v1/ai/analisis-semantico", {
                "documento_id": caso["id"], "rfc_titular": caso["titular"]["rfc"],
                "razon_social_titular": caso["titular"]["razon_social"], "usuario": "evaluacion",
            })
            auditorias.append({"documento": caso["id"], "estatus": respuesta["estatus_preliminar"],
                               "estatus_esperado": caso["esperado"]["estatus"], **medicion})
            print(f"[auditoría] {caso['id']:16s} {respuesta['estatus_preliminar']:12s} "
                  f"{medicion['tokens']['total_tokens']:>6} tokens", flush=True)
        for pregunta in preguntas:
            turnos.append(_turno(e, cliente, pregunta, []))
            _imprimir(turnos[-1])
        for numero, conversacion in enumerate(conversaciones, start=1):
            mensajes: list[dict[str, str]] = []
            for pregunta in conversacion:
                historial = mensajes[-bateria.TURNOS_HISTORIAL_FRONTEND:]
                turno = _turno(e, cliente, pregunta, historial)
                turno["conversacion"] = numero
                turnos.append(turno)
                _imprimir(turno)
                mensajes += [{"rol": "usuario", "contenido": pregunta.pregunta},
                             {"rol": "asistente", "contenido": turno["respuesta"]}]
        version = e.version()

    por_categoria = defaultdict(list)
    for t in turnos:
        por_categoria[t["categoria"]].append(t)
    return {
        "etiqueta": etiqueta,
        "bateria": nombre_bateria,
        "modo": modo,
        "ejecutado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "entorno": {**version, "python": platform.python_version(), "sistema": platform.platform(),
                    "procesador": platform.processor()},
        "resumen": _resumen(turnos),
        "por_categoria": {c: _resumen(ts) for c, ts in sorted(por_categoria.items())},
        "sueltas": _resumen([t for t in turnos if "conversacion" not in t]),
        "conversaciones": _resumen([t for t in turnos if "conversacion" in t]),
        "auditorias": auditorias,
        "turnos": turnos,
    }


def _imprimir(t: dict[str, Any]) -> None:
    print(f"[chat] {t['documento']:16s} {t['categoria']:14s} {'OK ' if t['acierta'] else 'NO '}"
          f"{t['tokens']['total_tokens']:>6} tokens {t['latencia_endpoint_ms']:>6} ms  {t['pregunta'][:60]}", flush=True)


def tabla(resultado: dict[str, Any]) -> str:
    filas = ["| Grupo | Turnos | Tokens/turno | Turnos/min | Sin modelo | p50 ms | p95 ms | Exactitud (IC 95 %) | "
             "Citas verificadas |", "|---|---|---|---|---|---|---|---|---|"]

    def fila(nombre: str, r: dict[str, Any]) -> str:
        ic = r["exactitud_ic95"]
        exactitud = f"{r['exactitud']:.0%} ({ic[0]:.0%}–{ic[1]:.0%})" if ic else "—"
        citas = f"{r['citas_verificadas']}/{r['citas']}" if r["citas"] else "—"
        return (f"| {nombre} | {r['turnos']} | {r['tokens_promedio']:,.0f} | {r['turnos_por_minuto'] or '—'} | "
                f"{r['sin_modelo']} | {r['latencia_p50_ms']:,.0f} | {r['latencia_p95_ms']:,.0f} | {exactitud} | {citas} |")

    filas.append(fila("**Total**", resultado["resumen"]))
    for categoria, r in resultado["por_categoria"].items():
        filas.append(fila(categoria.capitalize(), r))
    if resultado["conversaciones"]["turnos"]:
        filas.append(fila("Conversaciones (4 turnos)", resultado["conversaciones"]))
    return "\n".join(filas)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--etiqueta", required=True, help="Nombre de la medición (base, t3-t4, t0…)")
    parser.add_argument("--modo", choices=(entorno.GRABAR, entorno.REPRODUCIR), default=entorno.REPRODUCIR)
    parser.add_argument("--bateria", choices=tuple(BATERIAS), default="corta",
                        help="corta: 38 turnos sobre 6 documentos breves; extensa: 8 turnos sobre el contrato de 20 páginas")
    args = parser.parse_args()
    os.makedirs(os.path.dirname(RUTA_CASETE), exist_ok=True)
    try:
        resultado = medir(args.etiqueta, args.modo, args.bateria)
    except CorridaAbortada as exc:
        print(f"[abortada] {exc}", file=sys.stderr)
        sys.exit(2)
    os.makedirs(DIRECTORIO_RESULTADOS, exist_ok=True)
    sufijo = "" if args.bateria == "corta" else f"_{args.bateria}"
    ruta = os.path.join(DIRECTORIO_RESULTADOS, f"chat_{args.etiqueta}{sufijo}.json")
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print()
    print(tabla(resultado))
    print(f"\nResultado: {ruta}")
