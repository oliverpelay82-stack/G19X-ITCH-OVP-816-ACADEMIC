"""
Verificación del contenido de un documento contra las reglas RSC y RDS del
catálogo (DOC-05: RSC-01 cláusulas esenciales, RDS-02 criterios en lenguaje
natural definidos por el usuario).

Cada regla describe un elemento que el documento debe contener —la inscripción
en el Registro Público de un acta, la cláusula de penalización de un contrato—
y la recomendación que procede si falta. El modelo localiza cada elemento y
transcribe la cita que lo sustenta; el resultado lo decide código determinista:

  * CUMPLE          el modelo lo localizó y la cita aparece literalmente en el texto.
                    Si el modelo corrigió al transcribir un error de reconocimiento
                    («MORALES» donde el OCR leyó «MORALE»), la cita se ancla al
                    pasaje del documento y se guarda tal como está en él; las cifras
                    deben coincidir exactamente (``cita_literal``).
  * NO_LOCALIZADO   el modelo no lo encontró en el texto.
  * NO_VERIFICABLE  el modelo dice que cumple, pero su cita no está en el texto
                    (posible alucinación), o no pudo decidirlo.

Una omisión no rechaza el documento: es una «Omisión Contractual Relevante»
(RSC-01, semáforo amarillo) que resuelve el analista en el Nivel 5, igual que
las reglas dinámicas (RDS-03).

Excepción: las reglas de ``DETERMINISTAS`` se evalúan con código y sin el
modelo, porque verifican un hecho que el documento declara en un formato fijo.
Solo ellas producen NO_CUMPLE —el documento afirma lo contrario de lo exigido,
con su cita—, que sí deja el dictamen NO_CONFORME. Hoy es RSC-OPIN-SENT: una
opinión de cumplimiento 32-D en sentido negativo (PLUS-03).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from functools import lru_cache
from typing import Any

from clients import groq_client
from clients.groq_client import GroqNoDisponibleError, GroqRespuestaInvalidaError
from config import settings
from pipelines import fragmentos, opinion_cumplimiento

CUMPLE = "CUMPLE"
NO_LOCALIZADO = "NO_LOCALIZADO"
NO_VERIFICABLE = "NO_VERIFICABLE"
NO_CUMPLE = "NO_CUMPLE"

# Una cita más corta no prueba nada: cualquier palabra suelta aparece en el texto.
MIN_CARACTERES_CITA = 12
# Semejanza mínima para anclar una cita que difiere del texto solo por errores
# de reconocimiento (una letra de más o de menos). Por debajo, la diferencia ya
# no es del OCR sino de redacción: una paráfrasis no se acepta como cita.
UMBRAL_CITA_OCR = 0.93

SYSTEM_PROMPT = (
    "Eres un auditor documental de expedientes corporativos mexicanos. Verificas si un "
    "documento contiene elementos concretos. El texto puede venir de un reconocimiento "
    "óptico con errores menores; interprétalo pese al ruido.\n"
    "Reglas inviolables:\n"
    "1. Un elemento se da por presente solo si el texto lo contiene de forma explícita.\n"
    "2. La cita es una transcripción LITERAL y breve (una frase, máximo 200 caracteres) del "
    "fragmento que prueba el elemento. No la parafrasees ni la completes.\n"
    "3. Si el elemento no aparece, marca cumple en false y cita en null. Si el texto no "
    "permite decidir, marca cumple en null.\n"
    "4. Las leyendas de sellos registrales o notariales (por ejemplo, «INSCRITO EN EL REGISTRO "
    "PÚBLICO…») son evidencia del elemento aunque sus datos manuscritos (folio, fecha) no sean "
    "legibles en el texto: cita la leyenda y anota en la observación qué dato no se pudo leer.\n"
    "5. Respondes exclusivamente con un objeto JSON válido, sin texto adicional."
)


@dataclass
class ResultadoVerificacion:
    disponible: bool
    verificaciones: list[dict[str, Any]] = field(default_factory=list)
    nota: str | None = None
    uso_tokens: dict[str, Any] | None = None

    @property
    def pendientes(self) -> list[dict[str, Any]]:
        """Elementos que un analista debe confirmar (no localizados o no verificados)."""
        return [v for v in self.verificaciones if v["resultado"] in (NO_LOCALIZADO, NO_VERIFICABLE)]

    @property
    def incumplidos(self) -> list[dict[str, Any]]:
        """Elementos que el documento contradice de forma explícita (solo reglas deterministas)."""
        return [v for v in self.verificaciones if v["resultado"] == NO_CUMPLE]

    @property
    def incluye_reglas_dinamicas(self) -> bool:
        return any(v["familia_regla"] == "RDS" for v in self.verificaciones)


# Puntos suspensivos con los que el modelo une fragmentos de una misma cita.
_ELIPSIS = re.compile(r"\[?(?:\.{3,}|…)\]?")


def _normalizar(texto: str) -> str:
    """Minúsculas sin acentos ni signos, con los espacios colapsados: tolera saltos de renglón y OCR."""
    sin_acentos = unicodedata.normalize("NFKD", texto)
    sin_acentos = "".join(c for c in sin_acentos if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", sin_acentos.lower())).strip()


def compactar(texto: str) -> str:
    """Letras y cifras normalizadas, sin espacios: la forma en que se comparan las citas."""
    return _normalizar(texto).replace(" ", "")


def fragmentos_de_cita(cita: str) -> list[tuple[str, list[str]]]:
    """Cada fragmento de una cita unida con puntos suspensivos: (forma compacta, palabras normalizadas)."""
    fragmentos = []
    for parte in _ELIPSIS.split(cita):
        normalizada = _normalizar(parte)
        if normalizada:
            fragmentos.append((normalizada.replace(" ", ""), normalizada.split()))
    return fragmentos


def partes_de_cita(cita: str) -> list[str]:
    """Fragmentos compactados de una cita que el modelo unió con puntos suspensivos."""
    return [compacta for compacta, _ in fragmentos_de_cita(cita)]


@lru_cache(maxsize=8)
def _mapa_compacto(texto: str) -> tuple[str, tuple[int, ...]]:
    """Forma compacta del texto y, por cada carácter, su posición en el original."""
    caracteres: list[str] = []
    posiciones: list[int] = []
    for i, c in enumerate(texto):
        for d in unicodedata.normalize("NFKD", c.lower()):
            if not unicodedata.combining(d) and (d.isalnum() or d == "_"):
                caracteres.append(d)
                posiciones.append(i)
    return "".join(caracteres), tuple(posiciones)


def _cifras(texto: str) -> str:
    return "".join(c for c in texto if c.isdigit())


def _anclar(parte: str, compacto: str) -> tuple[int, int, bool] | None:
    """
    Tramo (inicio, fin, ajustado) del texto compacto que corresponde a la parte
    de una cita: exacto, o el más parecido por encima de ``UMBRAL_CITA_OCR`` con
    las mismas cifras. Se buscan anclas de 10 caracteres al inicio, al centro y
    al final de la parte; basta con que una no tenga errores de OCR.
    """
    inicio = compacto.find(parte)
    if inicio >= 0:
        return inicio, inicio + len(parte), False
    if len(parte) < MIN_CARACTERES_CITA:
        return None
    ancla = 10
    mejor: tuple[float, int, int] | None = None
    desplazamientos = sorted({0, max(0, len(parte) // 2 - ancla // 2), max(0, len(parte) - ancla)})
    for desplazamiento in desplazamientos:
        semilla = parte[desplazamiento:desplazamiento + ancla]
        k, vistos = compacto.find(semilla), 0
        while k >= 0 and vistos < 40:
            vistos += 1
            base = max(0, k - desplazamiento - 4)
            ventana = compacto[base:k - desplazamiento + len(parte) + 4]
            bloques = [b for b in SequenceMatcher(None, parte, ventana, autojunk=False).get_matching_blocks() if b.size]
            if bloques:
                coincidentes = sum(b.size for b in bloques)
                ini, fin = base + bloques[0].b, base + bloques[-1].b + bloques[-1].size
                puntaje = 2 * coincidentes / (len(parte) + (fin - ini))
                if (mejor is None or puntaje > mejor[0]) and _cifras(parte) == _cifras(compacto[ini:fin]):
                    mejor = (puntaje, ini, fin)
            k = compacto.find(semilla, k + 1)
    if mejor and mejor[0] >= UMBRAL_CITA_OCR:
        return mejor[1], mejor[2], True
    return None


def cita_literal(cita: str | None, texto: str) -> tuple[str, bool] | None:
    """
    El pasaje del documento que sustenta la cita, tal como está escrito en él,
    y si hubo que ajustarlo (``True`` cuando el modelo corrigió errores de OCR
    al transcribir). ``None`` si alguna parte no aparece: posible alucinación o
    paráfrasis. Las partes unidas con «...» se devuelven unidas con « … ».
    """
    if not cita:
        return None
    partes = partes_de_cita(cita)
    if not partes or max(len(p) for p in partes) < MIN_CARACTERES_CITA:
        return None
    compacto, posiciones = _mapa_compacto(texto)
    pasajes, ajustada = [], False
    for parte in partes:
        tramo = _anclar(parte, compacto)
        if tramo is None:
            return None
        ini, fin, ajustado = tramo
        ajustada = ajustada or ajustado
        pasajes.append(" ".join(texto[posiciones[ini]:posiciones[fin - 1] + 1].split()))
    return " … ".join(pasajes), ajustada


def cita_en_texto(cita: str | None, texto: str) -> bool:
    """
    La cita aparece literalmente en el texto (salvo acentos, signos y espacios).
    Se comparan las letras y cifras sin espacios porque el OCR parte palabras
    («SIET E» por «SIETE»): la secuencia de caracteres debe seguir siendo la misma.
    Una cita que une fragmentos con puntos suspensivos se acepta solo si cada
    fragmento aparece literalmente.
    """
    if not cita:
        return False
    partes = partes_de_cita(cita)
    if not partes or max(len(p) for p in partes) < MIN_CARACTERES_CITA:
        return False
    compacto = compactar(texto)
    return all(p in compacto for p in partes)


def _prompt(texto: str, criterios: list[dict[str, Any]]) -> str:
    lista = "\n".join(f'  - "{c["codigo_regla"]}": {c["criterio"]}' for c in criterios)
    return f"""Verifica si el documento contiene cada uno de estos elementos:
{lista}

=== TEXTO DEL DOCUMENTO ===
{texto}
=== FIN DEL TEXTO ===

Devuelve EXACTAMENTE este objeto JSON, con una entrada por cada código de la lista:

{{
  "verificaciones": [
    {{"codigo_regla": "el código de la lista", "cumple": true, "cita": "transcripción literal o null", "observacion": "una frase en español"}}
  ]
}}"""


def _verificacion(criterio: dict[str, Any], resultado: str, cita: str | None, observacion: str) -> dict[str, Any]:
    return {
        "codigo_regla": criterio["codigo_regla"],
        "nombre_regla": criterio["nombre_regla"],
        "familia_regla": criterio["familia_regla"],
        "severidad": criterio["severidad"],
        "resultado": resultado,
        "cita": cita,
        "observacion": observacion,
        "recomendacion": None if resultado == CUMPLE else criterio["recomendacion"],
    }


def _sentido_opinion(texto: str, criterio: dict[str, Any]) -> dict[str, Any]:
    """RSC-OPIN-SENT: el sentido de la opinión 32-D, leído del texto sin el modelo (PLUS-03)."""
    sentido = opinion_cumplimiento.leer_sentido(texto)
    if sentido.valor == opinion_cumplimiento.POSITIVO:
        return _verificacion(criterio, CUMPLE, sentido.cita, "La opinión se emitió en sentido positivo.")
    if sentido.valor == opinion_cumplimiento.NEGATIVO:
        return _verificacion(criterio, NO_CUMPLE, sentido.cita,
                             "La opinión de cumplimiento se emitió en sentido NEGATIVO: el contribuyente no está al "
                             "corriente de sus obligaciones fiscales.")
    if sentido.valor == opinion_cumplimiento.AMBIGUO:
        return _verificacion(criterio, NO_VERIFICABLE, sentido.cita,
                             "El texto declara más de un sentido; un analista debe confirmar cuál es el de la opinión.")
    if sentido.valor in (opinion_cumplimiento.SIN_OBLIGACIONES, opinion_cumplimiento.NO_INSCRITO):
        leyenda = "inscrito sin obligaciones" if sentido.valor == opinion_cumplimiento.SIN_OBLIGACIONES else "no inscrito"
        return _verificacion(criterio, NO_VERIFICABLE, sentido.cita,
                             f"La opinión declara «{leyenda}», no un sentido positivo; un analista debe decidir si "
                             "basta para el expediente.")
    return _verificacion(criterio, NO_LOCALIZADO, None,
                         "No se localizó en el texto la declaración del sentido de la opinión.")


# Reglas que se verifican con código y sin el modelo: código de regla -> evaluador.
DETERMINISTAS = {opinion_cumplimiento.CODIGO_REGLA: _sentido_opinion}


def verificar(texto: str, criterios: list[dict[str, Any]], paginas: list[dict] | None = None) -> ResultadoVerificacion:
    """
    Localiza en el texto los elementos que exigen las reglas RSC y RDS del tipo
    de documento. El contexto se arma con los mejores fragmentos de cada
    criterio por separado (``fragmentos.seleccionar_por_criterios``), dentro de
    ``MAX_CARACTERES_VERIFICACION``: el límite de tokens por minuto de Groq se
    comparte con la extracción de la misma auditoría.
    """
    if not criterios:
        return ResultadoVerificacion(disponible=True)

    locales = {
        c["codigo_regla"].upper(): DETERMINISTAS[c["codigo_regla"].upper()](texto, c)
        for c in criterios if c["codigo_regla"].upper() in DETERMINISTAS
    }
    para_modelo = [c for c in criterios if c["codigo_regla"].upper() not in locales]
    if not para_modelo:
        return ResultadoVerificacion(disponible=True, verificaciones=[locales[c["codigo_regla"].upper()] for c in criterios])

    consultas = [f"{c['nombre_regla']} {c['criterio']}" for c in para_modelo]
    seleccion = fragmentos.seleccionar_por_criterios(
        texto, consultas, presupuesto=settings.MAX_CARACTERES_VERIFICACION, paginas=paginas
    )
    try:
        crudo = groq_client.generar_json(prompt=_prompt(seleccion.texto, para_modelo), system=SYSTEM_PROMPT)
    except (GroqNoDisponibleError, GroqRespuestaInvalidaError) as exc:
        # Lo verificado sin el modelo sigue valiendo: una opinión negativa no
        # debe pasar inadvertida porque Groq no respondió.
        return ResultadoVerificacion(
            disponible=False,
            verificaciones=list(locales.values()),
            nota=f"La verificación de contenido no pudo completarse ({exc.__class__.__name__}); "
                 "los elementos del documento deben revisarse manualmente.",
        )

    respuestas = {}
    for v in crudo.get("verificaciones") or []:
        if isinstance(v, dict) and v.get("codigo_regla"):
            respuestas[str(v["codigo_regla"]).strip().upper()] = v

    verificaciones = []
    for criterio in criterios:
        if criterio["codigo_regla"].upper() in locales:
            verificaciones.append(locales[criterio["codigo_regla"].upper()])
            continue
        v = respuestas.get(criterio["codigo_regla"].upper(), {})
        cita = v.get("cita") if isinstance(v.get("cita"), str) and v.get("cita").strip() else None
        observacion = str(v.get("observacion") or "").strip()
        anclada = cita_literal(cita, texto) if v.get("cumple") is True else None
        if anclada:
            resultado = CUMPLE
            cita, ajustada = anclada
            if ajustada:
                observacion = (f"{observacion} La cita se tomó del texto del documento: el modelo corrigió "
                               "errores de reconocimiento al transcribirla.").strip()
        elif v.get("cumple") is False:
            resultado = NO_LOCALIZADO
        else:
            resultado = NO_VERIFICABLE
            if v.get("cumple") is True:
                observacion = ("El modelo lo reporta presente, pero su cita no aparece literalmente en el "
                               "documento; debe confirmarse manualmente.")
            elif not v:
                observacion = "El modelo no evaluó este elemento."
        verificaciones.append(_verificacion(criterio, resultado, cita if resultado == CUMPLE else None, observacion))
    return ResultadoVerificacion(disponible=True, verificaciones=verificaciones, uso_tokens=groq_client.uso_de(crudo))
