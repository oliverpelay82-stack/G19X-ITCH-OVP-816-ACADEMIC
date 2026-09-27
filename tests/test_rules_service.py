"""
Pruebas del rules-service (:8002) — catálogo de reglas del DOC-05.

Verifica, en proceso y sin modificar el catálogo:
1. El health check responde y reporta la conexión a PostgreSQL.
2. El listado devuelve reglas con los campos del esquema ReglaResponse.
3. Las reglas pertenecen a las familias oficiales RIE, RCV, RSC y RDS.
4. El filtro por familia solo devuelve reglas de esa familia.
5. La consulta por un identificador inexistente responde 404.
6. Una regla con datos inválidos se rechaza con 422 sin llegar a la BD.
7. Motor de vigencia (unitario, fechas fijas, sin BD): límites de la caducidad
   estricta de 90 días, casos indeterminados, reglas pausadas y RCV-01.
8. Endpoint /reglas/evaluar-vigencia contra el catálogo real con RCV-02.
9. Inventario de documentos obligatorios (HU-09): agregación unitaria de las
   reglas RIE y endpoint /reglas/documentos-obligatorios (solo lectura).

Uso:  python tests/test_rules_service.py   (requiere PostgreSQL con el seed del DOC-05)
"""
import os
import sys
from datetime import date, timedelta
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402

servicios.activar("rules-service")

from fastapi.testclient import TestClient  # noqa: E402

from main import app  # noqa: E402
from motor import obligatorios, vigencia  # noqa: E402

client = TestClient(app)
FAMILIAS = {"RIE", "RCV", "RSC", "RDS"}
CAMPOS = {"id", "codigo_regla", "nombre_regla", "familia_regla", "descripcion", "severidad", "accion", "activo"}

_resultados: list[bool] = []


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def main() -> int:
    print("=== PRUEBAS DEL RULES-SERVICE (:8002) ===\n")

    salud = client.get("/api/v1/health")
    verificar(salud.status_code == 200, "Health check responde 200")
    verificar(salud.json().get("conexion_bd") is True, "Conexión a PostgreSQL activa")

    respuesta = client.get("/api/v1/reglas")
    reglas = respuesta.json() if respuesta.status_code == 200 else []
    verificar(respuesta.status_code == 200 and len(reglas) > 0, "El catálogo lista reglas", f"{len(reglas)} reglas")
    verificar(all(CAMPOS <= set(r) for r in reglas), "Cada regla trae los campos del esquema")
    verificar(
        all(r["familia_regla"] in FAMILIAS for r in reglas),
        "Todas las reglas pertenecen a una familia oficial",
        ", ".join(sorted({r["familia_regla"] for r in reglas})),
    )

    rie = client.get("/api/v1/reglas", params={"familia_regla": "RIE"})
    verificar(
        rie.status_code == 200 and all(r["familia_regla"] == "RIE" for r in rie.json()),
        "El filtro por familia devuelve solo esa familia",
        f"{len(rie.json())} reglas RIE",
    )

    inexistente = client.get("/api/v1/reglas/00000000-0000-0000-0000-000000000000")
    verificar(inexistente.status_code == 404, "Un id inexistente responde 404", f"HTTP {inexistente.status_code}")

    invalida = client.post("/api/v1/reglas", json={"codigo_regla": "X", "nombre_regla": "ab"})
    verificar(invalida.status_code == 422, "Una regla inválida se rechaza con 422", f"HTTP {invalida.status_code}")

    prueba_motor_vigencia()
    prueba_endpoint_vigencia()
    prueba_documentos_obligatorios()

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def _regla(codigo, tipo, dias, activo=True):
    return SimpleNamespace(codigo_regla=codigo, nombre_regla=codigo, familia_regla="RCV", severidad="ALTA",
                           tipo_documento=tipo, dias_maximos_vigencia=dias, activo=activo)


def prueba_motor_vigencia() -> None:
    print("\n[7] Motor de vigencia (unitario, fecha de referencia fija 2026-09-23)")
    ref = date(2026, 9, 23)
    rcv01, rcv02 = _regla("RCV-01", None, 30), _regla("RCV-02", "COMP_DOMICILIO", 90)
    catalogo = [rcv01, rcv02]

    def ev(tipo="COMP_DOMICILIO", emision=None, vencimiento=None, reglas=catalogo):
        return vigencia.evaluar(reglas, tipo, emision, vencimiento, ref)

    r = ev(emision=ref - timedelta(days=90))
    verificar(r.resultado == "VIGENTE" and r.dias_calculados == 90, "Exactamente 90 días de antigüedad: VIGENTE (límite inclusivo)")
    r = ev(emision=ref - timedelta(days=91))
    verificar(r.resultado == "VENCIDO" and r.es_vigente is False and r.dias_calculados == 91, "91 días de antigüedad: VENCIDO")
    r = ev(emision=date(2019, 4, 13))
    verificar(r.resultado == "VENCIDO", "Recibo de CFE de 2019: VENCIDO", f"{r.dias_calculados} días")
    r = ev(emision=None)
    verificar(r.resultado == "INDETERMINADO" and r.es_vigente is None, "Sin fecha de emisión: INDETERMINADO (revisión humana)")
    r = ev(emision=ref + timedelta(days=5))
    verificar(r.resultado == "INDETERMINADO", "Emisión posterior a la referencia: INDETERMINADO")
    r = ev(emision=ref - timedelta(days=200), reglas=[rcv01, _regla("RCV-02", "COMP_DOMICILIO", 90, activo=False)])
    verificar(r.resultado == "SIN_REGLAS", "Con RCV-02 pausada, la antigüedad deja de evaluarse")
    r = ev(tipo="CSF_SAT", emision=ref - timedelta(days=200))
    verificar(r.resultado == "SIN_REGLAS", "RCV-02 no se aplica a otros tipos de documento")
    r = ev(tipo="CSF_SAT", vencimiento=ref + timedelta(days=10))
    verificar(r.resultado == "PROXIMO_A_VENCER", "RCV-01: vencimiento en 10 días es PRÓXIMO A VENCER")
    r = ev(emision=ref - timedelta(days=30), vencimiento=ref - timedelta(days=1))
    verificar(r.resultado == "VENCIDO" and r.dias_calculados == 30,
              "Varias reglas: prevalece el resultado más grave (vencimiento pasado)")


def prueba_endpoint_vigencia() -> None:
    print("\n[8] Endpoint POST /api/v1/reglas/evaluar-vigencia (catálogo real)")
    reglas = client.get("/api/v1/reglas", params={"familia_regla": "RCV"}).json()
    rcv02 = next((r for r in reglas if r["codigo_regla"] == "RCV-02"), None)
    verificar(rcv02 is not None and rcv02["tipo_documento"] == "COMP_DOMICILIO" and rcv02["dias_maximos_vigencia"] == 90,
              "RCV-02 está en el catálogo para COMP_DOMICILIO con 90 días")
    if not rcv02 or not rcv02["activo"]:
        verificar(False, "RCV-02 debe estar activa para las pruebas del endpoint")
        return

    ref = date(2026, 9, 23)

    def post(**cuerpo):
        return client.post("/api/v1/reglas/evaluar-vigencia", json={"fecha_referencia": ref.isoformat(), **cuerpo})

    r = post(tipo_documento="COMP_DOMICILIO", fecha_emision=(ref - timedelta(days=90)).isoformat()).json()
    verificar(r["resultado"] == "VIGENTE" and r["dias_calculados"] == 90, "Comprobante con 90 días: VIGENTE")
    r = post(tipo_documento="comp_domicilio", fecha_emision=(ref - timedelta(days=91)).isoformat()).json()
    verificar(r["resultado"] == "VENCIDO" and any(e["codigo_regla"] == "RCV-02" for e in r["evaluaciones"]),
              "Comprobante con 91 días: VENCIDO por RCV-02 (tipo insensible a mayúsculas)")
    r = post(tipo_documento="COMP_DOMICILIO").json()
    verificar(r["resultado"] == "INDETERMINADO" and r["es_vigente"] is None, "Sin fecha de emisión: INDETERMINADO")
    invalida = post(tipo_documento="COMP_DOMICILIO", fecha_emision="2026-13-40")
    verificar(invalida.status_code == 422, "Una fecha inválida se rechaza con 422", f"HTTP {invalida.status_code}")

    rcv03 = next((r for r in reglas if r["codigo_regla"] == "RCV-03"), None)
    verificar(rcv03 is not None and rcv03["activo"] and rcv03["tipo_documento"] == "CSF_SAT"
              and rcv03["dias_maximos_vigencia"] == 90,
              "RCV-03 está activa en el catálogo para CSF_SAT con 90 días (DOC-02, Tabla 2)")
    r = post(tipo_documento="CSF_SAT", fecha_emision=(ref - timedelta(days=30)).isoformat()).json()
    verificar(r["resultado"] == "VIGENTE", "Constancia fiscal con 30 días: VIGENTE", r["resultado"])
    r = post(tipo_documento="CSF_SAT", fecha_emision=(ref - timedelta(days=91)).isoformat()).json()
    verificar(r["resultado"] == "VENCIDO" and any(e["codigo_regla"] == "RCV-03" for e in r["evaluaciones"]),
              "Constancia fiscal con 91 días: VENCIDA por RCV-03", r["resultado"])


def prueba_documentos_obligatorios() -> None:
    print("\n[9] Documentos obligatorios del expediente (HU-09)")

    def rie(codigo, tipo, severidad="CRITICA", obligatorio=True, activo=True, familia="RIE"):
        return SimpleNamespace(codigo_regla=codigo, familia_regla=familia, severidad=severidad, tipo_documento=tipo,
                               documento_obligatorio=obligatorio, activo=activo)

    inventario = obligatorios.documentos_obligatorios([
        rie("RIE-01", None),                                   # regla general: no aporta un tipo
        rie("RIE-01-CSF", "CSF_SAT"),
        rie("RIE-01-DOM", "comp_domicilio", severidad="ALTA"),
        rie("RDS-01-DOM", "COMP_DOMICILIO", severidad="CRITICA", familia="RDS"),  # otra familia: se ignora
        rie("RIE-01-ACTA", "ACTA_CONSTITUTIVA", activo=False),  # pausada
        rie("RIE-01-EDO", "ESTADO_CUENTA", obligatorio=False),  # opcional
        rie("RIE-09-DOM", "COMP_DOMICILIO", severidad="CRITICA"),
    ])
    por_tipo = {d.tipo_documento: d for d in inventario}
    verificar(set(por_tipo) == {"CSF_SAT", "COMP_DOMICILIO"},
              "Solo cuentan reglas RIE activas, obligatorias y con tipo", ", ".join(sorted(por_tipo)))
    verificar(por_tipo["COMP_DOMICILIO"].severidad == "CRITICA" and por_tipo["COMP_DOMICILIO"].codigo_regla == "RIE-09-DOM",
              "Si dos reglas exigen el mismo tipo, prevalece la más severa")

    print("\n[10] Inventario por tipo de expediente y anexos vinculados (RF-06, RIE-02)")

    def regla(codigo, tipo, tipo_expediente=None, principal=None, severidad="CRITICA"):
        return SimpleNamespace(codigo_regla=codigo, familia_regla="RIE", severidad=severidad, tipo_documento=tipo,
                               documento_obligatorio=True, activo=True, tipo_expediente=tipo_expediente,
                               documento_principal=principal)

    catalogo = [
        regla("RIE-01-CSF", "CSF_SAT", "CORPORATIVO"),
        regla("RIE-01-JUR-CONT", "CONTRATO_SERVICIOS", "JURIDICO"),
        regla("RIE-01-GEN", "AVISO_PRIVACIDAD"),                                 # sin tipo: aplica a todos
        regla("RIE-02-CONT-ANX", "ANEXO_CONTRATO", principal="CONTRATO_SERVICIOS", severidad="ALTA"),
    ]
    juridico = {(d.tipo_documento, d.documento_principal) for d in obligatorios.documentos_obligatorios(catalogo, "juridico")}
    verificar(juridico == {("CONTRATO_SERVICIOS", None), ("AVISO_PRIVACIDAD", None),
                           ("ANEXO_CONTRATO", "CONTRATO_SERVICIOS")},
              "El jurídico recibe sus reglas, las generales y el anexo; no la CSF del corporativo")
    todos = obligatorios.documentos_obligatorios(catalogo)
    verificar(len(todos) == 4, "Sin tipo de expediente se devuelven todas las reglas (compatibilidad)")

    invalido = client.get("/api/v1/reglas/documentos-obligatorios", params={"tipo_expediente": "FISCAL"})
    verificar(invalido.status_code == 422, "Un tipo de expediente inválido responde 422", f"HTTP {invalido.status_code}")
    for tipo in ("JURIDICO", "CORPORATIVO", "REGULATORIO"):
        datos = client.get("/api/v1/reglas/documentos-obligatorios", params={"tipo_expediente": tipo}).json()
        verificar(all(d["tipo_expediente"] in (None, tipo) for d in datos),
                  f"El catálogo real para {tipo} solo trae reglas de ese tipo o generales",
                  ", ".join(d["tipo_documento"] for d in datos if not d["documento_principal"]))
    anexo_propio = client.post("/api/v1/reglas", json={
        "codigo_regla": "RIE-99-TEST", "nombre_regla": "Anexo inválido", "familia_regla": "RIE",
        "descripcion": "Un documento no puede ser anexo de sí mismo.", "severidad": "ALTA", "accion": "Ninguna",
        "tipo_documento": "FIANZA", "documento_principal": "FIANZA"})
    verificar(anexo_propio.status_code == 422, "Un documento no puede ser anexo de sí mismo (422, no se guarda)")

    respuesta = client.get("/api/v1/reglas/documentos-obligatorios")
    verificar(respuesta.status_code == 200, "El endpoint responde", f"HTTP {respuesta.status_code}")
    datos = respuesta.json()
    reglas_rie = {r["codigo_regla"]: r for r in client.get("/api/v1/reglas", params={"familia_regla": "RIE"}).json()}
    verificar(all(d["codigo_regla"] in reglas_rie and reglas_rie[d["codigo_regla"]]["activo"] for d in datos),
              "Cada tipo exigido proviene de una regla RIE activa del catálogo real",
              ", ".join(d["tipo_documento"] for d in datos) or "catálogo sin obligatorios (ejecute el seed)")


def test_rules_service():
    assert main() == 0, "Hay verificaciones del rules-service en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    sys.exit(main())
