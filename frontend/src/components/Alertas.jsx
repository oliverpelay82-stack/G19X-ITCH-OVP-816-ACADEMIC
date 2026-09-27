import { ArrowUpRight, Lightbulb } from 'lucide-react'
import { ALERTA_META, getSeveridadMeta } from '../constants.js'

/**
 * Alerta del motor con su recomendación correctiva (RF-18, RF-21). La
 * severidad se comunica con color y etiqueta; la recomendación va destacada
 * porque es lo accionable. `expediente` (opcional) muestra a qué expediente
 * pertenece y permite abrirlo desde la bandeja general.
 */
export function AlertaItem({ alerta, expediente, onAbrirExpediente }) {
  const sev = getSeveridadMeta(alerta.severidad)
  const categoria = ALERTA_META[alerta.codigo]?.label || alerta.codigo
  return (
    <li className={`alerta alerta--${sev.tono}`}>
      <div className="alerta-head">
        <span className={`badge badge--${sev.tono}`}>
          <span className={`status-dot status-dot--${sev.tono}`} aria-hidden="true" />
          {sev.label}
        </span>
        <span className="tag">{categoria}</span>
        {alerta.regla && <span className="mono cell-muted alerta-regla">{alerta.regla}</span>}
        {expediente && (
          <button type="button" className="alerta-exp" onClick={() => onAbrirExpediente?.(expediente.id)}>
            <span className="mono">{expediente.codigo}</span>
            <span className="alerta-exp-nombre">{expediente.nombre}</span>
            <ArrowUpRight size={12} strokeWidth={1.75} aria-hidden="true" />
          </button>
        )}
      </div>
      <p className="alerta-titulo">{alerta.titulo}</p>
      <p className="alerta-detalle">{alerta.detalle}</p>
      <p className="alerta-recomendacion">
        <Lightbulb size={13} aria-hidden="true" />
        <span>
          <span className="sr-only">Recomendación: </span>
          {alerta.recomendacion}
        </span>
      </p>
    </li>
  )
}

export function ListaAlertas({ alertas }) {
  return (
    <ul className="alerta-lista">
      {alertas.map((a, i) => (
        <AlertaItem key={`${a.codigo}-${a.tipo_documento}-${i}`} alerta={a} />
      ))}
    </ul>
  )
}
