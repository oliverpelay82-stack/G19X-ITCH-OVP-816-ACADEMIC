import { Cpu, Gauge, ScanText, Timer } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'

/**
 * Panel de estado en vivo del motor de inteligencia artificial (ai-service :8003).
 *
 * Lee el payload que el sondeo de salud ya trae en cada ciclo, de modo que no
 * abre una petición propia. Muestra las dependencias del análisis —el modelo
 * de lenguaje servido por Groq Cloud, el motor OCR, las bandas de confianza y
 * las reglas de vigencia del rules-service— para que el operador sepa, antes
 * de auditar, si los Niveles 2 a 4 del pipeline están realmente disponibles.
 */
export default function MotorIaPanel({ estado, reglas = [], loading }) {
  const online = Boolean(estado?.online)
  const datos = estado?.payload || null
  const inferencia = datos?.motor_inferencia
  const ocr = datos?.motor_ocr
  const bandas = datos?.bandas_confianza
  const vigencia = reglas.filter((r) => r.familia_regla === 'RCV')
  const vigenciaActivas = vigencia.filter((r) => r.activo)

  const tonoGeneral = !online ? 'bad' : datos?.capacidades_operativas ? 'ok' : 'warn'
  const etiquetaGeneral = !online ? 'Sin respuesta' : datos?.capacidades_operativas ? 'Operativo' : 'Degradado'

  const items = [
    {
      id: 'inferencia',
      icon: Cpu,
      titulo: 'Modelo de lenguaje',
      valor: inferencia?.modelo_requerido || '—',
      pie: online
        ? inferencia?.modelo_disponible
          ? `${inferencia?.proveedor || 'Groq Cloud'} · temperatura ${inferencia?.temperatura_auditoria ?? '—'}`
          : inferencia?.detalle || 'Groq no está disponible.'
        : 'El microservicio de IA no responde.',
      disponible: Boolean(inferencia?.modelo_disponible),
    },
    {
      id: 'ocr',
      icon: ScanText,
      titulo: 'Reconocimiento óptico',
      valor: ocr?.disponible ? `${ocr.proveedor} ${ocr.version}` : '—',
      pie: ocr?.disponible
        ? `${ocr.idiomas_disponibles?.join(', ')} · ${ocr.dpi_rasterizado} ppp`
        : 'Tesseract no está disponible en el servidor.',
      disponible: Boolean(ocr?.disponible),
    },
    {
      id: 'hitl',
      icon: Gauge,
      titulo: 'Bandas de confianza',
      valor: bandas
        ? `≥ ${(bandas.conforme_desde * 100).toFixed(0)}% · ${(bandas.revision_humana_desde * 100).toFixed(0)}–${(bandas.conforme_desde * 100 - 1).toFixed(0)}%`
        : '—',
      pie: 'Debajo de la primera banda, revisión humana (Nivel 5).',
      disponible: online,
    },
    {
      id: 'vigencia',
      icon: Timer,
      titulo: 'Reglas de vigencia',
      valor: vigenciaActivas.length ? vigenciaActivas.map((r) => r.codigo_regla).join(' · ') : '—',
      pie: vigencia.length
        ? `${vigenciaActivas.length} de ${vigencia.length} activas · rules-service (Nivel 2)`
        : 'Catálogo RCV no disponible.',
      disponible: vigenciaActivas.length > 0,
    },
  ]

  return (
    <section className="card ia-panel" aria-label="Estado del motor de inteligencia artificial">
      <header className="section-head">
        <div>
          <h2 className="section-title">Motor de IA</h2>
          <p className="section-desc">Niveles 2 a 4 · ai-service :8003 · Groq LPU</p>
        </div>
        <span className={`badge badge--${tonoGeneral}`}>
          <span className={`status-dot status-dot--${tonoGeneral}`} aria-hidden="true" />
          {etiquetaGeneral}
          {online && estado.latencia !== null ? ` · ${estado.latencia} ms` : ''}
        </span>
      </header>

      <dl className="ia-panel-grid">
        {items.map(({ id, icon: Icono, titulo, valor, pie, disponible }) => (
          <div className="stat" key={id}>
            <dt className="stat-label">
              <Icono size={13} strokeWidth={1.75} aria-hidden="true" />
              {titulo}
              <span className={`status-dot status-dot--${disponible ? 'ok' : 'off'}`} aria-hidden="true" />
            </dt>
            <dd className="stat-value mono">{loading ? <Skeleton w={120} h={13} /> : valor}</dd>
            <dd className="stat-foot">{pie}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
