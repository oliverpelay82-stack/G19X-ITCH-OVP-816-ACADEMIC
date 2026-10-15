"""
Notificaciones por correo electrónico (RF-20, HU-17; PRD §5.2, fase F5 del Módulo 7).

Dos avisos, a los usuarios activos con rol VALIDADOR asignados al expediente
(HU-31, tabla ``expediente_asignaciones``):

  * **Estatus crítico:** el semáforo pasa de otro estado a NO_CONFORME
    (``cumplimiento.sincronizar``). La apertura no avisa: todo expediente nuevo
    nace sin documentos y, por eso, en rojo.
  * **Documento por vencer:** en la reevaluación programada, un documento alcanza un
    umbral de anticipación (RF-17, HU-14; por omisión 30, 15 o 5 días, motor/umbrales.py).
    Se avisa solo el umbral más cercano que alcanzó: un servicio detenido varios días
    no manda tres correos atrasados.

Cada aviso deja un evento NOTIFICACION_CORREO en la bitácora (RF-27) con su estado:
SIN_DESTINATARIOS y ENVIO_DESACTIVADO (sin ``SMTP_HOST``) en la misma transacción
que lo originó; ENVIADO o FALLIDO desde el hilo de envío, después de hablar con el
servidor. El aviso de un umbral no se repite: cuenta como dado con cualquier estado
salvo FALLIDO, que se reintenta en la siguiente reevaluación programada.

El envío nunca retrasa la petición: el mensaje se encola cuando la transacción se
confirma (un rollback lo descarta) y lo despacha un hilo propio con ``smtplib``.
"""
from __future__ import annotations

import os
import queue
import smtplib
import ssl
import threading
from dataclasses import dataclass, field
from email import policy
from email.message import EmailMessage
from typing import Any, Iterable
from urllib.parse import quote

from sqlalchemy import event
from sqlalchemy.orm import Session

from config import seguridad
from config.catalogo import etiqueta_documento
from config.database import SessionLocal
from models.bitacora import EVENTO_NOTIFICACION_CORREO, BitacoraAuditoria
from models.expediente import Expediente
from models.usuario import ExpedienteAsignacion, Usuario
from motor import bitacora
from motor.redaccion import dias, fecha_legible, texto_llano

TIPO_ESTATUS_CRITICO = "ESTATUS_CRITICO"
TIPO_DOCUMENTO_POR_VENCER = "DOCUMENTO_POR_VENCER"

ESTADO_ENVIADO = "ENVIADO"
ESTADO_FALLIDO = "FALLIDO"
ESTADO_SIN_DESTINATARIOS = "SIN_DESTINATARIOS"
ESTADO_ENVIO_DESACTIVADO = "ENVIO_DESACTIVADO"

# Causas de sincronización que no son un cambio a estatus crítico.
CAUSAS_SIN_AVISO = frozenset({"APERTURA_EXPEDIENTE"})

ASUNTO_PREFIJO = "Motor de Validación"
# Plegar las cabeceras a 78 columnas parte el asunto con acentos en palabras codificadas
# que se leen con espacios de más («vence en 12   días»); 998 es el límite de RFC 5322.
_POLITICA = policy.SMTP.clone(max_line_length=998)
_CLAVE_PENDIENTES = "rf20_correos_pendientes"


# ── Configuración (se lee en cada aviso: el .env puede cambiar sin reiniciar las pruebas) ──

@dataclass(frozen=True)
class ConfiguracionSmtp:
    host: str
    puerto: int
    usuario: str
    contrasena: str
    remitente: str
    starttls: bool
    timeout: float


def configuracion() -> ConfiguracionSmtp | None:
    """La del .env, o ``None`` si ``SMTP_HOST`` está vacío (envío apagado)."""
    host = os.getenv("SMTP_HOST", "").strip()
    if not host:
        return None
    try:
        puerto = int(os.getenv("SMTP_PORT", "587"))
    except ValueError:
        puerto = 587
    try:
        timeout = float(os.getenv("SMTP_TIMEOUT_SEGUNDOS", "15"))
    except ValueError:
        timeout = 15.0
    usuario = os.getenv("SMTP_USUARIO", "").strip()
    return ConfiguracionSmtp(
        host=host,
        puerto=puerto,
        usuario=usuario,
        contrasena=os.getenv("SMTP_CONTRASENA", ""),
        remitente=os.getenv("SMTP_REMITENTE", "").strip() or usuario or f"motor@{host}",
        starttls=os.getenv("SMTP_STARTTLS", "true").strip().lower() not in ("false", "0", "no"),
        timeout=timeout,
    )


def enlace_expediente(folio: str) -> str:
    base = os.getenv("FRONTEND_URL", "http://localhost:5173").strip().rstrip("/")
    return f"{base}/#/expedientes/{quote(folio)}"


# ── Aviso ──────────────────────────────────────────────────────────

@dataclass
class Aviso:
    tipo: str
    expediente_id: str
    asunto: str
    cuerpo: str
    destinatarios: list[str]
    documento_id: str | None = None
    detalle: dict[str, Any] = field(default_factory=dict)

    def clave(self) -> tuple:
        """Identidad del aviso de un umbral, para no encolarlo dos veces antes de su evento."""
        return (self.tipo, self.documento_id, self.detalle.get("umbral"), self.detalle.get("fecha_caducidad"))


def destinatarios(db: Session, expediente_id: str) -> list[str]:
    """Correos de los VALIDADOR activos asignados al expediente (HU-31), en orden."""
    filas = (
        db.query(Usuario.email)
        .join(ExpedienteAsignacion, ExpedienteAsignacion.usuario_id == Usuario.id)
        .filter(ExpedienteAsignacion.expediente_id == expediente_id,
                Usuario.activo.is_(True), Usuario.rol == seguridad.VALIDADOR)
        .order_by(Usuario.email)
        .all()
    )
    return [email for (email,) in filas]


def _encabezado(expediente: Expediente) -> str:
    titular = getattr(expediente.titular, "razon_social", None)
    nombre = expediente.nombre or "sin nombre"
    return f"Expediente {expediente.codigo_expediente} ({nombre}{', ' + titular if titular else ''})"


def _pie(expediente: Expediente) -> str:
    return (
        f"\nAbrir el expediente: {enlace_expediente(expediente.codigo_expediente)}\n\n"
        "Recibe este aviso porque tiene asignado el expediente como validador. "
        "Es un mensaje automático del Motor de Validación de Cumplimiento Documental; no lo responda.\n"
    )


def avisar_estatus_critico(
    db: Session,
    expediente: Expediente,
    *,
    estado_anterior: str | None,
    motivos: Iterable[str],
    causa: str,
) -> None:
    """El semáforo pasó a NO CONFORME. No confirma la transacción."""
    if causa in CAUSAS_SIN_AVISO:
        return
    motivos = [m for m in (texto_llano(x) for x in motivos) if m]
    lista = "\n".join(f"  • {m}" for m in motivos) or "  • Consulte el detalle del expediente."
    asunto = f"{ASUNTO_PREFIJO}: el expediente {expediente.codigo_expediente} pasó a no conforme"
    cuerpo = (
        f"{_encabezado(expediente)}\n\n"
        "El expediente pasó a NO CONFORME (semáforo en rojo). Motivos:\n"
        f"{lista}\n"
        f"{_pie(expediente)}"
    )
    _procesar(db, Aviso(
        tipo=TIPO_ESTATUS_CRITICO, expediente_id=expediente.id, asunto=asunto, cuerpo=cuerpo,
        destinatarios=destinatarios(db, expediente.id),
        detalle={"causa": causa, "estado_anterior": estado_anterior, "motivos": motivos},
    ))


def umbral_alcanzado(dias_restantes: int | None, umbrales: Iterable[int]) -> int | None:
    """El umbral más cercano que ya alcanzó un documento vigente (12 días con 30/15/5 → 15)."""
    if dias_restantes is None or dias_restantes < 0:
        return None
    alcanzados = [u for u in umbrales if dias_restantes <= u]
    return min(alcanzados) if alcanzados else None


def _ya_avisado(db: Session, documento_id: str, umbral: int, fecha_caducidad: str) -> bool:
    eventos = (
        db.query(BitacoraAuditoria.detalle)
        .filter(BitacoraAuditoria.evento == EVENTO_NOTIFICACION_CORREO,
                BitacoraAuditoria.documento_id == documento_id)
        .all()
    )
    for (detalle,) in eventos:
        d = detalle or {}
        if (d.get("tipo") == TIPO_DOCUMENTO_POR_VENCER and d.get("umbral") == umbral
                and d.get("fecha_caducidad") == fecha_caducidad and d.get("estado") != ESTADO_FALLIDO):
            return True
    return False


def avisar_vencimientos(db: Session, expediente: Expediente, documentos: Iterable[Any], umbrales: Iterable[int]) -> int:
    """
    Reevaluación programada: un aviso por documento que alcanzó un umbral sin aviso
    previo. ``documentos`` son los ``EstadoDocumento`` de la evaluación. Devuelve
    cuántos avisos se registraron o encolaron. No confirma la transacción.
    """
    umbrales = tuple(umbrales)
    avisos = 0
    correos: list[str] | None = None
    for doc in documentos:
        umbral = umbral_alcanzado(doc.dias_para_vencer, umbrales)
        if umbral is None or doc.fecha_caducidad is None:
            continue
        fecha = doc.fecha_caducidad.isoformat()
        aviso_clave = (TIPO_DOCUMENTO_POR_VENCER, doc.documento_id, umbral, fecha)
        if aviso_clave in _despachador.en_vuelo() or _ya_avisado(db, doc.documento_id, umbral, fecha):
            continue
        if correos is None:
            correos = destinatarios(db, expediente.id)
        nombre = etiqueta_documento(doc.tipo_documento)
        restantes = "hoy" if doc.dias_para_vencer == 0 else f"en {dias(doc.dias_para_vencer)}"
        asunto = f"{ASUNTO_PREFIJO}: {nombre} del expediente {expediente.codigo_expediente} vence {restantes}"
        cuerpo = (
            f"{_encabezado(expediente)}\n\n"
            f"El documento «{doc.nombre_archivo_original}» ({nombre}) vence el "
            f"{fecha_legible(doc.fecha_caducidad)}, {restantes}.\n"
            "Inicie su renovación para que el expediente no pase a no conforme.\n"
            f"{_pie(expediente)}"
        )
        _procesar(db, Aviso(
            tipo=TIPO_DOCUMENTO_POR_VENCER, expediente_id=expediente.id, documento_id=doc.documento_id,
            asunto=asunto, cuerpo=cuerpo, destinatarios=list(correos),
            detalle={"umbral": umbral, "dias_para_vencer": doc.dias_para_vencer, "fecha_caducidad": fecha,
                     "tipo_documento": doc.tipo_documento},
        ))
        avisos += 1
    return avisos


def _registrar(db: Session, aviso: Aviso, estado: str, error: str | None = None) -> None:
    detalle = {"tipo": aviso.tipo, "estado": estado, "destinatarios": aviso.destinatarios,
               "asunto": aviso.asunto, **aviso.detalle}
    if error:
        detalle["error"] = error
    bitacora.registrar(db, EVENTO_NOTIFICACION_CORREO, expediente_id=aviso.expediente_id,
                       documento_id=aviso.documento_id, detalle=detalle)


def _procesar(db: Session, aviso: Aviso) -> None:
    if not aviso.destinatarios:
        _registrar(db, aviso, ESTADO_SIN_DESTINATARIOS)
    elif configuracion() is None:
        _registrar(db, aviso, ESTADO_ENVIO_DESACTIVADO)
    else:
        # Se envía solo si la transacción se confirma (ver _al_confirmar).
        db.info.setdefault(_CLAVE_PENDIENTES, []).append(aviso)


@event.listens_for(SessionLocal, "after_commit")
def _al_confirmar(db: Session) -> None:
    for aviso in db.info.pop(_CLAVE_PENDIENTES, []):
        _despachador.encolar(aviso)


@event.listens_for(SessionLocal, "after_rollback")
def _al_revertir(db: Session) -> None:
    db.info.pop(_CLAVE_PENDIENTES, None)


# ── Envío ──────────────────────────────────────────────────────────

def mensaje(aviso: Aviso, config: ConfiguracionSmtp) -> EmailMessage:
    correo = EmailMessage(policy=_POLITICA)
    correo["Subject"] = aviso.asunto
    correo["From"] = config.remitente
    correo["To"] = ", ".join(aviso.destinatarios)
    correo.set_content(aviso.cuerpo)
    return correo


def enviar(aviso: Aviso, config: ConfiguracionSmtp) -> None:
    """Entrega el mensaje al servidor SMTP; cualquier rechazo o falla de red se propaga."""
    with smtplib.SMTP(config.host, config.puerto, timeout=config.timeout) as smtp:
        if config.starttls:
            smtp.starttls(context=ssl.create_default_context())
        if config.usuario:
            smtp.login(config.usuario, config.contrasena)
        smtp.send_message(mensaje(aviso, config))


class _Despachador:
    """Un hilo de envío por proceso; los avisos se atienden en orden de llegada."""

    def __init__(self) -> None:
        self._cola: queue.Queue[Aviso] = queue.Queue()
        self._en_vuelo: set[tuple] = set()
        self._candado = threading.Lock()
        self._hilo: threading.Thread | None = None

    def en_vuelo(self) -> set[tuple]:
        with self._candado:
            return set(self._en_vuelo)

    def encolar(self, aviso: Aviso) -> None:
        with self._candado:
            self._en_vuelo.add(aviso.clave())
            if self._hilo is None or not self._hilo.is_alive():
                self._hilo = threading.Thread(target=self._atender, name="correo-rf20", daemon=True)
                self._hilo.start()
        self._cola.put(aviso)

    def esperar(self, timeout: float = 10.0) -> bool:
        """Espera a que se atiendan los avisos encolados (pruebas). True si terminaron."""
        hecho = threading.Event()
        threading.Thread(target=lambda: (self._cola.join(), hecho.set()), daemon=True).start()
        return hecho.wait(timeout)

    def _atender(self) -> None:
        while True:
            aviso = self._cola.get()
            try:
                self._despachar(aviso)
            finally:
                with self._candado:
                    self._en_vuelo.discard(aviso.clave())
                self._cola.task_done()

    @staticmethod
    def _despachar(aviso: Aviso) -> None:
        config = configuracion()
        estado, error = ESTADO_ENVIADO, None
        try:
            if config is None:
                estado = ESTADO_ENVIO_DESACTIVADO
            else:
                enviar(aviso, config)
        except (smtplib.SMTPException, OSError) as exc:
            # El texto del error nunca incluye la contraseña: smtplib no la repite.
            estado, error = ESTADO_FALLIDO, f"{type(exc).__name__}: {exc}"[:300]
        db = SessionLocal()
        try:
            _registrar(db, aviso, estado, error)
            db.commit()
        except Exception as exc:  # el hilo no debe morir: el siguiente aviso sigue su curso
            db.rollback()
            print(f"[core-service] No se registró el aviso por correo en la bitácora: {exc}")
        finally:
            db.close()


_despachador = _Despachador()


def esperar_envios(timeout: float = 10.0) -> bool:
    return _despachador.esperar(timeout)
