"""
Selección de fragmentos relevantes para el Nivel 4 (recuperación léxica BM25).

El modelo solo admite ``MAX_CARACTERES_CONTEXTO`` caracteres por consulta. En un
documento extenso —un acta constitutiva de 26 páginas rinde más de 130,000—
enviar ciegamente el inicio deja fuera las cláusulas que suelen estar al final:
capital social, acciones, comisario, facultades y firmas. Este módulo arma el
contexto con el **encabezado** del documento (identidad, fedatario, fecha) más
los **fragmentos que mejor responden a la consulta**, en orden de aparición.

Método:
  * El texto se corta en ventanas de ~``FRAGMENTO_CARACTERES`` caracteres sobre
    límites de renglón, con un traslape de ~20 % para que una cláusula partida
    entre dos ventanas aparezca completa en alguna.
  * Cada ventana se puntúa con BM25 contra la consulta, tras normalizar acentos,
    descartar palabras vacías y aplicar un stemming ligero en español
    ("acciones" y "acción" cuentan como el mismo término).
  * Las frases de dos palabras de la consulta ("capital social") suman un bono
    cuando aparecen juntas en la ventana.

Es deliberadamente léxico: no requiere modelos de embeddings ni dependencias
nuevas, es determinista (misma consulta, mismo contexto: auditable) y funciona
sobre texto de OCR con erratas, porque basta con que los términos clave se
reconozcan en alguna aparición.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass, field

from config import settings

_STOPWORDS = frozenset(
    """a al algo ante antes asi aun bajo cada como con contra cual cuales cuando de del desde donde dos
    el ella ellas ellos en entre era es esa ese eso esta este esto fue ha hay la las le les lo los mas
    me mi muy ni no nos o otra otro para pero por que quien se segun ser si sin sobre su sus tal
    tambien te tiene todo tras tu un una uno unos unas y ya cual cuales cuanto dime dame documento
    este esta dice decir favor puedes podrias hace hacer indica menciona""".split()
)

_SEPARADOR = "\n[…]\n"


def _normalizar(texto: str) -> str:
    sin_acentos = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in sin_acentos if unicodedata.category(c) != "Mn")


def _raiz(token: str) -> str:
    """Stemming ligero: reduce plurales y la terminación -ción/-cion."""
    if len(token) > 5 and token.endswith("ciones"):
        return token[:-2]          # acciones -> accion
    if len(token) > 4 and token.endswith("es") and token[-3] in "dlnrz":
        return token[:-2]          # facultades -> facultad, notariales -> notarial
    if len(token) > 3 and token.endswith("s"):
        return token[:-1]          # firmas -> firma, socios -> socio
    return token


def tokenizar(texto: str) -> list[str]:
    return [_raiz(t) for t in re.findall(r"[a-z0-9]+", _normalizar(texto)) if t not in _STOPWORDS and len(t) > 1]


# Expansiones para preguntas legales frecuentes. En un acta, "¿quién es el
# comisario?" se responde en la cláusula que lo DESIGNA, no en los estatutos
# que mencionan la palabra "comisario" veinte veces; sin expansión, BM25
# prefiere los estatutos por frecuencia.
_EXPANSIONES: dict[str, str] = {
    "quien": "designa designan nombra nombran nombramiento cargo",
    "quienes": "designa designan nombra nombran nombramiento cargo",
    "firma": "firmaron firmantes firmo rubrica comparecientes",
    "firman": "firmaron firmantes firmo rubrica comparecientes",
    "socio": "accionista comparecientes otorgan suscripcion suscritas",
    "socios": "accionista comparecientes otorgan suscripcion suscritas",
    "fundadores": "comparecientes otorgan constitucion",
    "cuanto": "cantidad monto pesos",
    "cuantas": "cantidad numero total",
    "cuando": "fecha",
}


def terminos_consulta(consulta: str) -> list[str]:
    """Tokeniza la consulta y le suma las expansiones de las palabras interrogativas."""
    crudos = re.findall(r"[a-z0-9]+", _normalizar(consulta))
    extra = " ".join(_EXPANSIONES[t] for t in crudos if t in _EXPANSIONES)
    return tokenizar(consulta) + tokenizar(extra)


@dataclass
class Ventana:
    inicio: int
    fin: int
    texto: str
    tokens: list[str] = field(default_factory=list)
    puntaje: float = 0.0


@dataclass
class SeleccionContexto:
    """Contexto listo para el LLM y la traza de cómo se armó."""
    texto: str
    estrategia: str                      # 'completo' | 'fragmentos' | 'inicio'
    caracteres_documento: int
    fragmentos: list[dict] = field(default_factory=list)

    @property
    def recortado(self) -> bool:
        return self.estrategia != "completo"

    def traza(self) -> dict:
        return {
            "estrategia_contexto": self.estrategia,
            "caracteres_documento": self.caracteres_documento,
            "caracteres_contexto": len(self.texto),
            "fragmentos_relevantes": self.fragmentos,
        }


def _ventanas(texto: str, tamanio: int) -> list[Ventana]:
    """Corta el texto en ventanas sobre límites de renglón, con traslape."""
    renglones = []
    posicion = 0
    for linea in texto.splitlines(keepends=True):
        renglones.append((posicion, linea))
        posicion += len(linea)

    ventanas: list[Ventana] = []
    i = 0
    while i < len(renglones):
        inicio = renglones[i][0]
        j, largo = i, 0
        while j < len(renglones) and (largo < tamanio or j == i):
            largo += len(renglones[j][1])
            j += 1
        fin = renglones[j - 1][0] + len(renglones[j - 1][1])
        # Un renglón gigante (texto sin saltos) se trocea por caracteres.
        if fin - inicio > tamanio * 2:
            for k in range(inicio, fin, tamanio):
                ventanas.append(Ventana(k, min(k + tamanio, fin), texto[k:min(k + tamanio, fin)]))
        else:
            ventanas.append(Ventana(inicio, fin, texto[inicio:fin]))
        if j >= len(renglones):
            break
        # Avanza ~80 % de la ventana para traslapar el 20 % final.
        avance, acumulado = i, 0
        while avance < j - 1 and acumulado < tamanio * 0.8:
            acumulado += len(renglones[avance][1])
            avance += 1
        i = max(avance, i + 1)
    return ventanas


def _bm25(ventanas: list[Ventana], consulta: list[str], k1: float = 1.5, b: float = 0.75) -> None:
    n = len(ventanas)
    promedio = sum(len(v.tokens) for v in ventanas) / max(n, 1) or 1.0
    df: dict[str, int] = {}
    for v in ventanas:
        for termino in set(v.tokens):
            df[termino] = df.get(termino, 0) + 1

    terminos = list(dict.fromkeys(consulta))
    bigramas = {(a, b_) for a, b_ in zip(consulta, consulta[1:])}
    for v in ventanas:
        frecuencias: dict[str, int] = {}
        for t in v.tokens:
            frecuencias[t] = frecuencias.get(t, 0) + 1
        puntaje = 0.0
        for t in terminos:
            f = frecuencias.get(t, 0)
            if not f:
                continue
            idf = math.log((n - df[t] + 0.5) / (df[t] + 0.5) + 1.0)
            puntaje += idf * f * (k1 + 1) / (f + k1 * (1 - b + b * len(v.tokens) / promedio))
        if bigramas:
            presentes = set(zip(v.tokens, v.tokens[1:]))
            puntaje += 1.5 * len(bigramas & presentes)
        v.puntaje = puntaje


def seleccionar(
    texto: str,
    consulta: str,
    presupuesto: int | None = None,
    max_fragmentos: int | None = None,
) -> SeleccionContexto:
    """
    Arma el contexto para el LLM: el documento completo si cabe; si no, su
    encabezado más los fragmentos de mayor puntaje BM25 contra ``consulta``.
    """
    presupuesto = presupuesto or settings.MAX_CARACTERES_CONTEXTO
    texto = texto.strip()
    if len(texto) <= presupuesto:
        return SeleccionContexto(texto, "completo", len(texto))

    tamanio = settings.FRAGMENTO_CARACTERES
    encabezado_fin = min(settings.ENCABEZADO_CARACTERES, presupuesto // 3)
    # El encabezado termina en un salto de renglón para no cortar una palabra.
    corte = texto.rfind("\n", 0, encabezado_fin)
    encabezado_fin = corte if corte > encabezado_fin // 2 else encabezado_fin
    encabezado = texto[:encabezado_fin].rstrip()

    terminos = terminos_consulta(consulta)
    ventanas = [v for v in _ventanas(texto, tamanio) if v.fin > encabezado_fin]
    for v in ventanas:
        v.tokens = tokenizar(v.texto)
    if terminos and ventanas:
        _bm25(ventanas, terminos)

    candidatas = sorted((v for v in ventanas if v.puntaje > 0), key=lambda v: v.puntaje, reverse=True)
    if not candidatas:
        # Nada coincide con la consulta: se conserva el comportamiento previo.
        return SeleccionContexto(texto[:presupuesto], "inicio", len(texto))

    elegidas: list[Ventana] = []
    disponible = presupuesto - len(encabezado)
    limite = max_fragmentos or 99
    for v in candidatas:
        if len(elegidas) >= limite:
            break
        # Se descartan ventanas que repiten más de la mitad de otra ya elegida.
        if any(min(v.fin, e.fin) - max(v.inicio, e.inicio) > (v.fin - v.inicio) / 2 for e in elegidas):
            continue
        costo = len(v.texto.strip()) + len(_SEPARADOR)
        if costo > disponible:
            continue
        elegidas.append(v)
        disponible -= costo

    elegidas.sort(key=lambda v: v.inicio)
    partes = [encabezado] + [v.texto.strip() for v in elegidas]
    fragmentos = [
        {
            "posicion_pct": round(100 * v.inicio / len(texto)),
            "caracteres": len(v.texto.strip()),
            "puntaje": round(v.puntaje, 2),
            "inicio": v.texto.strip()[:80],
        }
        for v in elegidas
    ]
    return SeleccionContexto(_SEPARADOR.join(partes), "fragmentos", len(texto), fragmentos)
