import { cloneElement, isValidElement } from 'react'

/**
 * Micro-indicador para acciones compactas. Envuelve un único elemento y le
 * añade `data-tooltip`: el globo lo pinta App.css ([data-tooltip]::after) al
 * pasar el cursor o al enfocar con el teclado (:focus-visible), sin montar
 * nodos ni listeners.
 *
 * El contenido de un pseudo-elemento no llega a todos los lectores de
 * pantalla; si el hijo no tiene texto visible (un icono), `nombra` usa el
 * texto del tooltip como su nombre accesible (aria-label), salvo que ya
 * tenga uno.
 */
export default function Tooltip({ texto, nombra = false, children }) {
  if (!isValidElement(children)) return children
  const extra = { 'data-tooltip': texto }
  if (nombra && !children.props['aria-label']) extra['aria-label'] = texto
  return cloneElement(children, extra)
}
