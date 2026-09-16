/**
 * Catálogo oficial de tipos documentales (espejo de schemas/documento_schema.py
 * → TipoDocumentoEnum, conforme al DOC-05 Regla RIE y DOC-08).
 */
export const TIPOS_DOCUMENTO = [
  { value: 'CSF_SAT', label: 'Constancia de Situación Fiscal (SAT)' },
  { value: 'COMP_DOMICILIO', label: 'Comprobante de Domicilio Fiscal' },
  { value: 'ACTA_CONSTITUTIVA', label: 'Acta Constitutiva / Poder Notarial' },
  { value: 'OPINION_CUMPLIMIENTO', label: 'Opinión de Cumplimiento SAT (Art. 32-D)' },
  { value: 'ESTADO_CUENTA', label: 'Carátula de Estado de Cuenta Bancario' },
]

export const FAMILIAS_REGLA = ['RIE', 'RCV', 'RSC', 'RDS']

export const SEVERIDADES = ['CRITICA', 'ALTA', 'MEDIA', 'MEDIA_ALTA']

/** Mapa de badges de estado de auditoría (paleta corporativa CLAUDE.md). */
export const ESTADO_BADGE = {
  CONFORME: { fg: '#059669', bg: '#ECFDF5', label: 'Conforme' },
  APROBADO: { fg: '#059669', bg: '#ECFDF5', label: 'Aprobado' },
  EN_REVISION: { fg: '#D97706', bg: '#FFFBEB', label: 'En Revisión' },
  REQUIERE_REVISION_HUMANA: { fg: '#D97706', bg: '#FFFBEB', label: 'Revisión Humana' },
  NO_CONFORME: { fg: '#DC2626', bg: '#FEF2F2', label: 'No Conforme' },
  RECHAZADO: { fg: '#DC2626', bg: '#FEF2F2', label: 'Rechazado' },
  BLOQUEADO: { fg: '#DC2626', bg: '#FEF2F2', label: 'Bloqueado' },
}

export const getEstadoBadge = (estado) =>
  ESTADO_BADGE[estado] || { fg: '#475569', bg: '#F1F5F9', label: estado || 'Desconocido' }

/** Firmas binarias (Magic Bytes) para el lector client-side del Nivel 1. */
export const MAGIC_BYTES = [
  { mime: 'application/pdf', label: 'PDF', signature: [0x25, 0x50, 0x44, 0x46, 0x2d] }, // %PDF-
  { mime: 'image/jpeg', label: 'JPEG', signature: [0xff, 0xd8, 0xff] },
  { mime: 'image/png', label: 'PNG', signature: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
]

export const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
