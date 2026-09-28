import { useMemo, useState } from 'react'
import { FileBarChart2, SearchX } from 'lucide-react'
import ExportarReporte from './ExportarReporte.jsx'
import TableroOperativo from './TableroOperativo.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { Badge, Card, EmptyRow, SearchBox, Select, Tag } from './ui/index.js'
import {
  ALERTA_META,
  getEstadoBadge,
  getSeveridadMeta,
  SEVERIDADES,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_EXPEDIENTE,
} from '../constants.js'

const COLUMNAS = 6

/** Barra horizontal con su etiqueta y cifra; el color solo acompaña al texto. */
function Barra({ label, n, total, tono = 'neutral', elemento: Elemento = 'li' }) {
  const pct = total ? Math.round((n / total) * 100) : 0
  return (
    <Elemento className="dist-row">
      <span className="dist-label">{label}</span>
      <span className="dist-track" aria-hidden="true">
        <span className={`dist-fill dist-fill--${tono}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="dist-value tabular">{n}</span>
    </Elemento>
  )
}

/**
 * Reportes y panel de cumplimiento (Módulo 6): indicadores globales (RF-22),
 * exportación del reporte global y del dictamen de cada expediente en PDF y
 * Excel (RF-23, RF-24; HU-26, HU-28, HU-29).
 */
export default function ReportesTab({ expedientes, loading, isOnline = true, onAbrirExpediente }) {
  const [tipoGlobal, setTipoGlobal] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const consulta = useDebounce(busqueda, 220)

  const ind = useMemo(() => {
    const cuenta = (estado) => expedientes.filter((e) => e.estado_cumplimiento === estado).length
    const alertas = expedientes.flatMap((e) => e.evaluacion?.alertas || [])
    const porCodigo = new Map()
    for (const a of alertas) porCodigo.set(a.codigo, (porCodigo.get(a.codigo) || 0) + 1)
    const total = expedientes.length
    return {
      total,
      conformes: cuenta('CONFORME'),
      revision: cuenta('EN_REVISION'),
      noConformes: cuenta('NO_CONFORME'),
      global: total ? (cuenta('CONFORME') / total) * 100 : 0,
      alertas,
      porSeveridad: SEVERIDADES.map((s) => [s, alertas.filter((a) => a.severidad === s).length]),
      porCodigo: [...porCodigo.entries()].sort((a, b) => b[1] - a[1]),
      // Hallazgos por área (RF-22): el área es el tipo de expediente (DOC-02).
      porArea: TIPOS_EXPEDIENTE.map((t) => {
        const delArea = expedientes.filter((e) => e.tipo_expediente === t.value)
        const hallazgos = delArea.flatMap((e) => e.evaluacion?.alertas || [])
        return {
          tipo: t.value,
          expedientes: delArea.length,
          hallazgos: hallazgos.length,
          graves: hallazgos.filter((a) => a.severidad === 'CRITICA' || a.severidad === 'ALTA').length,
        }
      }),
    }
  }, [expedientes])

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return expedientes.filter(
      (e) =>
        !q ||
        [e.codigo_expediente, e.nombre, e.titular?.razon_social, e.titular?.rfc]
          .filter(Boolean)
          .some((t) => t.toLowerCase().includes(q))
    )
  }, [expedientes, consulta])

  return (
    <div className="tab-panel">
      <section className="report-grid" aria-label="Indicadores de cumplimiento">
        <Card as="article" className="report-card">
          <p className="eyebrow">Cumplimiento global</p>
          <p className="report-kpi tabular">{loading ? '—' : `${ind.global.toFixed(1)}%`}</p>
          <p className="field-hint">
            {ind.conformes} de {ind.total} expedientes conformes al 100 % (RF-22).
          </p>
          <ul className="dist-list">
            <Barra label="Conformes" n={ind.conformes} total={ind.total} tono="ok" />
            <Barra label="En revisión" n={ind.revision} total={ind.total} tono="warn" />
            <Barra label="No conformes" n={ind.noConformes} total={ind.total} tono="bad" />
          </ul>
        </Card>

        <Card as="article" className="report-card">
          <p className="eyebrow">Alertas por severidad · {ind.alertas.length}</p>
          <ul className="dist-list">
            {ind.porSeveridad.map(([s, n]) => (
              <Barra key={s} label={getSeveridadMeta(s).label} n={n} total={ind.alertas.length} tono={getSeveridadMeta(s).tono} />
            ))}
          </ul>
          <p className="eyebrow report-sub">Hallazgos por categoría</p>
          <ul className="dist-list">
            {ind.porCodigo.length === 0 && <li className="field-hint">Sin hallazgos vigentes.</li>}
            {ind.porCodigo.map(([c, n]) => (
              <Barra key={c} label={ALERTA_META[c]?.label || c} n={n} total={ind.alertas.length} />
            ))}
          </ul>
        </Card>

        <Card as="article" className="report-card">
          <p className="eyebrow">Hallazgos por área · {ind.alertas.length}</p>
          <ul className="dist-list">
            {ind.porArea.map((a) => (
              <li key={a.tipo} className="area-fila">
                <Barra
                  elemento="div"
                  label={TIPO_EXPEDIENTE_LABEL[a.tipo]}
                  n={a.hallazgos}
                  total={ind.alertas.length}
                  tono={a.graves ? 'bad' : a.hallazgos ? 'warn' : 'ok'}
                />
                <span className="area-sub">
                  {a.expedientes} {a.expedientes === 1 ? 'expediente' : 'expedientes'}
                  {a.graves > 0 && ` · ${a.graves} ${a.graves === 1 ? 'crítica o alta' : 'críticas o altas'}`}
                </span>
              </li>
            ))}
          </ul>
          <p className="eyebrow report-sub">Reporte global</p>
          <p className="field-hint">Indicadores, expedientes y alertas con recomendación.</p>
          <Select
            etiqueta="Tipo de expediente del reporte"
            claseContenedor="report-select"
            value={tipoGlobal}
            onChange={(e) => setTipoGlobal(e.target.value)}
          >
            <option value="">Todos los expedientes</option>
            {TIPOS_EXPEDIENTE.map((t) => (
              <option key={t.value} value={t.value}>
                Solo {t.label.toLowerCase()}s
              </option>
            ))}
          </Select>
          <ExportarReporte ruta="/reportes/cumplimiento" params={{ tipo_expediente: tipoGlobal }} disabled={!isOnline} />
        </Card>
      </section>

      <TableroOperativo expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />

      <div className="toolbar">
        <SearchBox value={busqueda} onChange={setBusqueda} placeholder="Folio, nombre, empresa o RFC…" label="Buscar expediente" />
      </div>

      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table">
            <colgroup>
              <col style={{ width: '30%' }} />
              <col style={{ width: '12%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '12%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: '22%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Expediente</th>
                <th>Tipo</th>
                <th>Estado</th>
                <th className="col-right">Completitud</th>
                <th className="col-right">Alertas</th>
                <th className="col-right">Dictamen de cumplimiento</th>
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows rows={4} cols={COLUMNAS} />}
              {!loading && filtrados.length === 0 && (
                <EmptyRow
                  columnas={COLUMNAS}
                  icon={expedientes.length === 0 ? FileBarChart2 : SearchX}
                  titulo={expedientes.length === 0 ? 'Aún no hay expedientes' : 'Sin coincidencias'}
                  descripcion={expedientes.length === 0 ? 'Los reportes se generan a partir de los expedientes.' : 'Ajusta la búsqueda.'}
                />
              )}
              {!loading &&
                filtrados.map((e) => {
                  const meta = getEstadoBadge(e.estado_cumplimiento)
                  return (
                    <tr key={e.id}>
                      <td>
                        <span className="cell-stack">
                          <span className="identity-name">{e.titular?.razon_social || 'Titular no disponible'}</span>
                          <span className="cell-sub mono">
                            {e.codigo_expediente}
                            {e.nombre ? ` · ${e.nombre}` : ''}
                          </span>
                        </span>
                      </td>
                      <td>
                        <Tag tipo>{TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente}</Tag>
                      </td>
                      <td>
                        <Badge tono={meta.tono} punto>
                          {meta.label}
                        </Badge>
                      </td>
                      <td className="col-right tabular">{Number(e.porcentaje_completitud || 0).toFixed(0)}%</td>
                      <td className="col-right tabular">{e.evaluacion?.alertas?.length || 0}</td>
                      <td className="col-right">
                        <ExportarReporte ruta={`/reportes/expedientes/${e.id}`} compacto disabled={!isOnline} />
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
