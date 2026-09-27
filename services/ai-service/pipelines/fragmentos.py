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
from functools import lru_cache

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


# Encabezados de estatutos o de un instrumento notarial, en MAYÚSCULAS al inicio
# de un renglón: «ARTÍCULO SEXTO. - CAPITAL SOCIAL», «CLÁUSULA TERCERA. - OBJETO»
# o las cláusulas transitorias «CUARTA.- Se designa…». Las referencias en el
# cuerpo del texto («el artículo 132 de la Ley…») no cuentan como encabezado.
_ENCABEZADO_LEGAL = re.compile(
    r"^\s*("
    r"(?:ART[IÍ]CULO|CL[AÁ]USULA|CAP[IÍ]TULO)\s+[^\n.]{1,40}\.\s*-?\s*[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ ,]{2,60}"
    r"|(?:PRIMER|SEGUND|TERCER|CUART|QUINT|SEXT|S[ÉE]PTIM|OCTAV|NOVEN|D[ÉE]CIM)[AO]\s*\.\s*-?\s*[^\n]{0,80}"
    r")"
)
_INICIO_CLAUSULA = re.compile(r"^\s*(?:ART[IÍ]CULO|CL[AÁ]USULA|CAP[IÍ]TULO)\b")


def _recortar(texto: str, largo: int = 60) -> str:
    texto = " ".join(texto.split())
    return texto if len(texto) <= largo else texto[:largo].rsplit(" ", 1)[0] + "…"


def titulo_fragmento(texto: str, terminos: list[str]) -> str:
    """
    Etiqueta legible de un fragmento para citarlo en la interfaz: el encabezado
    legal bajo el que está el renglón que mejor coincide con la consulta o, si el
    fragmento no incluye ese encabezado, el propio renglón.
    """
    buscados = set(terminos)
    renglones = texto.splitlines()
    tokens = [buscados & set(tokenizar(r)) for r in renglones]
    # Un término raro en el fragmento pesa más que uno que se repite en cada renglón.
    frecuencia = {t: sum(t in ts for ts in tokens) for t in buscados}
    vigente, mejor, coincidencias = None, None, 0.0
    for renglon, presentes in zip(renglones, tokens):
        m = _ENCABEZADO_LEGAL.match(renglon)
        if m:
            vigente = re.sub(r"[\s\-–—.:,]+$", "", m.group(1))
        elif _INICIO_CLAUSULA.match(renglon):
            vigente = None  # cláusula sin rubro: el encabezado anterior ya no aplica
        n = sum(1 / frecuencia[t] for t in presentes)
        if n > coincidencias:
            mejor, coincidencias = (vigente or renglon), n
    if mejor:
        return _recortar(mejor)
    m = next((_ENCABEZADO_LEGAL.match(r) for r in texto.splitlines() if _ENCABEZADO_LEGAL.match(r)), None)
    return _recortar(m.group(1)) if m else _recortar(texto)


def terminos_consulta(consulta: str) -> list[str]:
    """Tokeniza la consulta y le suma las expansiones de las palabras interrogativas."""
    crudos = re.findall(r"[a-z0-9]+", _normalizar(consulta))
    extra = " ".join(_EXPANSIONES[t] for t in crudos if t in _EXPANSIONES)
    return tokenizar(consulta) + tokenizar(extra)


@dataclass(frozen=True)
class Ventana:
    inicio: int
    fin: int
    texto: str


@dataclass(frozen=True)
class _Indice:
    """
    Ventanas del documento con sus términos ya contados. Se construye una sola
    vez por texto (``_indice``): el chat y la auditoría consultan el mismo
    documento muchas veces y retokenizar un acta de 130,000 caracteres en cada
    pregunta era el costo dominante de la selección.
    """
    ventanas: tuple[Ventana, ...]
    frecuencias: tuple[dict[str, int], ...]
    largos: tuple[int, ...]
    bigramas: tuple[frozenset[tuple[str, str]], ...]
    df: dict[str, int]
    promedio: float


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


@lru_cache(maxsize=16)
def _indice(texto: str, tamanio: int) -> _Indice:
    ventanas = tuple(_ventanas(texto, tamanio))
    frecuencias, largos, bigramas = [], [], []
    df: dict[str, int] = {}
    for v in ventanas:
        tokens = tokenizar(v.texto)
        conteo: dict[str, int] = {}
        for t in tokens:
            conteo[t] = conteo.get(t, 0) + 1
        for t in conteo:
            df[t] = df.get(t, 0) + 1
        frecuencias.append(conteo)
        largos.append(len(tokens))
        bigramas.append(frozenset(zip(tokens, tokens[1:])))
    promedio = sum(largos) / max(len(largos), 1) or 1.0
    return _Indice(ventanas, tuple(frecuencias), tuple(largos), tuple(bigramas), df, promedio)


def _bm25(indice: _Indice, consulta: list[str], k1: float = 1.5, b: float = 0.75) -> list[float]:
    """Puntaje BM25 de cada ventana del índice, más un bono por bigrama de la consulta presente."""
    n = len(indice.ventanas)
    terminos = [t for t in dict.fromkeys(consulta) if t in indice.df]
    bigramas_consulta = set(zip(consulta, consulta[1:]))
    idf = {t: math.log((n - indice.df[t] + 0.5) / (indice.df[t] + 0.5) + 1.0) for t in terminos}
    puntajes = []
    for frecuencias, largo, bigramas in zip(indice.frecuencias, indice.largos, indice.bigramas):
        puntaje = 0.0
        normalizador = k1 * (1 - b + b * largo / indice.promedio)
        for t in terminos:
            f = frecuencias.get(t, 0)
            if f:
                puntaje += idf[t] * f * (k1 + 1) / (f + normalizador)
        if bigramas_consulta:
            puntaje += 1.5 * len(bigramas_consulta & bigramas)
        puntajes.append(puntaje)
    return puntajes


def pagina_de(posicion: int, paginas: list[dict] | None) -> int | None:
    """
    Página del documento donde cae una posición del texto consolidado, según
    ``detalle_paginas[].inicio`` del Nivel 3. None si no hay esa información.
    """
    if not paginas:
        return None
    tramos = sorted((p["inicio"], p["pagina"]) for p in paginas if "inicio" in p and "pagina" in p)
    actual = None
    for inicio, numero in tramos:
        if inicio > posicion:
            break
        actual = numero
    return actual if actual is not None else (tramos[0][1] if tramos else None)


def _encabezado(texto: str, presupuesto: int) -> tuple[str, int]:
    fin = min(settings.ENCABEZADO_CARACTERES, presupuesto // 3)
    # El encabezado termina en un salto de renglón para no cortar una palabra.
    corte = texto.rfind("\n", 0, fin)
    fin = corte if corte > fin // 2 else fin
    return texto[:fin].rstrip(), fin


def _repite(v: Ventana, elegidas: list[Ventana]) -> bool:
    """La ventana repite más de la mitad de otra ya elegida (por el traslape)."""
    return any(min(v.fin, e.fin) - max(v.inicio, e.inicio) > (v.fin - v.inicio) / 2 for e in elegidas)


def _armar(
    texto: str,
    encabezado: str,
    elegidas: list[tuple[Ventana, float, list[str]]],
    paginas: list[dict] | None,
) -> SeleccionContexto:
    elegidas = sorted(elegidas, key=lambda e: e[0].inicio)
    partes = [encabezado] + [v.texto.strip() for v, _, _ in elegidas]
    fragmentos = [
        {
            "posicion_pct": round(100 * v.inicio / len(texto)),
            "pagina": pagina_de(v.inicio + (len(v.texto) - len(v.texto.lstrip())), paginas),
            "caracteres": len(v.texto.strip()),
            "puntaje": round(puntaje, 2),
            "inicio": v.texto.strip()[:80],
            "titulo": titulo_fragmento(v.texto, terminos),
        }
        for v, puntaje, terminos in elegidas
    ]
    return SeleccionContexto(_SEPARADOR.join(partes), "fragmentos", len(texto), fragmentos)


def seleccionar(
    texto: str,
    consulta: str,
    presupuesto: int | None = None,
    max_fragmentos: int | None = None,
    paginas: list[dict] | None = None,
) -> SeleccionContexto:
    """
    Arma el contexto para el LLM: el documento completo si cabe; si no, su
    encabezado más los fragmentos de mayor puntaje BM25 contra ``consulta``.
    Con ``paginas`` (``detalle_paginas`` del Nivel 3), cada fragmento indica su página.
    """
    presupuesto = presupuesto or settings.MAX_CARACTERES_CONTEXTO
    texto = texto.strip()
    if len(texto) <= presupuesto:
        return SeleccionContexto(texto, "completo", len(texto))

    encabezado, encabezado_fin = _encabezado(texto, presupuesto)
    terminos = terminos_consulta(consulta)
    indice = _indice(texto, settings.FRAGMENTO_CARACTERES)
    puntajes = _bm25(indice, terminos) if terminos else [0.0] * len(indice.ventanas)
    candidatas = sorted(
        ((v, p) for v, p in zip(indice.ventanas, puntajes) if p > 0 and v.fin > encabezado_fin),
        key=lambda c: c[1], reverse=True,
    )
    if not candidatas:
        # Nada coincide con la consulta: se conserva el comportamiento previo.
        return SeleccionContexto(texto[:presupuesto], "inicio", len(texto))

    elegidas: list[tuple[Ventana, float, list[str]]] = []
    disponible = presupuesto - len(encabezado)
    limite = max_fragmentos or 99
    for v, puntaje in candidatas:
        if len(elegidas) >= limite:
            break
        costo = len(v.texto.strip()) + len(_SEPARADOR)
        if costo > disponible or _repite(v, [e[0] for e in elegidas]):
            continue
        elegidas.append((v, puntaje, terminos))
        disponible -= costo
    return _armar(texto, encabezado, elegidas, paginas)


def seleccionar_por_criterios(
    texto: str,
    consultas: list[str],
    presupuesto: int | None = None,
    por_consulta: int = 2,
    paginas: list[dict] | None = None,
) -> SeleccionContexto:
    """
    Contexto para verificar varios elementos a la vez (reglas RSC/RDS). Una sola
    consulta con todos los criterios juntos favorece al elemento con más
    términos; aquí cada criterio se puntúa por separado y los fragmentos se
    eligen por turnos —primero el mejor de cada criterio, luego el segundo—, de
    modo que ningún elemento se queda sin su evidencia más probable aunque esté
    en la última página del documento.
    """
    presupuesto = presupuesto or settings.MAX_CARACTERES_CONTEXTO
    texto = texto.strip()
    if len(texto) <= presupuesto:
        return SeleccionContexto(texto, "completo", len(texto))

    encabezado, encabezado_fin = _encabezado(texto, presupuesto)
    indice = _indice(texto, settings.FRAGMENTO_CARACTERES)
    rankings: list[tuple[list[str], list[tuple[Ventana, float]]]] = []
    for consulta in consultas:
        terminos = terminos_consulta(consulta)
        if not terminos:
            continue
        puntajes = _bm25(indice, terminos)
        ranking = sorted(
            ((v, p) for v, p in zip(indice.ventanas, puntajes) if p > 0 and v.fin > encabezado_fin),
            key=lambda c: c[1], reverse=True,
        )
        rankings.append((terminos, ranking))
    if not any(r for _, r in rankings):
        return SeleccionContexto(texto[:presupuesto], "inicio", len(texto))

    elegidas: list[tuple[Ventana, float, list[str]]] = []
    disponible = presupuesto - len(encabezado)
    # Páginas que ya aportaron un fragmento a cada criterio: el segundo turno
    # prefiere otra página. Sin esto, una cláusula que menciona el elemento
    # («debiéndose inscribir en el Registro Público…») acaparaba los turnos con
    # ventanas vecinas y dejaba fuera la evidencia real en otra hoja (el sello
    # de inscripción de la última página).
    paginas_usadas: list[set] = [set() for _ in rankings]
    for turno in range(por_consulta):
        for i, (terminos, ranking) in enumerate(rankings):
            candidatas = [(v, p) for v, p in ranking if not _repite(v, [e[0] for e in elegidas])]
            if turno and paginas_usadas[i]:
                otras = [(v, p) for v, p in candidatas[:_ALTERNATIVAS_POR_PAGINA]
                         if _pagina_o_tramo(v, paginas, len(texto)) not in paginas_usadas[i]]
                candidatas = otras + [c for c in candidatas if c not in otras]
            # El mejor fragmento aún no elegido de este criterio que quepa.
            for v, puntaje in candidatas[:1]:
                costo = len(v.texto.strip()) + len(_SEPARADOR)
                if costo <= disponible:
                    elegidas.append((v, puntaje, terminos))
                    disponible -= costo
                    paginas_usadas[i].add(_pagina_o_tramo(v, paginas, len(texto)))
    return _armar(texto, encabezado, elegidas, paginas)


# Candidatas de un criterio entre las que se busca una de otra página.
_ALTERNATIVAS_POR_PAGINA = 6


def _pagina_o_tramo(v: Ventana, paginas: list[dict] | None, largo: int) -> int:
    """Página de la ventana; sin ``paginas``, el décimo del documento en que cae."""
    pagina = pagina_de(v.inicio, paginas)
    return pagina if pagina is not None else -(10 * v.inicio // max(largo, 1))
