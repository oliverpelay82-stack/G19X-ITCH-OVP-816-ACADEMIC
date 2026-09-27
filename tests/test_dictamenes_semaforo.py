"""
Pruebas del motor de reglas de la Semana 6 (core-service): dictámenes,
bitácora, semáforo consolidado, RIE-03 y ratificación humana.

  1. Documentos obligatorios desde el catálogo de reglas (HU-09) y respaldo
     controlado cuando el rules-service no responde.
  2. Semáforo: expediente vacío NO_CONFORME; obligatorios sin auditar
     EN_REVISION; nunca CONFORME solo por subir archivos (RN-01).
  3. Guardado y consulta de dictámenes; un recibo vencido por RCV-02 deja el
     expediente NO_CONFORME (RN-02).
  4. Documento vigente por tipo: recargar el comprobante lo sustituye.
  5. Ratificación humana con justificación (RF-14, RN-05) y sus restricciones.
  6. RIE-03: un binario alterado se bloquea (409), recibe dictamen NO_CONFORME,
     queda en la bitácora y arrastra al expediente a NO_CONFORME.
  7. Inmutabilidad: la base rechaza modificar o borrar bitácora y dictámenes.

Aislamiento: base de datos plurione_compliance_test (recreada en cada
ejecución) y bóveda temporal. Nunca toca los expedientes ni la bóveda reales.

Uso:  python tests/test_dictamenes_semaforo.py   (requiere PostgreSQL)
"""
import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import DBAPIError  # noqa: E402

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.documento import Documento  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import integridad  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
client = TestClient(app)
_resultados: list[bool] = []

OBTENER_REAL = rules_client.obtener_documentos_obligatorios
TRES_OBLIGATORIOS = ("CSF_SAT", "COMP_DOMICILIO", "ACTA_CONSTITUTIVA")


def verificar(condicion: bool, titulo: str, detalle: str = "") -> None:
    _resultados.append(bool(condicion))
    print(f"  {'[ OK ]' if condicion else '[FALLA]'} {titulo}" + (f"  -> {detalle}" if detalle else ""))


def catalogo(tipos=TRES_OBLIGATORIOS, severidad="CRITICA"):
    """Simula la respuesta del rules-service con los tipos indicados."""
    rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
        documentos={t: {"codigo_regla": f"RIE-01-{t[:4]}", "severidad": severidad} for t in tipos},
        fuente=rules_client.FUENTE_CATALOGO,
    )


def crear_expediente(rfc: str) -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Titular de Pruebas {rfc} S.A. de C.V.", tipo_persona="MORAL")
        db.add(titular)
        db.commit()
        titular_id = titular.id
    finally:
        db.close()
    r = client.post("/api/v1/expedientes", json={"titular_id": titular_id})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def subir(exp_id: str, tipo: str, contenido: bytes, nombre: str) -> dict:
    r = client.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": tipo, "usuario": "analista.pruebas"},
        files={"file": (nombre, b"%PDF-1.4 " + contenido, "application/pdf")},
    )
    assert r.status_code == 201, r.text
    return r.json()


def expediente(exp_id: str) -> dict:
    return client.get(f"/api/v1/expedientes/{exp_id}").json()


def dictaminar(doc_id: str, estatus: str, confianza: float = 0.95, vigencia: dict | None = None, **extra) -> dict:
    cuerpo = {
        "documento_id": doc_id,
        "estatus": estatus,
        "nivel_confianza": confianza,
        "requiere_revision_humana": estatus == "EN_REVISION",
        "observaciones": [f"Dictamen {estatus}: prueba automatizada."],
        "modelo_utilizado": "qwen/qwen3.8-27b",
        "vigencia": vigencia,
        **extra,
    }
    r = client.post("/api/v1/dictamenes", json=cuerpo)
    assert r.status_code == 201, r.text
    return r.json()


VIGENCIA_RCV02_VENCIDA = {
    "disponible": True,
    "tipo_documento": "COMP_DOMICILIO",
    "resultado": "VENCIDO",
    "dias_calculados": 2722,
    "evaluaciones": [
        {"codigo_regla": "RCV-02", "nombre_regla": "Caducidad Estricta del Comprobante de Domicilio Fiscal",
         "severidad": "ALTA", "criterio": "ANTIGUEDAD_DESDE_EMISION", "resultado": "VENCIDO", "limite_dias": 90,
         "dias_calculados": 2722, "detalle": "El documento tiene 2722 días naturales de antigüedad; el máximo es 90."}
    ],
}
VENCIMIENTO_LEJANO = (date.today() + timedelta(days=400)).isoformat()
VIGENCIA_VIGENTE = {
    "disponible": True, "tipo_documento": "CSF_SAT", "resultado": "VIGENTE", "dias_calculados": None,
    "evaluaciones": [{"codigo_regla": "RCV-01", "resultado": "VIGENTE", "limite_dias": 30,
                      "dias_calculados": 120, "detalle": "El documento vence en 120 días."}],
}


def prueba_catalogo_obligatorios() -> None:
    print("\n[1] Documentos obligatorios desde el catálogo de reglas (HU-09)")
    rules_client.obtener_documentos_obligatorios = OBTENER_REAL
    url_real = rules_client.RULES_BASE_URL
    rules_client.RULES_BASE_URL = "http://127.0.0.1:9"  # puerto cerrado: rules-service caído
    try:
        inventario = rules_client.obtener_documentos_obligatorios()
    finally:
        rules_client.RULES_BASE_URL = url_real
    verificar(inventario.fuente == rules_client.FUENTE_RESPALDO, "rules-service caído: se aplica el respaldo DOC-02",
              inventario.fuente)
    verificar(set(inventario.documentos) == set(TRES_OBLIGATORIOS), "El respaldo exige CSF, domicilio y acta")
    verificar(bool(inventario.advertencia), "La advertencia del respaldo viaja en la respuesta")

    exp_id = crear_expediente("CAT010101AAA")
    catalogo(tipos=("CSF_SAT",))
    subir(exp_id, "CSF_SAT", b"catalogo csf", "csf_catalogo.pdf")
    datos = expediente(exp_id)
    verificar(datos["porcentaje_completitud"] == 100.0,
              "Con un catálogo que solo exige la CSF, la completitud es 100%", f"{datos['porcentaje_completitud']}%")
    verificar(datos["evaluacion"]["fuente_obligatorios"] == "rules-service", "La evaluación indica su fuente")
    catalogo(tipos=TRES_OBLIGATORIOS, severidad="ALTA")
    datos = expediente(exp_id)
    verificar(datos["estado_cumplimiento"] == "EN_REVISION",
              "Faltan obligatorios NO críticos: EN_REVISION, no NO_CONFORME", datos["estado_cumplimiento"])


def prueba_semaforo_y_dictamenes() -> tuple[str, dict]:
    print("\n[2] Semáforo consolidado del expediente (RN-01)")
    catalogo()
    exp_id = crear_expediente("SEM010101AAA")
    datos = expediente(exp_id)
    verificar(datos["estado_cumplimiento"] == "NO_CONFORME", "Expediente sin documentos: NO_CONFORME (RIE-01 crítica)",
              ", ".join(datos["evaluacion"]["faltantes"]))

    csf = subir(exp_id, "CSF_SAT", b"csf semaforo", "csf.pdf")
    dom = subir(exp_id, "COMP_DOMICILIO", b"recibo cfe 2019", "recibo_cfe.pdf")
    acta = subir(exp_id, "ACTA_CONSTITUTIVA", b"acta notarial", "acta.pdf")
    datos = expediente(exp_id)
    verificar(datos["porcentaje_completitud"] == 100.0 and datos["estado_cumplimiento"] == "EN_REVISION",
              "3 obligatorios subidos sin auditar: 100% pero EN_REVISION, nunca CONFORME", datos["estado_cumplimiento"])
    verificar(all(d["estado"] == "SIN_DICTAMEN" for d in datos["evaluacion"]["documentos"]),
              "Cada documento aparece como SIN_DICTAMEN")

    print("\n[3] Guardado y consulta de dictámenes; RCV-02 vencida (RN-02)")
    # Vencimiento lejano y relativo a hoy: la vigencia se recalcula en cada consulta (RN-02).
    d_csf = dictaminar(csf["id"], "CONFORME", vigencia=VIGENCIA_VIGENTE, fecha_vencimiento=VENCIMIENTO_LEJANO,
                       rfc_detectado="SEM010101AAA", match_titular=True)
    verificar(d_csf["estatus"] == "CONFORME" and d_csf["hash_sha256"] == csf["hash_sha256"],
              "Dictamen guardado con la huella del archivo evaluado")
    verificar(d_csf["reglas_aplicadas"][0]["codigo_regla"] == "RIE-03", "RIE-03 verificada antes de dictaminar")
    verificar(str(d_csf["fecha_vencimiento_extraida"]) == VENCIMIENTO_LEJANO, "Fecha de vencimiento extraída persistida")
    dictaminar(acta["id"], "CONFORME", vigencia={"disponible": True, "resultado": "SIN_REGLAS", "evaluaciones": []})
    d_dom = dictaminar(dom["id"], "NO_CONFORME", vigencia=VIGENCIA_RCV02_VENCIDA, fecha_emision="2019-04-13")
    verificar(d_dom["estado_expediente"] == "NO_CONFORME",
              "Recibo vencido por RCV-02: el expediente queda NO_CONFORME", d_dom["estado_expediente"])
    verificar(any(r["codigo_regla"] == "RCV-02" and r["resultado"] == "VENCIDO" for r in d_dom["reglas_aplicadas"]),
              "reglas_aplicadas registra RCV-02: VENCIDO")
    verificar(d_dom["vigencia_resultado"] == "VENCIDO", "vigencia_resultado = VENCIDO")

    historial = client.get("/api/v1/dictamenes", params={"documento_id": dom["id"]}).json()
    verificar(len(historial) == 1 and historial[0]["id"] == d_dom["id"], "Consulta del historial por documento")
    uno = client.get(f"/api/v1/dictamenes/{d_dom['id']}")
    verificar(uno.status_code == 200 and uno.json()["estatus_preliminar"] == "NO_CONFORME", "Consulta por identificador")
    verificar(client.get("/api/v1/dictamenes/no-existe").status_code == 404, "Dictamen inexistente: 404")
    estatus_invalido = client.post("/api/v1/dictamenes", json={"documento_id": csf["id"], "estatus": "APROBADO",
                                                            "nivel_confianza": 0.9})
    verificar(estatus_invalido.status_code == 422, "Un estatus fuera del catálogo se rechaza con 422")
    eventos = {e["evento"] for e in client.get("/api/v1/bitacora", params={"expediente_id": exp_id}).json()}
    verificar({"APERTURA_EXPEDIENTE", "INGESTA_DOCUMENTO", "DICTAMEN_IA", "EVALUACION_REGLAS"} <= eventos,
              "La bitácora registra apertura, ingesta, dictamen y evaluación", ", ".join(sorted(eventos)))
    return exp_id, {"csf": csf, "dom": dom, "acta": acta, "d_dom": d_dom}


def prueba_ratificacion(exp_id: str, docs: dict) -> None:
    print("\n[4] Documento vigente por tipo y ratificación humana (RF-14, RN-05)")
    dom2 = subir(exp_id, "COMP_DOMICILIO", b"recibo cfe reciente", "recibo_cfe_2026.pdf")
    datos = expediente(exp_id)
    verificar(datos["estado_cumplimiento"] == "EN_REVISION" and datos["evaluacion"]["sustituidos"] == 1,
              "El comprobante nuevo sustituye al vencido: EN_REVISION", datos["estado_cumplimiento"])

    confirmado = client.post(f"/api/v1/dictamenes/{docs['d_dom']['id']}/ratificar",
                             json={"nuevo_estatus": "NO_CONFORME",
                                   "justificacion": "Se confirma: el recibo de 2019 excede los 90 días de RCV-02.",
                                   "usuario": "analista.pruebas"})
    verificar(confirmado.status_code == 200 and confirmado.json()["estado_expediente"] == "EN_REVISION",
              "El analista confirma el NO_CONFORME del recibo sustituido; no afecta al semáforo",
              f"HTTP {confirmado.status_code}")

    d_rev = dictaminar(dom2["id"], "EN_REVISION", confianza=0.78)
    verificar(d_rev["estado_expediente"] == "EN_REVISION", "Confianza 0.78 (< 0.85): expediente EN_REVISION")

    corta = client.post(f"/api/v1/dictamenes/{d_rev['id']}/ratificar",
                        json={"nuevo_estatus": "CONFORME", "justificacion": "ok", "usuario": "ana"})
    verificar(corta.status_code == 422, "Una justificación de menos de 10 caracteres se rechaza (422)")

    justificacion = "Recibo de CFE de agosto de 2026 cotejado contra el original; domicilio y titular correctos."
    r = client.post(f"/api/v1/dictamenes/{d_rev['id']}/ratificar",
                    json={"nuevo_estatus": "CONFORME", "justificacion": justificacion, "usuario": "ana.lopez"})
    cuerpo = r.json()
    verificar(r.status_code == 200 and cuerpo["estatus"] == "CONFORME" and cuerpo["revisado_por_humano"],
              "Ratificación CONFORME aceptada", f"HTTP {r.status_code}")
    verificar(cuerpo["estatus_preliminar"] == "EN_REVISION", "El estatus automático original se conserva")
    verificar(cuerpo["justificacion_humana"] == justificacion and cuerpo["revisado_por"] == "ana.lopez",
              "Justificación y analista registrados en el dictamen")
    verificar(cuerpo["estado_expediente"] == "CONFORME",
              "Todos los vigentes conformes: el expediente pasa a CONFORME", cuerpo["estado_expediente"])

    otra = client.post(f"/api/v1/dictamenes/{d_rev['id']}/ratificar",
                       json={"nuevo_estatus": "NO_CONFORME", "justificacion": "Segundo intento de ratificación."})
    verificar(otra.status_code == 409, "Un dictamen ya ratificado no admite otra decisión (409)")

    ratificaciones = client.get("/api/v1/bitacora", params={"documento_id": dom2["id"],
                                                             "evento": "RATIFICACION_HUMANA"}).json()
    verificar(len(ratificaciones) == 1 and ratificaciones[0]["detalle"]["justificacion"] == justificacion
              and ratificaciones[0]["usuario"] == "ana.lopez", "La bitácora guarda la ratificación con su justificación")

    # Una auditoría posterior sustituye al dictamen ratificado: el anterior ya no es el vigente.
    d_nuevo = dictaminar(dom2["id"], "CONFORME")
    verificar(d_nuevo["estado_expediente"] == "CONFORME", "Nueva auditoría conforme: el expediente sigue CONFORME")


def prueba_rie03(exp_id: str, docs: dict) -> None:
    print("\n[5] RIE-03: detección de alteración en la bóveda")
    csf = docs["csf"]
    ok = client.get(f"/api/v1/documentos/{csf['id']}/integridad")
    verificar(ok.status_code == 200 and ok.json()["integro"], "Binario intacto: integridad verificada")
    contenido = client.get(f"/api/v1/documentos/{csf['id']}/contenido")
    verificar(contenido.status_code == 200 and contenido.headers.get("X-Hash-SHA256") == csf["hash_sha256"],
              "Descarga verificada del binario")

    db = SessionLocal()
    try:
        ruta = integridad.ruta_binario(db.query(Documento).filter(Documento.id == csf["id"]).first())
    finally:
        db.close()
    with open(ruta, "ab") as archivo:
        archivo.write(b" -- linea agregada fuera del sistema")

    r = client.get(f"/api/v1/documentos/{csf['id']}/integridad")
    verificar(r.status_code == 409 and "RIE-03" in r.json()["detail"], "Huella distinta: HTTP 409", f"HTTP {r.status_code}")
    ficha = client.get(f"/api/v1/documentos/{csf['id']}").json()
    verificar(ficha["estado_integridad"] == "ALTERADO", "El documento queda marcado ALTERADO")
    verificar(client.get(f"/api/v1/documentos/{csf['id']}/contenido").status_code == 409,
              "Un documento alterado no se entrega (409)")
    historial = client.get("/api/v1/dictamenes", params={"documento_id": csf["id"]}).json()
    verificar(historial[0]["origen"] == "RIE-03" and historial[0]["estatus"] == "NO_CONFORME",
              "Se emite un dictamen NO_CONFORME de origen RIE-03")
    alertas = client.get("/api/v1/bitacora", params={"documento_id": csf["id"], "evento": "ALERTA_INTEGRIDAD"}).json()
    verificar(len(alertas) == 1 and alertas[0]["detalle"]["hash_registrado"] == csf["hash_sha256"]
              and alertas[0]["detalle"]["hash_actual"] != csf["hash_sha256"],
              "El incidente queda en la bitácora con ambas huellas")
    datos = expediente(exp_id)
    verificar(datos["estado_cumplimiento"] == "NO_CONFORME", "El expediente pasa a NO_CONFORME",
              datos["estado_cumplimiento"])

    r = client.post("/api/v1/dictamenes", json={"documento_id": csf["id"], "estatus": "CONFORME", "nivel_confianza": 0.99})
    verificar(r.status_code == 409, "No se puede dictaminar un documento alterado (409)")
    r = client.post(f"/api/v1/dictamenes/{historial[0]['id']}/ratificar",
                    json={"nuevo_estatus": "CONFORME", "justificacion": "Intento de aprobar un archivo alterado."})
    verificar(r.status_code == 409, "Una alteración RIE-03 no admite ratificación (409)")


def prueba_inmutabilidad() -> None:
    print("\n[6] Inmutabilidad en la base de datos (RF-27, RN-04)")
    for tabla, sentencia in [
        ("bitacora_auditoria", "UPDATE bitacora_auditoria SET usuario = 'intruso'"),
        ("bitacora_auditoria", "DELETE FROM bitacora_auditoria"),
        ("dictamenes_auditoria", "DELETE FROM dictamenes_auditoria"),
        ("dictamenes_auditoria", "UPDATE dictamenes_auditoria SET estatus = 'CONFORME' WHERE NOT revisado_por_humano"),
    ]:
        try:
            with engine.begin() as conn:
                conn.execute(text(sentencia))
            rechazada = False
        except DBAPIError:
            rechazada = True
        verificar(rechazada, f"La base rechaza: {sentencia.split(' SET')[0].split(' WHERE')[0]}", tabla)


def run_tests() -> int:
    print("=== MOTOR DE REGLAS (SEMANA 6): DICTÁMENES, SEMÁFORO, RIE-03 Y RATIFICACIÓN ===")
    try:
        prueba_catalogo_obligatorios()
        exp_id, docs = prueba_semaforo_y_dictamenes()
        prueba_ratificacion(exp_id, docs)
        prueba_rie03(exp_id, docs)
        prueba_inmutabilidad()
    finally:
        rules_client.obtener_documentos_obligatorios = OBTENER_REAL
        bd_pruebas.limpiar_boveda(BOVEDA)

    aprobadas = sum(_resultados)
    print(f"\nResultado: {aprobadas}/{len(_resultados)} verificaciones aprobadas")
    return 0 if aprobadas == len(_resultados) else 1


def test_dictamenes_semaforo():
    assert run_tests() == 0, "Hay verificaciones de dictámenes/semáforo en [FALLA] (ver salida con -s)"


if __name__ == "__main__":
    sys.exit(run_tests())
