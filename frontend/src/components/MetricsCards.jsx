import { useMemo } from 'react'
import { Building2, FolderKanban, Gauge, Vault } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import { Card } from './ui/index.js'
import { tonoPorPorcentaje } from '../constants.js'

const contar = (lista, prueba) => lista.reduce((n, x) => n + (prueba(x) ? 1 : 0), 0)

/** Tamaño agregado de la bóveda siempre en MB, para que la cifra sea comparable. */
const enMB = (bytes) => `${(bytes / (1024 * 1024)).toLocaleString('es-MX', { maximumFractionDigits: 1 })} MB`

/**
 * Fila de KPIs compacta: cuatro tarjetas de igual ancho con icono en
 * micro-squircle, etiqueta en versales, cifra tabular y, debajo, un desglose
 * que explica de dónde sale el número (nunca se recorta). Se elevan 1 px al
 * pasar el cursor.
 */
export default function MetricsCards({ titulares, expedientes, documentos, loading }) {
  const datos = useMemo(() => {
    const morales = contar(titulares, (t) => t.tipo_persona === 'MORAL')
    const bytes = documentos.reduce((acc, d) => acc + Number(d.tamanio_bytes || 0), 0)
    const completitud = expedientes.length
      ? expedientes.reduce((acc, e) => acc + Number(e.porcentaje_completitud || 0), 0) / expedientes.length
      : 0
    return {
      morales,
      fisicas: titulares.length - morales,
      semaforo: [
        { id: 'ok', label: ['conforme', 'conformes'], n: contar(expedientes, (e) => e.estado_cumplimiento === 'CONFORME') },
        { id: 'warn', label: ['en revisión', 'en revisión'], n: contar(expedientes, (e) => e.estado_cumplimiento === 'EN_REVISION') },
        { id: 'bad', label: ['no conforme', 'no conformes'], n: contar(expedientes, (e) => e.estado_cumplimiento === 'NO_CONFORME') },
      ],
      bytes,
      completitud,
      completos: contar(expedientes, (e) => Number(e.porcentaje_completitud || 0) >= 100),
    }
  }, [titulares, expedientes, documentos])

  const tarjetas = [
    {
      id: 'empresas',
      icon: Building2,
      label: 'Empresas',
      valor: titulares.length,
      pie: (
        <span className="metric-foot">{`${datos.morales} ${datos.morales === 1 ? 'moral' : 'morales'} · ${datos.fisicas} ${datos.fisicas === 1 ? 'física' : 'físicas'}`}</span>
      ),
    },
    {
      id: 'expedientes',
      icon: FolderKanban,
      label: 'Expedientes',
      valor: expedientes.length,
      pie: (
        <span className="metric-estados" aria-label="Semáforo de expedientes">
          {datos.semaforo.map((s) => (
            <span key={s.id} className={`metric-estado metric-estado--${s.id}`}>
              <span className={`status-dot status-dot--${s.id}`} aria-hidden="true" />
              <strong className="tabular">{s.n}</strong>
              {s.label[s.n === 1 ? 0 : 1]}
            </span>
          ))}
        </span>
      ),
    },
    {
      id: 'boveda',
      icon: Vault,
      label: 'Bóveda',
      valor: documentos.length,
      pie: <span className="metric-foot">{`${enMB(datos.bytes)} bajo custodia`}</span>,
    },
    {
      id: 'completitud',
      icon: Gauge,
      label: 'Completitud',
      valor: `${datos.completitud.toFixed(0)}%`,
      pie: <span className="metric-foot">{`${datos.completos} de ${expedientes.length} expedientes completos`}</span>,
      progreso: datos.completitud,
    },
  ]

  return (
    <section className="metrics-grid" aria-label="Indicadores del motor">
      {tarjetas.map(({ id, icon: Icono, label, valor, pie, progreso }) => (
        <Card as="article" className="metric-card" key={id}>
          <span className="squircle" aria-hidden="true">
            <Icono size={15} />
          </span>
          <div className="metric-text">
            <p className="metric-label">{label}</p>
            {loading ? (
              <Skeleton w={110} h={20} />
            ) : (
              <div className="metric-body">
                <p className="metric-value tabular">{valor}</p>
                {pie}
              </div>
            )}
            {progreso !== undefined && (
              <span className="metric-bar" aria-hidden="true">
                <span
                  className={`metric-bar-fill metric-bar-fill--${tonoPorPorcentaje(progreso)}`}
                  style={{ width: `${loading ? 0 : progreso}%` }}
                />
              </span>
            )}
          </div>
        </Card>
      ))}
    </section>
  )
}
