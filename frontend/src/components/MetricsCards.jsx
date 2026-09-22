import { useMemo } from 'react'
import { Activity, Building2, FolderKanban, ShieldCheck, Vault } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import { SERVICIOS, tonoPorPorcentaje } from '../constants.js'

/**
 * Anillo de progreso. Es un medidor de un solo valor: la pista no es gris
 * neutro sino un paso claro del mismo tono que el relleno, para que el
 * estado se lea a lo largo de todo el arco.
 */
function ProgressRing({ value, tono, size = 62, stroke = 6 }) {
  const radio = (size - stroke) / 2
  const circunferencia = 2 * Math.PI * radio
  const avance = Math.max(0, Math.min(100, value))
  const offset = circunferencia - (avance / 100) * circunferencia

  return (
    <svg
      className="ring"
      width={size}
      height={size}
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label={`${avance.toFixed(0)} por ciento`}
      style={{ '--ring-circumference': circunferencia }}
    >
      <circle
        className={`ring-track ring-track--${tono}`}
        cx={size / 2}
        cy={size / 2}
        r={radio}
        fill="none"
        strokeWidth={stroke}
      />
      <circle
        className={`ring-fill ring-fill--${tono}`}
        cx={size / 2}
        cy={size / 2}
        r={radio}
        fill="none"
        strokeWidth={stroke}
        strokeLinecap="round"
        strokeDasharray={circunferencia}
        strokeDashoffset={offset}
        transform={`rotate(-90 ${size / 2} ${size / 2})`}
      />
    </svg>
  )
}

/**
 * Fila de KPIs ejecutivos. Cada tarjeta es un "stat tile": el número es el
 * dato, no hay gráfica de una sola barra. El valor va en tinta primaria y es
 * el icono o el medidor quien carga el tono de estado.
 */
export default function MetricsCards({ titulares, expedientes, documentos, health, loading }) {
  const metricas = useMemo(() => {
    const totalExpedientes = expedientes.length
    const cumplimiento = totalExpedientes
      ? expedientes.reduce((acc, e) => acc + Number(e.porcentaje_completitud || 0), 0) / totalExpedientes
      : 0
    const conformes = expedientes.filter((e) => Number(e.porcentaje_completitud || 0) >= 100).length
    const bytes = documentos.reduce((acc, d) => acc + Number(d.tamanio_bytes || 0), 0)
    const serviciosArriba = SERVICIOS.filter((s) => health?.[s.key]?.online).length
    const saludMotor = (serviciosArriba / SERVICIOS.length) * 100
    return { totalExpedientes, cumplimiento, conformes, bytes, serviciosArriba, saludMotor }
  }, [expedientes, documentos, health])

  const megas = metricas.bytes / (1024 * 1024)

  const cards = [
    {
      id: 'empresas',
      icon: Building2,
      tono: 'brand',
      label: 'Empresas registradas',
      value: titulares.length,
      pie: `${titulares.filter((t) => t.tipo_persona === 'MORAL').length} morales · ${
        titulares.filter((t) => t.tipo_persona === 'FISICA').length
      } físicas`,
    },
    {
      id: 'expedientes',
      icon: FolderKanban,
      tono: 'warn',
      label: 'Expedientes activos',
      value: metricas.totalExpedientes,
      pie: `${metricas.conformes} al 100 % de completitud`,
    },
    {
      id: 'boveda',
      icon: Vault,
      tono: 'vault',
      label: 'Documentos en bóveda',
      value: documentos.length,
      pie: `${megas < 1 ? `${(metricas.bytes / 1024).toFixed(0)} KB` : `${megas.toFixed(1)} MB`} bajo custodia`,
    },
  ]

  const tonoCumplimiento = tonoPorPorcentaje(metricas.cumplimiento)
  const tonoSalud = metricas.saludMotor === 100 ? 'ok' : metricas.saludMotor >= 60 ? 'warn' : 'bad'

  return (
    <section className="metrics-grid" aria-label="Indicadores del motor">
      {cards.map((card) => (
        <article className="metric-card" key={card.id}>
          <div className="metric-card-head">
            <span className={`metric-icon metric-icon--${card.tono}`}>
              <card.icon size={17} strokeWidth={2.3} />
            </span>
            <span className="metric-label">{card.label}</span>
          </div>
          {loading ? (
            <Skeleton w={84} h={38} style={{ margin: '4px 0 10px' }} />
          ) : (
            <p className="metric-value">{card.value}</p>
          )}
          {loading ? <Skeleton w="70%" h={12} /> : <p className="metric-foot">{card.pie}</p>}
        </article>
      ))}

      <article className="metric-card metric-card--gauge">
        <div className="metric-card-head">
          <span className={`metric-icon metric-icon--${tonoCumplimiento}`}>
            <ShieldCheck size={17} strokeWidth={2.3} />
          </span>
          <span className="metric-label">Cumplimiento global</span>
        </div>

        <div className="gauge-row">
          <div className="gauge-ring">
            {loading ? (
              <Skeleton w={62} h={62} r="50%" />
            ) : (
              <>
                <ProgressRing value={metricas.cumplimiento} tono={tonoCumplimiento} />
                <span className="gauge-ring-value">{metricas.cumplimiento.toFixed(0)}%</span>
              </>
            )}
          </div>
          <div className="gauge-detail">
            {loading ? (
              <>
                <Skeleton w="80%" h={12} />
                <Skeleton w="60%" h={12} style={{ marginTop: 8 }} />
              </>
            ) : (
              <>
                <p className="metric-foot">
                  Promedio de completitud documental sobre {metricas.totalExpedientes}{' '}
                  {metricas.totalExpedientes === 1 ? 'expediente' : 'expedientes'}.
                </p>
                <span className={`chip-status chip-status--${tonoSalud}`}>
                  <Activity size={12} strokeWidth={2.6} />
                  Motor {metricas.serviciosArriba}/{SERVICIOS.length} servicios
                </span>
              </>
            )}
          </div>
        </div>
      </article>
    </section>
  )
}
