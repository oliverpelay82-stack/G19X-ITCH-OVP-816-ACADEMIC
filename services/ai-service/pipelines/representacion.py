"""
Datos de representación legal del Nivel 4 — P2 (PRD §21.2): RSC-02, HU-23, HU-37.

En la MISMA llamada de extracción del Nivel 4, el modelo devuelve además:

  * de un contrato o NDA con una regla RSC-02 activa, los **firmantes**
    (nombre, cargo y empresa que representan);
  * de un poder notarial o un acta constitutiva, los **apoderados** o
    representantes (nombre, cargo y facultades).

Como en la verificación de contenido, el modelo solo transcribe: cada persona
trae la cita del renglón donde aparece, la cita se ancla en el texto
(``verificacion_contenido.cita_literal``) y además debe contener el nombre. Si
no, la persona queda ``cita_verificada = False``: se muestra al analista, pero
no prueba nada por sí sola. El cotejo firmante-apoderado (RN-03) no se hace
aquí: lo calcula el core-service en cada evaluación del expediente, con los
datos de los dictámenes de ambos documentos.
"""
from __future__ import annotations

from typing import Any

from pipelines import verificacion_contenido

PREFIJO_RSC_02 = "RSC-02"
TIPOS_ACREDITANTES = frozenset({"PODER_NOTARIAL", "ACTA_CONSTITUTIVA"})

FIRMANTES = "FIRMANTES"
APODERADOS = "APODERADOS"

# Máximo de personas por documento: acota los tokens de salida (GROQ_MAX_TOKENS).
MAX_PERSONAS = 8

# Términos que el BM25 suma a la consulta de la auditoría para que el modelo
# vea el bloque de firmas del contrato o el de facultades del poder o del acta.
CONSULTA = {
    FIRMANTES: "firma firmas por la parte representada por su representante legal apoderado comparece "
               "en su carácter de director general administrador único",
    APODERADOS: "otorga poder general apoderado facultades pleitos y cobranzas actos de administración "
                "actos de dominio administrador único consejo de administración presidente representante legal",
}


def es_regla_rsc_02(criterio: dict[str, Any]) -> bool:
    return str(criterio.get("codigo_regla", "")).upper().startswith(PREFIJO_RSC_02)


def rol_de(tipo_registrado: str | None, criterios: list[dict[str, Any]]) -> str | None:
    """Qué datos de representación pide la auditoría de este documento, si pide alguno."""
    if any(es_regla_rsc_02(c) for c in criterios):
        return FIRMANTES
    if (tipo_registrado or "").upper() in TIPOS_ACREDITANTES:
        return APODERADOS
    return None


def instrucciones(rol: str | None) -> str:
    """Campos adicionales del objeto JSON de la extracción (vacío si el documento no los necesita)."""
    if rol == FIRMANTES:
        return (
            '  "firmantes": [{"nombre": "nombre completo de la persona física que firma", '
            '"cargo": "su cargo o carácter (representante legal, apoderado, director general…) o null", '
            '"empresa": "razón social de la parte a la que representa, o null", '
            '"cita": "transcripción literal y breve del renglón del documento donde aparece su nombre"}],\n'
        )
    if rol == APODERADOS:
        return (
            '  "apoderados": [{"nombre": "nombre completo de la persona física con facultades de representación", '
            '"cargo": "apoderado, administrador único, presidente del consejo… o null", '
            '"facultades": "resumen breve: pleitos y cobranzas, actos de administración, actos de dominio… o null", '
            '"cita": "transcripción literal y breve del renglón del documento donde se le nombra"}],\n'
        )
    return ""


def nota(rol: str | None) -> str:
    """Instrucción que acompaña a los campos adicionales en el prompt."""
    if rol is None:
        return ""
    quien = "quienes firman el documento" if rol == FIRMANTES else "a quienes se confieren facultades de representación"
    return (
        f"\nIdentifica también a {quien}: solo personas físicas cuyo nombre aparezca en el texto, como máximo "
        f"{MAX_PERSONAS}. Si no aparece ninguna, devuelve la lista vacía. La cita es una transcripción LITERAL "
        "del renglón donde aparece el nombre, sin corregirla ni completarla."
    )


def _texto(valor: Any) -> str | None:
    return " ".join(valor.split()) if isinstance(valor, str) and valor.strip() else None


def nombre_en_cita(nombre: str, cita: str) -> bool:
    """Cada palabra del nombre (de 3 letras o más) aparece en la cita, salvo acentos, signos y espacios."""
    compacta = verificacion_contenido.compactar(cita)
    palabras = [p for p in verificacion_contenido.compactar_palabras(nombre) if len(p) >= 3]
    return bool(palabras) and all(p in compacta for p in palabras)


def procesar(rol: str | None, crudo: dict[str, Any], texto: str) -> dict[str, Any] | None:
    """Personas extraídas por el modelo, con su cita anclada en el texto del documento."""
    if rol is None:
        return None
    clave = "firmantes" if rol == FIRMANTES else "apoderados"
    personas: list[dict[str, Any]] = []
    vistos: set[str] = set()
    for p in crudo.get(clave) or []:
        if not isinstance(p, dict):
            continue
        nombre = _texto(p.get("nombre"))
        if not nombre or len(nombre) < 5:
            continue
        llave = verificacion_contenido.compactar(nombre)
        if llave in vistos:
            continue
        vistos.add(llave)
        cita_modelo = _texto(p.get("cita"))
        anclada = verificacion_contenido.cita_literal(cita_modelo, texto)
        verificada = bool(anclada and nombre_en_cita(nombre, anclada[0]))
        persona = {
            "nombre": nombre,
            "cargo": _texto(p.get("cargo")),
            "cita": anclada[0] if verificada else cita_modelo,
            "cita_verificada": verificada,
        }
        if rol == FIRMANTES:
            persona["empresa"] = _texto(p.get("empresa"))
        else:
            persona["facultades"] = _texto(p.get("facultades"))
        personas.append(persona)
        if len(personas) >= MAX_PERSONAS:
            break
    return {"rol": rol, "personas": personas}


def verificacion(criterio: dict[str, Any], datos: dict[str, Any] | None) -> dict[str, Any]:
    """Resultado de la regla RSC-02 del catálogo: si se identificó al firmante con una cita verificable."""
    personas = (datos or {}).get("personas") or []
    verificadas = [p for p in personas if p["cita_verificada"]]
    if verificadas:
        resultado = verificacion_contenido.CUMPLE
        descripcion = "; ".join(
            p["nombre"] + (f" ({', '.join(x for x in (p.get('cargo'), p.get('empresa')) if x)})"
                           if p.get("cargo") or p.get("empresa") else "")
            for p in verificadas
        )
        observacion = (f"Firmantes identificados: {descripcion}. La representación la confirma el analista contra "
                       "el poder notarial o el acta del expediente (RN-03).")
        cita = verificadas[0]["cita"]
    elif personas:
        resultado = verificacion_contenido.NO_VERIFICABLE
        observacion = ("El modelo identificó firmantes, pero su cita no aparece en el documento; deben confirmarse "
                       "manualmente.")
        cita = None
    else:
        resultado = verificacion_contenido.NO_LOCALIZADO
        observacion = "No se identificó en el texto a la persona que firma el documento."
        cita = None
    return {
        "codigo_regla": criterio["codigo_regla"],
        "nombre_regla": criterio["nombre_regla"],
        "familia_regla": criterio["familia_regla"],
        "severidad": criterio["severidad"],
        "resultado": resultado,
        "cita": cita,
        "observacion": observacion,
        "recomendacion": criterio["recomendacion"],
    }
