"""
C6 — Índice de cumplimiento del expediente (DOC-05; PRD §10.5;
docs/uml/c6-actividad-indice-cumplimiento.puml).

índice = cumplidas / (cumplidas + incumplidas + pendientes) × 100

Cálculo (función pura motor.cumplimiento.indice_cumplimiento)
  1. Sin reglas aplicables, el porcentaje no tiene valor (no es 0 %).
  2. Cada regla vale 1: sin ponderación por severidad.
  3. Lo pendiente cuenta en el denominador: sin auditar o sin ratificar, el
     expediente no llega al 100 % (RDS-03).
  4. Bloqueo por criticidad (obligatorio crítico ausente, vencido, alterado)
     sin alterar el porcentaje; próximo a vencer cuenta como cumplida.
  5. Titularidad, contenido RSC/RDS, PDF protegido y cotejo del firmante (RN-03).
  6. La ratificación decide lo que viene del dictamen (RN-05).
  7. El expediente del entorno de desarrollo (Grupo Bimbo) da 11 / 16.

Integración
  8. GET /expedientes/{id} expone evaluacion.indice_cumplimiento.

Aislamiento: base de datos de pruebas plurione_compliance_test y bóveda
temporal (tests/bd_pruebas.py).
"""
import os
import sys
from datetime import date, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import cumplimiento, representacion  # noqa: E402
from motor.cumplimiento import CUMPLIDA, INCUMPLIDA, PENDIENTE, EstadoDocumento, indice_cumplimiento  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
auth = bd_pruebas.Autenticacion()

HOY = date(2026, 9, 29)


# ─────────────────────────── ayudantes ───────────────────────────
def _obligatorio(tipo: str, presente: bool, severidad: str = "CRITICA", principal: str | None = None) -> dict:
    return {"tipo_documento": tipo, "codigo_regla": f"RIE-01-{tipo[:4]}", "severidad": severidad,
            "presente": presente, "documento_principal": principal}


def _documento(doc_id: str, tipo: str, estado: str = "CONFORME", integridad: str = "INTEGRO") -> EstadoDocumento:
    return EstadoDocumento(documento_id=doc_id, tipo_documento=tipo, nombre_archivo_original=f"{doc_id}.pdf",
                           obligatorio=True, estado=estado, estado_integridad=integridad)


def _dictamen(estatus: str = "CONFORME", match: bool | None = True, reglas: list | None = None,
              preliminar: str | None = None, ratificado: bool = False, origen: str = "NIVEL_4_IA"):
    return SimpleNamespace(estatus=estatus, estatus_preliminar=preliminar or estatus, match_titular=match,
                           reglas_aplicadas=reglas or [], revisado_por_humano=ratificado, origen=origen)


def _vigencia(estado: str, dias: int = 100) -> cumplimiento._Vigencia:
    return cumplimiento._Vigencia(estado, HOY + timedelta(days=dias), dias,
                                  cumplimiento.CRITERIO_VENCIMIENTO, None, "RCV-01")


def _resultados(indice) -> dict[str, str]:
    return {f"{r.documento_id or '-'}:{r.regla}": r.resultado for r in indice.reglas}


# ─────────────────────────── cálculo ───────────────────────────
def test_sin_reglas_aplicables_el_indice_no_tiene_valor():
    indice = indice_cumplimiento([], [], {}, {})
    assert indice.porcentaje is None and indice.aplicables == 0 and not indice.bloqueado


def test_todo_cumplido_da_100():
    indice = indice_cumplimiento(
        [_obligatorio("CSF_SAT", True)], [_documento("d1", "CSF_SAT")],
        {"d1": _dictamen(reglas=[{"codigo_regla": "RSC-X", "nombre_regla": "Elemento X", "resultado": "CUMPLE"}])},
        {"d1": _vigencia("VIGENTE")},
    )
    # RIE-01, RIE-03, vigencia, titularidad y el elemento RSC: 5 de 5.
    assert (indice.cumplidas, indice.aplicables, indice.porcentaje) == (5, 5, 100.0)
    assert not indice.bloqueado


def test_cada_regla_vale_uno_sin_ponderar_la_severidad():
    critica = indice_cumplimiento([_obligatorio("CSF_SAT", False), _obligatorio("COMP_DOMICILIO", True)], [], {}, {})
    media = indice_cumplimiento([_obligatorio("CSF_SAT", False, "MEDIA"), _obligatorio("COMP_DOMICILIO", True)],
                                [], {}, {})
    assert critica.porcentaje == media.porcentaje == 50.0
    # La severidad solo actúa por el bloqueo.
    assert critica.bloqueado and not media.bloqueado


def test_el_bloqueo_por_criticidad_no_altera_el_porcentaje():
    indice = indice_cumplimiento(
        [_obligatorio("CSF_SAT", False), _obligatorio("COMP_DOMICILIO", True), _obligatorio("ACTA_CONSTITUTIVA", True)],
        [], {}, {},
    )
    assert indice.bloqueado and indice.porcentaje == round(2 / 3 * 100, 1)
    assert indice.bloqueos == ["Falta Constancia de Situación Fiscal (SAT) (obligatorio de severidad crítica)."]
    assert [r.bloqueante for r in indice.reglas] == [True, False, False]


def test_un_anexo_ausente_incumple_sin_bloquear():
    indice = indice_cumplimiento([_obligatorio("ANEXO_CONTRATO", False, "ALTA", "CONTRATO_SERVICIOS")], [], {}, {})
    [regla] = indice.reglas
    assert regla.resultado == INCUMPLIDA and not regla.bloqueante and not indice.bloqueado
    assert "Contrato de Prestación de Servicios" in regla.nombre


def test_vencido_bloquea_y_proximo_a_vencer_cumple():
    docs = [_documento("v", "POLIZA_SEGURO"), _documento("p", "LICENCIA_OPERACION")]
    dictamenes = {"v": _dictamen(), "p": _dictamen()}
    indice = indice_cumplimiento([], docs, dictamenes, {"v": _vigencia("VENCIDO", -3), "p": _vigencia("PROXIMO_A_VENCER", 10)})
    resultados = _resultados(indice)
    assert resultados["v:RCV-01"] == INCUMPLIDA and resultados["p:RCV-01"] == CUMPLIDA
    assert indice.bloqueado and "venció" in indice.bloqueos[0]


def test_sin_fechas_la_vigencia_no_aplica():
    indice = indice_cumplimiento([], [_documento("a", "ACTA_CONSTITUTIVA")], {"a": _dictamen()}, {})
    assert "a:RCV-01" not in _resultados(indice)


def test_un_documento_alterado_solo_cuenta_su_integridad():
    indice = indice_cumplimiento(
        [], [_documento("x", "CSF_SAT", "NO_CONFORME", "ALTERADO")],
        {"x": _dictamen(reglas=[{"codigo_regla": "RSC-X", "resultado": "CUMPLE"}])}, {},
    )
    assert _resultados(indice) == {"x:RIE-03": INCUMPLIDA}
    assert indice.bloqueado and "alterado" in indice.bloqueos[0]


def test_lo_pendiente_impide_el_100():
    # Obligatorio presente pero sin auditar: RIE-01 y RIE-03 cumplen, la auditoría queda pendiente.
    indice = indice_cumplimiento([_obligatorio("CSF_SAT", True)], [_documento("d", "CSF_SAT", "SIN_DICTAMEN")], {}, {})
    assert (indice.cumplidas, indice.pendientes, indice.aplicables) == (2, 1, 3)
    assert indice.porcentaje == round(2 / 3 * 100, 1) and not indice.bloqueado


def test_titularidad():
    docs = [_documento("ajeno", "CSF_SAT", "NO_CONFORME"), _documento("sin_rfc", "ACTA_CONSTITUTIVA", "EN_REVISION"),
            _documento("propio", "COMP_DOMICILIO")]
    dictamenes = {
        "ajeno": _dictamen("NO_CONFORME", match=False),         # RFC de otra empresa: el motor lo rechazó
        "sin_rfc": _dictamen("EN_REVISION", match=False),       # sin RFC y otra razón social: decide el analista
        "propio": _dictamen("CONFORME", match=True),
    }
    resultados = _resultados(indice_cumplimiento([], docs, dictamenes, {}))
    assert resultados["ajeno:TITULARIDAD"] == INCUMPLIDA
    assert resultados["sin_rfc:TITULARIDAD"] == PENDIENTE
    assert resultados["propio:TITULARIDAD"] == CUMPLIDA


def test_elementos_de_contenido_y_ratificacion():
    reglas = [
        {"codigo_regla": "RSC-A", "nombre_regla": "Objeto (RSC-01)", "resultado": "CUMPLE"},
        {"codigo_regla": "RSC-B", "nombre_regla": "Penalización", "resultado": "NO_LOCALIZADO"},
        {"codigo_regla": "RDS-01", "nombre_regla": "Criterio", "resultado": "NO_VERIFICABLE"},
        {"codigo_regla": "RSC-C", "nombre_regla": "Sentido", "resultado": "NO_CUMPLE"},
        {"codigo_regla": "RIE-03", "resultado": "CUMPLE"},          # se evalúa a la fecha, no desde el dictamen
        {"codigo_regla": "RCV-01", "resultado": "NO_APLICA"},
    ]
    doc = [_documento("c", "CONTRATO_SERVICIOS", "EN_REVISION")]
    sin_ratificar = _resultados(indice_cumplimiento([], doc, {"c": _dictamen("EN_REVISION", reglas=reglas)}, {}))
    assert [sin_ratificar[f"c:{r}"] for r in ("RSC-A", "RSC-B", "RDS-01", "RSC-C")] == \
        [CUMPLIDA, PENDIENTE, PENDIENTE, INCUMPLIDA]
    assert list(sin_ratificar).count("c:RIE-03") == 1

    # RN-05: ratificado, la decisión del analista prevalece en todo lo que viene del dictamen.
    conforme = indice_cumplimiento([], doc, {"c": _dictamen("CONFORME", reglas=reglas, preliminar="EN_REVISION",
                                                            ratificado=True, match=None)}, {})
    assert conforme.pendientes == 0 and conforme.incumplidas == 0 and conforme.porcentaje == 100.0
    rechazo = indice_cumplimiento([], doc, {"c": _dictamen("NO_CONFORME", reglas=reglas, preliminar="EN_REVISION",
                                                           ratificado=True)}, {})
    assert _resultados(rechazo)["c:RSC-A"] == INCUMPLIDA and rechazo.pendientes == 0
    # El nombre del elemento va en lenguaje llano (RNF-08).
    assert any(r.nombre == "Objeto" for r in conforme.reglas)


def test_pdf_protegido_incumple():
    indice = indice_cumplimiento([], [_documento("p", "CSF_SAT", "NO_CONFORME")],
                                 {"p": _dictamen("NO_CONFORME", match=None, origen="NIVEL_1")}, {})
    assert _resultados(indice) == {"p:RIE-03": CUMPLIDA, "p:NIVEL_1": INCUMPLIDA}


def test_cotejo_del_firmante_rn03():
    doc = [_documento("c", "CONTRATO_SERVICIOS", "EN_REVISION")]
    for estado, esperado in ((representacion.ACREDITADO, CUMPLIDA), (representacion.NO_ACREDITADO, INCUMPLIDA),
                             (representacion.PODER_VENCIDO, INCUMPLIDA), (representacion.PENDIENTE, PENDIENTE)):
        cotejo = representacion.CotejoRepresentacion(documento_id="c", tipo_documento="CONTRATO_SERVICIOS",
                                                     nombre_archivo_original="c.pdf", estado=estado, motivo="")
        indice = indice_cumplimiento([], doc, {"c": _dictamen("EN_REVISION")}, {}, [cotejo])
        assert _resultados(indice)["c:RN-03"] == esperado, estado
    ratificado = indice_cumplimiento([], doc, {"c": _dictamen("CONFORME", preliminar="EN_REVISION", ratificado=True)},
                                     {}, [representacion.CotejoRepresentacion(
                                         documento_id="c", tipo_documento="CONTRATO_SERVICIOS",
                                         nombre_archivo_original="c.pdf", estado=representacion.NO_ACREDITADO,
                                         motivo="", ratificado=True)])
    assert _resultados(ratificado)["c:RN-03"] == CUMPLIDA


def test_expediente_del_entorno_de_desarrollo():
    """
    Grupo Bimbo (base local, 29/09/2026): corporativo con sus tres obligatorios
    presentes; acta de asamblea y «otro documento» con RFC ajeno; acta
    constitutiva sin RFC en revisión con tres elementos localizados; constancia
    y domicilio sin auditar. Cálculo del diseño aprobado: 11 / 16.
    """
    obligatorios = [_obligatorio(t, True) for t in ("ACTA_CONSTITUTIVA", "COMP_DOMICILIO", "CSF_SAT")]
    docs = [_documento("asamblea", "ACTA_ASAMBLEA", "NO_CONFORME"),
            _documento("acta", "ACTA_CONSTITUTIVA", "EN_REVISION"),
            _documento("dom", "COMP_DOMICILIO", "SIN_DICTAMEN"),
            _documento("csf", "CSF_SAT", "SIN_DICTAMEN"),
            _documento("otro", "OTRO", "NO_CONFORME")]
    rsc = [{"codigo_regla": c, "resultado": "CUMPLE"} for c in ("RSC-ACTA-ADMON", "RSC-ACTA-ESCR", "RSC-ACTA-RPC")]
    dictamenes = {
        "asamblea": _dictamen("NO_CONFORME", match=False, reglas=[{"codigo_regla": "RCV-01", "resultado": "NO_APLICA"}]),
        "acta": _dictamen("EN_REVISION", match=False, reglas=rsc),
        "otro": _dictamen("NO_CONFORME", match=False),
    }
    indice = indice_cumplimiento(obligatorios, docs, dictamenes, {})
    assert (indice.cumplidas, indice.incumplidas, indice.pendientes, indice.aplicables) == (11, 2, 3, 16)
    assert indice.porcentaje == 68.8 and not indice.bloqueado


# ─────────────────────────── integración ───────────────────────────
def test_la_api_expone_el_indice(monkeypatch):
    # monkeypatch restaura el cliente al terminar: las demás suites comparten el proceso.
    monkeypatch.setattr(rules_client, "obtener_documentos_obligatorios", lambda *_: rules_client.InventarioObligatorio(
        documentos={"CSF_SAT": {"codigo_regla": "RIE-01-CSF", "severidad": "CRITICA"},
                    "COMP_DOMICILIO": {"codigo_regla": "RIE-01-DOM", "severidad": "CRITICA"}},
        fuente=rules_client.FUENTE_CATALOGO,
    ))
    client = auth.cliente(app)
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc="IND010101AAA", razon_social="Índice de Prueba, S.A. de C.V.",
                                    tipo_persona="MORAL", categoria="PROVEEDOR")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    exp = client.post("/api/v1/expedientes", json={"titular_id": titular_id, "tipo_expediente": "CORPORATIVO"})
    assert exp.status_code == 201, exp.text
    r = client.post("/api/v1/documentos/upload", data={"expediente_id": exp.json()["id"], "tipo_documento": "CSF_SAT"},
                    files={"file": ("csf.pdf", b"%PDF-1.4 indice " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text

    indice = client.get(f"/api/v1/expedientes/{exp.json()['id']}").json()["evaluacion"]["indice_cumplimiento"]

    # RIE-01: constancia presente, domicilio ausente (crítico); la constancia: RIE-03 y auditoría pendiente.
    assert (indice["cumplidas"], indice["incumplidas"], indice["pendientes"], indice["aplicables"]) == (2, 1, 1, 4)
    assert indice["porcentaje"] == 50.0 and indice["bloqueado"] is True
    assert indice["bloqueos"] == ["Falta Comprobante de Domicilio Fiscal (obligatorio de severidad crítica)."]
    assert {r["resultado"] for r in indice["reglas"]} == {"CUMPLIDA", "INCUMPLIDA", "PENDIENTE"}


def test_la_hoja_reglas_no_muestra_codigos_internos():
    from motor import reportes
    evaluacion = SimpleNamespace(indice_cumplimiento=indice_cumplimiento(
        [_obligatorio("CSF_SAT", True)], [_documento("d", "CSF_SAT", "SIN_DICTAMEN")], {}, {}))
    filas = reportes._filas_reglas(evaluacion)
    assert [f["regla"] for f in filas] == ["RIE-01-CSF_", "RIE-03", "—"]
    assert [f["resultado"] for f in filas] == ["Cumplida", "Cumplida", "Pendiente"]
