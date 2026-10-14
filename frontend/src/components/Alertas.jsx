import { ArrowUpRight, Lightbulb } from './iconos.js'
import { Button, Tag } from './ui/index.js'
import { ALERTA_META, getSeveridadMeta } from '../constants.js'
import FolioExpediente from './FolioExpediente.jsx'

/**
 * Alerta del motor con su recomendación correctiva (RF-18, RF-21) en la
 * bandeja de Alertas. La severidad la dicen el título del grupo y el filete
 * de color (y, para lectores de pantalla, un texto oculto); la recomendación
 * va destacada porque es lo accionable. `expediente` (opcional) ocupa una
 * columna propia con su folio, la empresa y el acceso al expediente. En el
 * detalle del expediente, cada recomendación va bajo su motivo
 * (DetalleExpediente).
 */
export function AlertaItem({ alerta, expediente, onAbrirExpediente, claveFlip, indice = 0 }) {
  const sev = getSeveridadMeta(alerta.severidad)
  const categoria = ALERTA_META[alerta.codigo]?.label || alerta.codigo
  return (
    <li className={`alerta alerta--${sev.tono}`} data-flip={claveFlip} style={{ '--i': indice }}>
      <div className="alerta-cuerpo">
        <div className="alerta-head">
          <span className="sr-only">Severidad {sev.label.toLowerCase()}. </span>
          <Tag>{categoria}</Tag>
          {alerta.regla && <span className="mono cell-muted alerta-regla">{alerta.regla}</span>}
        </div>
        <p className="alerta-titulo">{alerta.titulo}</p>
        <p className="alerta-detalle">{alerta.detalle}</p>
        <p className="alerta-recomendacion">
          <Lightbulb size={14} aria-hidden="true" />
          <span>
            <span className="sr-only">Recomendación: </span>
            {alerta.recomendacion}
          </span>
        </p>
      </div>
      {expediente && (
        <div className="alerta-expediente">
          <span className="eyebrow">Expediente</span>
          <FolioExpediente expediente={expediente.completo} className="mono alerta-expediente-folio">
            {expediente.codigo}
          </FolioExpediente>
          <span className="alerta-expediente-nombre" title={expediente.nombre}>
            {expediente.nombre}
          </span>
          <Button compacto icono={ArrowUpRight} onClick={() => onAbrirExpediente?.(expediente.id)}>
            Abrir expediente
          </Button>
        </div>
      )}
    </li>
  )
}
