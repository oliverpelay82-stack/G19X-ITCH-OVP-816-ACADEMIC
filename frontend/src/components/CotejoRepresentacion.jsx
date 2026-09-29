import { useEffect, useState } from 'react'
import { Badge, KeyValue, KeyValueList } from './ui/index.js'
import { useEvidencia } from './evidencia-context.js'
import { getExpedienteById } from '../services/api.js'

/** Contratos cuyo firmante se coteja con los apoderados del expediente (RSC-02-CONT, RSC-02-NDA). */
const TIPOS_CONTRATO = ['CONTRATO_SERVICIOS', 'ACUERDO_CONFIDENCIALIDAD']

const ESTADO = {
  ACREDITADO: { tono: 'ok', label: 'Acreditado' },
  NO_ACREDITADO: { tono: 'bad', label: 'No acreditado' },
  PODER_VENCIDO: { tono: 'bad', label: 'Poder vencido' },
  PENDIENTE: { tono: 'warn', label: 'Pendiente' },
}

function Persona({ persona, detalle, onCita }) {
  return (
    <span className="cell-stack">
      <span>
        {persona.nombre}
        {detalle && <span className="cell-muted"> · {detalle}</span>}
      </span>
      {persona.cita &&
        (onCita ? (
          <button type="button" className="cita-enlace contenido-cita" onClick={onCita} title="Ver la cita resaltada en el documento">
            <q>{persona.cita}</q>
          </button>
        ) : (
          <q className="contenido-cita">{persona.cita}</q>
        ))}
      {persona.cita_verificada === false && <span className="cell-sub">Cita no localizada en el documento</span>}
    </span>
  )
}

/**
 * Cotejo del firmante del contrato con los apoderados del poder notarial o del
 * acta constitutiva del expediente (RN-03, RSC-02, HU-23). Lo calcula el
 * core-service en cada evaluación; aquí solo se presenta, con sus citas, para
 * que el analista decida al ratificar el dictamen del contrato (RN-05).
 */
export default function CotejoRepresentacion({ doc, recarga = 0 }) {
  const evidencia = useEvidencia()
  const [cotejo, setCotejo] = useState(null)
  const [error, setError] = useState('')
  const aplica = TIPOS_CONTRATO.includes(doc.tipo_documento)

  useEffect(() => {
    if (!aplica) return undefined
    let vigente = true
    getExpedienteById(doc.expediente_id)
      .then((exp) => {
        if (!vigente) return
        setCotejo((exp.evaluacion?.representacion || []).find((c) => c.documento_id === doc.id) || null)
        setError('')
      })
      .catch((err) => vigente && setError(err.message))
    return () => {
      vigente = false
    }
  }, [aplica, doc.id, doc.expediente_id, recarga])

  if (!aplica) return null
  const estado = cotejo ? ESTADO[cotejo.estado] || ESTADO.PENDIENTE : null
  const coincidencia = cotejo?.coincidencias?.[0]
  const apoderados = coincidencia ? [coincidencia] : cotejo?.apoderados || []

  return (
    <div className="ia-bloque">
      <h5 className="section-title section-title--sm">Representación legal</h5>
      {error && <p className="field-hint">No se pudo consultar el cotejo: {error}</p>}
      {!error && !cotejo && <p className="field-hint">Este documento no es el contrato vigente de su tipo en el expediente.</p>}
      {cotejo && (
        <article className="registro-card">
          <header className="registro-head">
            <Badge tono={estado.tono}>{estado.label}</Badge>
            {cotejo.ratificado && <Badge>Ratificado</Badge>}
            <span className="registro-origen">Cotejo automático del firmante con los apoderados</span>
          </header>
          <KeyValueList className="registro-grid registro-grid--cotejo">
            <KeyValue etiqueta="Firmante del titular">
              {cotejo.firmantes.length === 0
                ? '—'
                : cotejo.firmantes.map((f) => (
                    <Persona
                      key={f.nombre}
                      persona={f}
                      detalle={f.cargo}
                      onCita={evidencia && f.cita_verificada ? () => evidencia.mostrar({ cita: f.cita, tono: 'ok' }) : null}
                    />
                  ))}
            </KeyValue>
            <KeyValue etiqueta={coincidencia ? 'Apoderado que coincide' : 'Apoderados del expediente'}>
              {apoderados.length === 0
                ? '—'
                : apoderados.map((a) => (
                    <Persona
                      key={`${a.documento_id}-${a.apoderado || a.nombre}`}
                      persona={{ ...a, nombre: a.apoderado || a.nombre }}
                      detalle={[a.cargo, a.facultades, a.nombre_archivo_original].filter(Boolean).join(' · ')}
                    />
                  ))}
            </KeyValue>
          </KeyValueList>
          <p className="registro-nota">
            {cotejo.motivo} {cotejo.recomendacion}
          </p>
        </article>
      )}
    </div>
  )
}
