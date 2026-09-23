import { Skeleton } from './Skeleton.jsx'

/**
 * Panel de estado en vivo del motor de inteligencia artificial (ai-service :8003).
 *
 * Lee el payload que el sondeo de salud ya trae en cada ciclo, de modo que no
 * abre una petición propia. Muestra las dos dependencias de las que depende el
 * análisis —el modelo de lenguaje servido por Groq Cloud y el motor
 * OCR— para que el operador sepa, antes de cargar un expediente, si el Nivel 3
 * y el Nivel 4 del pipeline están realmente disponibles.
 */
export default function MotorIaPanel({ estado, loading }) {
  const online = Boolean(estado?.online)
  const datos = estado?.payload || null
  const inferencia = datos?.motor_inferencia
  const ocr = datos?.motor_ocr
  const bandas = datos?.bandas_confianza

  const tonoGeneral = !online ? 'bad' : datos?.capacidades_operativas ? 'ok' : 'warn'
  const etiquetaGeneral = !online
    ? 'Sin respuesta'
    : datos?.capacidades_operativas
      ? 'Operativo'
      : 'Degradado'

  const items = [
    {
      id: 'inferencia',
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
      titulo: 'Reconocimiento óptico',
      valor: ocr?.disponible ? `${ocr.proveedor} ${ocr.version}` : '—',
      pie: ocr?.disponible
        ? `${ocr.idiomas_disponibles?.join(', ')} · ${ocr.dpi_rasterizado} ppp`
        : 'Tesseract no está disponible en el servidor.',
      disponible: Boolean(ocr?.disponible),
    },
    {
      id: 'hitl',
      titulo: 'Bandas de confianza',
      valor: bandas
        ? `≥ ${(bandas.conforme_desde * 100).toFixed(0)}% · ${(bandas.revision_humana_desde * 100).toFixed(0)}–${(bandas.conforme_desde * 100 - 1).toFixed(0)}%`
        : '—',
      pie: 'Por debajo de la primera banda se turna al Nivel 5 (revisión humana).',
      disponible: online,
    },
  ]

  return (
    <section className="card ia-panel" aria-label="Estado del motor de inteligencia artificial">
      <header className="section-head">
        <div>
          <h2 className="section-title">Motor de IA</h2>
          <p className="section-desc">Niveles 3 y 4 · ai-service :8003 · Groq Cloud</p>
        </div>
        <span className={`badge badge--${tonoGeneral}`}>
          {etiquetaGeneral}
          {online && estado.latencia !== null ? ` · ${estado.latencia} ms` : ''}
        </span>
      </header>

      <dl className="ia-panel-grid">
        {items.map((item) => (
          <div className="stat" key={item.id}>
            <dt className="stat-label">
              <span className={`status-dot status-dot--${item.disponible ? 'ok' : 'off'}`} aria-hidden="true" />
              {item.titulo}
            </dt>
            <dd className="stat-value mono">{loading ? <Skeleton w={120} h={14} /> : item.valor}</dd>
            <dd className="stat-foot">{item.pie}</dd>
          </div>
        ))}
      </dl>
    </section>
  )
}
