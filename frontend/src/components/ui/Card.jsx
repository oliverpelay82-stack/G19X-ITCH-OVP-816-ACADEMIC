import { cx } from './clases.js'

/**
 * Superficie estándar (`.card`): blanco puro, borde de 1 px, radio de
 * tarjeta y micro-sombra. `as` elige el elemento semántico (article para un
 * perfil o expediente, section para un bloque de reporte). La variante la da
 * la clase del contexto (`table-card`, `report-card`, `metric-card`…).
 */
export default function Card({ as: Elemento = 'div', className, children, ...props }) {
  return (
    <Elemento className={cx('card', className)} {...props}>
      {children}
    </Elemento>
  )
}
