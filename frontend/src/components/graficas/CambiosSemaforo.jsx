import { useEffect, useState } from 'react'
import { ArrowUpRight } from '../iconos.js'
import { Bar, BarChart, CartesianGrid, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getBitacora } from '../../services/api.js'
import { getEstadoBadge } from '../../constants.js'
import { formatFechaCorta, plural } from '../../utils/format.js'
import { Skeleton } from '../Skeleton.jsx'
import { agruparCambios, DIAS, diaCorto, esCambioDeTendencia, LIMITE } from './cambios.js'
import { DatosDeLaGrafica, Leyenda, TarjetaGrafica, TooltipGrafica } from './comun.jsx'
import { animar, EJE, RETICULA } from './estilo.js'

const MEJORA = { etiqueta: 'Mejoraron', color: 'var(--chart-ok)' }
const DETERIORO = { etiqueta: 'Empeoraron', color: 'var(--chart-bad)' }
// Cambios más recientes que se listan bajo la gráfica, cada uno con el acceso a su expediente.
const ULTIMOS = 4

/**
 * V4 · ¿Hacia dónde vamos? Cuántos expedientes mejoraron o empeoraron su
 * semáforo cada día de los últimos 30, según la bitácora inmutable. La
 * tendencia sale de eventos ya registrados: no requiere guardar historia.
 * Debajo, los últimos cambios con el acceso a su expediente (antes eran una
 * tarjeta aparte que consultaba otra vez la bitácora).
 */
export default function CambiosSemaforo({ expedientes = [], onAbrirExpediente }) {
  const [eventos, setEventos] = useState(null)
  const [desde, setDesde] = useState(0) // inicio de la ventana de DIAS, fijado al recibir la bitácora
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    getBitacora({ evento: 'EVALUACION_REGLAS', limite: LIMITE })
      .then((r) => {
        if (!vigente) return
        setDesde(Date.now() - DIAS * 24 * 60 * 60 * 1000)
        setEventos(r)
      })
      .catch((e) => vigente && setError(e?.message || 'No se pudo consultar la bitácora.'))
    return () => {
      vigente = false
    }
  }, [])

  const dias = eventos ? agruparCambios(eventos) : []
  const mejoras = dias.reduce((n, d) => n + d.mejoras, 0)
  const deterioros = -dias.reduce((n, d) => n + d.deterioros, 0)
  const truncada = eventos?.length === LIMITE
  const ultimos = (eventos || [])
    .filter((e) => esCambioDeTendencia(e) && new Date(e.creado_en).getTime() >= desde)
    .slice(0, ULTIMOS)
  const folios = new Map(expedientes.map((e) => [e.id, e.codigo_expediente]))

  return (
    <TarjetaGrafica
      titulo="Tendencia del semáforo"
      subtitulo={eventos ? `Últimos ${DIAS} días · ${plural(mejoras, 'mejora', 'mejoras')}, ${plural(deterioros, 'deterioro', 'deterioros')}` : `Últimos ${DIAS} días`}
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
            {/* Las marcas se cuentan desde el final: el último día (hoy) siempre lleva su fecha. */}
            <XAxis dataKey="dia" tickFormatter={diaCorto} ticks={dias.filter((_, i) => (dias.length - 1 - i) % 7 === 0).map((d) => d.dia)} {...EJE} />
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
          <ul className="tablero-lista" aria-label="Últimos cambios del semáforo">
            {ultimos.map((e) => {
              const nuevo = getEstadoBadge(e.detalle?.estado_nuevo)
              return (
                <li key={e.id}>
                  <button type="button" className="tablero-fila" onClick={() => onAbrirExpediente?.(e.expediente_id)}>
                    <span className={`status-dot status-dot--${nuevo.tono}`} aria-hidden="true" />
                    <span className="tablero-fila-texto">
                      <span className="tablero-fila-titulo">
                        {getEstadoBadge(e.detalle?.estado_anterior).label} → {nuevo.label}
                      </span>
                      <span className="tablero-fila-sub mono">{folios.get(e.expediente_id) || 'Expediente'}</span>
                    </span>
                    <span className="tablero-fila-dato tabular">{formatFechaCorta(e.creado_en)}</span>
                    <ArrowUpRight size={12} aria-hidden="true" />
                  </button>
                </li>
              )
            })}
          </ul>
          <DatosDeLaGrafica
            columnas={['Día', 'Mejoraron', 'Empeoraron']}
            filas={dias.filter((d) => d.mejoras || d.deterioros).map((d) => [diaCorto(d.dia), d.mejoras, -d.deterioros])}
          />
        </>
      )}
    </TarjetaGrafica>
  )
}
