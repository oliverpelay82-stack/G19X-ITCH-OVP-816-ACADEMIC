"""
Segundo factor TOTP del Módulo 7 (RF-25; PRD §5.2; docs/uml/m7-actividad-mfa.puml).

Códigos de 6 dígitos que cambian cada 30 s (RFC 6238), compatibles con Google
Authenticator, Microsoft Authenticator y similares. Se acepta el código del
intervalo vigente y el de cada intervalo vecino (±30 s) por la diferencia de reloj
entre el teléfono y el servidor.

Vive en el core y no en config/seguridad.py: ese archivo es idéntico en los tres
servicios y solo el core guarda cuentas.
"""
from __future__ import annotations

import re

import pyotp

EMISOR = "Motor de Validación"
VENTANA = 1  # intervalos de 30 s aceptados antes y después del vigente
_CODIGO = re.compile(r"^\d{6}$")


def nuevo_secreto() -> str:
    """Secreto aleatorio en base32 (160 bits), el formato de las apps autenticadoras."""
    return pyotp.random_base32(32)


def uri(secreto: str, correo: str) -> str:
    """URI otpauth:// que la app lee del código QR (o el usuario escribe con el secreto)."""
    return pyotp.TOTP(secreto).provisioning_uri(name=correo, issuer_name=EMISOR)


def codigo_valido(secreto: str | None, codigo: str | None) -> bool:
    if not secreto or not codigo:
        return False
    codigo = codigo.strip().replace(" ", "")
    return bool(_CODIGO.match(codigo)) and pyotp.TOTP(secreto).verify(codigo, valid_window=VENTANA)
