import { useMemo } from 'react'
import { Skeleton } from './Skeleton.jsx'

/**
 * Fila de KPIs: cada tarjeta es un número grande con su etiqueta debajo.
 * La profundidad la da el contraste de superficie, no las sombras.
 */
export default function MetricsCards({ titulares, expedientes, documentos, loading }) {
  const cumplimiento = useMemo(() => {
    if (!expedientes.length) return 0
    return expedientes.reduce((acc, e) => acc + Number(e.porcentaje_completitud || 0), 0) / expedientes.length
  }, [expedientes])

  const cards = [
    { id: 'empresas', label: 'Empresas registradas', value: titulares.length },
    { id: 'expedientes', label: 'Expedientes activos', value: expedientes.length },
    { id: 'boveda', label: 'Documentos en bóveda', value: documentos.length },
    { id: 'cumplimiento', label: 'Cumplimiento global', value: `${cumplimiento.toFixed(0)}%` },
  ]

  return (
    <section className="metrics-grid" aria-label="Indicadores del motor">
      {cards.map((card) => (
        <article className="card metric-card" key={card.id}>
          {loading ? <Skeleton w={64} h={32} /> : <p className="metric-value">{card.value}</p>}
          <p className="metric-label">{card.label}</p>
        </article>
      ))}
    </section>
  )
}
