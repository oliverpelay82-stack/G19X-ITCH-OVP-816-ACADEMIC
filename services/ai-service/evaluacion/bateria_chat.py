"""
Batería de pruebas del chat documental (docs/VALIDACION_CUANTITATIVA.md §6.2).

30 preguntas sobre 6 documentos del Gold Standard (5 por documento) y 2
conversaciones de 4 turnos. Cada pregunta lleva su categoría, la ruta que se
prevé para ella tras P4 y su respuesta esperada, escrita antes de ejecutar:

  * ``contiene``: grupos de alternativas; la respuesta acierta si contiene al
    menos una alternativa de cada grupo (comparación sin acentos, mayúsculas,
    negritas ni espacios repetidos).
  * ``ausente``: la respuesta debe decir que el dato no aparece en el documento.

Las alternativas cubren las formas razonables de escribir el mismo dato (fecha
en ISO, en palabras o en números; cifra con o sin separadores); no premian una
redacción concreta.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

SUGERIDA, FACTUAL, LOCALIZACION, INTERPRETATIVA, AUSENTE = (
    "SUGERIDA", "FACTUAL", "LOCALIZACION", "INTERPRETATIVA", "AUSENTE")
DOCUMENTOS = ("GS-CONT-01", "GS-CONT-03", "GS-ACTA-01-ESC", "GS-PODER-01", "GS-CSF-01", "GS-OPIN-01")


def fecha(iso: str) -> list[str]:
    """Formas aceptadas de una fecha: ISO, en palabras y dd/mm/aaaa."""
    from evaluacion.gold_standard import en_letra, en_numeros
    return [iso, en_letra(iso), en_numeros(iso)]


@dataclass
class Pregunta:
    documento: str
    pregunta: str
    categoria: str
    ruta_prevista: str
    contiene: list[list[str]] = field(default_factory=list)
    ausente: bool = False


# Preguntas sueltas: cada una se hace con el historial vacío.
PREGUNTAS: list[Pregunta] = [
    # Contrato completo
    Pregunta("GS-CONT-01", "¿Qué le falta a este documento?", SUGERIDA, "T0",
             [["no le falta", "no falta", "completo", "contiene todas", "firmante", "apoderad", "facultades"]]),
    Pregunta("GS-CONT-01", "¿Quiénes firman el contrato?", FACTUAL, "T0",
             [["maria elena ruiz soto"], ["jorge alberto trevino garza"]]),
    Pregunta("GS-CONT-01", "¿Cuál es el monto de la contraprestación?", LOCALIZACION, "T1",
             [["185,000", "185000", "185 000", "ciento ochenta y cinco mil"]]),
    Pregunta("GS-CONT-01", "¿Qué dice la cláusula de penalización?", LOCALIZACION, "T1",
             [["diez por ciento", "10 %", "10%"]]),
    Pregunta("GS-CONT-01", "¿Puede el cliente terminar el contrato antes de tiempo?", INTERPRETATIVA, "MODELO",
             [["treinta dias", "30 dias"]]),
    # Contrato sin penalización
    Pregunta("GS-CONT-03", "¿Qué le falta a este documento?", SUGERIDA, "T0", [["penaliz", "pena convencional"]]),
    Pregunta("GS-CONT-03", "¿Qué recomiendas corregir?", SUGERIDA, "T0", [["penaliz", "pena convencional"]]),
    Pregunta("GS-CONT-03", "¿Cuándo vence este documento?", SUGERIDA, "T0", [fecha("2027-03-01")]),
    Pregunta("GS-CONT-03", "¿Qué pena convencional se pactó por incumplimiento?", AUSENTE, "MODELO", ausente=True),
    Pregunta("GS-CONT-03", "¿Cuál es el RFC del prestador?", FACTUAL, "T0", [["sin150302kl7"]]),
    # Acta constitutiva escaneada
    Pregunta("GS-ACTA-01-ESC", "Resume los datos clave de este archivo", SUGERIDA, "T0",
             [["plurione"], ["2018", "12,845", "12845"]]),
    Pregunta("GS-ACTA-01-ESC", "¿Quién es el administrador único?", FACTUAL, "T0", [["hector daniel quiroga salas"]]),
    Pregunta("GS-ACTA-01-ESC", "¿Cuál es el folio mercantil de inscripción?", LOCALIZACION, "T1", [["48213"]]),
    Pregunta("GS-ACTA-01-ESC", "¿Cuál es el capital social?", LOCALIZACION, "T1",
             [["50,000", "50000", "50 000", "cincuenta mil"]]),
    Pregunta("GS-ACTA-01-ESC", "¿La apoderada puede firmar contratos en nombre de la sociedad?", INTERPRETATIVA,
             "MODELO", [["actos de administracion", "administracion"]]),
    # Poder notarial
    Pregunta("GS-PODER-01", "¿Quién es el apoderado?", FACTUAL, "T0", [["maria elena ruiz soto"]]),
    Pregunta("GS-PODER-01", "¿Ante qué notario se otorgó el poder?", FACTUAL, "T0", [["ernesto valdivia cortes"]]),
    Pregunta("GS-PODER-01", "¿Cuándo vence este documento?", SUGERIDA, "MODELO",
             [["indefinid", "no vence", "no tiene fecha de vencimiento", "no declara", "no establece", "no senala"]]),
    Pregunta("GS-PODER-01", "¿Qué número de escritura tiene el poder?", LOCALIZACION, "T1", [["20,117", "20117"]]),
    Pregunta("GS-PODER-01", "¿El apoderado puede vender inmuebles de la empresa?", INTERPRETATIVA, "MODELO",
             [["dominio"]]),
    # Constancia de situación fiscal
    Pregunta("GS-CSF-01", "¿Cuál es el RFC del contribuyente?", FACTUAL, "T0", [["plu180514ab3"]]),
    Pregunta("GS-CSF-01", "¿Cuál es la razón social?", FACTUAL, "T0", [["plurione"]]),
    Pregunta("GS-CSF-01", "¿Cuál es la fecha de emisión?", FACTUAL, "T0", [fecha("2026-09-10")]),
    Pregunta("GS-CSF-01", "¿Cuándo vence este documento?", SUGERIDA, "T0",
             [fecha("2026-12-09") + ["90 dias", "noventa dias"]]),
    Pregunta("GS-CSF-01", "¿Cuál es la CLABE bancaria del contribuyente?", AUSENTE, "MODELO", ausente=True),
    # Opinión de cumplimiento 32-D
    Pregunta("GS-OPIN-01", "¿Cuál es el sentido de la opinión?", FACTUAL, "T0", [["positiv"]]),
    Pregunta("GS-OPIN-01", "¿Cuál es el folio de la opinión?", FACTUAL, "T0", [["26na4471902"]]),
    Pregunta("GS-OPIN-01", "Resume los datos clave de este archivo", SUGERIDA, "T0",
             [["positiv"], ["plu180514ab3", "plurione"]]),
    Pregunta("GS-OPIN-01", "¿Con base en qué artículo se emite la opinión?", LOCALIZACION, "T1", [["32-d", "32 d"]]),
    Pregunta("GS-OPIN-01", "¿Sigue vigente esta opinión para un trámite hoy?", INTERPRETATIVA, "MODELO",
             [["vigente", "30 dias", "treinta dias"]]),
]

# Conversaciones: el historial se acumula como lo hace Chat.jsx.
CONVERSACIONES: list[list[Pregunta]] = [
    [
        Pregunta("GS-CONT-01", "¿Quién es el prestador del servicio?", FACTUAL, "T0",
                 [["servicios integrales del norte"]]),
        Pregunta("GS-CONT-01", "¿y quién lo firma?", FACTUAL, "T0", [["jorge alberto trevino garza"]]),
        Pregunta("GS-CONT-01", "¿con qué cargo?", FACTUAL, "MODELO", [["representante legal"]]),
        Pregunta("GS-CONT-01", "¿hasta cuándo está vigente el contrato?", FACTUAL, "T0", [fecha("2027-03-01")]),
    ],
    [
        Pregunta("GS-ACTA-01-ESC", "¿Quiénes son los socios?", FACTUAL, "MODELO", [["hector"], ["laura"]]),
        Pregunta("GS-ACTA-01-ESC", "¿cuántas acciones tiene cada uno?", LOCALIZACION, "MODELO", [["250"]]),
        Pregunta("GS-ACTA-01-ESC", "¿quién es el comisario?", FACTUAL, "MODELO", [["ana sofia beltran ruelas"]]),
        Pregunta("GS-ACTA-01-ESC", "¿y el domicilio de la sociedad?", FACTUAL, "MODELO", [["chihuahua"]]),
    ],
]

# Batería del documento extenso (contrato marco de 20 páginas, escaneado): los datos
# están repartidos en todo el texto, así que el contexto del chat llega a su tope.
DOCUMENTOS_EXTENSOS = ("GS-CONT-EXT-ESC",)
PREGUNTAS_EXTENSAS: list[Pregunta] = [
    Pregunta("GS-CONT-EXT-ESC", "¿Qué le falta a este documento?", SUGERIDA, "T0",
             [["no le falta", "no falta", "completo", "contiene todas", "firmante", "apoderad", "facultades"]]),
    Pregunta("GS-CONT-EXT-ESC", "Resume los datos clave de este archivo", SUGERIDA, "T0",
             [["plurione"], ["servicios integrales del norte"]]),
    Pregunta("GS-CONT-EXT-ESC", "¿Quiénes firman el contrato?", FACTUAL, "T0",
             [["maria elena ruiz soto"], ["jorge alberto trevino garza"]]),
    Pregunta("GS-CONT-EXT-ESC", "¿Hasta cuándo está vigente el contrato?", FACTUAL, "T0", [fecha("2027-03-01")]),
    Pregunta("GS-CONT-EXT-ESC", "¿Cuál es el monto mensual total de los servicios?", LOCALIZACION, "T1",
             [["185,000", "185000", "185 000", "ciento ochenta y cinco mil"]]),
    Pregunta("GS-CONT-EXT-ESC", "¿Cuál es el tiempo de respuesta de la mesa de ayuda para un incidente de "
             "prioridad crítica?", LOCALIZACION, "T1", [["15 minutos", "quince minutos"]]),
    Pregunta("GS-CONT-EXT-ESC", "¿Qué deductiva se aplica si la disponibilidad de los servidores baja del 99.5 %?",
             LOCALIZACION, "T1", [["cinco por ciento", "5 %", "5%"]]),
    Pregunta("GS-CONT-EXT-ESC", "¿Puede el prestador subcontratar los servicios?", INTERPRETATIVA, "MODELO",
             [["autorizacion"]]),
]

# Cuántos mensajes previos manda Chat.jsx (MAX_TURNOS_HISTORIAL).
TURNOS_HISTORIAL_FRONTEND = 6

_AUSENCIA = re.compile(
    r"no (aparece|se localiz|se encontr|se encuentra|contiene|incluye|se menciona|se indica|se establece|"
    r"se especifica|se pacto|hay|consta|figura|esta disponible|viene)"
)


def normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).replace("**", "").lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", texto).strip()


def acierta(respuesta: str, pregunta: Pregunta) -> bool:
    texto = normalizar(respuesta)
    if pregunta.ausente:
        return bool(_AUSENCIA.search(texto))
    return all(any(normalizar(alternativa) in texto for alternativa in grupo) for grupo in pregunta.contiene)


def variante_escrita(pregunta: Pregunta) -> Pregunta:
    """La misma pregunta como la teclearía otro analista: sin acentos, mayúsculas ni signos."""
    # Solo los signos de interrogación y exclamación: el punto y la coma de una cifra (99.5 %) son parte del dato.
    texto = re.sub(r"[¿?¡!]", "", normalizar(pregunta.pregunta)).strip()
    return Pregunta(pregunta.documento, texto, pregunta.categoria, pregunta.ruta_prevista, pregunta.contiene,
                    pregunta.ausente)


def total_turnos() -> int:
    return len(PREGUNTAS) + sum(len(c) for c in CONVERSACIONES)
