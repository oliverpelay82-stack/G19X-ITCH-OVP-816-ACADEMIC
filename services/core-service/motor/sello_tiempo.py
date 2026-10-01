"""
Sello de tiempo de un tercero sobre la bitácora (P7, PLUS-22, PRD §21.7).

La cadena sellada (P3) delata una alteración parcial, pero quien administre la
base podría reescribirla completa y recalcular todos los hashes. Un sello de
tiempo RFC 3161 lo impide: una autoridad externa firma, con su reloj, la huella
del último eslabón, y desde ese momento la bitácora no puede reescribirse
hacia atrás sin que el sello deje de coincidir con la cadena.

  * **Solo viaja la huella** (``hash_evento``, SHA-256): ningún dato del
    expediente ni de la bitácora sale del motor.
  * **Apagado por omisión.** Sin ``SELLO_TIEMPO_URL`` no se hace ninguna llamada
    externa: los entornos de prueba y las redes que bloqueen el servicio no se
    ven afectados. Una falla de la autoridad se informa y se reintenta en el
    siguiente ciclo; nunca detiene la reevaluación.
  * Se pide una vez por ciclo de la reevaluación programada (24 h por omisión)
    y a demanda (``POST /api/v1/bitacora/sello-tiempo``). Si el último eslabón
    ya es un SELLO_TIEMPO, no hay nada nuevo que sellar.
  * El token DER se guarda íntegro en ``sellos_tiempo`` (solo inserción) y se
    descarga para verificarlo con ``openssl ts -verify -token_in``. El motor
    comprueba que el sello cubre la huella pedida y el nonce; la firma de la
    autoridad la comprueba openssl con su certificado.

No sustituye la constancia de conservación de un Prestador de Servicios de
Certificación acreditado (NOM-151-SCFI-2016).

El protocolo se codifica con un subconjunto mínimo de DER (sin dependencias
nuevas): la solicitud es fija y de la respuesta solo se leen los campos del
TSTInfo que el motor verifica y guarda.
"""
from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from urllib.parse import urlsplit

import requests
from sqlalchemy.orm import Session

from models.bitacora import EVENTO_SELLO_TIEMPO
from models.sello_tiempo import SelloTiempo
from motor import bitacora

ORIGEN_PROGRAMADO = "PROGRAMADO"
ORIGEN_A_DEMANDA = "A_DEMANDA"

OID_SHA256 = "2.16.840.1.101.3.4.2.1"
OID_SIGNED_DATA = "1.2.840.113549.1.7.2"
OID_TST_INFO = "1.2.840.113549.1.9.16.1.4"

ESTADOS_PKI = {
    0: "concedido", 1: "concedido con modificaciones", 2: "rechazado", 3: "en espera",
    4: "aviso de revocación", 5: "notificación de revocación",
}


class SelloTiempoError(Exception):
    """La autoridad no respondió o su respuesta no es un sello válido sobre la huella pedida."""


class SelloTiempoApagado(SelloTiempoError):
    """``SELLO_TIEMPO_URL`` está vacía: el motor no llama a ningún servicio externo."""


def url() -> str:
    return os.getenv("SELLO_TIEMPO_URL", "").strip()


def activo() -> bool:
    return bool(url())


def timeout() -> float:
    try:
        return max(float(os.getenv("SELLO_TIEMPO_TIMEOUT", "10")), 1.0)
    except ValueError:
        return 10.0


def autoridad(direccion: str) -> str:
    """La dirección de la autoridad sin credenciales ni parámetros (se imprime en los reportes)."""
    partes = urlsplit(direccion)
    return f"{partes.scheme}://{partes.hostname or ''}{f':{partes.port}' if partes.port else ''}{partes.path}"


# ═══════════════════ DER mínimo ═══════════════════

def _longitud(n: int) -> bytes:
    if n < 0x80:
        return bytes([n])
    cuerpo = n.to_bytes((n.bit_length() + 7) // 8, "big")
    return bytes([0x80 | len(cuerpo)]) + cuerpo


def _tlv(etiqueta: int, contenido: bytes) -> bytes:
    return bytes([etiqueta]) + _longitud(len(contenido)) + contenido


def _entero(n: int) -> bytes:
    return _tlv(0x02, n.to_bytes((n.bit_length() + 8) // 8, "big"))


def _oid(punteado: str) -> bytes:
    arcos = [int(a) for a in punteado.split(".")]
    cuerpo = bytearray([40 * arcos[0] + arcos[1]])
    for arco in arcos[2:]:
        grupo = [arco & 0x7F]
        arco >>= 7
        while arco:
            grupo.append(0x80 | (arco & 0x7F))
            arco >>= 7
        cuerpo += bytes(reversed(grupo))
    return _tlv(0x06, bytes(cuerpo))


def _secuencia(*partes: bytes) -> bytes:
    return _tlv(0x30, b"".join(partes))


@dataclass
class _Nodo:
    etiqueta: int
    contenido: bytes
    crudo: bytes          # el TLV completo, tal como llegó


def _leer(datos: bytes, pos: int = 0) -> tuple[_Nodo, int]:
    etiqueta = datos[pos]
    largo = datos[pos + 1]
    inicio = pos + 2
    if largo & 0x80:
        n = largo & 0x7F
        if n == 0 or n > 4:
            raise ValueError("longitud DER no admitida")
        largo = int.from_bytes(datos[inicio:inicio + n], "big")
        inicio += n
    fin = inicio + largo
    if fin > len(datos):
        raise ValueError("DER truncado")
    return _Nodo(etiqueta, datos[inicio:fin], datos[pos:fin]), fin


def _hijos(contenido: bytes) -> list[_Nodo]:
    nodos, pos = [], 0
    while pos < len(contenido):
        nodo, pos = _leer(contenido, pos)
        nodos.append(nodo)
    return nodos


def _esperar(nodo: _Nodo, etiqueta: int, que: str) -> _Nodo:
    if nodo.etiqueta != etiqueta:
        raise ValueError(f"se esperaba {que}")
    return nodo


def _valor_entero(nodo: _Nodo) -> int:
    return int.from_bytes(_esperar(nodo, 0x02, "un INTEGER").contenido, "big", signed=True)


def _valor_oid(nodo: _Nodo) -> str:
    cuerpo = _esperar(nodo, 0x06, "un OID").contenido
    arcos = [cuerpo[0] // 40, cuerpo[0] % 40]
    valor = 0
    for b in cuerpo[1:]:
        valor = (valor << 7) | (b & 0x7F)
        if not b & 0x80:
            arcos.append(valor)
            valor = 0
    return ".".join(str(a) for a in arcos)


def _fecha_generalizada(nodo: _Nodo) -> datetime:
    texto = _esperar(nodo, 0x18, "un GeneralizedTime").contenido.decode("ascii")
    if not texto.endswith("Z"):
        raise ValueError("la fecha del sello no está en UTC")
    base, _, fraccion = texto[:-1].partition(".")
    fecha = datetime.strptime(base, "%Y%m%d%H%M%S")
    return fecha.replace(microsecond=int((fraccion + "000000")[:6])) if fraccion else fecha


# ═══════════════════ Protocolo RFC 3161 ═══════════════════

def solicitud(huella_hex: str, nonce: int) -> bytes:
    """TimeStampReq v1 sobre una huella SHA-256, con nonce y el certificado de la autoridad en el token."""
    imprint = _secuencia(_secuencia(_oid(OID_SHA256), b"\x05\x00"), _tlv(0x04, bytes.fromhex(huella_hex)))
    return _secuencia(_entero(1), imprint, _entero(nonce), b"\x01\x01\xff")


@dataclass
class Sello:
    numero_serie: int
    fecha: datetime                  # genTime en UTC, sin zona
    politica: str
    token_der: bytes


def interpretar_respuesta(der: bytes, huella_hex: str, nonce: int) -> Sello:
    """Lee un TimeStampResp y comprueba que el sello concedido cubre la huella y el nonce pedidos."""
    try:
        respuesta, _ = _leer(der)
        partes = _hijos(_esperar(respuesta, 0x30, "un TimeStampResp").contenido)
        estado = _valor_entero(_hijos(partes[0].contenido)[0])
        if estado not in (0, 1):
            raise SelloTiempoError(f"La autoridad no concedió el sello (estado {estado}: "
                                   f"{ESTADOS_PKI.get(estado, 'desconocido')}).")
        if len(partes) < 2:
            raise ValueError("la respuesta no trae el token")
        token = partes[1]
        info = _hijos(token.contenido)
        if _valor_oid(info[0]) != OID_SIGNED_DATA:
            raise ValueError("el token no es un SignedData")
        firmado = _hijos(_leer(_esperar(info[1], 0xA0, "el contenido del token").contenido)[0].contenido)
        encapsulado = _hijos(_esperar(firmado[2], 0x30, "el contenido encapsulado").contenido)
        if _valor_oid(encapsulado[0]) != OID_TST_INFO:
            raise ValueError("el token no contiene un TSTInfo")
        octetos = _leer(_esperar(encapsulado[1], 0xA0, "el TSTInfo").contenido)[0]
        tst = _hijos(_esperar(_leer(_esperar(octetos, 0x04, "un OCTET STRING").contenido)[0], 0x30,
                              "el TSTInfo").contenido)
        politica = _valor_oid(tst[1])
        algoritmo, hashed = _hijos(tst[2].contenido)
        if _valor_oid(_hijos(algoritmo.contenido)[0]) != OID_SHA256 or hashed.contenido != bytes.fromhex(huella_hex):
            raise SelloTiempoError("El sello recibido no cubre la huella enviada: se descarta.")
        nonce_recibido = next((_valor_entero(n) for n in tst[5:] if n.etiqueta == 0x02), None)
        if nonce_recibido != nonce:
            raise SelloTiempoError("El sello recibido no corresponde a esta solicitud (nonce distinto): se descarta.")
        return Sello(numero_serie=_valor_entero(tst[3]), fecha=_fecha_generalizada(tst[4]),
                     politica=politica, token_der=token.crudo)
    except SelloTiempoError:
        raise
    except (IndexError, ValueError, UnicodeDecodeError) as exc:
        raise SelloTiempoError(f"La respuesta de la autoridad no es un sello de tiempo válido ({exc}).") from exc


def _enviar(direccion: str, cuerpo: bytes) -> bytes:
    """Solo viaja la solicitud con la huella: ni folios internos ni datos del motor."""
    try:
        r = requests.post(direccion, data=cuerpo, headers={"Content-Type": "application/timestamp-query"},
                          timeout=timeout())
    except requests.RequestException as exc:
        raise SelloTiempoError(f"La autoridad de sellado no respondió: {exc}") from exc
    if r.status_code != 200:
        raise SelloTiempoError(f"La autoridad de sellado respondió {r.status_code}.")
    return r.content


# ═══════════════════ Sellado de la bitácora ═══════════════════

def ultimo(db: Session) -> SelloTiempo | None:
    return db.query(SelloTiempo).order_by(SelloTiempo.secuencia.desc(), SelloTiempo.creado_en.desc()).first()


def sellar(db: Session, origen: str) -> tuple[SelloTiempo, bool]:
    """
    Pide el sello del último eslabón y lo guarda con su evento SELLO_TIEMPO, en
    una sola transacción. Devuelve el sello y si es nuevo (False: el último
    eslabón ya era un SELLO_TIEMPO y se devuelve el vigente).
    """
    direccion = url()
    if not direccion:
        raise SelloTiempoApagado("El sello de tiempo está apagado: configure SELLO_TIEMPO_URL con una autoridad RFC 3161.")
    eslabon = bitacora.ultimo_sellado(db)
    if eslabon is None:
        raise SelloTiempoError("La bitácora aún no tiene eventos sellados.")
    vigente = ultimo(db)
    if eslabon.evento == EVENTO_SELLO_TIEMPO and vigente is not None:
        return vigente, False

    nonce = secrets.randbits(63)
    sello = interpretar_respuesta(_enviar(direccion, solicitud(eslabon.hash_evento, nonce)), eslabon.hash_evento, nonce)
    registro = SelloTiempo(
        secuencia=eslabon.secuencia, evento_id=eslabon.id, hash_evento=eslabon.hash_evento,
        autoridad=autoridad(direccion), politica=sello.politica, numero_serie=str(sello.numero_serie),
        fecha_sello=sello.fecha, token_der=sello.token_der, origen=origen,
    )
    db.add(registro)
    db.flush()
    bitacora.registrar(db, EVENTO_SELLO_TIEMPO, detalle={
        "sello_id": registro.id, "secuencia_sellada": registro.secuencia, "hash_evento": registro.hash_evento,
        "autoridad": registro.autoridad, "fecha_sello": registro.fecha_sello.isoformat() + "Z",
        "numero_serie": registro.numero_serie, "politica": registro.politica, "origen": origen,
    })
    db.commit()
    return registro, True


def resumen(s: SelloTiempo, coincide: bool | None = None) -> dict[str, Any]:
    return {
        "id": s.id, "secuencia": s.secuencia, "evento_id": s.evento_id, "hash_evento": s.hash_evento,
        "autoridad": s.autoridad, "politica": s.politica, "numero_serie": s.numero_serie,
        "fecha_sello": s.fecha_sello.isoformat() + "Z", "origen": s.origen, "coincide": coincide,
    }
