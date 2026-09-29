// «Auditar pendientes» (HU-32): audita en secuencia los documentos vigentes sin dictamen.
import { useState } from 'react'
import { Check, Loader2, Minus, Sparkles, X } from 'lucide-react'
import { Badge, Button } from '../ui/index.js'
import { analizarDocumento, getExpedienteById } from '../../services/api.js'
import { getEstadoBadge } from '../../constants.js'

/** Estado de un documento dentro de «Auditar pendientes». */
const PASO = {
  cola: { icono: null, texto: 'En cola' },
  auditando: { icono: Loader2, texto: 'Auditando…' },
  hecho: { icono: Check, texto: null },
  error: { icono: X, texto: null },
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
        marcar(d.id, { estado: 'error', detalle: err?.message || 'Error del ai-service' })
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
          {pendientes.length} {pendientes.length === 1 ? 'documento sin auditar' : 'documentos sin auditar'}. Se validan
          con reglas e IA uno por uno.
        </p>
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
              <Badge tono={getEstadoBadge(resultado.antes.estado).tono}>{getEstadoBadge(resultado.antes.estado).label}</Badge>{' '}
              →{' '}
              <Badge tono={getEstadoBadge(resultado.despues.estado).tono}>{getEstadoBadge(resultado.despues.estado).label}</Badge>
              {' · '}
              {resultado.despues.alertas} {resultado.despues.alertas === 1 ? 'alerta' : 'alertas'} (antes{' '}
              {resultado.antes.alertas})
            </p>
          )}
        </div>
      )}
      {(!pasos || resultado) && pendientes.length > 0 && (
        <Button
          variante="primary"
          icono={Sparkles}
          onClick={auditar}
          disabled={enCurso || !iaOnline}
          title={iaOnline ? undefined : 'El ai-service (:8003) no responde'}
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
