"""
Huella de las instrucciones al modelo (P5, dictamen reproducible; protocolo de
auditoría del DOC-05).

Junto con ``version_lectura()`` del Nivel 3, permite explicar por qué dos
dictámenes del mismo archivo difieren: si cambió la lectura, las instrucciones
o ninguna de las dos. Se calcula de las instrucciones del sistema y de las
plantillas que arman cada petición (análisis, verificación de contenido y
representación legal), así que cambia sola cuando cambia cualquiera de ellas.
"""
import hashlib
import inspect
from functools import lru_cache

from pipelines import analisis_semantico, representacion, verificacion_contenido


@lru_cache(maxsize=1)
def version_instrucciones() -> str:
    partes = (
        analisis_semantico.SYSTEM_PROMPT,
        inspect.getsource(analisis_semantico._plantilla_prompt),
        verificacion_contenido.SYSTEM_PROMPT,
        inspect.getsource(verificacion_contenido._prompt),
        inspect.getsource(representacion.instrucciones),
    )
    return "inst-" + hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()[:12]
