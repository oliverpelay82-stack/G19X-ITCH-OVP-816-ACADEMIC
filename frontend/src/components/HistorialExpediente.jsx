import { useState } from 'react'
import { History, Loader2 } from 'lucide-react'
import { Badge, Button } from './ui/index.js'
import { getBitacora, verificarCadena } from '../services/api.js'
import { getEstadoBadge, TIPO_DOCUMENTO_LABEL } from '../constants.js'
import { formatFecha } from '../utils/format.js'

/** Causas con que el core-service reevalúa el semáforo (bitácora, EVALUACION_REGLAS). */
const CAUSA = {
  APERTURA_EXPEDIENTE: 'apertura',
  INGESTA_DOCUMENTO: 'carga de un documento',
  DICTAMEN_IA: 'dictamen de la IA',
  RATIFICACION_HUMANA: 'ratificación de un analista',
  REEVALUACION_PROGRAMADA: 'reevaluación programada',
  CONSULTA_EXPEDIENTE: 'consulta',
  CONSULTA_EXPEDIENTES: 'consulta',
  CONSULTA_ALERTAS: 'consulta de alertas',
  REPORTE_EXPEDIENTE: 'reporte',
  REPORTE_GLOBAL: 'reporte global',
}

const estado = (e) => getEstadoBadge(e)

// Eventos que se muestran antes de «Ver todo».
const VISIBLES = 10

/**
 * Agrupa eventos consecutivos idénticos (mismo título y detalle): una serie de
 * reauditorías del mismo documento se lee como una línea con «×N» y la fecha
 * de la más reciente. La bitácora no cambia: solo su presentación.
 */
function agrupar(eventos, nombres) {
  const grupos = []
  for (const e of eventos) {
    const descripcion = describir(e, nombres)
    const previo = grupos[grupos.length - 1]
    if (previo && previo.titulo === descripcion.titulo && previo.detalle === descripcion.detalle) {
      previo.veces += 1
    } else {
      grupos.push({ ...descripcion, evento: e, veces: 1 })
    }
  }
  return grupos
}

/** Un evento de la bitácora en lenguaje del analista: título, detalle y tono. */
function describir(evento, nombres) {
  const d = evento.detalle || {}
  const documento = nombres.get(evento.documento_id) || d.nombre_archivo_original
  switch (evento.evento) {
    case 'APERTURA_EXPEDIENTE':
      return { titulo: 'Expediente abierto', tono: 'neutral' }
    case 'INGESTA_DOCUMENTO':
      return {
        titulo: `Documento custodiado: ${d.nombre_archivo_original || 'archivo'}`,
        detalle: TIPO_DOCUMENTO_LABEL[d.tipo_documento] || d.tipo_documento,
        tono: 'neutral',
      }
    case 'DICTAMEN_IA':
      return {
        titulo: `Dictamen de la IA: ${estado(d.estatus).label}`,
        detalle: documento,
        tono: estado(d.estatus).tono,
      }
    case 'RATIFICACION_HUMANA':
      return {
        titulo: `Ratificado por ${evento.usuario}: ${estado(d.estatus_nuevo).label}`,
        detalle: [documento, d.justificacion && `«${d.justificacion}»`].filter(Boolean).join(' · '),
        tono: estado(d.estatus_nuevo).tono,
      }
    case 'EVALUACION_REGLAS':
      return {
        titulo: `Semáforo: ${estado(d.estado_anterior).label} → ${estado(d.estado_nuevo).label}`,
        detalle: d.causa ? `Por ${CAUSA[d.causa] || d.causa.toLowerCase()}` : null,
        tono: estado(d.estado_nuevo).tono,
      }
    case 'ALERTA_INTEGRIDAD':
      return { titulo: 'Integridad comprometida', detalle: documento, tono: 'bad' }
    case 'ARCHIVO_PROTEGIDO':
      return { titulo: 'PDF protegido con contraseña', detalle: documento, tono: 'bad' }
    case 'SELLO_GENESIS':
      return { titulo: 'Inicio del sellado de la bitácora', detalle: `${d.eventos_previos ?? 0} eventos previos cubiertos por su huella`, tono: 'neutral' }
    case 'EXPORTACION_REPORTE':
      return {
        titulo: `${d.reporte === 'FICHA_CUSTODIA' ? 'Ficha de custodia' : 'Reporte'} exportado (${String(d.formato || '').toUpperCase()})`,
        detalle: d.reporte === 'FICHA_CUSTODIA' ? documento : null,
        tono: 'neutral',
      }
    case 'ACTUALIZACION_EXPEDIENTE': {
      const { anterior, nuevo } = d.cambios?.nombre || {}
      return {
        titulo: nuevo ? `Expediente renombrado: «${nuevo}»` : 'Nombre del expediente quitado',
        detalle: anterior ? `Antes: «${anterior}»` : 'Antes no tenía nombre',
        tono: 'neutral',
      }
    }
    case 'DESCARGA_DOCUMENTO':
      return { titulo: 'Archivo original descargado', detalle: documento, tono: 'neutral' }
    default:
      return { titulo: evento.evento, tono: 'neutral' }
  }
}

/**
 * Historial del expediente (HU-30): la bitácora inmutable en lenguaje del
 * analista, del evento más reciente al más antiguo. Se consulta al abrirlo.
 * `documentos` traduce el identificador de cada documento a su nombre.
 */
export default function HistorialExpediente({ expedienteId, documentos = [] }) {
  const [eventos, setEventos] = useState(null)
  const [error, setError] = useState('')
  const [cargando, setCargando] = useState(false)
  const [completo, setCompleto] = useState(false)
  const [cadena, setCadena] = useState(null)
  const nombres = new Map(documentos.map((d) => [d.id, d.nombre_archivo_original]))

  const cargar = async () => {
    setCargando(true)
    setError('')
    try {
      setEventos(await getBitacora({ expediente_id: expedienteId, limite: 200 }))
      // P3: la verificación de la cadena es informativa; si falla, el historial se muestra igual.
      setCadena(await verificarCadena().catch(() => null))
    } catch (err) {
      setError(err?.message || 'No se pudo consultar la bitácora.')
    } finally {
      setCargando(false)
    }
  }

  return (
    // Se consulta cada vez que se despliega: una auditoría, una ratificación o la
    // reevaluación programada agregan eventos mientras el expediente sigue abierto.
    // Al reconsultar se conservan los eventos ya mostrados, sin aviso de carga,
    // para que la lista no salte.
    <details className="exp-historial" onToggle={(e) => e.currentTarget.open && !cargando && cargar()}>
      <summary className="desplegable-titulo">
        <History size={12} aria-hidden="true" />
        Historial del expediente
        {eventos && <span className="tabular cell-muted"> · {eventos.length}</span>}
      </summary>
      {cargando && !eventos && (
        <p className="field-hint">
          <Loader2 className="spin" size={12} aria-hidden="true" /> Consultando la bitácora…
        </p>
      )}
      {error && <p className="notice notice--warn">{error}</p>}
      {cadena?.sellada && (
        <p
          className="field-hint"
          title={`Último sello ${cadena.ultimo_hash} · ${cadena.eventos_previos} eventos previos al sellado · ${cadena.algoritmo}`}
        >
          <span className={`status-dot status-dot--${cadena.integra ? 'ok' : 'bad'}`} aria-hidden="true" />{' '}
          {cadena.integra
            ? `Cadena de custodia íntegra · ${cadena.eventos_sellados} ${cadena.eventos_sellados === 1 ? 'evento sellado' : 'eventos sellados'}`
            : `Cadena de custodia comprometida · ${cadena.total_hallazgos} ${cadena.total_hallazgos === 1 ? 'hallazgo' : 'hallazgos'}: consulte la verificación de la bitácora`}
          {/* PLUS-22: sello de tiempo de un tercero, solo si está configurado. */}
          {cadena.sello_tiempo?.coincide && ` · sello de tiempo de un tercero del ${formatFecha(cadena.sello_tiempo.fecha_sello)}`}
        </p>
      )}
      {eventos && eventos.length === 0 && <p className="field-hint">Sin eventos registrados.</p>}
      {eventos && eventos.length > 0 && (() => {
        const grupos = agrupar(eventos, nombres)
        const mostrados = completo ? grupos : grupos.slice(0, VISIBLES)
        return (
          <>
            <ol className="historial">
              {mostrados.map(({ titulo, detalle, tono, evento: e, veces }) => (
                <li key={e.id} className="historial-evento">
                  <span className={`status-dot status-dot--${tono}`} aria-hidden="true" />
                  <div>
                    <p className="historial-titulo">
                      {titulo}
                      {veces > 1 && <Badge className="historial-veces">×{veces}</Badge>}
                    </p>
                    {detalle && <p className="historial-detalle">{detalle}</p>}
                    <p className="historial-meta tabular">
                      {veces > 1 ? 'Último: ' : ''}
                      {formatFecha(e.creado_en)} · {e.usuario}
                      {e.ip_origen ? ` · ${e.ip_origen}` : ''}
                    </p>
                  </div>
                </li>
              ))}
            </ol>
            {grupos.length > VISIBLES && (
              <Button compacto onClick={() => setCompleto(!completo)}>
                {completo ? 'Ver solo lo reciente' : `Ver todo (${grupos.length - VISIBLES} más)`}
              </Button>
            )}
          </>
        )
      })()}
    </details>
  )
}
