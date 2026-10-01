import { useMemo, useState } from 'react'
import { FileBarChart2, SearchX } from 'lucide-react'
import ExportarReporte from './ExportarReporte.jsx'
import MetricsCards from './MetricsCards.jsx'
import { EncabezadoOrdenable } from './OrdenTabla.jsx'
import useOrden, { RANGO_ESTADO } from '../hooks/useOrden.js'
import HallazgosCategoria from './HallazgosCategoria.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { Badge, Button, Card, EmptyRow, SearchBox, Select, Tag } from './ui/index.js'
import AnilloSemaforo from './graficas/AnilloSemaforo.jsx'
import CambiosSemaforo from './graficas/CambiosSemaforo.jsx'
import HallazgosPorArea from './graficas/HallazgosPorArea.jsx'
import Vencimientos from './graficas/Vencimientos.jsx'
import { formatIndice, indiceDe } from '../utils/indice.js'
import { getEstadoBadge, TIPO_EXPEDIENTE_LABEL, TIPOS_EXPEDIENTE } from '../constants.js'
import FolioExpediente from './FolioExpediente.jsx'

const COLUMNAS = 6

/** Sección de la página con su título y, opcionalmente, una acción a la derecha. */
function Seccion({ titulo, accion, children }) {
  return (
    <section className="report-seccion" aria-label={titulo}>
      <div className="report-seccion-cabecera">
        <h2 className="section-title">{titulo}</h2>
        {accion}
      </div>
      {children}
    </section>
  )
}

/**
 * Reportes y panel de cumplimiento (Módulo 6): exportación del reporte global
 * arriba, métricas, hallazgos por área y por categoría (RF-22), vencimientos y tendencia, y el dictamen
 * de cada expediente en PDF y Excel (RF-23, RF-24; HU-26, HU-28, HU-29).
 */
export default function ReportesTab({
  expedientes,
  titulares = [],
  documentos = [],
  loading,
  isOnline = true,
  onAbrirExpediente,
}) {
  const [tipoGlobal, setTipoGlobal] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const consulta = useDebounce(busqueda, 220)

  const totalAlertas = useMemo(() => expedientes.reduce((n, e) => n + (e.evaluacion?.alertas?.length || 0), 0), [expedientes])

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

  // Orden por columna: el estado va de lo más grave a lo conforme; el cumplimiento, del menor al mayor.
  const clavesOrden = useMemo(
    () => ({
      expediente: (e) => e.titular?.razon_social,
      tipo: (e) => TIPO_EXPEDIENTE_LABEL[e.tipo_expediente],
      estado: (e) => RANGO_ESTADO[e.estado_cumplimiento],
      cumplimiento: (e) => indiceDe(e)?.porcentaje,
      alertas: (e) => e.evaluacion?.alertas?.length || 0,
    }),
    []
  )
  const { ordenada, orden, ordenar } = useOrden(filtrados, clavesOrden)

  return (
    <div className="tab-panel reportes">
      {/* El reporte global es una acción de toda la pestaña: va en la barra, como
          la acción principal de las demás vistas, y no dentro de una tarjeta. */}
      <div className="toolbar">
        <p className="toolbar-nota">
          <span className="eyebrow">Reporte global</span>
          Indicadores, expedientes y alertas con recomendación.
        </p>
        <div className="toolbar-action toolbar-grupo">
          <Select etiqueta="Tipo de expediente del reporte" value={tipoGlobal} onChange={(e) => setTipoGlobal(e.target.value)}>
            <option value="">Todos los expedientes</option>
            {TIPOS_EXPEDIENTE.map((t) => (
              <option key={t.value} value={t.value}>
                Solo {t.label.toLowerCase()}s
              </option>
            ))}
          </Select>
          <ExportarReporte ruta="/reportes/cumplimiento" params={{ tipo_expediente: tipoGlobal }} disabled={!isOnline} />
        </div>
      </div>

      <MetricsCards titulares={titulares} expedientes={expedientes} documentos={documentos} loading={loading} />

      {/* Fase A del plan visual: el semáforo, los hallazgos por área y severidad
          (RF-22) y, debajo, lo que vence y la tendencia. La categoría sigue como
          lista: son clases sin orden, más de las que un color distingue. */}
      <Seccion titulo={`Hallazgos · ${totalAlertas}`}>
        <div className="report-grid">
          <AnilloSemaforo expedientes={expedientes} />
          <HallazgosPorArea expedientes={expedientes} />
          <HallazgosCategoria expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
        </div>
      </Seccion>

      <Seccion titulo="Vencimientos y tendencia">
        <div className="report-grid report-grid--dos">
          <Vencimientos expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
          <CambiosSemaforo expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
        </div>
      </Seccion>

      <Seccion
        titulo="Dictamen por expediente"
        accion={
          <div className="toolbar-buscador">
            <SearchBox value={busqueda} onChange={setBusqueda} placeholder="Folio, nombre, empresa o RFC…" label="Buscar expediente" />
          </div>
        }
      >
        <Card className="table-card">
          <div className="table-scroll">
            <table className="data-table">
              <colgroup>
                <col style={{ width: '28%' }} />
                <col style={{ width: '11%' }} />
                <col style={{ width: '14%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '8%' }} />
                <col style={{ width: '22%' }} />
              </colgroup>
              <thead>
                <tr>
                  <EncabezadoOrdenable columna="expediente" orden={orden} onOrdenar={ordenar}>
                    Expediente
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="tipo" orden={orden} onOrdenar={ordenar}>
                    Tipo
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="estado" orden={orden} onOrdenar={ordenar}>
                    Estado
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="cumplimiento" orden={orden} onOrdenar={ordenar} className="col-right">
                    Cumplimiento
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="alertas" orden={orden} onOrdenar={ordenar} inicial="desc" className="col-right">
                    Alertas
                  </EncabezadoOrdenable>
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
                  >
                    {expedientes.length > 0 && (
                      <Button compacto onClick={() => setBusqueda('')}>
                        Limpiar búsqueda
                      </Button>
                    )}
                  </EmptyRow>
                )}
                {!loading &&
                  ordenada.map((e) => {
                    const meta = getEstadoBadge(e.estado_cumplimiento)
                    return (
                      <tr key={e.id}>
                        <td>
                          <span className="cell-stack">
                            <span className="identity-name">{e.titular?.razon_social || 'Titular no disponible'}</span>
                            <span className="cell-sub mono">
                              <FolioExpediente expediente={e} />
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
                        <td className="col-right">
                          <span className="cell-stack">
                            <span className="tabular">{formatIndice(indiceDe(e)?.porcentaje)}</span>
                            <span className="cell-sub tabular">
                              {Number(e.porcentaje_completitud || 0).toFixed(0)}% obligatorios
                            </span>
                          </span>
                        </td>
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
      </Seccion>
    </div>
  )
}
