// «Auditar pendientes» (HU-32): audita en secuencia los documentos vigentes sin dictamen.
import { useState } from 'react'
import { Check, CircleNotch, Minus, Sparkle, X } from '../iconos.js'
import { Button } from '../ui/index.js'
import { analizarDocumento, getExpedienteById } from '../../services/api.js'
import { getEstadoBadge } from '../../constants.js'
import EstadoBadge from '../EstadoBadge.jsx'
import { plural } from '../../utils/format.js'

/** Estado de un documento dentro de «Auditar pendientes». */
const PASO = {
  cola: { icono: null, texto: 'En cola' },
  auditando: { icono: CircleNotch, texto: 'Auditando…' },
  hecho: { icono: Check, texto: null },
  error: { icono: X, texto: null },
}

/**
 * D5 · Anillo de progreso de la auditoría: se llena con cada documento
 * terminado (auditado o con error) y muestra «n de m» al centro. Al terminar
 * se pone en verde si todos se auditaron, o en ámbar si alguno falló.
 */
function AnilloProgreso({ hechos, total, fallidos, terminado }) {
  const radio = 15
  const circunferencia = 2 * Math.PI * radio
  const avance = total ? hechos / total : 0
  const tono = !terminado ? 'curso' : fallidos ? 'warn' : 'ok'
  return (
    <div
      className={`anillo-progreso anillo-progreso--${tono}`}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={total}
      aria-valuenow={hechos}
      aria-label="Avance de la auditoría"
    >
      <svg viewBox="0 0 36 36" aria-hidden="true">
        <circle className="anillo-progreso-pista" cx="18" cy="18" r={radio} />
        <circle
          className="anillo-progreso-avance"
          cx="18"
          cy="18"
          r={radio}
          strokeDasharray={circunferencia}
          strokeDashoffset={circunferencia * (1 - avance)}
        />
      </svg>
      <span className="anillo-progreso-cifra tabular">
        {hechos}
        <span className="anillo-progreso-total">/{total}</span>
      </span>
    </div>
  )
}

/**
 * Validación del expediente con un solo botón (HU-32): audita en secuencia,
 * con reglas e IA, los documentos vigentes que aún no tienen dictamen. Es una
 * ejecución manual: subir un archivo nunca lo analiza por sí solo. Un fallo en
 * un documento no detiene los demás (HU-33). Muestra el avance por documento
 * y, al terminar, el resultado consolidado: el semáforo antes y después y las
 * alertas que quedan.
 */
export function AuditarPendientes({ exp, iaOnline, onTerminado }) {
  const [pasos, setPasos] = useState(null)
  const [resultado, setResultado] = useState(null)
  const pendientes = (exp.evaluacion?.documentos || []).filter(
    (d) => d.estado === 'SIN_DICTAMEN' && d.estado_integridad !== 'ALTERADO'
  )
  const enCurso = Boolean(pasos) && !resultado

  const auditar = async () => {
    const antes = { estado: exp.estado_cumplimiento, alertas: exp.evaluacion?.alertas?.length || 0 }
    const lista = pendientes.map((d) => ({ id: d.documento_id, nombre: d.nombre_archivo_original, estado: 'cola' }))
    setResultado(null)
    setPasos(lista)
    const marcar = (id, cambio) => setPasos((prev) => prev.map((p) => (p.id === id ? { ...p, ...cambio } : p)))
    let fallidos = 0
    for (const d of lista) {
      marcar(d.id, { estado: 'auditando' })
      try {
        const r = await analizarDocumento({
          documento_id: d.id,
          rfc_titular: exp.titular?.rfc || undefined,
          razon_social_titular: exp.titular?.razon_social || undefined,
        })
        marcar(d.id, { estado: 'hecho', dictamen: r?.estatus_preliminar })
      } catch (err) {
        fallidos += 1
        marcar(d.id, { estado: 'error', detalle: err?.message || 'Error del servicio de análisis con IA' })
      }
    }
    let despues = null
    try {
      const actualizado = await getExpedienteById(exp.id)
      despues = { estado: actualizado?.estado_cumplimiento, alertas: actualizado?.evaluacion?.alertas?.length || 0 }
    } catch {
      // El resultado se muestra sin el semáforo si el core-service no responde.
    }
    setResultado({ antes, despues, auditados: lista.length - fallidos, total: lista.length })
    onTerminado?.()
  }

  if (!pendientes.length && !pasos) return null
  return (
    <div className="exp-auditar">
      <p className="eyebrow">Validación del expediente</p>
      {!pasos && (
        <p className="field-hint">
          {plural(pendientes.length, 'documento sin auditar', 'documentos sin auditar')}. Se validan
          con reglas e IA uno por uno.
        </p>
      )}
      {pasos && (
        <div className="auditoria-avance">
          <AnilloProgreso
            hechos={pasos.filter((p) => p.estado === 'hecho' || p.estado === 'error').length}
            total={pasos.length}
            fallidos={pasos.filter((p) => p.estado === 'error').length}
            terminado={Boolean(resultado)}
          />
          <p className="field-hint">
            {resultado
              ? 'Auditoría terminada.'
              : `Auditando ${pasos.findIndex((p) => p.estado === 'auditando') + 1 || pasos.length} de ${pasos.length}…`}
          </p>
        </div>
      )}
      {pasos && (
        <ol className="auditoria-pasos" aria-live="polite">
          {pasos.map((p) => {
            const meta = PASO[p.estado]
            const Icono = meta.icono
            const estatus = p.dictamen && getEstadoBadge(p.dictamen)
            return (
              <li key={p.id} className={`auditoria-paso auditoria-paso--${p.estado}`}>
                <span className="auditoria-paso-icono" aria-hidden="true">
                  {Icono ? <Icono size={12} className={p.estado === 'auditando' ? 'spin' : undefined} /> : <Minus size={12} />}
                </span>
                <span className="cell-ellipsis" title={p.nombre}>
                  {p.nombre}
                </span>
                <span className={`auditoria-paso-estado ${p.estado === 'error' ? 'cell-bad' : ''}`} title={p.detalle}>
                  {estatus ? estatus.label : p.estado === 'error' ? 'Error' : meta.texto}
                </span>
              </li>
            )
          })}
        </ol>
      )}
      {resultado && (
        <div className="auditoria-resultado" role="status">
          <p>
            <strong>
              {resultado.auditados} de {resultado.total}
            </strong>{' '}
            {resultado.total === 1 ? 'documento auditado' : 'documentos auditados'}.
          </p>
          {resultado.despues && (
            <p>
              Semáforo{' '}
              <EstadoBadge estado={resultado.antes.estado} punto={false} />{' '}
              →{' '}
              <EstadoBadge estado={resultado.despues.estado} punto={false} />
              {' · '}
              {plural(resultado.despues.alertas, 'alerta', 'alertas')} (antes{' '}
              {resultado.antes.alertas})
            </p>
          )}
        </div>
      )}
      {(!pasos || resultado) && pendientes.length > 0 && (
        <Button
          variante="primary"
          icono={Sparkle}
          onClick={auditar}
          disabled={enCurso || !iaOnline}
          title={iaOnline ? undefined : 'El servicio de análisis con IA no responde'}
        >
          Auditar pendientes
        </Button>
      )}
      {enCurso && (
        <Button variante="primary" cargando>
          Auditando…
        </Button>
      )}
    </div>
  )
}
