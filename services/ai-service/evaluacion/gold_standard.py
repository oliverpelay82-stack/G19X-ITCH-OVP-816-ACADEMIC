"""
Gold Standard de la validación cuantitativa (docs/VALIDACION_CUANTITATIVA.md §2).

Especifica 30 documentos ficticios de los tipos del DOC-02 y su verdad
fundamental, y genera sus PDF: 30 vectoriales y 12 escaneados (42 casos).

Principios (§2.1):
  * Datos ficticios, rotulados en cada página como DOCUMENTO DE PRUEBA.
  * Fechas absolutas y fecha de referencia fija (FECHA_REFERENCIA): el texto de
    cada documento, y con él la huella de cada petición al modelo, no cambia
    entre corridas.
  * La anotación se escribe aquí, a partir de la especificación de cada caso y
    de las reglas del DOC-05 y el DOC-08, antes de ejecutar el sistema. El
    estatus esperado lleva su motivo. ``gold_standard.json`` se congela con su
    SHA-256 (``gold_standard.sha256``).
  * Las claves de tipo documental son las del catálogo que el Nivel 4 entrega
    (``analisis_semantico.TIPOS_DOCUMENTALES``); el tipo registrado, las del
    catálogo del core.

Uso:  cd services/ai-service && python -m evaluacion.gold_standard
      (con --catalogo vuelve a tomar la instantánea del seed del rules-service)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import textwrap
from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Any

import cv2
import fitz
import numpy as np

_AQUI = os.path.dirname(os.path.abspath(__file__))
_SERVICIO = os.path.dirname(_AQUI)
sys.path.insert(0, os.path.join(_SERVICIO, "tests"))
from generar_fixtures import degradar_como_escaneo  # noqa: E402

DIRECTORIO = os.path.join(_AQUI, "gold_standard")
DIRECTORIO_DOCUMENTOS = os.path.join(DIRECTORIO, "documentos")
RUTA_ANOTACION = os.path.join(DIRECTORIO, "gold_standard.json")
RUTA_HUELLA = os.path.join(DIRECTORIO, "gold_standard.sha256")
RUTA_CATALOGO = os.path.join(DIRECTORIO, "catalogo_reglas.json")

FECHA_REFERENCIA = date(2026, 9, 30)
LEYENDA = "DOCUMENTO DE PRUEBA - DATOS FICTICIOS. Sin validez oficial; generado para evaluar el motor."

TITULAR = {"rfc": "PLU180514AB3", "razon_social": "PLURIONE S.A. DE C.V."}
PRESTADOR = {"rfc": "SIN150302KL7", "razon_social": "SERVICIOS INTEGRALES DEL NORTE S.A. DE C.V."}
AJENO = {"rfc": "CBA120809QW4", "razon_social": "COMERCIALIZADORA DEL BAJIO S.A. DE C.V."}

# Personas ficticias.
APODERADA = "María Elena Ruiz Soto"
ADMINISTRADOR = "Héctor Daniel Quiroga Salas"
DIRECTOR = "Laura Patricia Ibarra Montes"
REP_PRESTADOR = "Jorge Alberto Treviño Garza"
NOTARIO = "Lic. Ernesto Valdivia Cortés"
APODERADO_2 = "Rodrigo Esteban Lara Villaseñor"

MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")


def en_letra(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    return f"{d.day} de {MESES[d.month - 1]} de {d.year}"


def en_numeros(fecha: str) -> str:
    d = date.fromisoformat(fecha)
    return f"{d.day:02d}/{d.month:02d}/{d.year}"


# ── Especificación ─────────────────────────────────────────────────────

@dataclass
class Esperado:
    tipo_documento: str
    rfc: str | None
    razon_social: str | None
    fecha_emision: str | None
    fecha_vencimiento: str | None
    estatus: str
    motivo: str
    personas: list[dict[str, str | None]] = field(default_factory=list)
    elementos: dict[str, bool] = field(default_factory=dict)


@dataclass
class Caso:
    id: str
    tipo_registrado: str
    descripcion: str
    paginas: list[list[str]]
    esperado: Esperado
    escaneado: bool = False
    sello_notarial: bool = False
    titular: dict[str, str] = field(default_factory=lambda: dict(TITULAR))

    @property
    def archivo(self) -> str:
        return f"{self.id.lower()}.pdf"


# Renglones que empiezan con "#" van en negritas; "" deja un renglón en blanco.

def _csf(rfc: str | None, razon: str, emision: str) -> list[list[str]]:
    return [[
        "# CONSTANCIA DE SITUACIÓN FISCAL",
        "SERVICIO DE ADMINISTRACIÓN TRIBUTARIA (FICTICIO)",
        "",
        "# DATOS DE IDENTIFICACIÓN DEL CONTRIBUYENTE",
        *([f"RFC: {rfc}"] if rfc else []),
        f"Denominación o Razón Social: {razon}",
        "Régimen de capital: SOCIEDAD ANÓNIMA DE CAPITAL VARIABLE",
        "Fecha de inicio de operaciones: 14 de mayo de 2018",
        "Estatus en el padrón: ACTIVO",
        "",
        "# DATOS DEL DOMICILIO REGISTRADO",
        "Calle: AVENIDA TECNOLÓGICO   Número exterior: 2909   Colonia: CENTRO",
        "Municipio: CHIHUAHUA   Entidad Federativa: CHIHUAHUA   Código Postal: 31200",
        "",
        "# RÉGIMENES",
        "Régimen General de Ley Personas Morales   Fecha de alta: 14/05/2018",
        "",
        f"Lugar y fecha de emisión: CHIHUAHUA, CHIHUAHUA, a {en_letra(emision)}",
        "",
        "Cadena original del sello digital:",
        f"||1.0|{emision}T09:14:22|{rfc or 'XAXX010101000'}|CONSTANCIA DE SITUACION FISCAL|31200||",
    ]]


def _opinion(rfc: str, razon: str, emision: str, sentido: str, folio: str) -> list[list[str]]:
    return [[
        "# OPINIÓN DEL CUMPLIMIENTO DE OBLIGACIONES FISCALES",
        "SERVICIO DE ADMINISTRACIÓN TRIBUTARIA (FICTICIO)",
        "",
        f"Folio: {folio}",
        f"Fecha de emisión: {en_numeros(emision)}",
        f"RFC: {rfc}",
        f"Nombre, denominación o razón social: {razon}",
        "",
        "En atención a su solicitud de opinión del cumplimiento de obligaciones fiscales, conforme al",
        "artículo 32-D del Código Fiscal de la Federación, se informa que:",
        f"Sentido de la opinión: {sentido}",
        "",
        *(["Se identificaron omisiones en la presentación de declaraciones del ejercicio 2025.",
           "El contribuyente debe regularizar su situación fiscal."] if sentido == "NEGATIVO" else
          ["El contribuyente se encuentra al corriente en el cumplimiento de sus obligaciones fiscales."]),
        "",
        "La presente opinión se emite con base en la información de las bases de datos institucionales",
        "a la fecha de su emisión.",
        "",
        "Cadena original del sello digital:",
        f"||{folio}|{rfc}|{emision}|{sentido}||",
    ]]


def _domicilio(emision: str) -> list[list[str]]:
    return [[
        "# RECIBO DE SUMINISTRO DE ENERGÍA ELÉCTRICA",
        "SUMINISTRADORA DE ENERGÍA DEL NORTE (FICTICIA)",
        "",
        f"Nombre del usuario: {TITULAR['razon_social']}",
        f"RFC: {TITULAR['rfc']}",
        "Número de servicio: 581 204 773 912",
        "Domicilio del servicio: AVENIDA TECNOLÓGICO 2909, COL. CENTRO, C.P. 31200, CHIHUAHUA, CHIH.",
        "Tarifa: GDMTH   Periodo facturado: bimestre anterior",
        "",
        f"Fecha de emisión: {en_letra(emision)}",
        "Total a pagar: $18,420.00 M.N.",
        "",
        "Este recibo es comprobante de domicilio para los trámites que así lo requieran.",
    ]]


def _acta(con_rpc: bool = True, rpc_al_final: bool = False) -> list[list[str]]:
    encabezado = [
        "# ESCRITURA PÚBLICA NÚMERO 12,845",
        "# LIBRO 312",
        "",
        "En la ciudad de Chihuahua, Chihuahua, a 14 de mayo de 2018, ante mí, " + NOTARIO + ",",
        "Notario Público número 27 de este Distrito Judicial Morelos, comparecen los señores",
        f"{ADMINISTRADOR} y {DIRECTOR}, y dijeron que por medio del presente instrumento",
        "otorgan el CONTRATO DE SOCIEDAD por el que se constituye una Sociedad Anónima de Capital",
        "Variable, al tenor de los siguientes:",
        "",
        "# ESTATUTOS",
        "# ARTÍCULO PRIMERO. DENOMINACIÓN.",
        f"La sociedad se denominará {TITULAR['razon_social']}",
        "# ARTÍCULO SEGUNDO. OBJETO SOCIAL.",
        "La sociedad tendrá por objeto el desarrollo de soluciones de software, consultoría en",
        "tecnologías de la información y la prestación de servicios de capacitación.",
        "# ARTÍCULO TERCERO. DURACIÓN.",
        "La duración de la sociedad será de noventa y nueve años contados a partir de su constitución.",
        "# ARTÍCULO CUARTO. DOMICILIO.",
        "El domicilio de la sociedad será la ciudad de Chihuahua, Chihuahua.",
        "# ARTÍCULO QUINTO. CAPITAL SOCIAL.",
        "El capital social mínimo fijo es de $50,000.00 M.N., representado por 500 acciones",
        "ordinarias, nominativas, con valor nominal de $100.00 cada una, suscritas así:",
        f"{ADMINISTRADOR}: 250 acciones.   {DIRECTOR}: 250 acciones.",
    ]
    administracion = [
        "# ARTÍCULO SEXTO. ADMINISTRACIÓN.",
        "La administración de la sociedad estará a cargo de un Administrador Único, quien tendrá la",
        "representación legal de la sociedad con poder general para pleitos y cobranzas, actos de",
        "administración y actos de dominio.",
        "",
        "# CLÁUSULAS TRANSITORIAS",
        f"PRIMERA. Se designa como Administrador Único a {ADMINISTRADOR}.",
        f"SEGUNDA. Se otorga a {APODERADA} poder general para pleitos y cobranzas y actos",
        "de administración, para que represente a la sociedad ante toda clase de autoridades.",
        "TERCERA. Se designa como Comisario a Ana Sofía Beltrán Ruelas.",
        "",
        "Leído que fue el presente instrumento a los comparecientes, lo ratifican y firman ante mí.",
        "DOY FE.",
        f"{NOTARIO}   Notario Público número 27",
    ]
    rpc = [
        "",
        "# NOTA DE INSCRIPCIÓN",
        "El primer testimonio de esta escritura quedó inscrito en el Registro Público de Comercio de",
        "Chihuahua bajo el Folio Mercantil Electrónico número 48213*1, el 4 de junio de 2018.",
    ]
    paginas = [encabezado, administracion + (rpc if con_rpc and not rpc_al_final else [])]
    if con_rpc and rpc_al_final:
        paginas.append([
            "# APÉNDICE",
            "Documentos agregados al apéndice de esta escritura: permiso de uso de denominación,",
            "identificaciones de los comparecientes y comprobante de pago de derechos.",
            *rpc,
        ])
    return paginas


def _poder(facultades: bool = True, dos_apoderados: bool = False) -> list[list[str]]:
    apoderados = f"{APODERADA} y {APODERADO_2}" if dos_apoderados else APODERADA
    return [[
        "# ESCRITURA PÚBLICA NÚMERO 20,117",
        "# PODER GENERAL",
        "",
        f"En la ciudad de Chihuahua, Chihuahua, a 10 de enero de 2025, ante mí, {NOTARIO},",
        "Notario Público número 27 de este Distrito Judicial Morelos, compareció",
        f"{TITULAR['razon_social']}, representada por su Administrador Único {ADMINISTRADOR},",
        "quien acredita su personalidad con la escritura pública número 12,845, y dijo que otorga",
        f"PODER GENERAL a favor de {apoderados}, en adelante el apoderado,",
        "al tenor de las siguientes:",
        "",
        "# CLÁUSULAS",
        *(["PRIMERA. El apoderado podrá ejercer el poder general para pleitos y cobranzas y para",
           "actos de administración, en los términos de los dos primeros párrafos del artículo 2554",
           "del Código Civil Federal, con todas las facultades generales y las especiales que",
           "requieran cláusula especial conforme a la ley."] if facultades else
          ["PRIMERA. El apoderado representará a la otorgante en los asuntos que esta le encomiende",
           "por escrito."]),
        "SEGUNDA. El presente poder se otorga por tiempo indefinido y podrá revocarse en cualquier",
        "momento.",
        "",
        "Leído que fue el presente instrumento al compareciente, lo ratifica y firma ante mí. DOY FE.",
        f"{NOTARIO}   Notario Público número 27",
    ]]


def _contrato(objeto=True, confidencialidad=True, penalizacion=True, vigencia=True, firmas=True,
              tercer_firmante=False) -> list[list[str]]:
    clausulas: list[str] = ["# CLÁUSULAS"]
    n = iter(("PRIMERA", "SEGUNDA", "TERCERA", "CUARTA", "QUINTA", "SEXTA", "SÉPTIMA", "OCTAVA"))
    if objeto:
        clausulas += [f"{next(n)}. OBJETO. EL PRESTADOR se obliga a prestar a EL CLIENTE los servicios de",
                      "soporte técnico y mantenimiento de su infraestructura de cómputo descritos en el Anexo A."]
    clausulas += [f"{next(n)}. CONTRAPRESTACIÓN. EL CLIENTE pagará a EL PRESTADOR la cantidad mensual de",
                  "$185,000.00 (ciento ochenta y cinco mil pesos 00/100 M.N.) más el Impuesto al Valor",
                  "Agregado, dentro de los diez días naturales siguientes a la recepción de la factura."]
    if vigencia:
        clausulas += [f"{next(n)}. VIGENCIA Y TERMINACIÓN ANTICIPADA. El presente contrato estará vigente del",
                      "2 de marzo de 2026 al 1 de marzo de 2027. Cualquiera de las partes podrá darlo por",
                      "terminado anticipadamente mediante aviso por escrito con treinta días naturales de",
                      "anticipación, sin responsabilidad para ninguna de ellas."]
    if confidencialidad:
        clausulas += [f"{next(n)}. CONFIDENCIALIDAD. Las partes se obligan recíprocamente a no divulgar la",
                      "información confidencial que reciban con motivo de este contrato, durante su vigencia y",
                      "dos años posteriores a su terminación."]
    if penalizacion:
        clausulas += [f"{next(n)}. PENA CONVENCIONAL. En caso de incumplimiento de las obligaciones a su cargo,",
                      "EL PRESTADOR pagará a EL CLIENTE una pena convencional equivalente al diez por ciento",
                      "del monto mensual de la contraprestación por cada mes de incumplimiento."]
    clausulas += [f"{next(n)}. JURISDICCIÓN. Para la interpretación y cumplimiento de este contrato, las partes",
                  "se someten a los tribunales competentes de la ciudad de Chihuahua, Chihuahua."]
    firmas_bloque: list[str] = []
    if firmas:
        firmas_bloque = [
            "",
            "Leído que fue el presente contrato, las partes lo firman por duplicado en la ciudad de",
            "Chihuahua, Chihuahua, el 2 de marzo de 2026.",
            "",
            "# EL CLIENTE",
            f"{TITULAR['razon_social']}",
            f"{APODERADA}, Apoderada legal",
            *([f"{DIRECTOR}, Directora General"] if tercer_firmante else []),
            "",
            "# EL PRESTADOR",
            f"{PRESTADOR['razon_social']}",
            f"{REP_PRESTADOR}, Representante legal",
        ]
    return [[
        "# CONTRATO DE PRESTACIÓN DE SERVICIOS",
        "",
        f"Contrato de prestación de servicios que celebran, por una parte, {TITULAR['razon_social']},",
        f"con RFC {TITULAR['rfc']}, en lo sucesivo EL CLIENTE, representada por {APODERADA},",
        f"y por la otra, {PRESTADOR['razon_social']}, con RFC {PRESTADOR['rfc']}, en lo sucesivo",
        f"EL PRESTADOR, representada por {REP_PRESTADOR}, al tenor de las siguientes:",
        "",
        "# DECLARACIONES",
        "I. Declara EL CLIENTE que es una sociedad mercantil constituida conforme a las leyes mexicanas,",
        "según consta en la escritura pública número 12,845 otorgada ante el Notario Público número 27",
        "de Chihuahua, y que su apoderada cuenta con facultades suficientes para obligarla.",
        "II. Declara EL PRESTADOR que cuenta con la capacidad técnica y los recursos necesarios para",
        "prestar los servicios objeto de este contrato.",
        "",
    ], clausulas + firmas_bloque]


def _nda(no_divulgacion=True, vigencia=True) -> list[list[str]]:
    return [[
        "# ACUERDO DE CONFIDENCIALIDAD",
        "",
        f"Acuerdo que celebran {TITULAR['razon_social']}, con RFC {TITULAR['rfc']}, representada por",
        f"{APODERADA}, y {PRESTADOR['razon_social']}, con RFC {PRESTADOR['rfc']}, representada por",
        f"{REP_PRESTADOR}, en la ciudad de Chihuahua, Chihuahua, el 15 de junio de 2026.",
        "",
        "# CLÁUSULAS",
        "PRIMERA. INFORMACIÓN CONFIDENCIAL. Se considera información confidencial toda la información",
        "técnica, comercial y financiera que una parte entregue a la otra con motivo del proyecto de",
        "migración de sistemas.",
        *(["SEGUNDA. NO DIVULGACIÓN. La parte receptora se obliga a no divulgar, publicar ni transmitir",
           "a terceros la información confidencial, y a usarla exclusivamente para el proyecto."]
          if no_divulgacion else
          ["SEGUNDA. ENTREGA. La información se entregará por los medios que las partes acuerden."]),
        *(["TERCERA. VIGENCIA. Las obligaciones de este acuerdo estarán vigentes hasta el 15 de junio",
           "de 2029."] if vigencia else []),
        "",
        "# FIRMAS",
        f"{TITULAR['razon_social']}   {APODERADA}, Apoderada legal",
        f"{PRESTADOR['razon_social']}   {REP_PRESTADOR}, Representante legal",
    ]]


def _poliza(inicio: str, fin: str, emision: str) -> list[list[str]]:
    return [[
        "# PÓLIZA DE SEGURO DE DAÑOS EMPRESARIAL",
        "ASEGURADORA DEL PACÍFICO (FICTICIA)",
        "",
        "Número de póliza: DAE-2026-004871",
        f"Asegurado: {TITULAR['razon_social']}   RFC: {TITULAR['rfc']}",
        "Ubicación asegurada: AVENIDA TECNOLÓGICO 2909, COL. CENTRO, CHIHUAHUA, CHIH.",
        f"Fecha de emisión: {en_numeros(emision)}",
        f"Vigencia: desde las 12:00 horas del {en_numeros(inicio)} hasta las 12:00 horas del {en_numeros(fin)}",
        "",
        "# COBERTURAS CONTRATADAS",
        "Incendio de edificio y contenidos        Suma asegurada: $5,000,000.00",
        "Robo con violencia                        Suma asegurada: $750,000.00",
        "Responsabilidad civil general             Suma asegurada: $2,000,000.00",
        "Prima total: $48,930.00 M.N.",
    ]]


def _licencia() -> list[list[str]]:
    return [[
        "# LICENCIA DE FUNCIONAMIENTO",
        "MUNICIPIO DE CHIHUAHUA (FICTICIO) - DIRECCIÓN DE DESARROLLO URBANO",
        "",
        "Número de licencia: LF-2026-01933",
        f"Titular: {TITULAR['razon_social']}   RFC: {TITULAR['rfc']}",
        "Domicilio del establecimiento: AVENIDA TECNOLÓGICO 2909, COL. CENTRO, C.P. 31200",
        "Fecha de expedición: 05/01/2026",
        "Vigencia: hasta el 31/12/2026",
        "",
        "La presente licencia autoriza el funcionamiento del establecimiento en el domicilio señalado,",
        "sujeta al cumplimiento de la normatividad municipal aplicable.",
    ]]


def _personas(*nombres_cargos: tuple[str, str | None]) -> list[dict[str, str | None]]:
    return [{"nombre": n, "cargo": c} for n, c in nombres_cargos]


_FIRMANTES_BASE = _personas((APODERADA, "Apoderada legal"), (REP_PRESTADOR, "Representante legal"))
_CONT_TODO = {"RSC-01-CONT-OBJ": True, "RSC-01-CONT-VIG": True, "RSC-01-CONT-PEN": True,
              "RSC-01-CONT-CONF": True, "RSC-01-CONT-FIRM": True}
_RSC02 = "el contrato identifica a sus firmantes y RSC-02 deja la decisión al analista (DOC-05)"


def _contrato_esperado(motivo: str, faltan: tuple[str, ...] = (), personas=_FIRMANTES_BASE,
                       vencimiento: str | None = "2027-03-01") -> Esperado:
    return Esperado(
        tipo_documento="CONTRATO", rfc=TITULAR["rfc"], razon_social=TITULAR["razon_social"],
        fecha_emision="2026-03-02", fecha_vencimiento=vencimiento, estatus="EN_REVISION", motivo=motivo,
        personas=list(personas), elementos={k: k not in faltan for k in _CONT_TODO},
    )


def casos() -> list[Caso]:
    """Los 30 documentos base; los marcados ``escaneado`` generan además su versión escaneada."""
    vig = "2026-09-10"  # emisión reciente: 20 días antes de la referencia
    return [
        # ── Constancia de situación fiscal (RCV-03: 90 días desde la emisión) ──
        Caso("GS-CSF-01", "CSF_SAT", "Constancia vigente del titular", _csf(TITULAR["rfc"], TITULAR["razon_social"], vig),
             Esperado("CONSTANCIA_SITUACION_FISCAL", TITULAR["rfc"], TITULAR["razon_social"], vig, None, "CONFORME",
                      "RFC del titular y 20 días de antigüedad (RCV-03: máximo 90)."), escaneado=True),
        Caso("GS-CSF-02", "CSF_SAT", "Constancia con más de 90 días", _csf(TITULAR["rfc"], TITULAR["razon_social"], "2026-05-04"),
             Esperado("CONSTANCIA_SITUACION_FISCAL", TITULAR["rfc"], TITULAR["razon_social"], "2026-05-04", None,
                      "NO_CONFORME", "149 días de antigüedad: caducidad estricta RCV-03 (90 días).")),
        Caso("GS-CSF-03", "CSF_SAT", "Constancia de otro contribuyente", _csf(AJENO["rfc"], AJENO["razon_social"], vig),
             Esperado("CONSTANCIA_SITUACION_FISCAL", AJENO["rfc"], AJENO["razon_social"], vig, None, "NO_CONFORME",
                      "El RFC del documento no es el del titular del expediente (DOC-08: RFC ajeno)."), escaneado=True),
        Caso("GS-CSF-04", "CSF_SAT", "Constancia sin RFC legible, razón social del titular",
             _csf(None, TITULAR["razon_social"], vig),
             Esperado("CONSTANCIA_SITUACION_FISCAL", None, TITULAR["razon_social"], vig, None, "CONFORME",
                      "Sin RFC, la titularidad se verifica por la razón social (DG Cap. I: «el nombre o el RFC»); "
                      "vigente.")),
        # ── Opinión de cumplimiento 32-D (RCV-04: 30 días; RSC-OPIN-SENT) ──
        Caso("GS-OPIN-01", "OPINION_CUMPLIMIENTO", "Opinión positiva vigente",
             _opinion(TITULAR["rfc"], TITULAR["razon_social"], "2026-09-18", "POSITIVO", "26NA4471902"),
             Esperado("OPINION_CUMPLIMIENTO", TITULAR["rfc"], TITULAR["razon_social"], "2026-09-18", None, "CONFORME",
                      "Sentido positivo y 12 días de antigüedad (RCV-04: máximo 30).",
                      elementos={"RSC-OPIN-SENT": True}), escaneado=True),
        Caso("GS-OPIN-02", "OPINION_CUMPLIMIENTO", "Opinión negativa",
             _opinion(TITULAR["rfc"], TITULAR["razon_social"], "2026-09-18", "NEGATIVO", "26NA4471903"),
             Esperado("OPINION_CUMPLIMIENTO", TITULAR["rfc"], TITULAR["razon_social"], "2026-09-18", None, "NO_CONFORME",
                      "Sentido negativo: el documento contradice el requisito (RSC-OPIN-SENT).",
                      elementos={"RSC-OPIN-SENT": False})),
        Caso("GS-OPIN-03", "OPINION_CUMPLIMIENTO", "Opinión positiva con más de 30 días",
             _opinion(TITULAR["rfc"], TITULAR["razon_social"], "2026-07-20", "POSITIVO", "26NA4471904"),
             Esperado("OPINION_CUMPLIMIENTO", TITULAR["rfc"], TITULAR["razon_social"], "2026-07-20", None, "NO_CONFORME",
                      "72 días de antigüedad: caducidad estricta RCV-04 (30 días).",
                      elementos={"RSC-OPIN-SENT": True})),
        Caso("GS-OPIN-04", "OPINION_CUMPLIMIENTO", "Opinión positiva de otro contribuyente",
             _opinion(AJENO["rfc"], AJENO["razon_social"], "2026-09-18", "POSITIVO", "26NA4471905"),
             Esperado("OPINION_CUMPLIMIENTO", AJENO["rfc"], AJENO["razon_social"], "2026-09-18", None, "NO_CONFORME",
                      "RFC ajeno al titular del expediente.", elementos={"RSC-OPIN-SENT": True})),
        # ── Comprobante de domicilio (RCV-02: 90 días) ──
        Caso("GS-DOM-01", "COMP_DOMICILIO", "Recibo reciente", _domicilio("2026-08-28"),
             Esperado("COMPROBANTE_DOMICILIO", TITULAR["rfc"], TITULAR["razon_social"], "2026-08-28", None, "CONFORME",
                      "33 días de antigüedad (RCV-02: máximo 90)."), escaneado=True),
        Caso("GS-DOM-02", "COMP_DOMICILIO", "Recibo con más de 90 días", _domicilio("2026-04-15"),
             Esperado("COMPROBANTE_DOMICILIO", TITULAR["rfc"], TITULAR["razon_social"], "2026-04-15", None, "NO_CONFORME",
                      "168 días de antigüedad: caducidad estricta RCV-02 (90 días).")),
        # ── Acta constitutiva ──
        Caso("GS-ACTA-01", "ACTA_CONSTITUTIVA", "Acta completa", _acta(),
             Esperado("ACTA_CONSTITUTIVA", None, TITULAR["razon_social"], "2018-05-14", None, "CONFORME",
                      "Escritura y notario, inscripción en el RPC y administración presentes; sin vencimiento.",
                      personas=_personas((ADMINISTRADOR, "Administrador Único"), (APODERADA, "Apoderada")),
                      elementos={"RSC-ACTA-ESCR": True, "RSC-ACTA-RPC": True, "RSC-ACTA-ADMON": True}),
             escaneado=True, sello_notarial=True),
        Caso("GS-ACTA-02", "ACTA_CONSTITUTIVA", "Acta sin inscripción en el RPC", _acta(con_rpc=False),
             Esperado("ACTA_CONSTITUTIVA", None, TITULAR["razon_social"], "2018-05-14", None, "EN_REVISION",
                      "Falta la inscripción en el Registro Público de Comercio (RSC-ACTA-RPC).",
                      personas=_personas((ADMINISTRADOR, "Administrador Único"), (APODERADA, "Apoderada")),
                      elementos={"RSC-ACTA-ESCR": True, "RSC-ACTA-RPC": False, "RSC-ACTA-ADMON": True})),
        Caso("GS-ACTA-03", "ACTA_CONSTITUTIVA", "Acta con la inscripción en el apéndice final", _acta(rpc_al_final=True),
             Esperado("ACTA_CONSTITUTIVA", None, TITULAR["razon_social"], "2018-05-14", None, "CONFORME",
                      "Completa; la inscripción está en la última página (la auditoría lee todo el documento).",
                      personas=_personas((ADMINISTRADOR, "Administrador Único"), (APODERADA, "Apoderada")),
                      elementos={"RSC-ACTA-ESCR": True, "RSC-ACTA-RPC": True, "RSC-ACTA-ADMON": True}),
             escaneado=True, sello_notarial=True),
        Caso("GS-ACTA-04", "ACTA_CONSTITUTIVA", "Se registró como acta y es un poder notarial", _poder(),
             Esperado("PODER_NOTARIAL", None, TITULAR["razon_social"], "2025-01-10", None, "EN_REVISION",
                      "El contenido es un poder notarial, no un acta: tipo incompatible con el registrado.",
                      personas=_personas((APODERADA, "Apoderado")),
                      elementos={"RSC-ACTA-ESCR": True, "RSC-ACTA-RPC": False, "RSC-ACTA-ADMON": False})),
        # ── Poder notarial ──
        Caso("GS-PODER-01", "PODER_NOTARIAL", "Poder general completo", _poder(),
             Esperado("PODER_NOTARIAL", None, TITULAR["razon_social"], "2025-01-10", None, "CONFORME",
                      "Otorgado ante notario, identifica otorgante y apoderado y señala facultades.",
                      personas=_personas((APODERADA, "Apoderado")),
                      elementos={"RSC-PODER-NOT": True, "RSC-PODER-PART": True, "RSC-PODER-FAC": True}),
             escaneado=True, sello_notarial=True),
        Caso("GS-PODER-02", "PODER_NOTARIAL", "Poder sin facultades definidas", _poder(facultades=False),
             Esperado("PODER_NOTARIAL", None, TITULAR["razon_social"], "2025-01-10", None, "EN_REVISION",
                      "No señala facultades de pleitos y cobranzas, administración o dominio (RSC-PODER-FAC).",
                      personas=_personas((APODERADA, "Apoderado")),
                      elementos={"RSC-PODER-NOT": True, "RSC-PODER-PART": True, "RSC-PODER-FAC": False})),
        Caso("GS-PODER-03", "PODER_NOTARIAL", "Poder a dos apoderados", _poder(dos_apoderados=True),
             Esperado("PODER_NOTARIAL", None, TITULAR["razon_social"], "2025-01-10", None, "CONFORME",
                      "Completo, con dos apoderados.",
                      personas=_personas((APODERADA, "Apoderado"), (APODERADO_2, "Apoderado")),
                      elementos={"RSC-PODER-NOT": True, "RSC-PODER-PART": True, "RSC-PODER-FAC": True})),
        # ── Contrato de prestación de servicios (RSC-01 y RSC-02) ──
        Caso("GS-CONT-01", "CONTRATO_SERVICIOS", "Contrato completo", _contrato(),
             _contrato_esperado(f"Todas las cláusulas presentes; {_RSC02}."), escaneado=True),
        Caso("GS-CONT-02", "CONTRATO_SERVICIOS", "Sin confidencialidad", _contrato(confidencialidad=False),
             _contrato_esperado("Falta la cláusula de confidencialidad: omisión contractual relevante (RSC-01).",
                                faltan=("RSC-01-CONT-CONF",))),
        Caso("GS-CONT-03", "CONTRATO_SERVICIOS", "Sin penalización", _contrato(penalizacion=False),
             _contrato_esperado("Falta la penalización por incumplimiento: omisión contractual relevante (RSC-01).",
                                faltan=("RSC-01-CONT-PEN",)), escaneado=True),
        Caso("GS-CONT-04", "CONTRATO_SERVICIOS", "Sin vigencia ni terminación", _contrato(vigencia=False),
             _contrato_esperado("Falta la vigencia y la terminación anticipada (RSC-01).",
                                faltan=("RSC-01-CONT-VIG",), vencimiento=None)),
        Caso("GS-CONT-05", "CONTRATO_SERVICIOS", "Sin objeto", _contrato(objeto=False),
             _contrato_esperado("No define el objeto del contrato (RSC-01-CONT-OBJ).", faltan=("RSC-01-CONT-OBJ",))),
        Caso("GS-CONT-06", "CONTRATO_SERVICIOS", "Sin apartado de firmas", _contrato(firmas=False),
             _contrato_esperado("No contiene el apartado de firmas (RSC-01-CONT-FIRM); los representantes solo se "
                                "mencionan en el proemio.", faltan=("RSC-01-CONT-FIRM",))),
        Caso("GS-CONT-07", "CONTRATO_SERVICIOS", "Tres firmantes", _contrato(tercer_firmante=True),
             _contrato_esperado(f"Completo, con dos firmantes por el cliente; {_RSC02}.",
                                personas=_FIRMANTES_BASE + _personas((DIRECTOR, "Directora General"))),
             escaneado=True),
        # ── Acuerdo de confidencialidad ──
        Caso("GS-NDA-01", "ACUERDO_CONFIDENCIALIDAD", "NDA completo", _nda(),
             Esperado("CONTRATO", TITULAR["rfc"], TITULAR["razon_social"], "2026-06-15", "2029-06-15", "EN_REVISION",
                      f"Completo; {_RSC02}.", personas=list(_FIRMANTES_BASE),
                      elementos={"RSC-01-NDA-NODIV": True, "RSC-01-NDA-PART": True, "RSC-01-NDA-VIG": True}),
             escaneado=True),
        Caso("GS-NDA-02", "ACUERDO_CONFIDENCIALIDAD", "NDA sin obligación de no divulgación", _nda(no_divulgacion=False),
             Esperado("CONTRATO", TITULAR["rfc"], TITULAR["razon_social"], "2026-06-15", "2029-06-15", "EN_REVISION",
                      "Falta la cláusula de no divulgación (RSC-01-NDA-NODIV).", personas=list(_FIRMANTES_BASE),
                      elementos={"RSC-01-NDA-NODIV": False, "RSC-01-NDA-PART": True, "RSC-01-NDA-VIG": True})),
        Caso("GS-NDA-03", "ACUERDO_CONFIDENCIALIDAD", "NDA sin vigencia", _nda(vigencia=False),
             Esperado("CONTRATO", TITULAR["rfc"], TITULAR["razon_social"], "2026-06-15", None, "EN_REVISION",
                      "Falta la vigencia de la obligación de confidencialidad (RSC-01-NDA-VIG).",
                      personas=list(_FIRMANTES_BASE),
                      elementos={"RSC-01-NDA-NODIV": True, "RSC-01-NDA-PART": True, "RSC-01-NDA-VIG": False})),
        # ── Regulatorio ──
        Caso("GS-POL-01", "POLIZA_SEGURO", "Póliza vigente", _poliza("2026-01-01", "2027-01-01", "2025-12-20"),
             Esperado("POLIZA", TITULAR["rfc"], TITULAR["razon_social"], "2025-12-20", "2027-01-01", "CONFORME",
                      "Coberturas y sumas aseguradas presentes; vence en 93 días (RCV-01: vigente).",
                      elementos={"RSC-POL-COB": True}), escaneado=True),
        Caso("GS-POL-02", "POLIZA_SEGURO", "Póliza vencida", _poliza("2025-01-01", "2026-01-01", "2024-12-18"),
             Esperado("POLIZA", TITULAR["rfc"], TITULAR["razon_social"], "2024-12-18", "2026-01-01", "NO_CONFORME",
                      "Venció el 1 de enero de 2026 (RCV-01).", elementos={"RSC-POL-COB": True})),
        Caso("GS-LIC-01", "LICENCIA_OPERACION", "Licencia sin giro autorizado", _licencia(),
             Esperado("LICENCIA", TITULAR["rfc"], TITULAR["razon_social"], "2026-01-05", "2026-12-31", "EN_REVISION",
                      "No indica el giro o actividad autorizada (RSC-LIC-GIRO).", elementos={"RSC-LIC-GIRO": False})),
    ]


# ── Generación de los PDF ─────────────────────────────────────────────

_ANCHO, _ALTO, _MARGEN = 612, 792, 62
_FUENTE = fitz.Font("helv")
_FUENTE_NEGRITA = fitz.Font("hebo")


def _renglones(pagina: list[str]) -> list[tuple[str, bool]]:
    salida = []
    for renglon in pagina:
        negrita = renglon.startswith("# ")
        texto = renglon[2:] if negrita else renglon
        partes = textwrap.wrap(texto, 96) or [""]
        salida += [(p, negrita) for p in partes]
    return salida


def texto_de_referencia(caso: Caso) -> str:
    """El texto exacto impreso en el documento, para medir el CER del OCR (§2.1)."""
    paginas = []
    for pagina in caso.paginas:
        paginas.append("\n".join([LEYENDA] + [t for t, _ in _renglones(pagina)]))
    return "\n\n".join(paginas)


def pdf_vectorial(caso: Caso) -> bytes:
    documento = fitz.open()
    for pagina_spec in caso.paginas:
        pagina = documento.new_page(width=_ANCHO, height=_ALTO)
        escritor = fitz.TextWriter(pagina.rect)
        escritor.append((_MARGEN, 44), LEYENDA, font=_FUENTE, fontsize=7.5)
        y = 84
        for texto, negrita in _renglones(pagina_spec):
            if texto:
                escritor.append((_MARGEN, y), texto, font=_FUENTE_NEGRITA if negrita else _FUENTE,
                                fontsize=10.5 if not negrita else 11)
            y += 16
        escritor.write_text(pagina, color=(0.08, 0.08, 0.1))
    documento.subset_fonts()
    contenido = documento.tobytes(garbage=3, deflate=True, no_new_id=True)
    documento.close()
    return contenido


def _sello(imagen_bgr: np.ndarray, azar: np.random.Generator) -> None:
    """Sello notarial en tinta azul, sobre el margen inferior derecho (evidencia visual, como en un acta real)."""
    alto, ancho = imagen_bgr.shape[:2]
    centro = (int(ancho * 0.74), int(alto * 0.83 + azar.integers(-20, 20)))
    radio = int(ancho * 0.11)
    cv2.circle(imagen_bgr, centro, radio, (170, 80, 40), 5)
    cv2.circle(imagen_bgr, centro, int(radio * 0.8), (170, 80, 40), 2)
    cv2.putText(imagen_bgr, "NOTARIA 27", (centro[0] - int(radio * 0.62), centro[1] + 8),
                cv2.FONT_HERSHEY_SIMPLEX, radio / 150, (170, 80, 40), 3, cv2.LINE_AA)


def pdf_escaneado(caso: Caso, vectorial: bytes, dpi: int = 200) -> bytes:
    """Rasteriza cada página, añade el sello si corresponde, la degrada y la reempaqueta sin capa de texto."""
    semilla = int(hashlib.sha256(caso.id.encode()).hexdigest()[:8], 16)
    azar = np.random.default_rng(semilla)
    destino = fitz.open()
    with fitz.open(stream=vectorial, filetype="pdf") as origen:
        for numero, pagina in enumerate(origen):
            pixmap = pagina.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72), colorspace=fitz.csRGB)
            rgb = np.frombuffer(pixmap.samples, dtype=np.uint8).reshape(pixmap.height, pixmap.width, 3)
            bgr = rgb[:, :, ::-1].copy()
            if caso.sello_notarial and numero == len(origen) - 1:
                _sello(bgr, azar)
            degradada = degradar_como_escaneo(bgr, semilla=semilla + numero)
            _, jpeg = cv2.imencode(".jpg", degradada, [int(cv2.IMWRITE_JPEG_QUALITY), 70])
            hoja = destino.new_page(width=pagina.rect.width, height=pagina.rect.height)
            hoja.insert_image(hoja.rect, stream=jpeg.tobytes())
    contenido = destino.tobytes(garbage=3, deflate=True, no_new_id=True)
    destino.close()
    return contenido


def casos_evaluados() -> list[dict[str, Any]]:
    """Los 42 casos (30 vectoriales y 12 escaneados) con su anotación, en el formato de gold_standard.json."""
    salida = []
    for caso in casos():
        for rendicion in ("VECTORIAL", "ESCANEADO") if caso.escaneado else ("VECTORIAL",):
            sufijo = "" if rendicion == "VECTORIAL" else "-ESC"
            salida.append({
                "id": caso.id + sufijo,
                "caso_base": caso.id,
                "archivo": caso.archivo.replace(".pdf", f"{sufijo.lower()}.pdf"),
                "rendicion": rendicion,
                "tipo_registrado": caso.tipo_registrado,
                "descripcion": caso.descripcion,
                "titular": caso.titular,
                "sello_notarial": caso.sello_notarial and rendicion == "ESCANEADO",
                "esperado": asdict(caso.esperado),
            })
    return salida


def _huella(ruta: str) -> str:
    with open(ruta, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def tomar_catalogo() -> None:
    """
    Instantánea de las reglas RSC y RCV del seed del rules-service. Se ejecuta en
    un subproceso con el directorio de ese servicio, porque su paquete ``config``
    choca con el del ai-service (CLAUDE.md §2.1).
    """
    rules = os.path.join(os.path.dirname(_SERVICIO), "rules-service")
    codigo = (
        "import json, seed_reglas_validacion as s;"
        "print(json.dumps([r for r in s.REGLAS_BASE if r['familia_regla'] in ('RSC', 'RCV')], ensure_ascii=False))"
    )
    salida = subprocess.run([sys.executable, "-c", codigo], cwd=rules, capture_output=True, text=True, check=True)
    reglas = json.loads(salida.stdout.strip().splitlines()[-1])
    with open(RUTA_CATALOGO, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"origen": "services/rules-service/seed_reglas_validacion.py", "reglas": reglas}, f,
                  ensure_ascii=False, indent=2)
        f.write("\n")
    print(f"[gold standard] catálogo: {len(reglas)} reglas RSC y RCV")


def generar() -> None:
    os.makedirs(DIRECTORIO_DOCUMENTOS, exist_ok=True)
    for caso in casos():
        vectorial = pdf_vectorial(caso)
        with open(os.path.join(DIRECTORIO_DOCUMENTOS, caso.archivo), "wb") as f:
            f.write(vectorial)
        if caso.escaneado:
            with open(os.path.join(DIRECTORIO_DOCUMENTOS, caso.archivo.replace(".pdf", "-esc.pdf")), "wb") as f:
                f.write(pdf_escaneado(caso, vectorial))
    evaluados = casos_evaluados()
    for c in evaluados:
        c["sha256_archivo"] = _huella(os.path.join(DIRECTORIO_DOCUMENTOS, c["archivo"]))
        c["texto_referencia"] = texto_de_referencia(next(x for x in casos() if x.id == c["caso_base"]))
    anotacion = {
        "version": 1,
        "fecha_referencia": FECHA_REFERENCIA.isoformat(),
        "titular": TITULAR,
        "catalogo_reglas_sha256": _huella(RUTA_CATALOGO),
        "casos": evaluados,
    }
    with open(RUTA_ANOTACION, "w", encoding="utf-8", newline="\n") as f:
        json.dump(anotacion, f, ensure_ascii=False, indent=2)
        f.write("\n")
    huella = _huella(RUTA_ANOTACION)
    with open(RUTA_HUELLA, "w", encoding="utf-8", newline="\n") as f:
        f.write(f"{huella}  gold_standard.json\n")
    print(f"[gold standard] {len(evaluados)} casos ({sum(c['rendicion'] == 'ESCANEADO' for c in evaluados)} "
          f"escaneados); gold_standard.json sha256 {huella}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--catalogo", action="store_true", help="Vuelve a tomar la instantánea del seed")
    args = parser.parse_args()
    if args.catalogo or not os.path.exists(RUTA_CATALOGO):
        os.makedirs(DIRECTORIO, exist_ok=True)
        tomar_catalogo()
    generar()
