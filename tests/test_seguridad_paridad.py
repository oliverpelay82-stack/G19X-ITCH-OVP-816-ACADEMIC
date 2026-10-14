"""
Módulo 7 (PRD §5.2): ``config/seguridad.py`` es el mismo archivo en los tres
servicios. Cada uno se construye en su propio contexto de Docker, así que no
pueden compartir un paquete; si una copia cambia sin las otras, un servicio
firmaría o validaría las sesiones distinto (roles, algoritmo, vigencia del token
SISTEMA). Para cambiarlo: editar una copia y copiarla a las otras dos.
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import servicios  # noqa: E402


def test_seguridad_es_identico_en_los_tres_servicios():
    huellas = {}
    for servicio in servicios.SERVICIOS:
        with open(os.path.join(servicios.directorio(servicio), "config", "seguridad.py"), "rb") as archivo:
            # Sin distinguir finales de línea: Git puede escribirlos como CRLF en Windows.
            huellas[servicio] = hashlib.sha256(archivo.read().replace(b"\r\n", b"\n")).hexdigest()
    assert len(set(huellas.values())) == 1, f"Las copias de config/seguridad.py difieren: {huellas}"
