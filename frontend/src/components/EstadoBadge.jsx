import { Badge } from './ui/index.js'
import { ESTADO_BADGE } from '../constants.js'

/**
 * Insignia de un estado del dominio: el semáforo del expediente, el estatus de
 * un dictamen (ESTADO_BADGE, por omisión) o el estado de un documento
 * (`mapa={ESTADO_DOCUMENTO}`). Toma el tono y la etiqueta del mapa, así que
 * ninguna vista los arma a mano. `children` sustituye la etiqueta cuando la
 * vista dice algo más preciso («Vencido»); `respaldo` es la clave del mapa
 * para un estado desconocido.
 */
export default function EstadoBadge({ estado, mapa = ESTADO_BADGE, respaldo, punto = true, grande = false, children, ...props }) {
  const meta = mapa[estado] || mapa[respaldo] || { tono: 'neutral', label: estado || 'Sin estado' }
  return (
    <Badge tono={meta.tono} punto={punto} grande={grande} {...props}>
      {children ?? meta.label}
    </Badge>
  )
}
