import { TIPO_DOCUMENTO_CORTO } from '../constants.js'

/** Etiqueta de la firma binaria a partir del MIME devuelto por el backend. */
export function firmaDeMime(mime) {
  if (mime === 'application/pdf') return { label: 'PDF', firma: '%PDF-' }
  if (mime === 'image/png') return { label: 'PNG', firma: '89 50 4E 47' }
  if (mime === 'image/jpeg') return { label: 'JPEG', firma: 'FF D8 FF' }
  return { label: mime || 'Desconocido', firma: '—' }
}

/** Nombre corto de un tipo de documento para tablas y filtros. */
export const tipoCorto = (tipo) => TIPO_DOCUMENTO_CORTO[tipo] || (tipo === 'OTRO' ? 'Otro' : tipo)
