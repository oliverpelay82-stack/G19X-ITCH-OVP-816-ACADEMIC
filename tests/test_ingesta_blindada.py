"""
P1 — Ingesta blindada del core-service (extensión PLUS, ESTADO_DEL_DESARROLLO §6.1):

PLUS-01 · Unicidad de la huella en el expediente
  1. Recargar el mismo archivo en el expediente responde 409, identifica el
     documento custodiado y no crea documento, evento ni cambio de semáforo.
  2. El mismo archivo con otro tipo documental también se rechaza.
  3. El mismo archivo en otro expediente se admite e informa el folio.
  4. Recargar el original de un documento ALTERADO (RIE-03) se admite.
  5. Dos cargas simultáneas del mismo archivo dejan un solo documento.

PLUS-02 · PDF protegido con contraseña detectado en el Nivel 1 (DOC-05, Tabla 1)
  6. Un PDF con contraseña de apertura se custodia con un dictamen
     NO_CONFORME de origen NIVEL_1, evento ARCHIVO_PROTEGIDO, alerta con su
     recomendación y advertencia en la respuesta; no admite ratificación.
  7. Un PDF con solo contraseña de propietario (permisos) es procesable.
  8. Cargar la versión sin contraseña sustituye a la protegida.
  9. Un PDF con estructura ilegible no se declara protegido.

PLUS-03 · Opinión de cumplimiento 32-D en el semáforo
 10. Una opinión negativa (RSC-OPIN-SENT: NO_CUMPLE) alerta con la cita y la
     recomendación de su regla.
 11. Una opinión auditada vigente vence por RCV-04 al pasar 30 días desde su
     emisión, sin reauditarse (RN-02), y la alerta cita RCV-04.

Aislamiento: base de datos de pruebas plurione_compliance_test y bóveda
temporal (tests/bd_pruebas.py).
"""
import io
import os
from datetime import date, timedelta
import sys
import threading
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()
os.environ["REEVALUACION_INTERVALO_HORAS"] = "0"

from pypdf import PdfWriter  # noqa: E402
from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from controllers import documento_controller  # noqa: E402
from models.bitacora import BitacoraAuditoria  # noqa: E402
from models.documento import Documento  # noqa: E402
from models.expediente import Expediente  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from motor import cumplimiento, integridad  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()

rules_client.obtener_documentos_obligatorios = lambda *_: rules_client.InventarioObligatorio(
    documentos={"CSF_SAT": {"codigo_regla": "RIE-01", "severidad": "CRITICA"}},
    fuente=rules_client.FUENTE_CATALOGO,
)
auth = bd_pruebas.Autenticacion()
client = auth.cliente(app)


def _expediente(codigo: str, rfc: str) -> str:
    db = SessionLocal()
    try:
        titular = TitularExpediente(rfc=rfc, razon_social=f"Titular {codigo} S.A. de C.V.", tipo_persona="MORAL",
                                    categoria="PROVEEDOR")
        db.add(titular)
        db.flush()
        expediente = Expediente(titular_id=titular.id, codigo_expediente=codigo, estado_cumplimiento="EN_REVISION",
                                porcentaje_completitud=0.0)
        db.add(expediente)
        db.commit()
        return expediente.id
    finally:
        db.close()


def _subir(exp_id: str, contenido: bytes, nombre: str = "csf.pdf", tipo: str = "CSF_SAT", cliente=client):
    return cliente.post(
        "/api/v1/documentos/upload",
        data={"expediente_id": exp_id, "tipo_documento": tipo},
        files={"file": (nombre, contenido, "application/pdf")},
    )


def _conteos(exp_id: str) -> tuple[int, int]:
    """Documentos del expediente y eventos de ingesta en la bitácora."""
    db = SessionLocal()
    try:
        documentos = db.query(Documento).filter(Documento.expediente_id == exp_id).count()
        ingestas = (
            db.query(BitacoraAuditoria)
            .filter(BitacoraAuditoria.expediente_id == exp_id, BitacoraAuditoria.evento == "INGESTA_DOCUMENTO")
            .count()
        )
        return documentos, ingestas
    finally:
        db.close()


def test_recargar_el_mismo_archivo_responde_409_sin_efectos():
    exp_id = _expediente("EXP-DUP-01", "DUP010101AAA")
    contenido = b"%PDF-1.4 constancia fiscal unica " + os.urandom(8)
    primero = _subir(exp_id, contenido, "constancia.pdf")
    assert primero.status_code == 201, primero.text
    estado_antes = client.get(f"/api/v1/expedientes/{exp_id}").json()["estado_cumplimiento"]

    repetido = _subir(exp_id, contenido, "constancia_copia.pdf")

    assert repetido.status_code == 409, repetido.text
    detalle = repetido.json()["detail"]
    assert "ya está custodiado" in detalle and "constancia.pdf" in detalle, detalle
    assert _conteos(exp_id) == (1, 1), "El 409 no debe crear documento ni evento de ingesta"
    assert client.get(f"/api/v1/expedientes/{exp_id}").json()["estado_cumplimiento"] == estado_antes
    assert not any("constancia_copia" in f for f in os.listdir(BOVEDA)), "El 409 no debe escribir en la bóveda"


def test_el_mismo_archivo_con_otro_tipo_tambien_se_rechaza():
    exp_id = _expediente("EXP-DUP-02", "DUP020202AAA")
    contenido = b"%PDF-1.4 acta registrada como otro tipo " + os.urandom(8)
    assert _subir(exp_id, contenido, "acta.pdf", "ACTA_CONSTITUTIVA").status_code == 201

    otro_tipo = _subir(exp_id, contenido, "acta.pdf", "PODER_NOTARIAL")

    assert otro_tipo.status_code == 409, otro_tipo.text
    assert "Acta Constitutiva" in otro_tipo.json()["detail"]


def test_el_mismo_archivo_en_otro_expediente_se_admite_e_informa_el_folio():
    origen = _expediente("EXP-DUP-03A", "DUP030303AAA")
    destino = _expediente("EXP-DUP-03B", "DUP030303BBB")
    contenido = b"%PDF-1.4 documento compartido " + os.urandom(8)
    assert _subir(origen, contenido).status_code == 201

    segundo = _subir(destino, contenido)

    assert segundo.status_code == 201, segundo.text
    assert segundo.json()["huella_en_otros_expedientes"] == ["EXP-DUP-03A"]


def test_recargar_el_original_de_un_documento_alterado_se_admite():
    exp_id = _expediente("EXP-DUP-04", "DUP040404AAA")
    contenido = b"%PDF-1.4 original que sera alterado " + os.urandom(8)
    documento = _subir(exp_id, contenido, "original.pdf").json()
    ruta = os.path.join(BOVEDA, f"{documento['hash_sha256'][:12]}_original.pdf")
    with open(ruta, "wb") as archivo:
        archivo.write(b"%PDF-1.4 contenido manipulado")
    assert client.get(f"/api/v1/documentos/{documento['id']}/integridad").status_code == 409
    db = SessionLocal()
    try:
        assert db.get(Documento, documento["id"]).estado_integridad == integridad.ALTERADO
    finally:
        db.close()

    recarga = _subir(exp_id, contenido, "original.pdf")

    assert recarga.status_code == 201, recarga.text
    assert recarga.json()["estado_integridad"] == integridad.INTEGRO


def test_cargas_simultaneas_del_mismo_archivo_dejan_un_solo_documento(monkeypatch):
    exp_id = _expediente("EXP-DUP-05", "DUP050505AAA")
    contenido = b"%PDF-1.4 carga concurrente " + os.urandom(8)
    reevaluar = documento_controller.cumplimiento.reevaluar

    def reevaluar_lento(*args, **kwargs):
        # Ensancha la ventana entre la verificación y el COMMIT: sin el candado
        # por expediente, la segunda carga pasaría la verificación en ella.
        time.sleep(0.6)
        return reevaluar(*args, **kwargs)

    monkeypatch.setattr(documento_controller.cumplimiento, "reevaluar", reevaluar_lento)
    respuestas: list[int] = []

    def cargar():
        # Sin «with»: el lifespan ejecuta init_db, cuyo ALTER TABLE espera a la
        # otra transacción y serializaría las cargas antes de la verificación.
        respuestas.append(_subir(exp_id, contenido, cliente=auth.cliente(app)).status_code)

    hilos = [threading.Thread(target=cargar) for _ in range(2)]
    for hilo in hilos:
        hilo.start()
    for hilo in hilos:
        hilo.join(timeout=30)

    assert sorted(respuestas) == [201, 409], respuestas
    assert _conteos(exp_id) == (1, 1)


def _pdf(contrasena_apertura: str | None = None, contrasena_propietario: str | None = None) -> bytes:
    """PDF de una página, único por su metadato; cifrado con AES-256 si se pide una contraseña."""
    escritor = PdfWriter()
    escritor.add_blank_page(width=200, height=200)
    escritor.add_metadata({"/Title": os.urandom(8).hex()})
    if contrasena_apertura is not None or contrasena_propietario is not None:
        escritor.encrypt(user_password=contrasena_apertura or "", owner_password=contrasena_propietario,
                         algorithm="AES-256")
    salida = io.BytesIO()
    escritor.write(salida)
    return salida.getvalue()


def _eventos(exp_id: str, evento: str) -> list[BitacoraAuditoria]:
    db = SessionLocal()
    try:
        return db.query(BitacoraAuditoria).filter(
            BitacoraAuditoria.expediente_id == exp_id, BitacoraAuditoria.evento == evento
        ).all()
    finally:
        db.close()


def _fila(datos: dict, documento_id: str) -> dict:
    return next(d for d in datos["evaluacion"]["documentos"] if d["documento_id"] == documento_id)


def test_pdf_con_contrasena_de_apertura_se_custodia_no_conforme():
    exp_id = _expediente("EXP-PROT-01", "PRO010101AAA")

    respuesta = _subir(exp_id, _pdf(contrasena_apertura="secreta"), "csf_protegida.pdf")

    assert respuesta.status_code == 201, respuesta.text
    documento = respuesta.json()
    assert documento["advertencia_nivel_1"] and "contraseña" in documento["advertencia_nivel_1"]
    assert documento["estado_integridad"] == integridad.INTEGRO, "El archivo está íntegro: solo no es procesable"

    datos = client.get(f"/api/v1/expedientes/{exp_id}").json()
    fila = _fila(datos, documento["id"])
    assert fila["estado"] == "NO_CONFORME" and fila["dictamen_id"], fila
    assert datos["estado_cumplimiento"] == "NO_CONFORME"
    assert any("protegido con contraseña" in m for m in datos["evaluacion"]["motivos"]), datos["evaluacion"]["motivos"]
    alerta = next(a for a in datos["evaluacion"]["alertas"] if a["codigo"] == "DICTAMEN_NO_CONFORME")
    assert "sin contraseña" in alerta["recomendacion"] and "protegido" in alerta["detalle"], alerta

    dictamen = client.get(f"/api/v1/dictamenes/{fila['dictamen_id']}").json()
    assert dictamen["origen"] == "NIVEL_1" and dictamen["estatus_preliminar"] == "NO_CONFORME"
    eventos = _eventos(exp_id, "ARCHIVO_PROTEGIDO")
    assert len(eventos) == 1 and eventos[0].dictamen_id == dictamen["id"]

    ratificacion = client.post(
        f"/api/v1/dictamenes/{dictamen['id']}/ratificar",
        json={"nuevo_estatus": "CONFORME", "justificacion": "Intento de aprobar un archivo ilegible."},
    )
    assert ratificacion.status_code == 409 and "contraseña" in ratificacion.json()["detail"], ratificacion.text


def test_pdf_con_solo_contrasena_de_propietario_es_procesable():
    exp_id = _expediente("EXP-PROT-02", "PRO020202AAA")

    respuesta = _subir(exp_id, _pdf(contrasena_propietario="solo-permisos"), "csf_con_permisos.pdf")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["advertencia_nivel_1"] is None
    fila = _fila(client.get(f"/api/v1/expedientes/{exp_id}").json(), respuesta.json()["id"])
    assert fila["estado"] == "SIN_DICTAMEN", fila
    assert not _eventos(exp_id, "ARCHIVO_PROTEGIDO")


def test_la_version_sin_contrasena_sustituye_a_la_protegida():
    exp_id = _expediente("EXP-PROT-03", "PRO030303AAA")
    assert _subir(exp_id, _pdf(contrasena_apertura="secreta"), "csf_protegida.pdf").status_code == 201

    corregida = _subir(exp_id, _pdf(), "csf_sin_contrasena.pdf")

    assert corregida.status_code == 201, corregida.text
    datos = client.get(f"/api/v1/expedientes/{exp_id}").json()
    assert _fila(datos, corregida.json()["id"])["estado"] == "SIN_DICTAMEN"
    assert "DICTAMEN_NO_CONFORME" not in {a["codigo"] for a in datos["evaluacion"]["alertas"]}
    assert datos["estado_cumplimiento"] == "EN_REVISION", "Sin la protegida vigente, queda pendiente de auditar"


def test_pdf_con_estructura_ilegible_no_se_declara_protegido():
    exp_id = _expediente("EXP-PROT-04", "PRO040404AAA")

    respuesta = _subir(exp_id, b"%PDF-1.4 /Encrypt sin estructura valida " + os.urandom(8), "roto.pdf")

    assert respuesta.status_code == 201, respuesta.text
    assert respuesta.json()["advertencia_nivel_1"] is None


# ── PLUS-03 · Opinión de cumplimiento 32-D en el semáforo ─────────────
def _dictaminar_opinion(doc_id: str, estatus: str, emitida_hace: int, verificaciones: list[dict]) -> None:
    resultado = "VENCIDO" if emitida_hace > 30 else "VIGENTE"
    respuesta = client.post("/api/v1/dictamenes", headers=auth.sistema(), json={
        "documento_id": doc_id, "estatus": estatus, "nivel_confianza": 0.95,
        "fecha_emision": (date.today() - timedelta(days=emitida_hace)).isoformat(),
        "vigencia": {"disponible": True, "resultado": resultado, "evaluaciones": [
            {"codigo_regla": "RCV-04", "resultado": resultado, "limite_dias": 30, "dias_calculados": emitida_hace,
             "criterio": "ANTIGUEDAD_DESDE_EMISION", "detalle": f"{emitida_hace} días desde la emisión."}]},
        "observaciones": ["Texto legible."], "verificaciones": verificaciones,
    })
    assert respuesta.status_code == 201, respuesta.text


def test_opinion_negativa_alerta_con_la_cita_y_la_recomendacion_de_su_regla():
    exp_id = _expediente("EXP-OPIN-01", "OPI010101AAA")
    doc = _subir(exp_id, _pdf(), "opinion_32d.pdf", "OPINION_CUMPLIMIENTO").json()
    _dictaminar_opinion(doc["id"], "NO_CONFORME", 5, [{
        "codigo_regla": "RSC-OPIN-SENT", "nombre_regla": "Sentido positivo de la opinión de cumplimiento",
        "familia_regla": "RSC", "severidad": "ALTA", "resultado": "NO_CUMPLE",
        "cita": "se emite opinión del cumplimiento en sentido NEGATIVO",
        "observacion": "La opinión de cumplimiento se emitió en sentido NEGATIVO.",
        "recomendacion": "Solicitar una opinión en sentido positivo emitida en los últimos 30 días.",
    }])

    datos = client.get(f"/api/v1/expedientes/{exp_id}").json()

    alerta = next(a for a in datos["evaluacion"]["alertas"] if a["codigo"] == "DICTAMEN_NO_CONFORME")
    assert alerta["regla"] == "RSC-OPIN-SENT" and "sentido positivo" in alerta["recomendacion"], alerta
    assert "en sentido NEGATIVO" in alerta["detalle"], alerta
    assert "CONTENIDO_NO_LOCALIZADO" not in {a["codigo"] for a in datos["evaluacion"]["alertas"]}


def test_opinion_con_mas_de_30_dias_vence_por_rcv04():
    exp_id = _expediente("EXP-OPIN-02", "OPI020202AAA")
    doc = _subir(exp_id, _pdf(), "opinion_vieja.pdf", "OPINION_CUMPLIMIENTO").json()
    _dictaminar_opinion(doc["id"], "CONFORME", 20, [])

    # Auditada vigente a los 20 días; se recalcula contra hoy (RN-02) con la fecha de
    # emisión del dictamen: aquí se simula que ya pasaron 40 días desde la emisión.
    datos = client.get(f"/api/v1/expedientes/{exp_id}").json()
    assert _fila(datos, doc["id"])["vigencia"] == "VIGENTE"
    db = SessionLocal()
    try:
        expediente = db.get(Expediente, exp_id)
        evaluacion = cumplimiento.evaluar(db, expediente, hoy=date.today() + timedelta(days=20))
    finally:
        db.close()

    fila = next(d for d in evaluacion.documentos if d.documento_id == doc["id"])
    assert fila.vigencia == "VENCIDO" and fila.estado == "NO_CONFORME", fila
    alerta = next(a for a in evaluacion.alertas if a.codigo == "DOCUMENTO_VENCIDO")
    assert alerta.regla == "RCV-04" and "30 días" in alerta.recomendacion, alerta
