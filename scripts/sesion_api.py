"""
Sesión de los scripts de prueba (Módulo 7, fase F6; PRD §5.1 y §5.2).

Desde el Módulo 7 toda ruta del core, del rules y del ai-service exige un token
Bearer (salvo la salud y el inicio de sesión). Este módulo es el único lugar donde
los scripts lo obtienen:

  * ``ENTORNO_AISLADO``: lo que reciben los servicios que un script levanta por su
    cuenta (e2e_api.levantar): una clave de sesión propia y las cuentas de
    demostración, sin administrador inicial ni correo.
  * ``sesion(core, rol)``: un ``requests.Session`` con el token de la cuenta de ese
    rol, obtenido con ``POST /auth/login`` como lo hace la interfaz.
  * ``cabeceras_sistema()``: el token SISTEMA del ai-service, el único que puede
    registrar un dictamen (``POST /dictamenes``); se firma con ``JWT_SECRET``.
  * ``nueva_pagina(navegador, core)``: una página de Playwright que ya entra con la
    sesión (la deja en ``sessionStorage`` antes de que cargue la interfaz).

Credenciales. Por omisión, las cuentas de demostración (``USUARIOS_DEMO=true``,
como en el docker-compose de la entrega). Contra servicios locales sin cuentas de
demostración, ``PRUEBAS_EMAIL`` y ``PRUEBAS_CONTRASENA`` dan otra cuenta, que se
usa para cualquier rol pedido.
"""
from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests

RAIZ = Path(__file__).resolve().parent.parent

# Las mismas de services/core-service/motor/usuarios_iniciales.py y del README
# (tests/test_permisos_roles.py comprueba que coinciden).
CUENTAS_DEMO: dict[str, tuple[str, str]] = {
    "ADMIN": ("admin@example.com", "Admin-Demo-2026"),
    "VALIDADOR": ("validador@example.com", "Validador-Demo-2026"),
    "AUDITOR": ("auditor@example.com", "Auditor-Demo-2026"),
    "CONSULTA": ("consulta@example.com", "Consulta-Demo-2026"),
}

# Solo para servicios aislados de las pruebas: nunca es la del .env ni la del compose.
SECRETO_AISLADO = "secreto-de-los-entornos-aislados-de-prueba-del-motor"
ENTORNO_AISLADO = {
    "JWT_SECRET": SECRETO_AISLADO,
    # RNF-04: la bóveda aislada se cifra con su propia llave.
    "BOVEDA_LLAVE": "3c" * 32,
    "USUARIOS_DEMO": "true",
    "ADMIN_INICIAL_EMAIL": "",
    "ADMIN_INICIAL_CONTRASENA": "",
    # RF-20: un SMTP_HOST del .env local mandaría correos reales desde las pruebas.
    "SMTP_HOST": "",
    "CORS_ORIGENES": "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:5174,http://localhost:5174",
}

CLAVE_SESION_NAVEGADOR = "plurione.sesion"  # frontend/src/services/sesion.js
TIMEOUT = 30


def _base(core: str) -> str:
    """Acepta ``http://host:puerto`` o ``http://host:puerto/api/v1``."""
    core = core.rstrip("/")
    return core[: -len("/api/v1")] if core.endswith("/api/v1") else core


def credenciales(rol: str = "ADMIN") -> tuple[str, str]:
    email, contrasena = os.getenv("PRUEBAS_EMAIL", "").strip(), os.getenv("PRUEBAS_CONTRASENA", "")
    if email and contrasena:
        return email, contrasena
    return CUENTAS_DEMO[rol]


_cache: dict[tuple[str, str], dict[str, Any]] = {}


def iniciar_sesion(core: str, rol: str = "ADMIN") -> dict[str, Any]:
    """Respuesta de ``POST /auth/login`` (token, vigencia y perfil); se reutiliza mientras siga vigente."""
    clave = (_base(core), rol)
    guardada = _cache.get(clave)
    if guardada and guardada["_vence"] > time.monotonic() + 60:
        return guardada
    email, contrasena = credenciales(rol)
    r = requests.post(f"{_base(core)}/api/v1/auth/login", json={"email": email, "contrasena": contrasena},
                      timeout=TIMEOUT)
    if r.status_code != 200 or not r.json().get("access_token"):
        raise RuntimeError(
            f"No se pudo iniciar sesión como {email} ({r.status_code}: {r.text[:200]}). Con servicios propios, "
            "active USUARIOS_DEMO=true o defina PRUEBAS_EMAIL y PRUEBAS_CONTRASENA (cuenta sin MFA ni contraseña temporal)."
        )
    datos = r.json()
    if datos["usuario"].get("debe_cambiar_contrasena"):
        raise RuntimeError(f"{email} tiene una contraseña temporal: cámbiela en la interfaz antes de usarla aquí.")
    datos["_vence"] = time.monotonic() + datos["expira_en"]
    _cache[clave] = datos
    return datos


def cabeceras(core: str, rol: str = "ADMIN") -> dict[str, str]:
    return {"Authorization": f"Bearer {iniciar_sesion(core, rol)['access_token']}"}


def sesion(core: str, rol: str = "ADMIN") -> requests.Session:
    """``requests.Session`` que envía el token de la cuenta de ese rol en cada petición."""
    s = requests.Session()
    s.headers.update(cabeceras(core, rol))
    return s


def _seguridad():
    """config/seguridad.py del core (idéntico en los tres servicios); no depende de la base."""
    nombre = "plurione_seguridad_scripts"
    if nombre not in sys.modules:
        ruta = RAIZ / "services" / "core-service" / "config" / "seguridad.py"
        spec = importlib.util.spec_from_file_location(nombre, ruta)
        modulo = importlib.util.module_from_spec(spec)
        sys.modules[nombre] = modulo  # sus dataclasses buscan el módulo aquí al definirse
        spec.loader.exec_module(modulo)
    return sys.modules[nombre]


def cabeceras_sistema(actor: str | None = None, secreto: str | None = None) -> dict[str, str]:
    """
    Token SISTEMA del ai-service (5 min) y, si se da, la persona que pidió la acción.
    Se firma con ``secreto`` o con el ``JWT_SECRET`` del entorno, que debe ser el de
    los servicios.
    """
    previo = os.environ.get("JWT_SECRET")
    if secreto:
        os.environ["JWT_SECRET"] = secreto
    try:
        return _seguridad().cabeceras_sistema("ai-service", actor)
    finally:
        if secreto:
            if previo is None:
                os.environ.pop("JWT_SECRET", None)
            else:
                os.environ["JWT_SECRET"] = previo


def guion_sesion(datos: dict[str, Any]) -> str:
    """Script de arranque que deja la sesión donde la busca la interfaz."""
    valor = {"token": datos["access_token"], "usuario": datos["usuario"]}
    return (f"(() => {{ const s = {json.dumps(valor)}; s.expira = Date.now() + {int(datos['expira_en'])} * 1000;"
            f" sessionStorage.setItem({json.dumps(CLAVE_SESION_NAVEGADOR)}, JSON.stringify(s)); }})()")


def entrar_en_pagina(pagina, core: str, rol: str = "ADMIN") -> None:
    """La página (y sus recargas) arrancan con la sesión ya iniciada."""
    pagina.add_init_script(guion_sesion(iniciar_sesion(core, rol)))


def nueva_pagina(navegador, core: str = "http://127.0.0.1:8001", rol: str = "ADMIN", **opciones):
    pagina = navegador.new_page(**opciones)
    entrar_en_pagina(pagina, core, rol)
    return pagina


def sesion_ficticia(rol: str = "ADMIN") -> dict[str, Any]:
    """
    Sesión sin servidor, para las pruebas que simulan el core caído: la interfaz
    entra con este perfil y sus peticiones fallan como fallarían de verdad.
    """
    email = CUENTAS_DEMO[rol][0]
    return {"access_token": "token-ficticio", "expira_en": 3600, "usuario": {
        "id": "00000000-0000-0000-0000-000000000000", "email": email, "nombre_completo": f"Prueba {rol.title()}",
        "rol": rol, "activo": True, "debe_cambiar_contrasena": False, "mfa_habilitado": False,
        "bloqueado_hasta": None, "ultimo_acceso": None, "creado_en": "2026-01-01T00:00:00"}}
