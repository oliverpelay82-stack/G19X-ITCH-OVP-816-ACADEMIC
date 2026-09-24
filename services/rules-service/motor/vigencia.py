"""
Evaluador determinista de las reglas Cronológicas y de Vigencia (familia RCV, DOC-05).

El DOC-05 define dos criterios temporales distintos, y este módulo los aplica a
partir de las reglas activas del catálogo:

  * **Vigencia mandatoria (RCV-01).** Regla general (sin tipo de documento):
    mide los días que faltan para la *fecha de vencimiento* del documento.
    Negativo: vencido. Entre 0 y ``dias_maximos_vigencia`` (30): próximo a
    vencer. Mayor: vigente.

  * **Caducidad estricta de documentos con vigencia legal fija.** Regla ligada
    a un tipo de documento: mide la antigüedad desde la *fecha de emisión*.
    Si supera ``dias_maximos_vigencia``, el documento está vencido aunque no
    declare fecha de vencimiento. Es el caso del comprobante de domicilio
    fiscal (RCV-02), que el DOC-02 exige «no mayor a 3 meses» y el DOC-08
    formaliza como la regla de los 90 días naturales. El límite es inclusivo:
    un documento con exactamente 90 días de antigüedad sigue vigente.

El módulo no toca la base de datos ni la red: recibe las reglas y las fechas y
devuelve el dictamen, de modo que el mismo documento evaluado en la misma
fecha de referencia produce siempre el mismo resultado (trazabilidad, DOC-05).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterable, Protocol

VIGENTE = "VIGENTE"
PROXIMO_A_VENCER = "PROXIMO_A_VENCER"
VENCIDO = "VENCIDO"
INDETERMINADO = "INDETERMINADO"   # la regla aplica, pero faltan datos para resolverla
NO_APLICA = "NO_APLICA"           # la regla no tiene nada que evaluar en este documento
SIN_REGLAS = "SIN_REGLAS"         # ninguna regla de vigencia activa cubre el documento

CRITERIO_ANTIGUEDAD = "ANTIGUEDAD_DESDE_EMISION"
CRITERIO_VENCIMIENTO = "DIAS_PARA_VENCIMIENTO"

# Del peor al mejor: el resultado global es el más grave de las reglas evaluadas.
_GRAVEDAD = [VENCIDO, INDETERMINADO, PROXIMO_A_VENCER, VIGENTE]


class ReglaVigencia(Protocol):
    codigo_regla: str
    nombre_regla: str
    familia_regla: str
    severidad: str
    tipo_documento: str | None
    dias_maximos_vigencia: int | None
    activo: bool


@dataclass
class EvaluacionRegla:
    codigo_regla: str
    nombre_regla: str
    severidad: str
    criterio: str
    resultado: str
    limite_dias: int
    dias_calculados: int | None
    detalle: str


@dataclass
class ResultadoVigencia:
    tipo_documento: str
    fecha_referencia: date
    resultado: str
    es_vigente: bool | None
    dias_calculados: int | None
    evaluaciones: list[EvaluacionRegla] = field(default_factory=list)


def _caducidad(regla: ReglaVigencia, emision: date | None, referencia: date) -> EvaluacionRegla:
    limite = regla.dias_maximos_vigencia
    base = dict(codigo_regla=regla.codigo_regla, nombre_regla=regla.nombre_regla, severidad=regla.severidad,
                criterio=CRITERIO_ANTIGUEDAD, limite_dias=limite)
    if emision is None:
        return EvaluacionRegla(**base, resultado=INDETERMINADO, dias_calculados=None,
                               detalle="El documento no declara fecha de emisión: la antigüedad no puede "
                                       "verificarse y el caso se turna a revisión humana.")
    dias = (referencia - emision).days
    if dias < 0:
        return EvaluacionRegla(**base, resultado=INDETERMINADO, dias_calculados=dias,
                               detalle=f"La fecha de emisión ({emision.isoformat()}) es posterior a la fecha "
                                       f"de referencia ({referencia.isoformat()}); se requiere revisión humana.")
    if dias > limite:
        return EvaluacionRegla(**base, resultado=VENCIDO, dias_calculados=dias,
                               detalle=f"El documento tiene {dias} días naturales de antigüedad; el máximo "
                                       f"permitido es {limite} días.")
    return EvaluacionRegla(**base, resultado=VIGENTE, dias_calculados=dias,
                           detalle=f"El documento tiene {dias} días naturales de antigüedad, dentro del máximo "
                                   f"de {limite} días (le quedan {limite - dias}).")


def _mandatoria(regla: ReglaVigencia, vencimiento: date | None, referencia: date) -> EvaluacionRegla:
    limite = regla.dias_maximos_vigencia
    base = dict(codigo_regla=regla.codigo_regla, nombre_regla=regla.nombre_regla, severidad=regla.severidad,
                criterio=CRITERIO_VENCIMIENTO, limite_dias=limite)
    if vencimiento is None:
        return EvaluacionRegla(**base, resultado=NO_APLICA, dias_calculados=None,
                               detalle="El documento no declara fecha de vencimiento.")
    dias = (vencimiento - referencia).days
    if dias < 0:
        return EvaluacionRegla(**base, resultado=VENCIDO, dias_calculados=dias,
                               detalle=f"El documento venció hace {abs(dias)} días ({vencimiento.isoformat()}).")
    if dias <= limite:
        return EvaluacionRegla(**base, resultado=PROXIMO_A_VENCER, dias_calculados=dias,
                               detalle=f"El documento vence en {dias} días ({vencimiento.isoformat()}).")
    return EvaluacionRegla(**base, resultado=VIGENTE, dias_calculados=dias,
                           detalle=f"El documento vence en {dias} días ({vencimiento.isoformat()}).")


def evaluar(
    reglas: Iterable[ReglaVigencia],
    tipo_documento: str,
    fecha_emision: date | None,
    fecha_vencimiento: date | None,
    fecha_referencia: date,
) -> ResultadoVigencia:
    """Aplica las reglas RCV activas que cubren el tipo de documento y consolida el dictamen."""
    tipo = tipo_documento.strip().upper()
    evaluaciones: list[EvaluacionRegla] = []
    for regla in reglas:
        if not regla.activo or regla.familia_regla != "RCV" or regla.dias_maximos_vigencia is None:
            continue
        if regla.tipo_documento and regla.tipo_documento.upper() == tipo:
            evaluaciones.append(_caducidad(regla, fecha_emision, fecha_referencia))
        elif not regla.tipo_documento:
            evaluaciones.append(_mandatoria(regla, fecha_vencimiento, fecha_referencia))

    resueltas = [e for e in evaluaciones if e.resultado != NO_APLICA]
    if not resueltas:
        return ResultadoVigencia(tipo, fecha_referencia, SIN_REGLAS, None, None, evaluaciones)

    resultado = min((e.resultado for e in resueltas), key=_GRAVEDAD.index)
    es_vigente = {VENCIDO: False, INDETERMINADO: None}.get(resultado, True)
    # Como en la tabla de dictámenes del DOC-08: días transcurridos entre la emisión y la validación.
    antiguedad = next((e.dias_calculados for e in resueltas if e.criterio == CRITERIO_ANTIGUEDAD), None)
    return ResultadoVigencia(tipo, fecha_referencia, resultado, es_vigente, antiguedad, evaluaciones)
