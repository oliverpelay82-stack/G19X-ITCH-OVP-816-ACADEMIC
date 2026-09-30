"""
Respuestas del chat desde los datos del dictamen, sin modelo — T0, PLUS-07 (PRD §21.4).

Al terminar una auditoría, ``ficha_de`` resume lo que el Nivel 4 extrajo y
verificó (tipo, RFC, razón social, fechas, firmantes o apoderados con su cita
anclada, elementos RSC con su cita y recomendación, reglas de vigencia) y el
controlador la guarda por huella del binario. En el chat, ``responder`` reconoce
con reglas deterministas las preguntas factuales y las que sugiere la interfaz, y
arma la respuesta con una plantilla: el dato en negritas y una cita «…» copiada
literalmente del documento, que el controlador marca como verificada con la
misma regla que las del modelo y que abre el visor.

Salvaguardas:
  * Solo responde si la ficha es la del dictamen vigente del documento (mismo
    ``dictamen_id`` y misma huella); lo demás lo decide ``None`` → el modelo.
  * **Nunca afirma que un dato no aparece en el documento.** Si la ficha no tiene
    el dato o no hay una cita literal que lo respalde, responde el modelo. Lo que
    sí informa son los resultados de la verificación del motor («según el
    dictamen, no se localizó…»), que es un hecho del sistema.
  * Las preguntas que piden interpretar («¿puede…?», «¿por qué…?») y las que
    preguntan por la otra parte de un contrato van al modelo.
  * Lo que cambia con el tiempo (estatus, ratificación) se toma del dictamen que
    el chat consulta en cada turno, no de la ficha.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, timedelta
from typing import Any

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")
ESTATUS_EN_PALABRAS = {"CONFORME": "conforme", "EN_REVISION": "en revisión", "NO_CONFORME": "no conforme"}
TIPOS_EN_PALABRAS = {
    "CONSTANCIA_SITUACION_FISCAL": "constancia de situación fiscal", "OPINION_CUMPLIMIENTO":
    "opinión de cumplimiento de obligaciones fiscales", "COMPROBANTE_DOMICILIO": "comprobante de domicilio",
    "ACTA_CONSTITUTIVA": "acta constitutiva", "ESTADO_CUENTA": "estado de cuenta bancario",
    "PODER_NOTARIAL": "poder notarial", "CONTRATO": "contrato", "POLIZA": "póliza de seguro",
    "LICENCIA": "licencia", "CERTIFICACION": "certificación",
}
_PENDIENTES = {"NO_LOCALIZADO", "NO_VERIFICABLE", "NO_CUMPLE"}
_MAX_CITA = 220

# ── Reconocimiento de la intención ─────────────────────────────────────

_INTERPRETATIVA = re.compile(
    r"\b(puede|pueden|podria|podrian|debe|deberia|es valid[oa]|alcanza|basta|suficiente|por que|porque|"
    r"explica|significa|implica|conviene|riesgo|que pasa si|en caso de)\b")
# El RFC y la razón social de la ficha son los del titular: si la pregunta es por otra
# parte del documento, responde el modelo.
_OTRA_PARTE = re.compile(r"\b(prestador|proveedor|contraparte|otra parte|arrendador|arrendatario|vendedor|comprador|"
                         r"socio|socios|notari[oa]|aseguradora|banco|emisor|testigo)\b")
# Los firmantes y apoderados de la ficha no incluyen a terceros ajenos al acto.
_TERCEROS = re.compile(r"\b(notari[oa]|socio|socios|aseguradora|banco|testigo|testigos|comisario)\b")
_INTENCIONES = [
    ("faltantes", re.compile(r"\b(que (le |les )?faltan?|falta algo|faltan elementos|que recomiend\w*|recomendacion\w*|"
                             r"que (debo|debe|hay que) corregir|que se debe corregir|el documento cumple|"
                             r"cumple (con )?(todo|los requisitos)|estatus del dictamen|estado del dictamen)\b")),
    ("resumen", re.compile(r"\b(resum\w*|datos clave|de que trata|que es este documento)\b")),
    ("vencimiento", re.compile(r"\b(vence|vencimiento|caduca|caducidad|vigente hasta|hasta cuando (esta |es )?vigente|"
                               r"cual es (la|su) vigencia)\b")),
    ("emision", re.compile(r"\b(fecha de (emision|expedicion|firma|celebracion)|cuando se (emitio|expidio|firmo|"
                           r"celebro|otorgo))\b")),
    ("rfc", re.compile(r"\brfc\b")),
    ("razon_social", re.compile(r"\b(razon social|denominacion|a nombre de quien|quien es el titular)\b")),
    ("sentido", re.compile(r"\bsentido\b")),
    ("personas", re.compile(r"\b(firma|firman|firmo|firmaron|firmante|firmantes|suscribe|suscriben|apoderad[oa]s?|"
                            r"representante legal|administrador unico)\b")),
    ("tipo", re.compile(r"\b(que tipo de documento|que documento es)\b")),
]
_ROLES = [("administrador", r"administrador"), ("apoderad", r"apoderad"), ("representante", r"representante"),
          ("director", r"director")]


def _normalizar(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", str(texto).lower())
    texto = "".join(c for c in texto if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", re.sub(r"[¿?¡!,;:()«»\"]", " ", texto)).strip()


def intencion(pregunta: str) -> str | None:
    texto = _normalizar(pregunta)
    if _INTERPRETATIVA.search(texto):
        return None
    for nombre, patron in _INTENCIONES:
        if patron.search(texto):
            if nombre in ("rfc", "razon_social") and _OTRA_PARTE.search(texto):
                return None
            if nombre == "personas" and _TERCEROS.search(texto):
                return None
            return nombre
    return None


# ── Ficha que deja la auditoría ────────────────────────────────────────

def ficha_de(resultado: Any, tipo_registrado: str | None, sello_digital_sat: bool) -> dict[str, Any]:
    """Datos de un ``ResultadoAnalisis`` que el chat puede usar sin volver al modelo."""
    vigencia = resultado.vigencia_nivel_2 or {}
    return {
        "tipo_documento_detectado": resultado.tipo_documento_detectado,
        "tipo_registrado": tipo_registrado,
        "rfc": resultado.rfc_detectado,
        "razon_social": resultado.razon_social_detectada,
        "fecha_emision": resultado.fecha_emision,
        "fecha_vencimiento": resultado.fecha_vencimiento,
        "titularidad": resultado.titularidad,
        "representacion": resultado.representacion,
        "verificaciones": [
            {k: v.get(k) for k in ("codigo_regla", "nombre_regla", "resultado", "cita", "recomendacion", "observacion")}
            for v in resultado.verificaciones or []
        ],
        "vigencia": {
            "resultado": vigencia.get("resultado"),
            "evaluaciones": [
                {k: e.get(k) for k in ("codigo_regla", "nombre_regla", "criterio", "limite_dias", "resultado")}
                for e in vigencia.get("evaluaciones") or []
            ],
        },
        "sello_digital_sat": sello_digital_sat,
    }


# ── Citas literales ────────────────────────────────────────────────────

def _fecha_en_letra(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def _variantes_fecha(iso: str) -> list[str]:
    d = date.fromisoformat(iso)
    return [_fecha_en_letra(iso), f"{d.day:02d}/{d.month:02d}/{d.year}", f"{d.day}/{d.month}/{d.year}", iso,
            f"{d.day:02d}-{d.month:02d}-{d.year}"]


def _renglon_con(texto: str, variantes: list[str]) -> str | None:
    """El renglón del documento que contiene alguna variante del dato, copiado tal cual (cita literal)."""
    for renglon in texto.splitlines():
        normal = _normalizar(renglon)
        for variante in variantes:
            v = _normalizar(variante)
            if v and v in normal:
                renglon = renglon.strip()
                if len(renglon) <= _MAX_CITA:
                    return renglon
                # Un renglón muy largo (OCR que funde líneas): se recorta alrededor del dato, sin alterarlo.
                inicio = max(0, normal.find(v) - 60)
                return renglon[inicio:inicio + _MAX_CITA].strip()
    return None


def _cita(texto: str | None) -> str:
    return f"«{texto}»" if texto else ""


# ── Respuestas ─────────────────────────────────────────────────────────

def _estatus(dictamen: dict[str, Any]) -> str:
    estatus = ESTATUS_EN_PALABRAS.get(dictamen.get("estatus"), str(dictamen.get("estatus") or "").lower())
    if dictamen.get("revisado_por_humano"):
        return f"**{estatus}**, ratificado por {dictamen.get('revisado_por') or 'un analista'}"
    return f"**{estatus}** (pendiente de ratificación)" if dictamen.get("requiere_revision_humana") else f"**{estatus}**"


def _faltantes(ficha: dict, dictamen: dict) -> str:
    reglas = dictamen.get("reglas_aplicadas") or []
    pendientes = [r for r in reglas if r.get("resultado") in _PENDIENTES and r.get("nombre_regla")]
    vencidas = [r for r in reglas if r.get("resultado") in ("VENCIDO", "INDETERMINADO")]
    lineas = [f"Según el dictamen del motor, el documento está {_estatus(dictamen)}."]
    if pendientes or vencidas:
        for r in pendientes:
            recomendacion = f" Se recomienda: {r['recomendacion']}" if r.get("recomendacion") else ""
            # Es el resultado de la verificación del motor, no una afirmación sobre el documento.
            lineas.append(f"- **{r['nombre_regla']}**: la verificación del motor no la localizó en el texto."
                          f"{recomendacion}")
        for r in vencidas:
            lineas.append(f"- **Vigencia**: {r.get('detalle') or 'no pudo verificarse'}")
    else:
        cumplidos = [v["nombre_regla"] for v in ficha.get("verificaciones") or []
                     if v.get("resultado") == "CUMPLE" and v.get("nombre_regla")]
        if cumplidos:
            lineas.append("Se localizaron, con su cita, todos los elementos que el catálogo exige a este tipo de "
                          f"documento: {', '.join(cumplidos)}.")
        else:
            lineas.append("La verificación del motor no encontró elementos pendientes.")
    if (ficha.get("representacion") or {}).get("rol") == "FIRMANTES":
        lineas.append("Queda pendiente que el analista confirme que el **firmante** corresponde con un **apoderado** "
                      "con facultades vigentes en el poder notarial o el acta constitutiva del expediente.")
    return "\n".join(lineas)


def _vencimiento(ficha: dict, texto: str) -> str | None:
    if ficha.get("fecha_vencimiento"):
        cita = _renglon_con(texto, _variantes_fecha(ficha["fecha_vencimiento"]))
        if not cita:
            return None
        return (f"El documento está vigente hasta el **{_fecha_en_letra(ficha['fecha_vencimiento'])}**, según el "
                f"dictamen del motor: {_cita(cita)}.")
    caducidad = next((e for e in (ficha.get("vigencia") or {}).get("evaluaciones") or []
                      if e.get("criterio") == "ANTIGUEDAD_DESDE_EMISION" and e.get("limite_dias")), None)
    if caducidad and ficha.get("fecha_emision"):
        cita = _renglon_con(texto, _variantes_fecha(ficha["fecha_emision"]))
        if not cita:
            return None
        limite = int(caducidad["limite_dias"])
        hasta = (date.fromisoformat(ficha["fecha_emision"]) + timedelta(days=limite)).isoformat()
        # El nombre de la regla va entre comillas tipográficas: «…» se reserva a las citas del documento.
        return (f"Su vigencia se cuenta desde la emisión: la regla “{caducidad.get('nombre_regla')}” admite "
                f"{limite} días naturales, así que vale hasta el **{_fecha_en_letra(hasta)}**. Fecha de emisión "
                f"según el documento: {_cita(cita)}.")
    return None


def _personas(ficha: dict, pregunta: str) -> str | None:
    representacion = ficha.get("representacion") or {}
    personas = [p for p in representacion.get("personas") or [] if p.get("cita_verificada") and p.get("nombre")]
    if not personas:
        return None
    texto = _normalizar(pregunta)
    pide_firma = re.search(r"\b(firma|firman|firmo|firmaron|firmante|firmantes|suscribe|suscriben)\b", texto)
    if pide_firma and representacion.get("rol") != "FIRMANTES":
        return None
    for _, patron in _ROLES:
        if re.search(patron, texto) and not pide_firma:
            personas = [p for p in personas if re.search(patron, _normalizar(p.get("cargo") or ""))]
            if not personas:
                return None
            break
    lineas = ["Según el dictamen del motor, " + (
        "firman el documento:" if representacion.get("rol") == "FIRMANTES"
        else "tienen facultades de representación:")]
    for p in personas:
        cargo = f", {p['cargo']}" if p.get("cargo") else ""
        empresa = p.get("empresa")
        lineas.append(f"- **{p['nombre']}**{cargo}{f' ({empresa})' if empresa else ''}: {_cita(p.get('cita'))}")
    return "\n".join(lineas)


def _resumen(ficha: dict, dictamen: dict, texto: str) -> str | None:
    tipo = TIPOS_EN_PALABRAS.get(ficha.get("tipo_documento_detectado"), "documento")
    partes = [f"Es un(a) **{tipo}**"]
    if ficha.get("razon_social"):
        partes.append(f"a nombre de **{ficha['razon_social']}**")
    if ficha.get("rfc"):
        partes.append(f"con RFC **{ficha['rfc']}**")
    lineas = [" ".join(partes) + "."]
    if ficha.get("fecha_emision"):
        lineas.append(f"- Fecha de emisión: **{_fecha_en_letra(ficha['fecha_emision'])}**.")
    if ficha.get("fecha_vencimiento"):
        lineas.append(f"- Vigente hasta: **{_fecha_en_letra(ficha['fecha_vencimiento'])}**.")
    sentido = next((v for v in ficha.get("verificaciones") or [] if v.get("codigo_regla") == "RSC-OPIN-SENT"), None)
    if sentido and sentido.get("cita"):
        lineas.append(f"- Sentido de la opinión: {_cita(sentido['cita'])}.")
    personas = [p for p in (ficha.get("representacion") or {}).get("personas") or [] if p.get("cita_verificada")]
    if personas:
        etiqueta = "Firmantes" if (ficha.get("representacion") or {}).get("rol") == "FIRMANTES" else "Representantes"
        # En un contrato, la empresa que representa cada firmante nombra a las partes.
        lineas.append(f"- {etiqueta}: " + "; ".join(
            f"**{p['nombre']}**" + (f" ({', '.join(x for x in (p.get('cargo'), p.get('empresa')) if x)})"
                                    if p.get("cargo") or p.get("empresa") else "")
            for p in personas) + ".")
    cumplidos = sum(1 for v in ficha.get("verificaciones") or [] if v.get("resultado") == "CUMPLE")
    total = len(ficha.get("verificaciones") or [])
    if total:
        lineas.append(f"- Elementos exigidos localizados: {cumplidos} de {total}.")
    lineas.append(f"- Dictamen del motor: {_estatus(dictamen)}.")
    cita = _renglon_con(texto, [ficha["razon_social"]]) if ficha.get("razon_social") else None
    if cita:
        lineas.append(f"Titular según el documento: {_cita(cita)}.")
    return "\n".join(lineas)


def responder(pregunta: str, texto: str, ficha: dict[str, Any], dictamen: dict[str, Any]) -> str | None:
    """Respuesta con los datos del dictamen, o ``None`` si la pregunta debe ir al modelo."""
    nombre = intencion(pregunta)
    if nombre is None:
        return None
    if nombre == "faltantes":
        return _faltantes(ficha, dictamen)
    if nombre == "resumen":
        return _resumen(ficha, dictamen, texto)
    if nombre == "vencimiento":
        return _vencimiento(ficha, texto)
    if nombre == "emision" and ficha.get("fecha_emision"):
        cita = _renglon_con(texto, _variantes_fecha(ficha["fecha_emision"]))
        return f"Fecha de emisión: **{_fecha_en_letra(ficha['fecha_emision'])}**: {_cita(cita)}." if cita else None
    if nombre == "rfc" and ficha.get("rfc"):
        cita = _renglon_con(texto, [ficha["rfc"]])
        return f"El RFC del documento es **{ficha['rfc']}**: {_cita(cita)}." if cita else None
    if nombre == "razon_social" and ficha.get("razon_social"):
        cita = _renglon_con(texto, [ficha["razon_social"]])
        return f"El documento está a nombre de **{ficha['razon_social']}**: {_cita(cita)}." if cita else None
    if nombre == "sentido":
        sentido = next((v for v in ficha.get("verificaciones") or [] if v.get("codigo_regla") == "RSC-OPIN-SENT"), None)
        if sentido and sentido.get("cita"):
            positivo = sentido.get("resultado") == "CUMPLE"
            return (f"La opinión es en sentido **{'positivo' if positivo else 'negativo'}**: "
                    f"{_cita(sentido['cita'])}.")
        return None
    if nombre == "personas":
        return _personas(ficha, pregunta)
    if nombre == "tipo" and ficha.get("tipo_documento_detectado") in TIPOS_EN_PALABRAS:
        return f"Es un(a) **{TIPOS_EN_PALABRAS[ficha['tipo_documento_detectado']]}**, según el dictamen del motor."
    return None
