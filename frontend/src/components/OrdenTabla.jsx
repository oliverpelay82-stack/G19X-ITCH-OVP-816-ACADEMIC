import { ArrowDown, ArrowUp, ArrowUpDown } from 'lucide-react'
import { cx } from './ui/clases.js'

/**
 * Encabezado de columna ordenable: un botón con la flecha del sentido y
 * `aria-sort` en la celda. La flecha solo se ve en la columna ordenada o al
 * pasar el cursor, para no cargar el encabezado.
 */
export function EncabezadoOrdenable({ columna, orden, onOrdenar, inicial = 'asc', className, children }) {
  const activo = orden?.columna === columna
  const Icono = !activo ? ArrowUpDown : orden.sentido === 'asc' ? ArrowUp : ArrowDown
  return (
    <th className={className} aria-sort={activo ? (orden.sentido === 'asc' ? 'ascending' : 'descending') : 'none'}>
      <button type="button" className={cx('th-orden', activo && 'is-activo')} onClick={() => onOrdenar(columna, inicial)}>
        {children}
        <Icono size={12} strokeWidth={1.75} aria-hidden="true" />
      </button>
    </th>
  )
}
