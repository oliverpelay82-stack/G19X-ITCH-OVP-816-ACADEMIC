import { useEffect, useState } from 'react'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getBitacora } from '../../services/api.js'
import { Skeleton } from '../Skeleton.jsx'
import { agruparCambios, DIAS, diaCorto, LIMITE } from './cambios.js'
import { DatosDeLaGrafica, Leyenda, TarjetaGrafica, TooltipGrafica } from './comun.jsx'
import { animar, EJE, RETICULA } from './estilo.js'

const MEJORA = { etiqueta: 'Mejoraron', color: 'var(--chart-ok)' }
const DETERIORO = { etiqueta: 'Empeoraron', color: 'var(--chart-bad)' }

/**
 * V4 · ¿Hacia dónde vamos? Cuántos expedientes mejoraron o empeoraron su
 * semáforo cada día de los últimos 30, según la bitácora inmutable. La
 * tendencia sale de eventos ya registrados: no requiere guardar historia.
 */
export default function CambiosSemaforo() {
  const [eventos, setEventos] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    getBitacora({ evento: 'EVALUACION_REGLAS', limite: LIMITE })
      .then((r) => vigente && setEventos(r))
      .catch((e) => vigente && setError(e?.message || 'No se pudo consultar la bitácora.'))
    return () => {
      vigente = false
    }
  }, [])

  const dias = eventos ? agruparCambios(eventos) : []
  const mejoras = dias.reduce((n, d) => n + d.mejoras, 0)
  const deterioros = -dias.reduce((n, d) => n + d.deterioros, 0)
  const truncada = eventos?.length === LIMITE

  return (
    <TarjetaGrafica
      titulo="Cambios del semáforo"
      subtitulo={eventos ? `Últimos ${DIAS} días · ${mejoras} ${mejoras === 1 ? 'mejora' : 'mejoras'}, ${deterioros} ${deterioros === 1 ? 'deterioro' : 'deterioros'}` : `Últimos ${DIAS} días`}
    >
      {error && <p className="grafica-vacia">{error}</p>}
      {!error && !eventos && <Skeleton h={180} />}
      {eventos && mejoras + deterioros === 0 && (
        <p className="grafica-vacia">Ningún expediente cambió de semáforo en los últimos {DIAS} días.</p>
      )}
      {eventos && mejoras + deterioros > 0 && (
        <ResponsiveContainer width="100%" height={180}>
          <BarChart data={dias} stackOffset="sign" margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap={2}>
            <CartesianGrid {...RETICULA} vertical={false} />
            <XAxis dataKey="dia" tickFormatter={diaCorto} interval={6} {...EJE} />
            <YAxis allowDecimals={false} tickFormatter={(v) => Math.abs(v)} width={28} {...EJE} axisLine={false} />
            <ReferenceLine y={0} stroke="var(--line-strong)" />
            <Tooltip
              cursor={{ fill: 'var(--bg-subtle)' }}
              content={({ active, payload }) => {
                const d = active && payload?.[0]?.payload
                return d ? (
                  <TooltipGrafica
                    titulo={diaCorto(d.dia)}
                    filas={[
                      { ...MEJORA, valor: d.mejoras },
                      { ...DETERIORO, valor: -d.deterioros },
                    ]}
                  />
                ) : null
              }}
            />
            {/* Esquinas redondeadas solo en la punta de cada barra: arriba las mejoras, abajo los deterioros. */}
            <Bar dataKey="mejoras" stackId="cambios" fill={MEJORA.color} radius={[4, 4, 0, 0]} maxBarSize={12} isAnimationActive={animar()} />
            <Bar dataKey="deterioros" stackId="cambios" fill={DETERIORO.color} radius={[0, 0, 4, 4]} maxBarSize={12} isAnimationActive={animar()} />
          </BarChart>
        </ResponsiveContainer>
      )}
      {eventos && mejoras + deterioros > 0 && (
        <>
          <Leyenda
            elementos={[
              { ...MEJORA, valor: mejoras },
              { ...DETERIORO, valor: deterioros },
            ]}
          />
          {truncada && <p className="field-hint">Se muestran los {LIMITE} cambios más recientes de la bitácora.</p>}
          <DatosDeLaGrafica
            columnas={['Día', 'Mejoraron', 'Empeoraron']}
            filas={dias.filter((d) => d.mejoras || d.deterioros).map((d) => [diaCorto(d.dia), d.mejoras, -d.deterioros])}
          />
        </>
      )}
    </TarjetaGrafica>
  )
}
