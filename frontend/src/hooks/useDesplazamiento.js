import { useLayoutEffect, useRef } from 'react'
import { CURVA, DURACION_LENTA, reducirMovimiento } from '../utils/movimiento.js'

/** Por encima de este número de elementos no se anima: medirlos costaría más de lo que aporta. */
const MAXIMO_ELEMENTOS = 150

/**
 * Desplazamiento animado de una lista que cambia (técnica FLIP): cuando se
 * reordena, se filtra o pierde un elemento, los que permanecen se deslizan
 * desde su posición anterior en lugar de saltar, y los nuevos entran con un
 * fundido. Devuelve la referencia del contenedor; cada elemento animable
 * lleva `data-flip` con una clave estable (su id, nunca su índice).
 *
 * Solo anima cuando cambia la secuencia de claves: un nuevo render con la
 * misma lista (un sondeo, un tooltip) o un desplazamiento por algo ajeno
 * (desplegar un expediente) no mueve nada. Las posiciones se miden contra el
 * contenedor, así que desplazar la página entre dos cambios no las altera.
 */
export default function useDesplazamiento() {
  const contenedor = useRef(null)
  const previo = useRef({ firma: null, posiciones: null })

  useLayoutEffect(() => {
    const raiz = contenedor.current
    const elementos = raiz ? [...raiz.querySelectorAll('[data-flip]')] : []
    if (elementos.length === 0 || elementos.length > MAXIMO_ELEMENTOS) {
      previo.current = { firma: null, posiciones: null }
      return
    }
    const firma = elementos.map((el) => el.dataset.flip).join('|')
    const anterior = previo.current
    const cambio = anterior.posiciones !== null && firma !== anterior.firma && !reducirMovimiento()
    // Un desplazamiento en curso se cancela antes de medir la posición de destino.
    if (cambio) elementos.forEach((el) => el.getAnimations().forEach((a) => a.id === 'flip' && a.cancel()))

    const base = raiz.getBoundingClientRect()
    const posiciones = new Map()
    for (const el of elementos) {
      const r = el.getBoundingClientRect()
      posiciones.set(el.dataset.flip, { x: r.left - base.left, y: r.top - base.top })
    }
    previo.current = { firma, posiciones }
    if (!cambio) return

    for (const el of elementos) {
      const antes = anterior.posiciones.get(el.dataset.flip)
      const ahora = posiciones.get(el.dataset.flip)
      if (!antes) {
        el.animate([{ opacity: 0 }, { opacity: 1 }], { id: 'flip', duration: DURACION_LENTA, easing: CURVA })
        continue
      }
      const dx = antes.x - ahora.x
      const dy = antes.y - ahora.y
      if (Math.abs(dx) < 1 && Math.abs(dy) < 1) continue
      el.animate([{ transform: `translate(${dx}px, ${dy}px)` }, { transform: 'none' }], {
        id: 'flip',
        duration: DURACION_LENTA,
        easing: CURVA,
      })
    }
  })

  return contenedor
}
