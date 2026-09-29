import { ArrowUpRight, Lightbulb } from 'lucide-react'
import { Badge, Tag } from './ui/index.js'
import { ALERTA_META, getSeveridadMeta, SEVERIDADES } from '../constants.js'

/**
 * Alerta del motor con su recomendación correctiva (RF-18, RF-21). La
 * severidad se comunica con color y etiqueta; la recomendación va destacada
 * porque es lo accionable. `expediente` (opcional) muestra a qué expediente
 * pertenece y permite abrirlo desde la bandeja general. `compacto` deja a la
 * vista el título y la recomendación y pliega el detalle: en el detalle del
 * expediente, los motivos del semáforo ya dicen por qué.
 */
export function AlertaItem({ alerta, expediente, onAbrirExpediente, compacto = false }) {
  const sev = getSeveridadMeta(alerta.severidad)
  const categoria = ALERTA_META[alerta.codigo]?.label || alerta.codigo
  return (
    <li className={`alerta alerta--${sev.tono}`}>
      <div className="alerta-head">
        <Badge tono={sev.tono} punto>
          {sev.label}
        </Badge>
        <Tag>{categoria}</Tag>
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
      {compacto ? (
        alerta.detalle && (
          <details className="alerta-mas">
            <summary>Ver detalle</summary>
            <p className="alerta-detalle">{alerta.detalle}</p>
          </details>
        )
      ) : (
        <p className="alerta-detalle">{alerta.detalle}</p>
      )}
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

export function ListaAlertas({ alertas, compacto = false }) {
  return (
    <ul className="alerta-lista">
      {alertas.map((a, i) => (
        <AlertaItem key={`${a.codigo}-${a.tipo_documento}-${i}`} alerta={a} compacto={compacto} />
      ))}
    </ul>
  )
}

/**
 * Alertas agrupadas por severidad, de la más grave a la menos grave. Las
 * críticas y altas se muestran abiertas; las demás, plegadas con su conteo,
 * para que un expediente con muchas alertas no esconda lo urgente.
 */
export function ListaAlertasAgrupadas({ alertas, compacto = false }) {
  const grupos = SEVERIDADES.map((sev) => ({ sev, items: alertas.filter((a) => a.severidad === sev) }))
    .concat([{ sev: null, items: alertas.filter((a) => !SEVERIDADES.includes(a.severidad)) }])
    .filter((g) => g.items.length)
  return (
    <div className="alerta-grupos">
      {grupos.map(({ sev, items }) => {
        const meta = getSeveridadMeta(sev)
        return (
          <details key={sev || 'otras'} className="alerta-grupo" open={sev === 'CRITICA' || sev === 'ALTA'}>
            <summary>
              <Badge tono={meta.tono} punto>
                {sev ? meta.label : 'Otras'}
              </Badge>
              <span className="tabular cell-muted">{items.length}</span>
            </summary>
            <ListaAlertas alertas={items} compacto={compacto} />
          </details>
        )
      })}
    </div>
  )
}
