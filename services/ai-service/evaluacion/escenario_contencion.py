"""
Escenario de contención por la cuota de Groq — T4, PLUS-11 (VALIDACION_CUANTITATIVA.md §10.1).

Reproduce el caso que motivó el presupuesto de tokens: el analista audita el
contrato escaneado de 20 páginas (≈ 7,000 tokens) y enseguida hace tres
preguntas en el chat, dentro del mismo minuto y con el límite de 8,000 tokens por
minuto del plan gratuito. Se ejecuta dos veces con Groq real:

  * ``sin_t4``: GROQ_TOKENS_POR_MINUTO=0; el chat envía su contexto completo y,
    si Groq rechaza la petición por límite de tasa, el SDK espera y reintenta.
  * ``con_t4``: el chat ve la cuota del último minuto y acota su contexto.

Cada variante usa un casete nuevo (todas las llamadas son reales, sin el
presupuesto propio del grabador) y una SQLite nueva (el caché del chat empieza
vacío). Entre variantes se espera 65 s para que la cuota se libere. Por pregunta
registra la latencia real del endpoint, el código HTTP, los tokens, si el
contexto se acotó y si la respuesta acierta.

Uso:  cd services/ai-service && python -m evaluacion.escenario_contencion
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone

from evaluacion import entorno  # noqa: I001
from evaluacion import bateria_chat as bateria
from evaluacion import documento_extenso
from evaluacion.medir_chat import DIRECTORIO_RESULTADOS
from config import settings
from pipelines import presupuesto_tokens

PREGUNTAS = [p for p in bateria.PREGUNTAS_EXTENSAS if p.categoria in (bateria.LOCALIZACION, bateria.INTERPRETATIVA)
             and "mesa de ayuda" not in p.pregunta]


def _variante(nombre: str, limite: int) -> dict:
    with open(documento_extenso.RUTA_ANOTACION, encoding="utf-8") as f:
        caso = next(c for c in json.load(f)["casos"] if c["id"] == "GS-CONT-EXT-ESC")
    settings.GROQ_TOKENS_POR_MINUTO = limite
    presupuesto_tokens.presupuesto.vaciar()
    ruta = os.path.join(tempfile.mkdtemp(prefix="contencion-"), "casete.json")
    turnos = []
    with entorno.Entorno([caso], ruta, entorno.GRABAR, registrar_presupuesto=True) as e:
        cliente = e.cliente()
        inicio = time.perf_counter()
        r = cliente.post("/api/v1/ai/analisis-semantico", json={
            "documento_id": caso["id"], "rfc_titular": caso["titular"]["rfc"],
            "razon_social_titular": caso["titular"]["razon_social"], "usuario": "evaluacion"})
        auditoria = {"http": r.status_code, "ms": round((time.perf_counter() - inicio) * 1000),
                     "tokens": sum((c["uso"] or {}).get("total_tokens") or 0 for c in e.casete.consultas)}
        print(f"[{nombre}] auditoría HTTP {r.status_code} {auditoria['ms']} ms {auditoria['tokens']} tokens", flush=True)
        for pregunta in PREGUNTAS:
            previas = len(e.casete.consultas)
            inicio = time.perf_counter()
            r = cliente.post("/api/v1/ai/chat-documento", json={"documento_id": caso["id"], "pregunta": pregunta.pregunta})
            ms = round((time.perf_counter() - inicio) * 1000)
            cuerpo = r.json() if r.status_code == 200 else {}
            nuevas = e.casete.consultas[previas:]
            turno = {
                "pregunta": pregunta.pregunta, "http": r.status_code, "ms": ms,
                "tokens": sum((c["uso"] or {}).get("total_tokens") or 0 for c in nuevas),
                "latencia_groq_ms": [c["latencia_ms"] for c in nuevas],
                "presupuesto_tokens": (cuerpo.get("contexto_llm") or {}).get("presupuesto_tokens"),
                "caracteres_de_contexto": cuerpo.get("caracteres_de_contexto"),
                "acierta": bateria.acierta(cuerpo.get("respuesta") or "", pregunta) if cuerpo else False,
                "respuesta": cuerpo.get("respuesta") or r.text[:300],
            }
            turnos.append(turno)
            reducido = (turno["presupuesto_tokens"] or {}).get("reducido")
            print(f"[{nombre}] HTTP {r.status_code} {ms:>6} ms {turno['tokens']:>5} tokens "
                  f"contexto={turno['caracteres_de_contexto']} acotado={reducido} acierta={turno['acierta']}", flush=True)
    return {"variante": nombre, "limite_tokens_por_minuto": limite, "auditoria": auditoria, "turnos": turnos}


def main() -> None:
    entorno.TOKENS_POR_MINUTO = 10 ** 9      # sin el presupuesto propio del grabador: la contención es el objeto
    original = settings.GROQ_TOKENS_POR_MINUTO
    try:
        sin_t4 = _variante("sin_t4", 0)
        print("[escenario] esperando 65 s a que se libere la cuota…", flush=True)
        time.sleep(65)
        con_t4 = _variante("con_t4", 8000)
    finally:
        settings.GROQ_TOKENS_POR_MINUTO = original
    resultado = {"ejecutado_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                 "modelo": settings.GROQ_MODEL, "variantes": [sin_t4, con_t4]}
    os.makedirs(DIRECTORIO_RESULTADOS, exist_ok=True)
    ruta = os.path.join(DIRECTORIO_RESULTADOS, "chat_t4_contencion.json")
    with open(ruta, "w", encoding="utf-8", newline="\n") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"Resultado: {ruta}")


if __name__ == "__main__":
    main()
