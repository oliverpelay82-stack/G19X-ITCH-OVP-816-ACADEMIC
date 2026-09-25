"""
Pruebas de la integración del dictamen del Nivel 4 con las reglas de vigencia
del rules-service (RCV-01 y RCV-02), sin red: las respuestas de Groq y del
rules-service se simulan para cubrir cada camino de forma determinista.

  1. Comprobante de domicilio con más de 90 días: NO_CONFORME por RCV-02,
     aunque el RFC coincida y la confianza sea alta.
  2. Comprobante reciente: CONFORME.
  3. Sin fecha de emisión (INDETERMINADO): EN_REVISION con revisión humana.
  4. rules-service caído: EN_REVISION con revisión humana y el motivo.
  5. Se evalúa el tipo registrado en el expediente; sin él, el tipo detectado
     traducido al catálogo del core (COMPROBANTE_DOMICILIO -> COMP_DOMICILIO).

Las simulaciones se instalan con ``monkeypatch`` de pytest y se deshacen al
terminar, así que ninguna otra suite hereda un cliente falso.

Uso:  cd services/ai-service && python tests/test_vigencia_dictamen.py
"""
import os
import sys
from datetime import date

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clients import groq_client, rules_client  # noqa: E402
from clients.rules_client import ReglasNoDisponiblesError  # noqa: E402
from pipelines import analisis_semantico  # noqa: E402

HOY = date(2026, 9, 23)
RFC = "PLU180514AB3"
_resultados: list[bool] = []
llamadas: list[tuple] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def modelo(mp: pytest.MonkeyPatch, fecha_emision):
    """Simula la extracción de Groq: comprobante de domicilio legible del titular."""
    mp.setattr(groq_client, "generar_json", lambda prompt, system: {
        "tipo_documento_detectado": "COMPROBANTE_DOMICILIO", "rfc_detectado": RFC,
        "razon_social_detectada": "PLURIONE S.A. DE C.V.", "fecha_emision": fecha_emision,
        "fecha_vencimiento": None, "nivel_confianza": 0.95, "observaciones": "Texto legible.",
    })


def reglas(mp: pytest.MonkeyPatch, resultado=None, falla=False):
    """Simula el rules-service con el resultado indicado para RCV-02."""
    def evaluar(tipo, emision, vencimiento, referencia):
        llamadas.append((tipo, emision, vencimiento, referencia))
        if falla:
            raise ReglasNoDisponiblesError("Connection refused")
        evaluacion = {"codigo_regla": "RCV-02", "nombre_regla": "Caducidad Estricta del Comprobante de Domicilio Fiscal",
                      "severidad": "ALTA", "criterio": "ANTIGUEDAD_DESDE_EMISION", "resultado": resultado,
                      "limite_dias": 90, "dias_calculados": None, "detalle": f"Resultado {resultado}."}
        return {"tipo_documento": tipo, "fecha_referencia": referencia.isoformat(), "resultado": resultado,
                "es_vigente": None, "dias_calculados": None, "evaluaciones": [evaluacion]}
    mp.setattr(rules_client, "evaluar_vigencia", evaluar)


def analizar(tipo_registrado="COMP_DOMICILIO"):
    return analisis_semantico.analizar("Recibo de luz ...", rfc_titular=RFC, fecha_referencia=HOY,
                                       tipo_documento_registrado=tipo_registrado)


def main(mp: pytest.MonkeyPatch) -> int:
    print("=== DICTAMEN DEL NIVEL 4 CON LAS REGLAS DE VIGENCIA (RCV) ===\n")
    _resultados.clear()
    llamadas.clear()

    modelo(mp, "2019-04-13"); reglas(mp, "VENCIDO")
    r = analizar()
    verificar(r.estatus_preliminar == "NO_CONFORME" and r.vigente is False and not r.requiere_revision_humana,
              "Comprobante vencido por RCV-02: NO_CONFORME aunque el RFC coincida", r.estatus_preliminar)
    verificar(any(o.startswith("RCV-02") for o in r.observaciones), "La observación cita la regla RCV-02")
    verificar(r.vigencia_nivel_2.get("disponible") and r.vigencia_nivel_2.get("resultado") == "VENCIDO",
              "El dictamen incluye la traza del Nivel 2")

    modelo(mp, "2026-08-01"); reglas(mp, "VIGENTE")
    r = analizar()
    verificar(r.estatus_preliminar == "CONFORME" and r.vigente is True, "Comprobante reciente: CONFORME", r.estatus_preliminar)

    modelo(mp, None); reglas(mp, "INDETERMINADO")
    r = analizar()
    verificar(r.estatus_preliminar == "EN_REVISION" and r.requiere_revision_humana and r.vigente is None,
              "Sin fecha de emisión: EN_REVISION con revisión humana", r.estatus_preliminar)

    modelo(mp, "2026-08-01"); reglas(mp, falla=True)
    r = analizar()
    verificar(r.estatus_preliminar == "EN_REVISION" and r.requiere_revision_humana,
              "rules-service caído: EN_REVISION, nunca CONFORME sin verificar la vigencia", r.estatus_preliminar)
    verificar(r.vigencia_nivel_2.get("disponible") is False and any("rules-service" in o for o in r.observaciones),
              "El motivo de la revisión queda registrado")

    llamadas.clear(); modelo(mp, "2026-08-01"); reglas(mp, "VIGENTE")
    analizar(tipo_registrado="COMP_DOMICILIO")
    analizar(tipo_registrado=None)
    verificar(llamadas[0][0] == "COMP_DOMICILIO", "Se evalúa el tipo registrado en el expediente")
    verificar(llamadas[1][0] == "COMP_DOMICILIO", "Sin tipo registrado, se traduce el tipo detectado al catálogo del core")
    verificar(llamadas[0][1] == "2026-08-01" and llamadas[0][3] == HOY, "Viajan la fecha de emisión extraída y la de referencia")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_vigencia_dictamen(monkeypatch):
    assert main(monkeypatch) == 0, "Hay verificaciones de vigencia del dictamen en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main(mp))
