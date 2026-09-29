// Stepper de las etapas de la auditoría.
import { Check, Loader2, Minus, X } from 'lucide-react'
import { Badge } from '../ui/index.js'
import { ETAPAS } from './etapas.js'

/**
 * Stepper de tres etapas. Mientras corre muestra la etapa activa; al terminar
 * queda como traza compacta del pipeline con el detalle de cada etapa. Una
 * etapa omitida por un fallo anterior se muestra en gris neutro, sin color de
 * estado: no dice nada sobre el cumplimiento del documento.
 */
export function Stepper({ etapas, compacto }) {
  return (
    <ol className={`stepper ${compacto ? 'stepper--compact' : ''}`} role="status" aria-live="polite">
      {ETAPAS.map((e, i) => {
        const { estado, detalle } = etapas[e.id]
        return (
          <li key={e.id} className={`step step--${estado}`}>
            <span className="step-marker" aria-hidden="true">
              {estado === 'activo' && <Loader2 className="spin" size={11} strokeWidth={1.75} />}
              {estado === 'hecho' && <Check size={11} strokeWidth={1.75} />}
              {estado === 'error' && <X size={11} strokeWidth={1.75} />}
              {estado === 'omitido' && <Minus size={11} strokeWidth={1.75} />}
              {(estado === 'pendiente' || estado === 'espera') && <span className="step-num">{i + 1}</span>}
            </span>
            <span className="step-body">
              <span className="step-label">
                {e.label}
                <span className="step-level">{e.nivel}</span>
                {estado === 'omitido' && <Badge tono="skip">Omitido</Badge>}
              </span>
              <span className="step-detail" title={detalle || undefined}>
                {detalle || (estado === 'pendiente' ? 'En cola' : ' ')}
              </span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}
