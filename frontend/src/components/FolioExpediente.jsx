import { useEffect, useId, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { Badge } from './ui/index.js'
import { getEstadoBadge, getSeveridadMeta, rangoSeveridad, TIPO_EXPEDIENTE_LABEL } from '../constants.js'
import { formatIndice, indiceDe } from '../utils/indice.js'

const RETARDO = 350 // ms: pasar el cursor de largo no abre nada
const ANCHO = 280

/**
 * D2 · Folio con vista previa: al detener el cursor (o el foco) sobre «EXP-…»
 * aparece una tarjeta con el semáforo, el índice, los obligatorios y la alerta
 * más grave, sin salir de la vista. La tarjeta va en un portal con posición
 * fija, así que ninguna tabla con desplazamiento la recorta.
 *
 * `enfocable={false}` cuando el folio va dentro de un botón o un enlace: un
 * elemento enfocable anidado no es válido y el botón ya lleva al expediente.
 */
export default function FolioExpediente({ expediente, enfocable = true, className = '', children }) {
  const [posicion, setPosicion] = useState(null)
  const ancla = useRef(null)
  const temporizador = useRef(null)
  const id = useId()

  const abrir = () => {
    clearTimeout(temporizador.current)
    temporizador.current = setTimeout(() => {
      const r = ancla.current?.getBoundingClientRect()
      if (!r) return
      const izquierda = Math.min(Math.max(8, r.left), window.innerWidth - ANCHO - 8)
      // Debajo del folio; si no cabe, encima.
      const abajo = window.innerHeight - r.bottom > 200
      setPosicion(abajo ? { left: izquierda, top: r.bottom + 6 } : { left: izquierda, bottom: window.innerHeight - r.top + 6 })
    }, RETARDO)
  }
  const cerrar = () => {
    clearTimeout(temporizador.current)
    setPosicion(null)
  }

  useEffect(() => {
    if (!posicion) return undefined
    const alEscape = (e) => e.key === 'Escape' && cerrar()
    window.addEventListener('keydown', alEscape)
    window.addEventListener('scroll', cerrar, true)
    return () => {
      window.removeEventListener('keydown', alEscape)
      window.removeEventListener('scroll', cerrar, true)
    }
  }, [posicion])
  useEffect(() => () => clearTimeout(temporizador.current), [])

  if (!expediente) return <span className={className}>{children}</span>

  return (
    <>
      <span
        ref={ancla}
        className={`folio-previa ${className}`.trim()}
        tabIndex={enfocable ? 0 : undefined}
        aria-describedby={posicion ? id : undefined}
        onPointerEnter={abrir}
        onPointerLeave={cerrar}
        onFocus={enfocable ? abrir : undefined}
        onBlur={enfocable ? cerrar : undefined}
      >
        {children ?? expediente.codigo_expediente}
      </span>
      {posicion && createPortal(<TarjetaPrevia id={id} expediente={expediente} posicion={posicion} />, document.body)}
    </>
  )
}

function TarjetaPrevia({ id, expediente: e, posicion }) {
  const estado = getEstadoBadge(e.estado_cumplimiento)
  const alertas = [...(e.evaluacion?.alertas || [])].sort((a, b) => rangoSeveridad(a.severidad) - rangoSeveridad(b.severidad))
  const masGrave = alertas[0]
  return (
    <div id={id} role="tooltip" className="folio-tarjeta" style={{ ...posicion, width: ANCHO }}>
      <p className="folio-tarjeta-titulo">{e.titular?.razon_social || 'Titular no disponible'}</p>
      <p className="folio-tarjeta-sub mono">
        {e.codigo_expediente} · {TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente}
      </p>
      <div className="folio-tarjeta-datos">
        <Badge tono={estado.tono} punto>
          {estado.label}
        </Badge>
        <span>
          <strong className="tabular">{formatIndice(indiceDe(e)?.porcentaje)}</strong> cumplimiento
        </span>
        <span>
          <strong className="tabular">{Number(e.porcentaje_completitud || 0).toFixed(0)}%</strong> obligatorios
        </span>
      </div>
      <p className="folio-tarjeta-alerta">
        {masGrave ? (
          <>
            <span className="tabular">
              {alertas.length} {alertas.length === 1 ? 'alerta' : 'alertas'}
            </span>
            {' · '}
            {getSeveridadMeta(masGrave.severidad).label}: {masGrave.titulo}
          </>
        ) : (
          'Sin alertas vigentes'
        )}
      </p>
    </div>
  )
}
