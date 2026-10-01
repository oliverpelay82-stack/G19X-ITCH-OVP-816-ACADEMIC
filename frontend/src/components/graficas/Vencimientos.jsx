import { CartesianGrid, ReferenceLine, ResponsiveContainer, Scatter, ScatterChart, Tooltip, XAxis, YAxis } from 'recharts'
import { TIPO_DOCUMENTO_LABEL, TIPOS_EXPEDIENTE } from '../../constants.js'
import { formatDia } from '../../utils/format.js'
import { DatosDeLaGrafica, Leyenda, TarjetaGrafica, TooltipGrafica } from './comun.jsx'
import { animar, EJE, RETICULA } from './estilo.js'

const HORIZONTE = 90

/** Franjas con los mismos umbrales que las alertas de vigencia (RCV-01: 30, 15 y 5 días). */
const FRANJAS = [
  { clave: 'urgente', etiqueta: '5 días o menos', hasta: 5, color: 'var(--chart-bad)' },
  { clave: 'proximo', etiqueta: '6 a 30 días', hasta: 30, color: 'var(--chart-warn)' },
  { clave: 'horizonte', etiqueta: '31 a 90 días', hasta: HORIZONTE, color: 'var(--off-solid)' },
]

const diasTexto = (d) => (d === 0 ? 'vence hoy' : `vence en ${d} ${d === 1 ? 'día' : 'días'}`)

/** Punto con anillo del color de la superficie: legible aunque se encime con otro. */
function Punto({ cx, cy, fill }) {
  return <circle cx={cx} cy={cy} r={5} fill={fill} stroke="var(--bg-surface)" strokeWidth={2} />
}

/**
 * V3 · ¿Qué vence y cuándo? Cada documento vigente que vence en los próximos
 * 90 días, como un punto en la franja de su área. Al pulsarlo se abre su
 * expediente (RN-02: la vigencia se recalcula en cada consulta).
 */
export default function Vencimientos({ expedientes, onAbrirExpediente }) {
  const areas = TIPOS_EXPEDIENTE.map((t) => t.value)
  const documentos = expedientes.flatMap((e) =>
    (e.evaluacion?.documentos || [])
      .filter((d) => d.dias_para_vencer != null)
      .map((d) => ({ ...d, expediente: e }))
  )
  const vencidos = documentos.filter((d) => d.dias_para_vencer < 0).length
  const enHorizonte = documentos
    .filter((d) => d.dias_para_vencer >= 0 && d.dias_para_vencer <= HORIZONTE)
    .sort((a, b) => a.dias_para_vencer - b.dias_para_vencer)

  // Los que caen en el mismo día y área se separan un poco en vertical.
  const repetidos = new Map()
  const puntos = enHorizonte.map((d) => {
    const fila = areas.indexOf(d.expediente.tipo_expediente)
    const clave = `${fila}:${d.dias_para_vencer}`
    const orden = repetidos.get(clave) || 0
    repetidos.set(clave, orden + 1)
    // 0, +1, −1, +2, −2: pasos de 0.2 alrededor de la fila (unos 9 px), sin salir de ella.
    const desplazamiento = orden === 0 ? 0 : (orden % 2 ? 1 : -1) * Math.min(Math.ceil(orden / 2), 2) * 0.2
    return { ...d, x: d.dias_para_vencer, y: fila + desplazamiento }
  })
  const porFranja = FRANJAS.map((f, i) => ({
    ...f,
    puntos: puntos.filter((p) => p.x <= f.hasta && (i === 0 || p.x > FRANJAS[i - 1].hasta)),
  }))

  const subtitulo =
    `${enHorizonte.length} ${enHorizonte.length === 1 ? 'documento vence' : 'documentos vencen'} en ${HORIZONTE} días` +
    (vencidos ? ` · ${vencidos} ya ${vencidos === 1 ? 'venció' : 'vencieron'}` : '')

  return (
    <TarjetaGrafica titulo="Vencimientos próximos" subtitulo={subtitulo}>
      {enHorizonte.length === 0 ? (
        <p className="grafica-vacia">Ningún documento vence en los próximos {HORIZONTE} días.</p>
      ) : (
        <ResponsiveContainer width="100%" height={180}>
          <ScatterChart margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
            <CartesianGrid {...RETICULA} vertical={false} />
            <XAxis
              type="number"
              dataKey="x"
              domain={[0, HORIZONTE]}
              ticks={[0, 15, 30, 60, 90]}
              tickFormatter={(d) => (d === 0 ? 'Hoy' : `${d} d`)}
              {...EJE}
            />
            <YAxis
              type="number"
              dataKey="y"
              domain={[-0.6, areas.length - 0.4]}
              ticks={areas.map((_, i) => i)}
              tickFormatter={(i) => TIPOS_EXPEDIENTE[i]?.label || ''}
              width={92}
              reversed
              {...EJE}
              axisLine={false}
            />
            <ReferenceLine x={30} stroke="var(--line-strong)" />
            <Tooltip
              cursor={false}
              content={({ active, payload }) => {
                const d = active && payload?.[0]?.payload
                if (!d) return null
                const franja = FRANJAS.find((f) => d.x <= f.hasta)
                return (
                  <TooltipGrafica
                    titulo={d.expediente.titular?.razon_social || d.expediente.codigo_expediente}
                    filas={[{ etiqueta: TIPO_DOCUMENTO_LABEL[d.tipo_documento] || d.tipo_documento, valor: diasTexto(d.x), color: franja.color }]}
                    nota={`${formatDia(d.fecha_caducidad)} · ${d.expediente.codigo_expediente} · pulse para abrir`}
                  />
                )
              }}
            />
            {porFranja.map((f) => (
              <Scatter
                key={f.clave}
                name={f.etiqueta}
                data={f.puntos}
                fill={f.color}
                shape={Punto}
                isAnimationActive={animar()}
                onClick={(p) => onAbrirExpediente?.(p?.payload?.expediente?.id ?? p?.expediente?.id)}
                className="grafica-pulsable"
              />
            ))}
          </ScatterChart>
        </ResponsiveContainer>
      )}
      {enHorizonte.length > 0 && (
        <>
          <Leyenda forma="punto" elementos={porFranja.map((f) => ({ etiqueta: f.etiqueta, color: f.color, valor: f.puntos.length }))} />
          <DatosDeLaGrafica
        columnas={['Documento', 'Empresa', 'Vence', 'Días']}
        filas={enHorizonte.map((d) => [
          `${TIPO_DOCUMENTO_LABEL[d.tipo_documento] || d.tipo_documento} · ${d.expediente.codigo_expediente}`,
          d.expediente.titular?.razon_social || '—',
          formatDia(d.fecha_caducidad),
          d.dias_para_vencer,
        ])}
          />
        </>
      )}
    </TarjetaGrafica>
  )
}
