"""
Aislamiento de imports entre microservicios para las pruebas de la raíz.

Cada microservicio es autónomo y se ejecuta con su propio directorio como raíz
de imports, por eso todos comparten nombres de primer nivel genéricos
(``main``, ``config``, ``models``, ``controllers``, ``schemas``, ``motor``...).
Cuando pytest recolecta en un solo proceso las pruebas de varios servicios, el
primero que importa ``main`` o ``motor`` deja su módulo en ``sys.modules`` y el
siguiente servicio recibe el ajeno: ``cannot import name 'obligatorios' from
'motor'``, o peor, una prueba de escritura que termina usando la conexión a la
base real que dejó cargada otra prueba.

``activar(servicio)`` deja el intérprete como si solo existiera ese servicio:
retira de ``sys.modules`` los paquetes de primer nivel de TODOS los servicios,
quita del ``sys.path`` los directorios de los demás, antepone el suyo y
restaura las variables de entorno originales (cada servicio lee su ``.env`` sin
sobrescribir lo que ya existe, así que un ``DB_NAME`` que dejó otra suite
—por ejemplo la base de pruebas del core— desviaría su conexión). Los
módulos de prueba ya importados conservan sus propias referencias, así que cada
uno sigue trabajando con los objetos de su servicio.
"""
import os
import sys

RAIZ = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
SERVICIOS_DIR = os.path.join(RAIZ, "services")
SERVICIOS = ("core-service", "rules-service", "ai-service")

# Módulo 7: las pruebas firman y validan las sesiones con su propia clave, nunca con
# la de un .env. Forma parte del entorno original, así que ``activar`` la conserva.
SECRETO_PRUEBAS = "secreto-de-las-pruebas-del-motor-de-validacion"
os.environ["JWT_SECRET"] = SECRETO_PRUEBAS

_ENTORNO_ORIGINAL = dict(os.environ)


def directorio(servicio: str) -> str:
    return os.path.join(SERVICIOS_DIR, servicio)


def _nombres_de_primer_nivel(servicio: str) -> set[str]:
    """Paquetes y módulos importables desde la raíz de un servicio."""
    nombres = set()
    for entrada in os.listdir(directorio(servicio)):
        ruta = os.path.join(directorio(servicio), entrada)
        if entrada.endswith(".py"):
            nombres.add(entrada[:-3])
        elif os.path.isdir(ruta) and entrada.isidentifier() and entrada not in {"tests", "__pycache__"}:
            nombres.add(entrada)
    return nombres


def activar(servicio: str) -> str:
    """Hace importable únicamente ``servicio`` y devuelve su directorio."""
    if servicio not in SERVICIOS:
        raise ValueError(f"Servicio desconocido: {servicio}")

    compartidos = set().union(*(_nombres_de_primer_nivel(s) for s in SERVICIOS))
    for nombre in list(sys.modules):
        if nombre.split(".", 1)[0] in compartidos:
            del sys.modules[nombre]

    ajenos = {os.path.normcase(directorio(s)) for s in SERVICIOS}
    sys.path[:] = [p for p in sys.path if os.path.normcase(os.path.abspath(p or os.curdir)) not in ajenos]
    sys.path.insert(0, directorio(servicio))

    for clave in set(os.environ) - set(_ENTORNO_ORIGINAL):
        del os.environ[clave]
    os.environ.update(_ENTORNO_ORIGINAL)
    return directorio(servicio)
