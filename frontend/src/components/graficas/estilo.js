import { reducirMovimiento } from '../../utils/movimiento.js'

/**
 * Parámetros visuales de las gráficas de Reportes. Los colores son tokens de
 * index.css (--chart-*, --line, --text-muted): el tema oscuro los redefine.
 */

/** Las gráficas se dibujan sin animación si el sistema pide reducir movimiento. */
export const animar = () => !reducirMovimiento()

/** Ejes y retícula: líneas finas y recesivas, cifras en texto atenuado. */
export const EJE = {
  tick: { fill: 'var(--text-muted)', fontSize: 11 },
  axisLine: { stroke: 'var(--line)' },
  tickLine: false,
}
export const RETICULA = { stroke: 'var(--line)', strokeDasharray: '' }

/** Separación de 2 px entre marcas que se tocan, del color de la superficie. */
export const SEPARACION = { stroke: 'var(--bg-surface)', strokeWidth: 2 }
