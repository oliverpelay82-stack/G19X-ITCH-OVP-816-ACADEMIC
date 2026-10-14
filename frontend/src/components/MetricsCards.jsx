import { useEffect, useMemo, useState } from 'react'
import { Buildings, FolderOpen, TrafficSignal, Vault } from './iconos.js'
import { Skeleton } from './Skeleton.jsx'
import { Card } from './ui/index.js'
import { TIPOS_EXPEDIENTE } from '../constants.js'
import { formatIndice, promedioIndice } from '../utils/indice.js'
import { reducirMovimiento } from '../utils/movimiento.js'
import { plural } from '../utils/format.js'

/** Duración del conteo: el doble de la transición lenta del sistema de diseño. */
const DURACION_CONTEO = 480

// Las cifras cuentan solo la primera vez que llegan los datos en la sesión:
// al volver a Expedientes o a Reportes, o con cada sondeo, se muestran fijas.
let cifrasContadas = false

/**
 * Cifra de una métrica que, en la primera carga, cuenta de 0 a su valor
 * (curva de salida, 480 ms). Terminado el conteo muestra el valor vivo, así
 * que un sondeo posterior la actualiza sin animar. Con «reducir movimiento»
 * no cuenta.
 */
function Cifra({ valor, formato = String }) {
  const [contando] = useState(() => !cifrasContadas && typeof valor === 'number' && valor > 0 && !reducirMovimiento())
  const [mostrado, setMostrado] = useState(0)
  const [terminado, setTerminado] = useState(!contando)
  useEffect(() => {
    if (!contando) return undefined
    const inicio = performance.now()
    let cuadro
    const paso = (ahora) => {
      const avance = Math.min(1, (ahora - inicio) / DURACION_CONTEO)
      setMostrado(valor * (1 - (1 - avance) ** 3))
      if (avance < 1) cuadro = requestAnimationFrame(paso)
      else setTerminado(true)
    }
    cuadro = requestAnimationFrame(paso)
    return () => cancelAnimationFrame(cuadro)
    // Solo al montarse: el destino es el valor con el que llegaron los datos.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])
  return formato(terminado ? valor : Math.round(mostrado))
}

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
      // El semáforo ya está en los filtros de Expedientes y en la gráfica de Reportes: aquí, el reparto por tipo.
      porTipo: TIPOS_EXPEDIENTE.map((t) => ({
        label: t.label.toLowerCase(),
        n: contar(expedientes, (e) => e.tipo_expediente === t.value),
      })).filter((t) => t.n > 0),
      bytes,
      completitud,
      indice: promedioIndice(expedientes),
    }
  }, [titulares, expedientes, documentos])

  // Con los primeros datos a la vista, las cifras ya contaron: no lo repiten.
  useEffect(() => {
    if (!loading) cifrasContadas = true
  }, [loading])

  const tarjetas = [
    {
      id: 'empresas',
      icon: Buildings,
      label: 'Empresas',
      valor: <Cifra valor={titulares.length} />,
      pie: (
        <span className="metric-foot">{`${plural(datos.morales, 'moral', 'morales')} · ${plural(datos.fisicas, 'física', 'físicas')}`}</span>
      ),
    },
    {
      id: 'expedientes',
      icon: FolderOpen,
      label: 'Expedientes',
      valor: <Cifra valor={expedientes.length} />,
      pie: (
        <span className="metric-foot">
          {datos.porTipo.length ? datos.porTipo.map((t) => `${t.n} ${t.label}`).join(' · ') : 'Sin expedientes'}
        </span>
      ),
    },
    {
      id: 'boveda',
      icon: Vault,
      label: 'Bóveda',
      valor: <Cifra valor={documentos.length} />,
      pie: <span className="metric-foot">{`${enMB(datos.bytes)} bajo custodia`}</span>,
    },
    {
      // Índice de cumplimiento del DOC-05 (C6). La completitud (documentos
      // obligatorios presentes) va aparte, con su nombre: no es cumplimiento.
      id: 'cumplimiento',
      icon: TrafficSignal,
      label: 'Cumplimiento',
      valor: <Cifra valor={datos.indice} formato={formatIndice} />,
      pie: <span className="metric-foot">{`Obligatorios presentes: ${datos.completitud.toFixed(0)}%`}</span>,
      progreso: datos.indice ?? 0,
      titulo: 'Promedio del índice de cumplimiento de los expedientes: reglas cumplidas entre reglas aplicables',
    },
  ]

  return (
    <section className="metrics-grid" aria-label="Indicadores del motor">
      {tarjetas.map(({ id, icon: Icono, label, valor, pie, progreso, titulo }, i) => (
        <Card as="article" className="metric-card" key={id} title={titulo} style={{ '--i': i }}>
          <span className="squircle" aria-hidden="true">
            <Icono size={16} />
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
                  className="metric-bar-fill"
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
