"""
Cotejo de representación legal — RN-03 con los datos de RSC-02 (P2, PRD §21.2).

«Al evaluar expedientes jurídicos que incluyan contratos mercantiles, el
sistema debe comprobar que el apoderado legal que suscribe el contrato cuente
con facultades notariales vigentes acreditadas en el poder o acta constitutiva
del expediente» (RN-03). El Nivel 4 extrae a los firmantes del contrato y a los
apoderados del poder o del acta; este módulo los compara con reglas
deterministas en cada evaluación del expediente, igual que la vigencia (RN-02):

  * El firmante del titular es el que representa a su empresa (o no declara
    empresa); el de la contraparte no se coteja.
  * Dos nombres coinciden si, sin acentos, títulos ni partículas, todas las
    palabras del más corto (al menos dos) están en el más largo.
  * Acreditan los poderes y actas vigentes de tipo, íntegros, del titular y con
    dictamen; la vigencia del poder se recalcula a la fecha (RCV-01, RN-02).

Estados: ACREDITADO, NO_ACREDITADO, PODER_VENCIDO y PENDIENTE. PENDIENTE nunca
rechaza: dice qué falta (auditar el contrato, el poder o el acta). La decisión
final es del analista (RSC-02, RN-05): el cotejo se la presenta preparada.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any

from models.dictamen import DictamenAuditoria
from models.documento import Documento

ACREDITADO = "ACREDITADO"
NO_ACREDITADO = "NO_ACREDITADO"
PODER_VENCIDO = "PODER_VENCIDO"
PENDIENTE = "PENDIENTE"

# Contratos cuyo firmante se coteja (reglas RSC-02-CONT y RSC-02-NDA del catálogo).
TIPOS_CONTRATO = ("CONTRATO_SERVICIOS", "ACUERDO_CONFIDENCIALIDAD")
# Documentos que acreditan facultades de representación (RN-03).
TIPOS_ACREDITANTES = ("PODER_NOTARIAL", "ACTA_CONSTITUTIVA")

_TITULOS = {
    "lic", "licenciado", "licenciada", "ing", "ingeniero", "ingeniera", "cp", "dr", "dra", "doctor", "doctora",
    "sr", "sra", "srita", "senor", "senora", "mtro", "mtra", "maestro", "maestra", "arq", "don", "dona",
}
_PARTICULAS = {"de", "del", "la", "las", "los", "y", "e"}
_SUFIJOS_SOCIETARIOS = re.compile(
    r"\b(s\s*a\s*p\s*i|s\s*a\s*b|s\s*a|s\s*de\s*r\s*l|s\s*c|a\s*c|s\s*r\s*l)(\s*de\s*c\s*v)?\b"
)


@dataclass
class CotejoRepresentacion:
    """Resultado del cotejo de un contrato vigente del expediente."""
    documento_id: str
    tipo_documento: str
    nombre_archivo_original: str
    estado: str
    motivo: str
    recomendacion: str | None = None
    firmantes: list[dict[str, Any]] = field(default_factory=list)
    apoderados: list[dict[str, Any]] = field(default_factory=list)
    coincidencias: list[dict[str, Any]] = field(default_factory=list)
    ratificado: bool = False


def _sin_acentos(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def palabras_nombre(nombre: str | None) -> set[str]:
    """Palabras que identifican a una persona: sin acentos, signos, títulos, partículas ni iniciales."""
    palabras = re.sub(r"[^a-zñ]+", " ", _sin_acentos(nombre or "")).split()
    return {p for p in palabras if len(p) > 1 and p not in _TITULOS and p not in _PARTICULAS}


def mismo_nombre(a: str | None, b: str | None) -> bool:
    """Todas las palabras del nombre más corto (al menos dos) están en el más largo."""
    pa, pb = palabras_nombre(a), palabras_nombre(b)
    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return len(corto) >= 2 and corto <= largo


def _palabras_razon(valor: str | None) -> set[str]:
    texto = re.sub(r"[^\w\s]", " ", _sin_acentos(valor or ""))
    texto = _SUFIJOS_SOCIETARIOS.sub(" ", re.sub(r"\s+", " ", texto))
    return set(texto.split())


def misma_empresa(a: str | None, b: str | None) -> bool:
    pa, pb = _palabras_razon(a), _palabras_razon(b)
    corto, largo = (pa, pb) if len(pa) <= len(pb) else (pb, pa)
    return bool(corto) and corto <= largo


def _personas(dictamen: DictamenAuditoria | None, rol: str) -> list[dict[str, Any]] | None:
    """Personas del dictamen con el rol pedido; None si el dictamen no trae esos datos."""
    datos = dictamen.representacion_legal if dictamen is not None else None
    if not isinstance(datos, dict) or datos.get("rol") != rol:
        return None
    return [p for p in datos.get("personas") or [] if isinstance(p, dict) and p.get("nombre")]


def _nombre_tipo(tipo: str) -> str:
    return {"PODER_NOTARIAL": "poder notarial", "ACTA_CONSTITUTIVA": "acta constitutiva"}.get(tipo, tipo)


def cotejar(
    razon_social_titular: str | None,
    vigentes: dict[str, Documento],
    dictamenes: dict[str, DictamenAuditoria],
    vigencias: dict[str, Any],
) -> list[CotejoRepresentacion]:
    """
    Cotejo de cada contrato vigente del expediente contra sus poderes y actas.
    ``vigencias`` es la vigencia recalculada de cada documento (cumplimiento.vigencia_actual).
    """
    fuentes: list[tuple[Documento, list[dict[str, Any]], bool]] = []   # (documento, apoderados, vencido)
    sin_auditar: list[Documento] = []
    descartados: list[Documento] = []   # de otro titular o no conformes por otra causa que su vigencia
    for tipo in TIPOS_ACREDITANTES:
        doc = vigentes.get(tipo)
        if doc is None or (doc.estado_integridad or "INTEGRO") != "INTEGRO":
            continue
        dictamen = dictamenes.get(doc.id)
        apoderados = _personas(dictamen, "APODERADOS")
        if apoderados is None:
            sin_auditar.append(doc)
            continue
        vigencia = vigencias.get(doc.id)
        vencido = bool(vigencia and vigencia.estado == "VENCIDO")
        # Un poder de otra empresa, o rechazado por otra causa que su vigencia, no acredita.
        if dictamen.match_titular is False or (dictamen.estatus == "NO_CONFORME" and not vencido):
            descartados.append(doc)
            continue
        fuentes.append((doc, apoderados, vencido))

    apoderados_vistos = [
        {**a, "documento_id": doc.id, "tipo_documento": doc.tipo_documento,
         "nombre_archivo_original": doc.nombre_archivo_original, "vencido": vencido}
        for doc, apoderados, vencido in fuentes for a in apoderados
    ]

    cotejos = []
    for tipo in TIPOS_CONTRATO:
        contrato = vigentes.get(tipo)
        if contrato is None:
            continue
        dictamen = dictamenes.get(contrato.id)
        base = dict(documento_id=contrato.id, tipo_documento=tipo,
                    nombre_archivo_original=contrato.nombre_archivo_original,
                    ratificado=bool(dictamen and dictamen.revisado_por_humano), apoderados=apoderados_vistos)
        firmantes = _personas(dictamen, "FIRMANTES")
        if dictamen is None:
            cotejos.append(CotejoRepresentacion(
                **base, estado=PENDIENTE, motivo="El contrato no se ha auditado.",
                recomendacion="Auditar el contrato para identificar a su firmante (RSC-02)."))
            continue
        if firmantes is None:
            cotejos.append(CotejoRepresentacion(
                **base, estado=PENDIENTE,
                motivo="El dictamen vigente del contrato no trae los datos del firmante (auditado antes del cotejo "
                       "o con la regla RSC-02 en pausa).",
                recomendacion="Volver a auditar el contrato con la regla RSC-02 activa."))
            continue
        propios = [f for f in firmantes if not f.get("empresa") or misma_empresa(f["empresa"], razon_social_titular)]
        verificados = [f for f in propios if f.get("cita_verificada")]
        if not verificados:
            motivo = ("El firmante del titular se identificó, pero su cita no aparece en el contrato."
                      if propios else "No se identificó en el contrato a la persona que firma por el titular.")
            cotejos.append(CotejoRepresentacion(
                **base, estado=PENDIENTE, motivo=motivo, firmantes=propios,
                recomendacion="Revisar el bloque de firmas del contrato y confirmar al firmante al ratificar."))
            continue
        if not fuentes and not sin_auditar and descartados:
            cotejos.append(CotejoRepresentacion(
                **base, estado=NO_ACREDITADO, firmantes=verificados,
                motivo="Ningún documento del expediente acredita al firmante: "
                       + ", ".join(f"«{d.nombre_archivo_original}»" for d in descartados)
                       + " no pertenece al titular o su dictamen es no conforme.",
                recomendacion="Custodiar el poder notarial vigente del firmante otorgado por el titular (RN-03)."))
            continue
        if not fuentes and not sin_auditar:
            cotejos.append(CotejoRepresentacion(
                **base, estado=PENDIENTE, firmantes=verificados,
                motivo="El expediente no tiene un poder notarial ni un acta constitutiva vigentes que acrediten al "
                       "firmante.",
                recomendacion="Custodiar el poder notarial del firmante o el acta constitutiva y auditarlos (RN-03)."))
            continue

        coincidencias = [
            {"firmante": f["nombre"], "apoderado": a["nombre"], "cargo": a.get("cargo"),
             "facultades": a.get("facultades"), "cita": a.get("cita"), "cita_verificada": a.get("cita_verificada"),
             "documento_id": a["documento_id"], "tipo_documento": a["tipo_documento"],
             "nombre_archivo_original": a["nombre_archivo_original"], "vencido": a["vencido"]}
            for f in verificados for a in apoderados_vistos if mismo_nombre(f["nombre"], a["nombre"])
        ]
        nombres = ", ".join(f["nombre"] for f in verificados)
        vigentes_ok = [c for c in coincidencias if not c["vencido"]]
        if vigentes_ok:
            c = vigentes_ok[0]
            cotejos.append(CotejoRepresentacion(
                **base, estado=ACREDITADO, firmantes=verificados, coincidencias=coincidencias,
                motivo=f"{c['firmante']} figura como {c.get('cargo') or 'apoderado'} en el "
                       f"{_nombre_tipo(c['tipo_documento'])} «{c['nombre_archivo_original']}».",
                recomendacion="Confirmar que sus facultades bastan para el acto y ratificar el dictamen del contrato."))
        elif coincidencias:
            c = coincidencias[0]
            cotejos.append(CotejoRepresentacion(
                **base, estado=PODER_VENCIDO, firmantes=verificados, coincidencias=coincidencias,
                motivo=f"{c['firmante']} solo figura en el {_nombre_tipo(c['tipo_documento'])} "
                       f"«{c['nombre_archivo_original']}», que ya venció (RCV-01).",
                recomendacion="Custodiar el poder vigente del firmante; si el analista confirma que el poder seguía "
                              "vigente al firmar, ratificar el dictamen del contrato con esa justificación."))
        elif sin_auditar:
            cotejos.append(CotejoRepresentacion(
                **base, estado=PENDIENTE, firmantes=verificados,
                motivo=f"{nombres} no figura en los documentos auditados; falta auditar: "
                       + ", ".join(f"«{d.nombre_archivo_original}»" for d in sin_auditar) + ".",
                recomendacion="Auditar el poder notarial o el acta pendientes para completar el cotejo (RN-03)."))
        else:
            cotejos.append(CotejoRepresentacion(
                **base, estado=NO_ACREDITADO, firmantes=verificados,
                motivo=f"{nombres} no figura como apoderado ni representante en el poder notarial o el acta "
                       "constitutiva vigentes del expediente.",
                recomendacion="Solicitar el poder notarial que acredite las facultades del firmante y custodiarlo; si "
                              "el analista confirma la representación por otro medio, ratificar el dictamen del "
                              "contrato con esa justificación (RN-05)."))
    return cotejos
