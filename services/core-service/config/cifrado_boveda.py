"""
RNF-04 — Cifrado AES-256 de la bóveda en reposo.

Cada archivo se cifra con AES-256-GCM y un nonce aleatorio propio. Formato:

    PLVC1 | id de la llave (8 bytes) | nonce (12 bytes) | cifrado con su etiqueta (16 bytes)

La huella SHA-256 registrada sigue siendo la del original (RF-03): se cifra
después de calcularla y se descifra antes de verificarla (RIE-03).

El id de la llave (los 8 primeros bytes del SHA-256 de la llave) separa dos
casos que GCM no distingue por sí solo: una llave equivocada o ausente es un
error de configuración (``LlaveBovedaError``) y no debe marcar como ALTERADO un
documento sano; con la llave correcta, una etiqueta que no verifica sí es una
alteración del archivo (``ArchivoCifradoAlteradoError``).

Sin ``BOVEDA_LLAVE`` los archivos se guardan en claro y ``/health`` lo
advierte. Los archivos que ya estaban en claro se siguen leyendo; los cifra
``scripts/cifrar_boveda.py``. Solo depende de ``cryptography``, para que
``scripts/respaldo.py`` pueda cargarlo sin el resto del core.
"""
from __future__ import annotations

import hashlib
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

CABECERA = b"PLVC1"
_LARGO_ID = 8
_LARGO_NONCE = 12
_INICIO_CIFRADO = len(CABECERA) + _LARGO_ID + _LARGO_NONCE
_LARGO_ETIQUETA = 16

# Llave que trae el docker-compose de la entrega para que la bóveda se cifre con
# un solo comando; /health del core advierte mientras siga en uso.
LLAVE_DEMOSTRACION = "5a1f0c7e3b9d2468ace013579bdf2468ace013579bdf2468ace013579bdf2468"


class LlaveBovedaError(RuntimeError):
    """BOVEDA_LLAVE inválida, ausente o distinta de la que cifró el archivo (error de configuración)."""


class ArchivoCifradoAlteradoError(ValueError):
    """Con la llave correcta, la etiqueta GCM no verifica: el archivo cifrado fue modificado."""


def _llave() -> bytes | None:
    valor = os.getenv("BOVEDA_LLAVE", "").strip()
    if not valor:
        return None
    try:
        llave = bytes.fromhex(valor)
    except ValueError:
        llave = b""
    if len(llave) != 32:
        raise LlaveBovedaError(
            "BOVEDA_LLAVE debe tener 64 caracteres hexadecimales (32 bytes, AES-256). "
            'Genere una con: python -c "import secrets; print(secrets.token_hex(32))"'
        )
    return llave


def _id_llave(llave: bytes) -> bytes:
    return hashlib.sha256(llave).digest()[:_LARGO_ID]


def verificar_configuracion() -> None:
    """Se llama al arrancar: una BOVEDA_LLAVE mal formada no deja levantar el servicio."""
    _llave()


def activo() -> bool:
    return _llave() is not None


def usa_llave_demostracion() -> bool:
    return os.getenv("BOVEDA_LLAVE", "").strip().lower() == LLAVE_DEMOSTRACION


def esta_cifrado(datos: bytes) -> bool:
    return datos.startswith(CABECERA)


def cifrar(original: bytes) -> bytes:
    """Lo que se escribe en la bóveda: cifrado si hay llave, el original si no."""
    llave = _llave()
    if llave is None:
        return original
    encabezado = CABECERA + _id_llave(llave)
    nonce = os.urandom(_LARGO_NONCE)
    # El encabezado va como dato asociado: cambiar el id de la llave también rompe la etiqueta.
    return encabezado + nonce + AESGCM(llave).encrypt(nonce, original, encabezado)


def descifrar(almacenado: bytes) -> bytes:
    """El original de un archivo de la bóveda (un archivo en claro se devuelve tal cual)."""
    if not esta_cifrado(almacenado):
        return almacenado
    if len(almacenado) < _INICIO_CIFRADO + _LARGO_ETIQUETA:
        raise ArchivoCifradoAlteradoError("El archivo cifrado está truncado: fue modificado.")
    llave = _llave()
    if llave is None:
        raise LlaveBovedaError(
            "El archivo de la bóveda está cifrado y falta BOVEDA_LLAVE: defina la llave con que se cifró."
        )
    encabezado = almacenado[: len(CABECERA) + _LARGO_ID]
    if encabezado[len(CABECERA):] != _id_llave(llave):
        raise LlaveBovedaError(
            "El archivo de la bóveda se cifró con otra llave: BOVEDA_LLAVE no es la que se usó al custodiarlo."
        )
    nonce = almacenado[len(encabezado):_INICIO_CIFRADO]
    try:
        return AESGCM(llave).decrypt(nonce, almacenado[_INICIO_CIFRADO:], encabezado)
    except InvalidTag as exc:
        raise ArchivoCifradoAlteradoError(
            "El archivo cifrado no supera la verificación de autenticidad (AES-GCM): fue modificado."
        ) from exc
