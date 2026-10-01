"""
Pruebas de la suite de precisión (evaluacion/evaluar_precision.py), sin red ni
modelo: se le dan respuestas de auditoría escritas a mano y se comprueban las
cifras contra un conteo hecho a mano.

  1. Personas: emparejamiento por nombre con la regla del cotejo RN-03 y cargo
     sin género ni acentos.
  2. Un caso: campos normalizados con las funciones del motor, elementos RSC
     (NO_VERIFICABLE y una regla no evaluada cuentan como omisión) y cita
     anclada contra el texto.
  3. Agregados: la omisión no detectada es una falsa conformidad; el estatus
     da falsa conformidad y rechazo indebido sobre sus denominadores.

Uso:  cd services/ai-service && python -m pytest tests/test_evaluar_precision.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluacion import evaluar_precision as ep  # noqa: E402

TEXTO = ("CONTRATO DE PRESTACIÓN DE SERVICIOS. PRIMERA. OBJETO. El prestador realizará el soporte técnico. "
         "Firma: María Elena Ruiz Soto, Apoderada legal.")


def _caso(estatus="EN_REVISION", elementos=None, personas=None, rendicion="VECTORIAL"):
    return {
        "id": "C1", "caso_base": "C1", "rendicion": rendicion, "tipo_registrado": "CONTRATO_SERVICIOS",
        "texto_referencia": TEXTO,
        "esperado": {
            "tipo_documento": "CONTRATO", "rfc": "PLU180514AB3", "razon_social": "PLURIONE S.A. DE C.V.",
            "fecha_emision": "2026-03-02", "fecha_vencimiento": None, "estatus": estatus, "motivo": "—",
            "personas": personas if personas is not None else [{"nombre": "María Elena Ruiz Soto",
                                                                 "cargo": "Apoderada legal"}],
            "elementos": elementos if elementos is not None else {"OBJ": True, "PEN": False, "CONF": True,
                                                                  "FIRM": True},
        },
    }


def _respuesta(estatus="EN_REVISION", verificaciones=None, personas=None, **campos):
    return {
        "tipo_documento_detectado": "contrato", "rfc_detectado": "plu-180514-ab3",
        "razon_social_detectada": "Plurione, S.A. de C.V.", "fecha_emision": "02/03/2026",
        "fecha_vencimiento": None, "estatus_preliminar": estatus, "nivel_confianza": 0.9,
        "requiere_revision_humana": estatus != "CONFORME", "observaciones": [],
        "verificaciones": verificaciones if verificaciones is not None else [
            {"codigo_regla": "OBJ", "resultado": "CUMPLE", "cita": "El prestador realizará el soporte técnico"},
            {"codigo_regla": "PEN", "resultado": "NO_LOCALIZADO", "cita": None},
            {"codigo_regla": "CONF", "resultado": "NO_VERIFICABLE", "cita": None},
            # FIRM no viene: regla no evaluada.
        ],
        "representacion": {"rol": "FIRMANTES", "personas": personas if personas is not None else [
            {"nombre": "Lic. María Elena Ruiz Soto", "cargo": "apoderado"},
            {"nombre": "Jorge Treviño", "cargo": "Representante legal"},
        ]},
        **campos,
    }


def test_personas_por_nombre_y_cargo():
    assert ep.mismo_nombre("Lic. María Elena Ruiz Soto", "MARIA ELENA RUIZ SOTO")
    assert not ep.mismo_nombre("María Ruiz", "María Soto")
    assert ep.mismo_cargo("Apoderada legal", "apoderado")
    assert ep.mismo_cargo("Administrador Único", "administrador unico")
    assert not ep.mismo_cargo("Representante legal", "Administrador único")
    assert not ep.mismo_cargo("Apoderada", None)
    conteo, cargos = ep.emparejar_personas(
        [{"nombre": "María Elena Ruiz Soto", "cargo": "Apoderada"},
         {"nombre": "Héctor Quiroga Salas", "cargo": "Administrador"}],
        [{"nombre": "Maria Elena Ruiz Soto", "cargo": None}, {"nombre": "Pedro Gómez", "cargo": "Testigo"}],
    )
    assert (conteo.vp, conteo.fp, conteo.fn) == (1, 1, 1)
    assert cargos == [False]   # un cargo vacío es un fallo, no se omite


def test_un_caso_contra_su_anotacion():
    ev = ep.evaluar_caso(_caso(), _respuesta(), TEXTO)
    # Los normalizadores del motor igualan mayúsculas, guiones, signos y formatos de fecha.
    assert all(c["conteo"]["vp"] + c["conteo"]["vn"] == 1 for c in ev["campos"].values())
    e = ev["elementos"]
    assert e["OBJ"]["presente_dictaminado"] and e["OBJ"]["cita_anclada"] is True
    assert not e["PEN"]["presente_dictaminado"]                       # omisión detectada
    assert e["CONF"]["resultado"] == "NO_VERIFICABLE" and not e["CONF"]["presente_dictaminado"]
    assert e["FIRM"]["resultado"] == "NO_EVALUADA" and not e["FIRM"]["presente_dictaminado"]
    assert ev["personas"]["conteo"]["vp"] == 1 and ev["personas"]["conteo"]["fp"] == 1
    assert ev["cer"] is None                                          # solo los escaneos


def test_cita_no_anclada_y_alucinacion():
    respuesta = _respuesta(fecha_vencimiento="2027-03-01", verificaciones=[
        {"codigo_regla": "OBJ", "resultado": "CUMPLE", "cita": "una cláusula que no está en el documento"}])
    ev = ep.evaluar_caso(_caso(), respuesta, TEXTO)
    assert ev["elementos"]["OBJ"]["cita_anclada"] is False
    assert ev["campos"]["fecha_vencimiento"]["conteo"]["fp"] == 1     # inventó una fecha que no hay
    agregado = ep.agregar([ev])
    assert agregado["entidades"]["alucinacion"]["exitos"] == 1


def test_falsa_conformidad_de_elementos_y_de_estatus():
    # PEN falta en el documento y el motor dice que está: falsa conformidad.
    falsa = _respuesta(estatus="CONFORME", verificaciones=[
        {"codigo_regla": c, "resultado": "CUMPLE", "cita": "El prestador realizará el soporte técnico"}
        for c in ("OBJ", "PEN", "CONF", "FIRM")])
    rechazo = _respuesta(estatus="NO_CONFORME")
    correcto = _respuesta(estatus="CONFORME")
    evaluaciones = [
        ep.evaluar_caso(_caso("EN_REVISION"), falsa, TEXTO),
        ep.evaluar_caso({**_caso("CONFORME"), "id": "C2"}, rechazo, TEXTO),
        ep.evaluar_caso({**_caso("CONFORME"), "id": "C3"}, correcto, TEXTO),
    ]
    a = ep.agregar(evaluaciones)
    assert a["elementos"]["falsas_conformidades"] == ["C1:PEN"]
    d = a["decisiones"]
    assert (d["falsa_conformidad"]["exitos"], d["falsa_conformidad"]["total"]) == (1, 1)
    assert (d["rechazo_indebido"]["exitos"], d["rechazo_indebido"]["total"]) == (1, 3)
    assert d["exactitud"]["exitos"] == 1
    assert d["matriz"]["EN_REVISION"]["CONFORME"] == 1
