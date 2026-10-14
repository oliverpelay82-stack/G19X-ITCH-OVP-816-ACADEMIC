import { CloudSlash } from './iconos.js'

/**
 * Estado vacío de una vista cuyo servicio no responde y que no tiene datos que
 * mostrar (props de EmptyState o EmptyRow). Una lista vacía por una caída no es
 * «aún no hay…» ni «todo cumple»: la vista dice que el servicio no responde y
 * que se actualizará sola (el sondeo de App.jsx corre cada 15 s).
 */
export function sinRespuesta(titulo, descripcion) {
  return { icon: CloudSlash, titulo, descripcion }
}

/** Título común de las vistas del core-service (Empresas, Expedientes, Bóveda, Alertas y Reportes). */
export const CORE_FUERA_DE_LINEA = 'Sistema de expedientes fuera de línea'
