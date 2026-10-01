import { useLayoutEffect, useRef, useState } from 'react'
import { reducirMovimiento } from '../../utils/movimiento.js'
import { cx } from './clases.js'

/**
 * Control segmentado para los filtros rápidos. Cada opción admite un conteo
 * y un tono de estado, que se pinta como punto junto a la etiqueta.
 *
 * La opción activa se marca con un indicador que se desliza de una opción a
 * otra. Se anima solo con `transform` (técnica FLIP): el indicador toma de
 * golpe el ancho de la opción nueva y arranca escalado y desplazado sobre la
 * anterior, para volver a su lugar sin escala; en reposo nunca está
 * deformado. Hasta medir (primer render, sin JavaScript) la opción activa se
 * pinta a sí misma, como antes.
 */
export default function Segmented({ opciones, valor, onChange, label, role = 'group' }) {
  const esTabs = role === 'tablist'
  const contenedor = useRef(null)
  const indicador = useRef(null)
  const previo = useRef(null)
  const [deslizante, setDeslizante] = useState(false)
  // Las opciones llegan como arreglo nuevo en cada render: se comparan por contenido.
  const firma = opciones.map((o) => `${o.id}:${o.label}:${o.conteo ?? ''}`).join('|')

  useLayoutEffect(() => {
    const caja = contenedor.current
    const barra = indicador.current
    if (!caja || !barra) return undefined

    const colocar = (animar) => {
      const activo = caja.querySelector('.segmented-item.is-active')
      if (!activo) {
        barra.style.opacity = '0'
        previo.current = null
        return
      }
      const x = activo.offsetLeft
      const w = activo.offsetWidth
      const p = previo.current
      // Sin cambio no se toca nada: el observador de tamaño se dispara al
      // empezar a observar y, si recolocara, cortaría el deslizamiento en curso.
      if (p && p.x === x && p.w === w) return
      barra.style.width = `${w}px`
      barra.style.opacity = '1'
      const desliza = animar && p && (p.x !== x || p.w !== w) && !reducirMovimiento()
      // Sin deslizamiento (primera medición, cambio de tamaño) el indicador
      // se coloca de golpe; con él, parte de la posición y el ancho previos.
      barra.style.transition = 'none'
      if (desliza) barra.style.transform = `translateX(${p.x}px) scaleX(${p.w / w})`
      else barra.style.transform = `translateX(${x}px)`
      barra.getBoundingClientRect() // fija el punto de partida antes de animar
      barra.style.transition = ''
      barra.style.transform = `translateX(${x}px)`
      previo.current = { x, w }
    }

    colocar(true)
    setDeslizante(true)
    // Un cambio de tamaño (conteos que crecen, ventana) recoloca sin animar.
    const observador = new ResizeObserver(() => colocar(false))
    observador.observe(caja)
    return () => observador.disconnect()
  }, [valor, firma])

  return (
    <div ref={contenedor} className={cx('segmented', deslizante && 'segmented--deslizante')} role={role} aria-label={label}>
      <span ref={indicador} className="segmented-indicador" aria-hidden="true" />
      {opciones.map((o) => {
        const activo = valor === o.id
        return (
          <button
            key={o.id}
            type="button"
            role={esTabs ? 'tab' : undefined}
            aria-selected={esTabs ? activo : undefined}
            aria-pressed={esTabs ? undefined : activo}
            className={`segmented-item ${activo ? 'is-active' : ''}`}
            onClick={() => onChange(o.id)}
            data-tooltip={o.tooltip}
          >
            {o.tono && <span className={`status-dot status-dot--${o.tono}`} aria-hidden="true" />}
            {o.label}
            {o.conteo !== undefined && <span className="segmented-count tabular">{o.conteo}</span>}
          </button>
        )
      })}
    </div>
  )
}
