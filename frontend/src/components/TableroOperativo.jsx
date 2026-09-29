import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, CalendarCheck, CalendarClock, ClipboardCheck, TrendingUp } from 'lucide-react'
import { Card, EmptyState } from './ui/index.js'
import { getBitacora } from '../services/api.js'
import { ALERTA_META, getEstadoBadge, TIPO_DOCUMENTO_LABEL } from '../constants.js'
import { formatFecha } from '../utils/format.js'

const MAX_FILAS = 6
const DIAS_EVOLUCION = 30

/** Alertas que esperan una acción del analista (Nivel 5), en el orden en que conviene atenderlas. */
const PENDIENTES = ['PENDIENTE_RATIFICACION', 'CONTENIDO_NO_LOCALIZADO', 'PENDIENTE_AUDITORIA']

function textoVencimiento(dias) {
  if (dias < 0) return `Venció hace ${Math.abs(dias)} ${Math.abs(dias) === 1 ? 'día' : 'días'}`
  if (dias === 0) return 'Vence hoy'
  return `Vence en ${dias} ${dias === 1 ? 'día' : 'días'}`
}

/** Documentos vencidos o próximos a vencer de todos los expedientes, del más urgente al menos (RF-16, RF-17). */
function ProximosVencimientos({ expedientes, onAbrirExpediente }) {
  const lista = useMemo(
    () =>
      expedientes
        .flatMap((e) =>
          (e.evaluacion?.documentos || [])
            .filter((d) => d.vigencia === 'VENCIDO' || d.vigencia === 'PROXIMO_A_VENCER')
            .map((d) => ({ ...d, expediente: e }))
        )
        .sort((a, b) => (a.dias_para_vencer ?? 0) - (b.dias_para_vencer ?? 0)),
    [expedientes]
  )
  return (
    <Card as="article" className="report-card">
      <p className="eyebrow eyebrow--icon">
        <CalendarClock size={12} aria-hidden="true" />
        Vencimientos · {lista.length}
      </p>
      {lista.length === 0 ? (
        <EmptyState
          className="empty-state--tarjeta"
          icon={CalendarCheck}
          titulo="Sin vencimientos"
          descripcion="Ningún documento vencido ni próximo a vencer."
        />
      ) : (
        <ul className="tablero-lista">
          {lista.slice(0, MAX_FILAS).map((d) => {
            const tono = d.vigencia === 'VENCIDO' ? 'bad' : 'warn'
            return (
              <li key={d.documento_id}>
                <button type="button" className="tablero-fila" onClick={() => onAbrirExpediente?.(d.expediente.id)}>
                  <span className={`status-dot status-dot--${tono}`} aria-hidden="true" />
                  <span className="tablero-fila-texto">
                    <span className="tablero-fila-titulo">{TIPO_DOCUMENTO_LABEL[d.tipo_documento] || d.tipo_documento}</span>
                    <span className="tablero-fila-sub mono">{d.expediente.codigo_expediente}</span>
                  </span>
                  <span className={`tablero-fila-dato cell-${tono} tabular`}>{textoVencimiento(d.dias_para_vencer ?? 0)}</span>
                  <ArrowUpRight size={12} aria-hidden="true" />
                </button>
              </li>
            )
          })}
          {lista.length > MAX_FILAS && <li className="field-hint">y {lista.length - MAX_FILAS} más.</li>}
        </ul>
      )}
    </Card>
  )
}

/** Lo que espera al analista: ratificaciones, contenido por confirmar y documentos sin auditar. */
function PendientesAnalista({ expedientes, onAbrirExpediente }) {
  const grupos = useMemo(
    () =>
      PENDIENTES.map((codigo) => {
        const porExpediente = expedientes
          .map((e) => ({ expediente: e, n: (e.evaluacion?.alertas || []).filter((a) => a.codigo === codigo).length }))
          .filter((x) => x.n > 0)
          .sort((a, b) => b.n - a.n)
        return { codigo, total: porExpediente.reduce((s, x) => s + x.n, 0), porExpediente }
      }),
    [expedientes]
  )
  const total = grupos.reduce((s, g) => s + g.total, 0)
  return (
    <Card as="article" className="report-card">
      <p className="eyebrow eyebrow--icon">
        <ClipboardCheck size={12} aria-hidden="true" />
        Pendientes del analista · {total}
      </p>
      {total === 0 ? (
        <EmptyState
          className="empty-state--tarjeta"
          icon={ClipboardCheck}
          titulo="Nada pendiente"
          descripcion="Todos los dictámenes están resueltos."
        />
      ) : (
        <ul className="tablero-lista">
          {grupos
            .filter((g) => g.total)
            .map((g) => (
              <li key={g.codigo} className="tablero-grupo">
                <p className="tablero-grupo-titulo">
                  {ALERTA_META[g.codigo]?.label || g.codigo} <span className="tabular cell-muted">· {g.total}</span>
                </p>
                <div className="tablero-chips">
                  {g.porExpediente.slice(0, 4).map(({ expediente, n }) => (
                    <button
                      key={expediente.id}
                      type="button"
                      className="chip chip--xs"
                      onClick={() => onAbrirExpediente?.(expediente.id)}
                      title={expediente.titular?.razon_social || undefined}
                    >
                      <span className="mono">{expediente.codigo_expediente}</span>
                      {/* Espacio de no separación: el chip es inline-flex y recorta el espacio inicial del texto. */}
                      {n > 1 ? ` · ${n}` : ''}
                    </button>
                  ))}
                </div>
              </li>
            ))}
        </ul>
      )}
    </Card>
  )
}

/**
 * Cambios del semáforo de los últimos días, tomados de la bitácora inmutable
 * (EVALUACION_REGLAS registra solo los cambios reales de estado).
 */
function EvolucionSemaforo({ expedientes, onAbrirExpediente }) {
  const [eventos, setEventos] = useState(null)
  const [error, setError] = useState('')
  useEffect(() => {
    let vigente = true
    getBitacora({ evento: 'EVALUACION_REGLAS', limite: 500 })
      // El corte del periodo se fija al recibir los datos, no en cada render.
      .then((r) => vigente && setEventos({ lista: r, desde: Date.now() - DIAS_EVOLUCION * 86_400_000 }))
      .catch((err) => vigente && setError(err?.message || 'No se pudo consultar la bitácora.'))
    return () => {
      vigente = false
    }
  }, [])

  const recientes = (eventos?.lista || []).filter((e) => new Date(e.creado_en).getTime() >= eventos.desde)
  const conteo = (estado) => recientes.filter((e) => e.detalle?.estado_nuevo === estado).length
  const codigos = new Map(expedientes.map((e) => [e.id, e.codigo_expediente]))

  return (
    <Card as="article" className="report-card">
      <p className="eyebrow eyebrow--icon">
        <TrendingUp size={12} aria-hidden="true" />
        Cambios del semáforo · {DIAS_EVOLUCION} días
      </p>
      {error && <p className="notice notice--warn">{error}</p>}
      {!eventos && !error && <p className="field-hint">Consultando la bitácora…</p>}
      {eventos && (
        <>
          <div className="tablero-cifras">
            {['NO_CONFORME', 'EN_REVISION', 'CONFORME'].map((estado) => {
              const meta = getEstadoBadge(estado)
              return (
                <div key={estado} className="tablero-cifra">
                  <span className="tablero-cifra-valor tabular">{conteo(estado)}</span>
                  <span className="tablero-cifra-etiqueta">
                    <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />a {meta.label.toLowerCase()}
                  </span>
                </div>
              )
            })}
          </div>
          {recientes.length === 0 ? (
            <p className="field-hint">Sin cambios en el periodo.</p>
          ) : (
            <ul className="tablero-lista">
              {recientes.slice(0, 4).map((e) => {
                const nuevo = getEstadoBadge(e.detalle?.estado_nuevo)
                return (
                  <li key={e.id}>
                    <button type="button" className="tablero-fila" onClick={() => onAbrirExpediente?.(e.expediente_id)}>
                      <span className={`status-dot status-dot--${nuevo.tono}`} aria-hidden="true" />
                      <span className="tablero-fila-texto">
                        <span className="tablero-fila-titulo">
                          {getEstadoBadge(e.detalle?.estado_anterior).label} → {nuevo.label}
                        </span>
                        <span className="tablero-fila-sub mono">{codigos.get(e.expediente_id) || 'Expediente'}</span>
                      </span>
                      <span className="tablero-fila-dato tabular">{formatFecha(e.creado_en, { day: '2-digit', month: 'short' })}</span>
                      <ArrowUpRight size={12} aria-hidden="true" />
                    </button>
                  </li>
                )
              })}
            </ul>
          )}
        </>
      )}
    </Card>
  )
}

/**
 * Segunda fila del tablero (RF-22, HU-26): lo que requiere atención. Todo se
 * calcula con las mismas evaluaciones que muestra el semáforo, salvo la
 * evolución, que viene de la bitácora. Cada fila abre su expediente.
 */
export default function TableroOperativo({ expedientes, onAbrirExpediente }) {
  return (
    <section className="report-grid" aria-label="Atención requerida">
      <ProximosVencimientos expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
      <PendientesAnalista expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
      <EvolucionSemaforo expedientes={expedientes} onAbrirExpediente={onAbrirExpediente} />
    </section>
  )
}
