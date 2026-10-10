import { Cell, Pie, PieChart, ResponsiveContainer, Tooltip } from 'recharts'
import { formatIndice, promedioIndice } from '../../utils/indice.js'
import { DatosDeLaGrafica, Leyenda, TarjetaGrafica, TooltipGrafica } from './comun.jsx'
import { animar, SEPARACION } from './estilo.js'
import { plural } from '../../utils/format.js'

const ESTADOS = [
  { clave: 'CONFORME', etiqueta: 'Conforme', color: 'var(--chart-ok)' },
  { clave: 'EN_REVISION', etiqueta: 'En revisión', color: 'var(--chart-warn)' },
  { clave: 'NO_CONFORME', etiqueta: 'No conforme', color: 'var(--chart-bad)' },
]

const expedientesTexto = (n) => plural(n, 'expediente', 'expedientes')
const pct = (n, total) => (total ? `${Math.round((n / total) * 100)}%` : '0%')

/**
 * V1 · ¿Cómo estamos? El semáforo de todos los expedientes como anillo, con el
 * índice de cumplimiento promedio al centro (RF-22; C6 del DOC-05). Un clic en
 * un sector abre la lista de Expedientes filtrada por ese estado (`onSeleccionar`).
 */
export default function AnilloSemaforo({ expedientes, onSeleccionar }) {
  const total = expedientes.length
  const datos = ESTADOS.map((e) => ({ ...e, n: expedientes.filter((x) => x.estado_cumplimiento === e.clave).length }))
  const indice = promedioIndice(expedientes)

  return (
    <TarjetaGrafica titulo="Semáforo de los expedientes" subtitulo={`${expedientesTexto(total)} ${total === 1 ? 'evaluado' : 'evaluados'}`}>
      <div className="anillo">
        <ResponsiveContainer width="100%" height={180}>
          <PieChart>
            <Pie
              data={datos.filter((d) => d.n > 0)}
              dataKey="n"
              nameKey="etiqueta"
              innerRadius={62}
              outerRadius={82}
              startAngle={90}
              endAngle={-270}
              cornerRadius={5}
              isAnimationActive={animar()}
              animationDuration={800}
              onClick={(sector) => {
                const clave = sector?.payload?.clave ?? sector?.clave
                if (clave) onSeleccionar?.(clave)
              }}
              {...SEPARACION}
            >
              {datos
                .filter((d) => d.n > 0)
                .map((d) => (
                  <Cell key={d.clave} fill={d.color} style={onSeleccionar ? { cursor: 'pointer' } : undefined} />
                ))}
            </Pie>
            <Tooltip
              content={({ active, payload }) =>
                active && payload?.length ? (
                  <TooltipGrafica
                    filas={[{ etiqueta: payload[0].payload.etiqueta, valor: expedientesTexto(payload[0].payload.n), color: payload[0].payload.color }]}
                    nota={`${pct(payload[0].payload.n, total)} del total`}
                  />
                ) : null
              }
            />
          </PieChart>
        </ResponsiveContainer>
        {/* La cifra protagonista va en HTML sobre el anillo: no estorba al puntero. */}
        <div className="anillo-centro" aria-hidden="true">
          <span className="anillo-cifra">{formatIndice(indice)}</span>
          <span className="anillo-pie">índice promedio</span>
        </div>
      </div>
      <p className="sr-only">Índice de cumplimiento promedio: {formatIndice(indice)}.</p>
      <Leyenda elementos={datos.map((d) => ({ etiqueta: d.etiqueta, color: d.color, valor: `${d.n} · ${pct(d.n, total)}` }))} />
      <DatosDeLaGrafica
        columnas={['Estado', 'Expedientes', 'Porcentaje']}
        filas={datos.map((d) => [d.etiqueta, d.n, pct(d.n, total)])}
      />
    </TarjetaGrafica>
  )
}
