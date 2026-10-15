"""
RF-20 — Notificaciones por correo electrónico (HU-17; PRD §5.2, fase F5 del Módulo 7;
docs/uml/rf20-actividad-notificacion-correo.puml).

  1. Estatus crítico: el paso a NO CONFORME avisa a los VALIDADOR activos asignados
     (no a los inactivos ni a otros roles), en lenguaje llano y con el enlace al
     expediente; la apertura de un expediente, que nace en rojo, no avisa.
  2. Cada aviso queda en la bitácora: ENVIADO, FALLIDO (con el error),
     SIN_DESTINATARIOS y ENVIO_DESACTIVADO (sin SMTP_HOST). Un rollback no envía nada.
  3. Documento por vencer: la reevaluación programada avisa el umbral alcanzado
     (30, 15 o 5 días) una sola vez; un aviso FALLIDO se reintenta en el ciclo siguiente.

El correo se entrega a un servidor SMTP en memoria (tests/servidor_smtp.py).
Aislamiento: base plurione_compliance_test y bóveda temporal (bd_pruebas.py).
"""
import os
import sys
import uuid
from datetime import date, timedelta

import pytest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bd_pruebas  # noqa: E402
from servidor_smtp import ServidorSmtp  # noqa: E402

BOVEDA = bd_pruebas.preparar_entorno()

from main import app  # noqa: E402
from clients import rules_client  # noqa: E402
from config import seguridad  # noqa: E402
from config.database import SessionLocal, engine, init_db  # noqa: E402
from models.expediente import Expediente  # noqa: E402
from models.titular import TitularExpediente  # noqa: E402
from models.usuario import Usuario  # noqa: E402
from motor import cumplimiento, notificaciones, reevaluacion_programada  # noqa: E402

bd_pruebas.verificar_aislamiento(engine)
init_db()
auth = bd_pruebas.Autenticacion()
admin = auth.cliente(app)

OBLIGATORIOS = ("CSF_SAT", "COMP_DOMICILIO", "ACTA_CONSTITUTIVA")
VIGENCIA_RCV01 = {"disponible": True, "resultado": "PROXIMO_A_VENCER", "evaluaciones": [
    {"codigo_regla": "RCV-01", "resultado": "PROXIMO_A_VENCER", "limite_dias": 30,
     "criterio": "DIAS_PARA_VENCIMIENTO", "dias_calculados": 12, "detalle": "Próximo a vencer."}]}


def _inventario(tipo_expediente: str = "CORPORATIVO") -> rules_client.InventarioObligatorio:
    return rules_client.InventarioObligatorio(
        documentos={t: {"codigo_regla": f"RIE-01-{t[:4]}", "severidad": "CRITICA"} for t in OBLIGATORIOS},
        fuente=rules_client.FUENTE_CATALOGO,
    )


@pytest.fixture(scope="module", autouse=True)
def entorno():
    """Catálogo simulado, servidor SMTP en memoria y el entorno de correo de la suite."""
    original = rules_client.obtener_documentos_obligatorios
    rules_client.obtener_documentos_obligatorios = _inventario
    servidor = ServidorSmtp().iniciar()
    previas = {v: os.environ.get(v) for v in ("SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS", "SMTP_REMITENTE",
                                               "FRONTEND_URL", "BARRIDO_INTEGRIDAD")}
    os.environ.update({"SMTP_PORT": str(servidor.puerto), "SMTP_STARTTLS": "false",
                       "SMTP_REMITENTE": "motor@example.com", "FRONTEND_URL": "http://interfaz.example.com/",
                       # La base trae documentos de otras suites, con bóvedas que ya no existen.
                       "BARRIDO_INTEGRIDAD": "false"})
    yield servidor
    servidor.detener()
    rules_client.obtener_documentos_obligatorios = original
    for variable, valor in previas.items():
        if valor is None:
            os.environ.pop(variable, None)
        else:
            os.environ[variable] = valor
    bd_pruebas.limpiar_boveda(BOVEDA)


@pytest.fixture
def smtp(entorno):
    """Envío encendido y buzón vacío; con SMTP_HOST vacío el envío queda apagado."""
    entorno.recibidos.clear()
    entorno.rechazar = False
    os.environ["SMTP_HOST"] = "127.0.0.1"
    yield entorno
    notificaciones.esperar_envios()
    os.environ.pop("SMTP_HOST", None)


def _cuenta(rol: str, activo: bool = True) -> tuple[str, str]:
    correo = f"rf20-{rol.lower()}-{uuid.uuid4().hex[:6]}@example.com"
    with SessionLocal() as db:
        u = Usuario(email=correo, nombre_completo=f"Aviso {rol}", rol=rol, activo=activo,
                    password_hash=seguridad.hash_contrasena("Clave-de-pruebas-1"))
        db.add(u)
        db.commit()
        return u.id, correo


def _expediente(*usuario_ids: str) -> dict:
    with SessionLocal() as db:
        t = TitularExpediente(rfc=bd_pruebas.rfc_ficticio("NOT"),
                              razon_social="Avisos de Prueba S.A. de C.V.", tipo_persona="MORAL")
        db.add(t)
        db.commit()
        titular_id = t.id
    r = admin.post("/api/v1/expedientes", json={"titular_id": titular_id, "nombre": "Proveedor con avisos"})
    assert r.status_code == 201, r.text
    exp = r.json()
    if usuario_ids:
        r = admin.put(f"/api/v1/expedientes/{exp['id']}/asignaciones", json={"usuario_ids": list(usuario_ids)})
        assert r.status_code == 200, r.text
    return exp


def _forzar_estado(exp_id: str, estado: str) -> None:
    with SessionLocal() as db:
        db.query(Expediente).filter(Expediente.id == exp_id).update({"estado_cumplimiento": estado})
        db.commit()


def _caer_a_no_conforme(exp_id: str) -> None:
    """Un semáforo guardado en revisión que la consulta recalcula en rojo (faltan obligatorios críticos)."""
    _forzar_estado(exp_id, "EN_REVISION")
    r = admin.get(f"/api/v1/expedientes/{exp_id}")
    assert r.status_code == 200 and r.json()["estado_cumplimiento"] == "NO_CONFORME", r.text
    assert notificaciones.esperar_envios(), "El hilo de envío no terminó"


def _avisos(exp_id: str) -> list[dict]:
    eventos = admin.get("/api/v1/bitacora", params={"expediente_id": exp_id, "evento": "NOTIFICACION_CORREO"})
    assert eventos.status_code == 200, eventos.text
    return [e["detalle"] for e in reversed(eventos.json())]


def _recibidos(servidor: ServidorSmtp, folio: str):
    return [m for m in servidor.recibidos if folio in m.mensaje["Subject"]]


# ── Estatus crítico ─────────────────────────────────────────────

def test_el_paso_a_no_conforme_avisa_solo_a_los_validadores_activos_asignados(smtp):
    validador_id, validador = _cuenta("VALIDADOR")
    inactivo_id, _ = _cuenta("VALIDADOR", activo=False)
    auditor_id, _ = _cuenta("AUDITOR")
    exp = _expediente(validador_id, inactivo_id, auditor_id)
    assert _avisos(exp["id"]) == [], "La apertura no es un cambio a estatus crítico"

    _caer_a_no_conforme(exp["id"])

    [recibido] = _recibidos(smtp, exp["codigo_expediente"])
    assert recibido.destinatarios == [validador] and recibido.mensaje["To"] == validador
    assert recibido.remitente == "motor@example.com"
    cuerpo = recibido.mensaje.get_content()
    assert f"http://interfaz.example.com/#/expedientes/{exp['codigo_expediente']}" in cuerpo
    assert "NO CONFORME" in cuerpo and "Avisos de Prueba S.A. de C.V." in cuerpo
    for codigo in ("RF-", "RN-", "HU-", "NO_CONFORME", "RIE-"):
        assert codigo not in cuerpo, f"El correo debe ir en lenguaje llano: cita «{codigo}»"

    [aviso] = _avisos(exp["id"])
    assert aviso["estado"] == "ENVIADO" and aviso["tipo"] == "ESTATUS_CRITICO"
    assert aviso["destinatarios"] == [validador] and aviso["estado_anterior"] == "EN_REVISION"
    assert aviso["causa"] == "CONSULTA_EXPEDIENTE" and aviso["motivos"]

    # Seguir en rojo no es un cambio: otra consulta no vuelve a avisar.
    admin.get(f"/api/v1/expedientes/{exp['id']}")
    assert notificaciones.esperar_envios() and len(_avisos(exp["id"])) == 1


def test_sin_validadores_asignados_queda_como_sin_destinatarios(smtp):
    auditor_id, _ = _cuenta("AUDITOR")
    exp = _expediente(auditor_id)
    _caer_a_no_conforme(exp["id"])
    [aviso] = _avisos(exp["id"])
    assert aviso["estado"] == "SIN_DESTINATARIOS" and aviso["destinatarios"] == []
    assert _recibidos(smtp, exp["codigo_expediente"]) == []


def test_sin_smtp_host_el_envio_esta_apagado_y_queda_en_la_bitacora(entorno):
    os.environ.pop("SMTP_HOST", None)
    entorno.recibidos.clear()
    validador_id, validador = _cuenta("VALIDADOR")
    exp = _expediente(validador_id)
    _caer_a_no_conforme(exp["id"])
    [aviso] = _avisos(exp["id"])
    assert aviso["estado"] == "ENVIO_DESACTIVADO" and aviso["destinatarios"] == [validador]
    assert entorno.recibidos == []


def test_un_servidor_que_rechaza_deja_el_aviso_como_fallido_sin_afectar_la_peticion(smtp):
    smtp.rechazar = True
    validador_id, _ = _cuenta("VALIDADOR")
    exp = _expediente(validador_id)
    _caer_a_no_conforme(exp["id"])  # la consulta responde 200 aunque el correo falle
    [aviso] = _avisos(exp["id"])
    assert aviso["estado"] == "FALLIDO" and "SMTPRecipientsRefused" in aviso["error"]


def test_una_transaccion_revertida_no_envia_el_aviso(smtp):
    validador_id, _ = _cuenta("VALIDADOR")
    exp = _expediente(validador_id)
    _forzar_estado(exp["id"], "EN_REVISION")
    with SessionLocal() as db:
        expediente = db.get(Expediente, exp["id"])
        assert cumplimiento.reevaluar(db, expediente, causa="CONSULTA_EXPEDIENTE").estado == "NO_CONFORME"
        db.rollback()
    assert notificaciones.esperar_envios()
    assert _recibidos(smtp, exp["codigo_expediente"]) == [] and _avisos(exp["id"]) == []


# ── Documento por vencer (reevaluación programada) ──────────────

def _con_csf_por_vencer(exp_id: str, dias: int) -> str:
    r = admin.post("/api/v1/documentos/upload", data={"expediente_id": exp_id, "tipo_documento": "CSF_SAT"},
                   files={"file": ("csf.pdf", b"%PDF-1.4 csf " + os.urandom(8), "application/pdf")})
    assert r.status_code == 201, r.text
    doc_id = r.json()["id"]
    r = admin.post("/api/v1/dictamenes", headers=auth.sistema(), json={
        "documento_id": doc_id, "estatus": "CONFORME", "nivel_confianza": 0.95,
        "observaciones": ["Prueba automatizada."], "vigencia": VIGENCIA_RCV01,
        "fecha_vencimiento": (date.today() + timedelta(days=dias)).isoformat()})
    assert r.status_code == 201, r.text
    return doc_id


def _vencimientos(exp_id: str) -> list[dict]:
    return [a for a in _avisos(exp_id) if a["tipo"] == "DOCUMENTO_POR_VENCER"]


def test_el_vencimiento_avisa_el_umbral_alcanzado_una_sola_vez(smtp):
    validador_id, validador = _cuenta("VALIDADOR")
    exp = _expediente(validador_id)
    _con_csf_por_vencer(exp["id"], 12)

    reevaluacion_programada.reevaluar_todos()
    assert notificaciones.esperar_envios()
    [aviso] = _vencimientos(exp["id"])
    assert aviso["estado"] == "ENVIADO" and aviso["umbral"] == 15 and aviso["dias_para_vencer"] == 12
    assert aviso["destinatarios"] == [validador]
    [recibido] = [m for m in _recibidos(smtp, exp["codigo_expediente"]) if "vence" in m.mensaje["Subject"]]
    assert "en 12 días" in recibido.mensaje["Subject"] and "csf.pdf" in recibido.mensaje.get_content()

    reevaluacion_programada.reevaluar_todos()
    assert notificaciones.esperar_envios()
    assert len(_vencimientos(exp["id"])) == 1, "El umbral ya avisado no se repite"


def test_un_aviso_de_vencimiento_fallido_se_reintenta_en_el_siguiente_ciclo(smtp):
    validador_id, _ = _cuenta("VALIDADOR")
    exp = _expediente(validador_id)
    _con_csf_por_vencer(exp["id"], 4)

    smtp.rechazar = True
    reevaluacion_programada.reevaluar_todos()
    assert notificaciones.esperar_envios()
    smtp.rechazar = False
    reevaluacion_programada.reevaluar_todos()
    assert notificaciones.esperar_envios()
    reevaluacion_programada.reevaluar_todos()
    assert notificaciones.esperar_envios()
    assert [(a["estado"], a["umbral"]) for a in _vencimientos(exp["id"])] == [("FALLIDO", 5), ("ENVIADO", 5)]


def test_umbral_alcanzado():
    umbrales = (30, 15, 5)
    assert notificaciones.umbral_alcanzado(31, umbrales) is None
    assert notificaciones.umbral_alcanzado(30, umbrales) == 30
    assert notificaciones.umbral_alcanzado(12, umbrales) == 15
    assert notificaciones.umbral_alcanzado(0, umbrales) == 5
    assert notificaciones.umbral_alcanzado(-1, umbrales) is None, "Vencido: lo avisa el estatus crítico"
    assert notificaciones.umbral_alcanzado(None, umbrales) is None
