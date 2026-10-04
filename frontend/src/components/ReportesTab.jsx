import { useMemo, useState } from 'react'
import ExportarReporte from './ExportarReporte.jsx'
import HallazgosCategoria from './HallazgosCategoria.jsx'
import { Select } from './ui/index.js'
import AnilloSemaforo from './graficas/AnilloSemaforo.jsx'
import CambiosSemaforo from './graficas/CambiosSemaforo.jsx'
import HallazgosPorArea from './graficas/HallazgosPorArea.jsx'
import Vencimientos from './graficas/Vencimientos.jsx'
import { TIPOS_EXPEDIENTE } from '../constants.js'

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
 * Reportes (Módulo 6): exportación del reporte global arriba, hallazgos por área
 * y por categoría (RF-22), vencimientos y tendencia (HU-26, HU-29). Sin métricas
 * ni lista de expedientes propias: las métricas están en Expedientes (la vista de
 * inicio) y el dictamen de cada expediente se exporta desde su detalle (RF-23,
 * RF-24; HU-28). Un sector del anillo abre Expedientes filtrado por ese estado.
 */
export default function ReportesTab({ expedientes, isOnline = true, onAbrirExpediente, onVerExpedientes }) {
  const [tipoGlobal, setTipoGlobal] = useState('')
  const totalAlertas = useMemo(() => expedientes.reduce((n, e) => n + (e.evaluacion?.alertas?.length || 0), 0), [expedientes])

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

      {/* Fase A del plan visual: el semáforo, los hallazgos por área y severidad
          (RF-22) y, debajo, lo que vence y la tendencia. La categoría sigue como
          lista: son clases sin orden, más de las que un color distingue. */}
      <Seccion titulo={`Hallazgos · ${totalAlertas}`}>
        <div className="report-grid">
          <AnilloSemaforo expedientes={expedientes} onSeleccionar={onVerExpedientes} />
          <HallazgosPorArea expedientes={expedientes} />
          <HallazgosCategoria expedientes={expedientes} />
        </div>
      </Seccion>

      <Seccion titulo="Vencimientos y tendencia">
        <div className="report-grid report-grid--dos">
          <Vencimientos expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
          <CambiosSemaforo expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
        </div>
      </Seccion>
    </div>
  )
}
