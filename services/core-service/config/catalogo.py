"""
Catálogos oficiales del motor (DOC-02 y DOC-04).

  * **Tipos de expediente (RF-01, HU-01).** Clasificación temática de la
    Tabla 5 del DOC-02: jurídico, corporativo y regulatorio.
  * **Tipos de documento.** Inventario de las Tablas 2 a 4 del DOC-02, más los
    documentos fiscales que ya custodiaba el expediente B2B (opinión de
    cumplimiento 32-D y carátula bancaria). Qué documentos exige cada tipo de
    expediente no se decide aquí: lo declaran las reglas RIE del rules-service
    (RF-06). Este módulo solo aporta los nombres legibles que usan las alertas
    y los reportes.
"""
from __future__ import annotations

TIPOS_EXPEDIENTE: dict[str, str] = {
    "JURIDICO": "Jurídico",
    "CORPORATIVO": "Corporativo",
    "REGULATORIO": "Regulatorio",
}

# Tipo con el que se clasificaron los expedientes creados antes de RF-01: el
# expediente B2B original (CSF, domicilio y acta) es el corporativo del DOC-02.
TIPO_EXPEDIENTE_PREDETERMINADO = "CORPORATIVO"

TIPOS_DOCUMENTO: dict[str, str] = {
    # Expediente corporativo (DOC-02, Tabla 3)
    "CSF_SAT": "Constancia de Situación Fiscal (SAT)",
    "COMP_DOMICILIO": "Comprobante de Domicilio Fiscal",
    "ACTA_CONSTITUTIVA": "Acta Constitutiva",
    "PODER_NOTARIAL": "Poder Notarial",
    "ESTATUTOS_SOCIALES": "Estatutos Sociales",
    "ACTA_ASAMBLEA": "Acta de Asamblea",
    "CEDULA_RFC": "Registro Federal de Contribuyentes (empresa)",
    "AVISO_PRIVACIDAD": "Aviso de Privacidad",
    "OPINION_CUMPLIMIENTO": "Opinión de Cumplimiento SAT (Art. 32-D)",
    "ESTADO_CUENTA": "Carátula de Estado de Cuenta Bancario",
    # Expediente jurídico (DOC-02, Tabla 4)
    "CONTRATO_SERVICIOS": "Contrato de Prestación de Servicios",
    "ACUERDO_CONFIDENCIALIDAD": "Acuerdo de Confidencialidad (NDA)",
    "ANEXO_CONTRATO": "Anexo Legal del Contrato",
    "DICTAMEN_PERICIAL": "Dictamen o Peritaje",
    "CONVENIO_MODIFICATORIO": "Convenio Modificatorio",
    # Expediente regulatorio (DOC-02, Tabla 5)
    "LICENCIA_OPERACION": "Licencia de Operación",
    "PERMISO_SECTORIAL": "Permiso Municipal o Sectorial",
    "CERTIFICACION": "Certificación (ISO, calidad, ambiental)",
    "POLIZA_SEGURO": "Póliza de Seguro",
    "POLIZA_RC": "Póliza de Responsabilidad Civil",
    "FIANZA": "Fianza",
    "CONSTANCIA_CAPACITACION": "Constancia de Capacitación",
    "REGISTRO_SECTORIAL": "Registro ante Autoridad Sectorial",
}


# OTRO es el tipo heredado de documentos custodiados antes del catálogo: se
# nombra, pero no se agrega a TIPOS_DOCUMENTO para que no se admita al cargar.
ETIQUETA_TIPO_HEREDADO = "Otro documento"


def etiqueta_documento(tipo: str | None) -> str:
    """Nombre legible de un tipo de documento; el código si no está en el catálogo."""
    if not tipo:
        return "Documento"
    if tipo.upper() == "OTRO":
        return ETIQUETA_TIPO_HEREDADO
    return TIPOS_DOCUMENTO.get(tipo.upper(), tipo)


def etiqueta_expediente(tipo: str | None) -> str:
    return TIPOS_EXPEDIENTE.get((tipo or "").upper(), tipo or "Sin clasificar")
