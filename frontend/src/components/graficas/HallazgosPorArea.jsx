import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { getSeveridadMeta, SEVERIDADES, TIPOS_EXPEDIENTE } from '../../constants.js'
import { DatosDeLaGrafica, Leyenda, TarjetaGrafica, TooltipGrafica } from './comun.jsx'
import { animar, EJE, RETICULA, SEPARACION } from './estilo.js'
import { plural } from '../../utils/format.js'

/** Rampa de un solo tono, validada: Crítica es el paso más marcado en ambos temas. */
const COLOR_SEVERIDAD = {
  CRITICA: 'var(--chart-sev-critica)',
  ALTA: 'var(--chart-sev-alta)',
  MEDIA_ALTA: 'var(--chart-sev-media-alta)',
  MEDIA: 'var(--chart-sev-media)',
}

/**
 * V2 · ¿Qué área concentra lo grave? Hallazgos vigentes por área (el tipo de
 * expediente del DOC-02) y severidad, apilados desde lo más grave (RF-22).
 */
export default function HallazgosPorArea({ expedientes }) {
  const filas = TIPOS_EXPEDIENTE.map((t) => {
    const delArea = expedientes.filter((e) => e.tipo_expediente === t.value)
    const alertas = delArea.flatMap((e) => e.evaluacion?.alertas || [])
    return {
      area: t.label,
      expedientes: delArea.length,
      total: alertas.length,
      ...Object.fromEntries(SEVERIDADES.map((s) => [s, alertas.filter((a) => a.severidad === s).length])),
    }
  })
  const porSeveridad = SEVERIDADES.map((s) => [s, filas.reduce((n, f) => n + f[s], 0)])
  const total = porSeveridad.reduce((n, [, v]) => n + v, 0)

  return (
    <TarjetaGrafica titulo="Hallazgos por área y severidad" subtitulo={plural(total, 'hallazgo vigente', 'hallazgos vigentes')}>
      <ResponsiveContainer width="100%" height={180}>
        <BarChart data={filas} layout="vertical" margin={{ top: 4, right: 12, bottom: 0, left: 0 }} barSize={20}>
          <CartesianGrid {...RETICULA} horizontal={false} />
          <XAxis type="number" allowDecimals={false} {...EJE} />
          <YAxis type="category" dataKey="area" width={92} {...EJE} axisLine={false} />
          <Tooltip
            cursor={{ fill: 'var(--bg-subtle)' }}
            content={({ active, payload }) => {
              const f = active && payload?.[0]?.payload
              return f ? (
                <TooltipGrafica
                  titulo={`${f.area} · ${plural(f.expedientes, 'expediente', 'expedientes')}`}
                  filas={SEVERIDADES.map((s) => ({ etiqueta: getSeveridadMeta(s).label, valor: f[s], color: COLOR_SEVERIDAD[s] }))}
                  nota={`${f.total} en total`}
                />
              ) : null
            }}
          />
          {SEVERIDADES.map((s) => (
            <Bar key={s} dataKey={s} name={getSeveridadMeta(s).label} stackId="hallazgos" fill={COLOR_SEVERIDAD[s]} isAnimationActive={animar()} {...SEPARACION} />
          ))}
        </BarChart>
      </ResponsiveContainer>
      <Leyenda elementos={porSeveridad.map(([s, n]) => ({ etiqueta: getSeveridadMeta(s).label, color: COLOR_SEVERIDAD[s], valor: n }))} />
      <DatosDeLaGrafica
        columnas={['Área', ...SEVERIDADES.map((s) => getSeveridadMeta(s).label), 'Total']}
        filas={filas.map((f) => [f.area, ...SEVERIDADES.map((s) => f[s]), f.total])}
      />
    </TarjetaGrafica>
  )
}
