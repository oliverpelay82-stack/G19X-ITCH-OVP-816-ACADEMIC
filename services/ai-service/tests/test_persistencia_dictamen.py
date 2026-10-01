"""
Pruebas de la persistencia del dictamen del Nivel 4 y de RIE-03 en el
ai-service, sin red: Groq, el rules-service y el core-service se simulan.

  1. Un análisis por ``documento_id`` persiste el dictamen en el core-service
     con el estatus, la confianza, las fechas, la vigencia RCV y el usuario.
  2. Si el core-service no responde, el dictamen se devuelve marcado como no
     persistido (la auditoría no se pierde, pero no se presenta como definitiva).
  3. Un análisis de texto suelto no se persiste (no pertenece a un expediente).
  4. RIE-03: un documento alterado responde 409, tanto al resolver su texto
     como al registrar el dictamen.
  5. El cliente del core traduce el 409 de integridad a DocumentoAlteradoError.

Las simulaciones se instalan con ``monkeypatch`` de pytest y se deshacen al
terminar, así que ninguna otra suite hereda un cliente falso.

Uso:  cd services/ai-service && python tests/test_persistencia_dictamen.py
"""
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from clients import core_client, groq_client, rules_client  # noqa: E402
from clients.core_client import CoreNoDisponibleError, DocumentoAlteradoError  # noqa: E402
from pipelines import repositorio_texto  # noqa: E402

client = TestClient(main.app)
RFC = "PLU180514AB3"
DOC_ID = "doc-prueba-001"
_resultados: list[bool] = []
registrados: list[dict] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def preparar(mp: pytest.MonkeyPatch, registro=None, texto_error=None):
    """Simula Groq, el rules-service, el texto del documento y el registro en el core."""
    mp.setattr(groq_client, "generar_json", lambda prompt, system: {
        "tipo_documento_detectado": "COMPROBANTE_DOMICILIO", "rfc_detectado": RFC,
        "razon_social_detectada": "PLURIONE S.A. DE C.V.", "fecha_emision": "2019-04-13",
        "fecha_vencimiento": None, "nivel_confianza": 0.95, "observaciones": "Texto legible.",
    })
    mp.setattr(rules_client, "evaluar_vigencia", lambda tipo, emision, vencimiento, referencia: {
        "tipo_documento": tipo, "fecha_referencia": referencia.isoformat(), "resultado": "VENCIDO",
        "es_vigente": False, "dias_calculados": 2722,
        "evaluaciones": [{"codigo_regla": "RCV-02", "nombre_regla": "Caducidad Estricta", "severidad": "ALTA",
                          "criterio": "ANTIGUEDAD_DESDE_EMISION", "resultado": "VENCIDO", "limite_dias": 90,
                          "dias_calculados": 2722, "detalle": "2722 días de antigüedad; máximo 90."}],
    })

    def obtener(documento_id, forzar_ocr=False, completar_en_fondo=True, texto_completo=False):
        if texto_error:
            raise texto_error
        return repositorio_texto.TextoDocumento(
            texto="RECIBO CFE ... RFC PLU180514AB3 ... FECHA DE EMISION 13/04/2019",
            metadatos={"id": documento_id, "tipo_documento": "COMP_DOMICILIO", "nombre_archivo_original": "cfe.pdf",
                       "hash_sha256": "a" * 64},
            traza={"confidence_score": 0.99, "total_paginas": 1},
            completo=True,
            sha256="a" * 64,
            fuente="persistencia",
        )

    mp.setattr(repositorio_texto, "obtener_por_documento", obtener)

    def registrar(carga):
        registrados.append(carga)
        if isinstance(registro, Exception):
            raise registro
        return {"id": "dictamen-001", "estatus": carga["estatus"], "estado_expediente": "NO_CONFORME"}

    mp.setattr(core_client, "registrar_dictamen", registrar)


def analizar(**cuerpo):
    return client.post("/api/v1/ai/analisis-semantico",
                       json={"rfc_titular": RFC, "razon_social_titular": "PLURIONE S.A. DE C.V.", **cuerpo})


def main_pruebas(mp: pytest.MonkeyPatch) -> int:
    print("=== PERSISTENCIA DEL DICTAMEN Y RIE-03 EN EL AI-SERVICE ===")
    _resultados.clear()

    print("\n[1] Dictamen persistido en el core-service")
    preparar(mp)
    registrados.clear()
    r = analizar(documento_id=DOC_ID, usuario="ana.lopez")
    cuerpo = r.json()
    verificar(r.status_code == 200 and cuerpo["estatus_preliminar"] == "NO_CONFORME",
              "Recibo de 2019: NO_CONFORME por RCV-02", cuerpo.get("estatus_preliminar"))
    verificar(cuerpo.get("persistencia", {}).get("guardado") is True, "La respuesta confirma el guardado")
    carga = registrados[0] if registrados else {}
    verificar(carga.get("documento_id") == DOC_ID and carga.get("estatus") == "NO_CONFORME",
              "Viajan el documento y el estatus")
    verificar(carga.get("fecha_emision") == "2019-04-13" and carga.get("nivel_confianza") == 0.95,
              "Viajan la fecha extraída y la confianza")
    verificar(carga.get("vigencia", {}).get("evaluaciones", [{}])[0].get("codigo_regla") == "RCV-02",
              "Viaja la evaluación RCV del Nivel 2")
    verificar(carga.get("usuario") == "ana.lopez", "Viaja el usuario que solicitó la auditoría")
    # P5 (protocolo del DOC-05): el dictamen dice con qué lectura e instrucciones se emitió.
    verificar(str(carga.get("version_lectura", "")).startswith("n3-") and
              str(carga.get("version_instrucciones", "")).startswith("inst-"),
              "Viajan la versión de la lectura y la huella de las instrucciones",
              f"{carga.get('version_lectura')} · {carga.get('version_instrucciones')}")
    verificar(cuerpo.get("versiones", {}).get("version_instrucciones") == carga.get("version_instrucciones"),
              "La respuesta muestra las mismas versiones que se guardaron")

    print("\n[2] core-service caído durante el registro")
    preparar(mp, registro=CoreNoDisponibleError("Connection refused"))
    r = analizar(documento_id=DOC_ID)
    persistencia = r.json().get("persistencia", {})
    verificar(r.status_code == 200 and persistencia.get("guardado") is False and "refused" in persistencia.get("detalle", ""),
              "El dictamen se devuelve marcado como no persistido")

    print("\n[3] Texto suelto")
    preparar(mp)
    registrados.clear()
    r = analizar(texto="CONSTANCIA DE SITUACION FISCAL RFC PLU180514AB3")
    verificar(r.status_code == 200 and "persistencia" not in r.json() and not registrados,
              "Un texto enviado por el cliente no se persiste")

    print("\n[4] RIE-03: documento alterado")
    preparar(mp, texto_error=DocumentoAlteradoError("[RIE-03] La huella SHA-256 del binario no coincide."))
    r = analizar(documento_id=DOC_ID)
    verificar(r.status_code == 409 and "RIE-03" in r.json()["detail"], "Resolver el texto de un alterado: 409")
    r = client.post("/api/v1/ai/chat-documento", json={"documento_id": DOC_ID, "pregunta": "¿Quién es el titular?"})
    verificar(r.status_code == 409, "El chat tampoco opera sobre un documento alterado: 409")
    preparar(mp, registro=DocumentoAlteradoError("[RIE-03] alterado al registrar"))
    r = analizar(documento_id=DOC_ID)
    verificar(r.status_code == 409, "Alteración detectada al registrar el dictamen: 409")

    print("\n[5] Cliente del core-service")
    # La sesión HTTP es compartida por el proceso: la simulación se deshace al salir del bloque.
    with pytest.MonkeyPatch.context() as local:
        local.setattr(core_client._sesion, "get", lambda url, timeout: SimpleNamespace(
            status_code=409, ok=False, text="", json=lambda: {"detail": "[RIE-03] huella distinta"}))
        try:
            core_client.verificar_integridad(DOC_ID)
            traducido = False
        except DocumentoAlteradoError as exc:
            traducido = "RIE-03" in str(exc)
    verificar(traducido, "HTTP 409 del core-service -> DocumentoAlteradoError")

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_persistencia_dictamen(monkeypatch):
    assert main_pruebas(monkeypatch) == 0, "Hay verificaciones de persistencia del dictamen en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    with pytest.MonkeyPatch.context() as mp:
        sys.exit(main_pruebas(mp))
