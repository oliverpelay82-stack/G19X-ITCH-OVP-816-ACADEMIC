/**
 * Catálogo oficial de tipos documentales (espejo de schemas/documento_schema.py
 * → TipoDocumentoEnum, conforme al DOC-05 Regla RIE y DOC-08).
 */
export const TIPOS_DOCUMENTO = [
  { value: 'CSF_SAT', label: 'Constancia de Situación Fiscal (SAT)', corto: 'CSF SAT' },
  { value: 'COMP_DOMICILIO', label: 'Comprobante de Domicilio Fiscal', corto: 'Domicilio' },
  { value: 'ACTA_CONSTITUTIVA', label: 'Acta Constitutiva / Poder Notarial', corto: 'Acta' },
  { value: 'OPINION_CUMPLIMIENTO', label: 'Opinión de Cumplimiento SAT (Art. 32-D)', corto: 'Opinión 32-D' },
  { value: 'ESTADO_CUENTA', label: 'Carátula de Estado de Cuenta Bancario', corto: 'Edo. Cuenta' },
]

export const TIPO_DOCUMENTO_LABEL = Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.label]))
export const TIPO_DOCUMENTO_CORTO = Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.corto]))

export const FAMILIAS_REGLA = ['RIE', 'RCV', 'RSC', 'RDS']

/** Metadatos de cada familia normativa del DOC-05. */
export const FAMILIA_META = {
  RIE: { nombre: 'Integridad y Estructura', nivel: 'Niveles 1 y 2', clase: 'rie' },
  RCV: { nombre: 'Cronológicas y de Vigencia', nivel: 'Nivel 2', clase: 'rcv' },
  RSC: { nombre: 'Semánticas y Contractuales', nivel: 'Nivel 4 — IA', clase: 'rsc' },
  RDS: { nombre: 'Dinámicas y Sectoriales', nivel: 'Configurables', clase: 'rds' },
}

export const SEVERIDADES = ['CRITICA', 'ALTA', 'MEDIA_ALTA', 'MEDIA']

/** Severidades con su etiqueta legible y el tono de estado que les toca. */
export const SEVERIDAD_META = {
  CRITICA: { label: 'Crítica', tono: 'bad' },
  ALTA: { label: 'Alta', tono: 'warn' },
  MEDIA_ALTA: { label: 'Media-Alta', tono: 'warn' },
  MEDIA: { label: 'Media', tono: 'brand' },
}

export const getSeveridadMeta = (severidad) =>
  SEVERIDAD_META[severidad] || { label: severidad || 'Sin severidad', tono: 'neutral' }

/** Los tres microservicios del DOC-08, tal como los expone docker-compose. */
export const SERVICIOS = [
  { key: 'core', nombre: 'Core Service', corto: 'Core', puerto: 8001, alcance: 'Titulares · Expedientes · Bóveda' },
  { key: 'rules', nombre: 'Rules Service', corto: 'Rules', puerto: 8002, alcance: 'Catálogo de reglas (Nivel 2)' },
  { key: 'ai', nombre: 'AI Service', corto: 'AI', puerto: 8003, alcance: 'Extracción y análisis semántico' },
]

/**
 * Mapa de estados de auditoría. `tono` apunta a los tokens de estado del
 * sistema de diseño; ningún estado se comunica solo con color, siempre
 * viaja acompañado de su etiqueta.
 */
export const ESTADO_BADGE = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  APROBADO: { tono: 'ok', label: 'Aprobado' },
  EN_REVISION: { tono: 'warn', label: 'En Revisión' },
  REQUIERE_REVISION_HUMANA: { tono: 'warn', label: 'Revisión Humana' },
  PENDIENTE: { tono: 'warn', label: 'Pendiente' },
  NO_CONFORME: { tono: 'bad', label: 'No Conforme' },
  RECHAZADO: { tono: 'bad', label: 'Rechazado' },
  BLOQUEADO: { tono: 'bad', label: 'Bloqueado' },
}

export const getEstadoBadge = (estado) =>
  ESTADO_BADGE[estado] || { tono: 'neutral', label: estado || 'Sin estado' }

/** Umbrales del semáforo de completitud documental (DOC-05). */
export function tonoPorPorcentaje(pct) {
  if (pct >= 100) return 'ok'
  if (pct >= 60) return 'warn'
  return 'bad'
}

/** Firmas binarias (Magic Bytes) para el lector client-side del Nivel 1. */
export const MAGIC_BYTES = [
  { mime: 'application/pdf', label: 'PDF', signature: [0x25, 0x50, 0x44, 0x46, 0x2d] }, // %PDF-
  { mime: 'image/jpeg', label: 'JPEG', signature: [0xff, 0xd8, 0xff] },
  { mime: 'image/png', label: 'PNG', signature: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
]

export const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
