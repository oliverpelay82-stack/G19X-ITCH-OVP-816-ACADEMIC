import { useMemo } from 'react'
import { Skeleton } from './Skeleton.jsx'
import { tonoPorPorcentaje } from '../constants.js'
import { formatBytes } from '../utils/format.js'

const contar = (lista, prueba) => lista.reduce((n, x) => n + (prueba(x) ? 1 : 0), 0)

/**
 * Fila de KPIs: etiqueta en versales, número grande y una línea de desglose
 * que explica de dónde sale la cifra.
 */
export default function MetricsCards({ titulares, expedientes, documentos, loading }) {
  const cards = useMemo(() => {
    const morales = contar(titulares, (t) => t.tipo_persona === 'MORAL')
    const conformes = contar(expedientes, (e) => e.estado_cumplimiento === 'CONFORME')
    const enRevision = contar(expedientes, (e) => e.estado_cumplimiento === 'EN_REVISION')
    const completos = contar(expedientes, (e) => Number(e.porcentaje_completitud || 0) >= 100)
    const bytes = documentos.reduce((acc, d) => acc + Number(d.tamanio_bytes || 0), 0)
    const cumplimiento = expedientes.length
      ? expedientes.reduce((acc, e) => acc + Number(e.porcentaje_completitud || 0), 0) / expedientes.length
      : 0

    return [
      {
        id: 'empresas',
        label: 'Empresas',
        valor: titulares.length,
        desglose: `${morales} morales · ${titulares.length - morales} físicas`,
      },
      {
        id: 'expedientes',
        label: 'Expedientes',
        valor: expedientes.length,
        desglose: `${conformes} conformes · ${enRevision} en revisión`,
      },
      {
        id: 'boveda',
        label: 'Bóveda',
        valor: documentos.length,
        desglose: `${formatBytes(bytes)} bajo custodia`,
      },
      {
        id: 'cumplimiento',
        label: 'Cumplimiento',
        valor: `${cumplimiento.toFixed(0)}%`,
        desglose: `${completos} de ${expedientes.length} expedientes completos`,
        progreso: cumplimiento,
      },
    ]
  }, [titulares, expedientes, documentos])

  return (
    <section className="metrics-grid" aria-label="Indicadores del motor">
      {cards.map((card) => (
        <article className="card metric-card" key={card.id}>
          <p className="metric-label">{card.label}</p>
          {loading ? (
            <>
              <Skeleton w={56} h={28} />
              <Skeleton w="70%" h={11} />
            </>
          ) : (
            <>
              <p className="metric-value tabular">{card.valor}</p>
              <p className="metric-foot">{card.desglose}</p>
            </>
          )}
          {card.progreso !== undefined && (
            <span className="metric-bar" aria-hidden="true">
              <span
                className={`metric-bar-fill metric-bar-fill--${tonoPorPorcentaje(card.progreso)}`}
                style={{ width: `${loading ? 0 : card.progreso}%` }}
              />
            </span>
          )}
        </article>
      ))}
    </section>
  )
}
