// Detalle desplegado del expediente: índice, motivos con su qué hacer, documentos, historial, carga y exportación.
import { useState } from 'react'
import { Lightbulb, Maximize2, Plus } from 'lucide-react'
import { Badge, Button, Card } from '../ui/index.js'
import DropZone from '../DropZone.jsx'
import { RenombrarExpediente } from '../CorreccionDatos.jsx'
import ExportarReporte from '../ExportarReporte.jsx'
import HistorialExpediente from '../HistorialExpediente.jsx'
import IndiceCumplimiento, { ReglasEvaluadas } from '../IndiceCumplimiento.jsx'
import {
  ESTADO_DOCUMENTO,
  getEstadoBadge,
  getSeveridadMeta,
  TIPO_DOCUMENTO_LABEL,
  tiposParaCarga,
  VIGENCIA_META,
} from '../../constants.js'
import { formatDia } from '../../utils/format.js'
import { AuditarPendientes } from './AuditarPendientes.jsx'

/**
 * Filas del detalle: cada documento que exige el catálogo de reglas (RIE-01),
 * los anexos que se volvieron exigibles (RIE-02) con el archivo vigente y su
 * estado, más los documentos opcionales cargados.
 */
function filasDetalle(evaluacion) {
  const obligatorios = evaluacion?.obligatorios || []
  const porTipo = new Map((evaluacion?.documentos || []).map((d) => [d.tipo_documento, d]))
  const filas = obligatorios.map((o) => {
    const doc = porTipo.get(o.tipo_documento)
    return {
      tipo: o.tipo_documento,
      regla: o.codigo_regla,
      severidad: o.severidad,
      anexoDe: o.documento_principal,
      obligatorio: true,
      doc,
      estado: o.presente ? doc?.estado || 'SIN_DICTAMEN' : 'FALTANTE',
    }
  })
  for (const d of evaluacion?.documentos || []) {
    if (!d.obligatorio) {
      filas.push({ tipo: d.tipo_documento, regla: null, severidad: null, obligatorio: false, doc: d, estado: d.estado })
    }
  }
  return filas
}

/** Línea de vigencia del archivo: estado a hoy y fecha en que vence o venció (RN-02). */
function Vigencia({ doc }) {
  if (!doc?.vigencia) return null
  const meta = VIGENCIA_META[doc.vigencia]
  const dias = doc.dias_para_vencer
  const texto =
    doc.vigencia === 'VENCIDO'
      ? `Venció el ${formatDia(doc.fecha_caducidad)}`
      : `Vence el ${formatDia(doc.fecha_caducidad)} · ${dias} ${dias === 1 ? 'día' : 'días'}`
  return <span className={`cell-sub cell-${meta?.tono === 'ok' ? 'muted' : meta?.tono}`}>{texto}</span>
}

const TITULO_MOTIVOS = {
  CONFORME: 'Por qué está conforme',
  EN_REVISION: 'Por qué está en revisión',
  NO_CONFORME: 'Por qué no está conforme',
}

/**
 * Un motivo del core («Acta de Asamblea (legado.pdf): dictamen no conforme.»)
 * separado en documento, archivo y causa para leerlo como fila; los motivos
 * generales («Faltan documentos obligatorios: …») quedan como texto.
 */
function partesMotivo(motivo) {
  // El archivo es el último paréntesis: el nombre del documento puede llevar uno («… (SAT)»).
  const m = /^(.+) \(([^()]+)\): (.+)$/.exec(motivo)
  return m ? { documento: m[1], archivo: m[2], causa: m[3] } : { causa: motivo }
}

/** Tono del punto de cada motivo; el texto dice la causa (el color nunca va solo). */
function tonoMotivo(causa) {
  const texto = causa.toLowerCase()
  if (/no conforme|cambió|vencido desde|protegido|faltan documentos obligatorios de severidad|no acreditada|requiere su anexo/.test(texto)) {
    return 'bad'
  }
  if (/sin auditar|pendiente|vence el|faltan documentos|ilegible|diferido/.test(texto)) return 'warn'
  return 'ok'
}

/** Documento al que se refiere una alerta: el core lo nombra tras los dos puntos del título («Dictamen no conforme: Acta de Asamblea»). */
const documentoDeAlerta = (alerta) => (alerta.titulo || '').split(': ').slice(1).join(': ')

/**
 * Reparte las alertas entre los motivos: las de un documento van con el motivo
 * de ese documento; las de los motivos generales («Faltan documentos
 * obligatorios: A, B», «… requiere su anexo «C»») con el motivo que nombra su
 * documento. Las que no encuentran motivo quedan aparte, para no perder ninguna
 * recomendación.
 */
function repartirAlertas(motivos, alertas) {
  const pendientes = [...alertas]
  const tomar = (prueba) => {
    const propias = pendientes.filter(prueba)
    for (const a of propias) pendientes.splice(pendientes.indexOf(a), 1)
    return propias
  }
  const filas = motivos.map((m) => ({ motivo: m, ...partesMotivo(m) }))
  for (const f of filas) {
    f.alertas = f.documento ? tomar((a) => documentoDeAlerta(a) === f.documento) : []
  }
  for (const f of filas.filter((x) => !x.documento)) {
    f.alertas = tomar((a) => documentoDeAlerta(a) && f.causa.includes(documentoDeAlerta(a)))
  }
  return { filas, sueltas: pendientes }
}

/** Qué hacer bajo un motivo: cada recomendación una vez y, plegado, el detalle con su severidad. */
function QueHacer({ alertas }) {
  if (!alertas.length) return null
  const recomendaciones = [...new Set(alertas.map((a) => a.recomendacion).filter(Boolean))]
  const detalles = alertas.filter((a) => a.detalle)
  return (
    <>
      {recomendaciones.map((r) => (
        <p key={r} className="exp-motivo-accion">
          <Lightbulb size={14} aria-hidden="true" />
          <span>
            <span className="sr-only">Qué hacer: </span>
            {r}
          </span>
        </p>
      ))}
      {detalles.length > 0 && (
        <details className="alerta-mas">
          <summary>Ver detalle</summary>
          {detalles.map((a) => (
            <p key={`${a.codigo}-${a.titulo}`} className="alerta-detalle">
              Severidad {getSeveridadMeta(a.severidad).label.toLowerCase()} · {a.detalle}
            </p>
          ))}
        </details>
      )}
    </>
  )
}

/**
 * Por qué el expediente tiene su estado y, bajo cada motivo, qué hacer: los
 * motivos del semáforo y las alertas del mismo documento en una sola fila, en
 * lugar de listar los documentos dos veces.
 */
function MotivosSemaforo({ estado, motivos = [], alertas = [] }) {
  if (!motivos.length && !alertas.length) return null
  const meta = getEstadoBadge(estado)
  const { filas, sueltas } = repartirAlertas(motivos, alertas)
  return (
    <section className="exp-motivos" aria-label={TITULO_MOTIVOS[estado] || 'Motivos del semáforo'}>
      <p className="exp-motivos-titulo">
        <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />
        {TITULO_MOTIVOS[estado] || 'Motivos del semáforo'}
        <span className="tabular cell-muted"> · {motivos.length}</span>
      </p>
      <ul className="exp-motivos-lista">
        {filas.map((f) => (
          <li key={f.motivo} className="exp-motivo">
            <span className={`status-dot status-dot--${tonoMotivo(f.causa)}`} aria-hidden="true" />
            <div className="exp-motivo-cuerpo">
              {f.documento ? (
                <>
                  <p className="exp-motivo-linea">
                    <span className="exp-motivo-nombre">{f.documento}</span>
                    <span className="exp-motivo-causa">{f.causa.replace(/\.$/, '')}</span>
                  </p>
                  <span className="cell-sub exp-motivo-archivo" title={f.archivo}>
                    {f.archivo}
                  </span>
                </>
              ) : (
                <p className="exp-motivo-linea">
                  <span className="exp-motivo-causa exp-motivo-causa--sola">{f.causa.replace(/\.$/, '')}</span>
                </p>
              )}
              <QueHacer alertas={f.alertas} />
            </div>
          </li>
        ))}
        {sueltas.map((a) => (
          <li key={`${a.codigo}-${a.titulo}`} className="exp-motivo">
            <span className={`status-dot status-dot--${getSeveridadMeta(a.severidad).tono}`} aria-hidden="true" />
            <div className="exp-motivo-cuerpo">
              <p className="exp-motivo-linea">
                <span className="exp-motivo-nombre">{a.titulo}</span>
              </p>
              <QueHacer alertas={[a]} />
            </div>
          </li>
        ))}
      </ul>
    </section>
  )
}

/**
 * Carga de un documento en el expediente. Si faltan obligatorios es la tarea
 * principal y la zona queda abierta; con todo completo se pliega tras un
 * botón (cargar un archivo del mismo tipo sustituye al vigente).
 */
function CustodiarDocumento({ faltantes, subiendo, tipos, onArchivo }) {
  const [abierta, setAbierta] = useState(false)
  const visible = faltantes > 0 || abierta || subiendo
  return (
    <>
      <p className="eyebrow">Custodiar documento</p>
      <p className="field-hint">
        {faltantes === 0
          ? 'Obligatorios completos. Cargar otro archivo del mismo tipo sustituye al vigente.'
          : faltantes === 1
            ? 'Falta 1 documento obligatorio.'
            : `Faltan ${faltantes} documentos obligatorios.`}
      </p>
      {visible ? (
        <DropZone compacto subiendo={subiendo} tipos={tipos} onArchivo={onArchivo} />
      ) : (
        <Button variante="secondary" compacto icono={Plus} onClick={() => setAbierta(true)}>
          Custodiar otro documento
        </Button>
      )}
    </>
  )
}

/** Detalle desplegado: índice, motivos con su qué hacer, documentos requeridos, historial, carga y exportación. */
export function DetalleExpediente({ exp, subiendo, onSubir, iaOnline, onRefresh, documentos, onAbrirDocumento }) {
  const evaluacion = exp.evaluacion
  const filas = filasDetalle(evaluacion)
  const alertas = evaluacion?.alertas || []
  const faltantes = evaluacion?.faltantes || []
  const tiposCarga = tiposParaCarga(exp.tipo_expediente, faltantes)
  const todos = documentos.filter((d) => d.expediente_id === exp.id)
  // Solo los documentos vigentes se navegan y auditan desde aquí: los sustituidos
  // por una versión más reciente siguen consultables en la Bóveda.
  const vigentes = new Set((evaluacion?.documentos || []).map((d) => d.documento_id))
  const delExpediente = todos.filter((d) => vigentes.has(d.id))

  return (
    <div className="exp-detail">
      <div className="exp-detail-main">
        <MotivosSemaforo estado={exp.estado_cumplimiento} motivos={evaluacion?.motivos} alertas={alertas} />

        <h3 className="section-title">Documentos requeridos</h3>
        <Card className="table-card table-card--flat">
          <table className="data-table data-table--inner">
            <colgroup>
              <col style={{ width: '42%' }} />
              <col />
              <col style={{ width: '132px' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Documento requerido</th>
                <th>Archivo vigente</th>
                <th className="col-right">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filas.length === 0 && (
                <tr className="empty-row">
                  <td colSpan={3} className="cell-muted">
                    El catálogo de reglas no declara documentos obligatorios.
                  </td>
                </tr>
              )}
              {filas.map((f) => {
                const meta = ESTADO_DOCUMENTO[f.estado] || ESTADO_DOCUMENTO.SIN_DICTAMEN
                const sev = f.severidad ? getSeveridadMeta(f.severidad) : null
                const nombreTipo = TIPO_DOCUMENTO_LABEL[f.tipo] || f.tipo
                const documento = f.doc && delExpediente.find((d) => d.id === f.doc.documento_id)
                return (
                  <tr key={f.tipo}>
                    <td>
                      <span className="cell-stack">
                        <span className="identity-name identity-name--completo">{nombreTipo}</span>
                        <span className="cell-sub cell-code" title={f.regla || undefined}>
                          {f.regla ? <span className="mono">{f.regla}</span> : 'Opcional'}
                          {sev && ` · ${sev.label}`}
                          {f.anexoDe && ` · anexo de ${TIPO_DOCUMENTO_LABEL[f.anexoDe] || f.anexoDe}`}
                        </span>
                      </span>
                    </td>
                    <td>
                      {f.doc ? (
                        <span className="cell-stack">
                          {documento ? (
                            <button
                              type="button"
                              className="enlace-archivo"
                              title={`Abrir ${f.doc.nombre_archivo_original}: auditoría y visor`}
                              onClick={() => onAbrirDocumento(documento, delExpediente)}
                            >
                              <span className="cell-ellipsis">{f.doc.nombre_archivo_original}</span>
                              <Maximize2 size={12} aria-hidden="true" />
                            </button>
                          ) : (
                            <span className="cell-ellipsis" title={f.doc.nombre_archivo_original}>
                              {f.doc.nombre_archivo_original}
                            </span>
                          )}
                          <Vigencia doc={f.doc} />
                          {f.doc.revisado_por_humano && <span className="cell-sub">Ratificado por un analista</span>}
                          {f.doc.estado_integridad === 'ALTERADO' && <span className="cell-sub cell-bad">Alterado</span>}
                        </span>
                      ) : (
                        <span className="cell-muted">No cargado</span>
                      )}
                    </td>
                    <td className="col-right">
                      <Badge tono={meta.tono} punto>
                        {f.doc?.vigencia === 'VENCIDO' ? 'Vencido' : meta.label}
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>

        {evaluacion?.sustituidos > 0 && (
          <p className="field-hint exp-tabla-nota">
            {evaluacion.sustituidos} {evaluacion.sustituidos === 1 ? 'archivo sustituido' : 'archivos sustituidos'} por uno
            más reciente del mismo tipo; su historial se conserva en la bitácora.
          </p>
        )}
        {evaluacion?.advertencia && <p className="notice notice--warn">{evaluacion.advertencia}</p>}

        <div className="exp-desplegables">
          <ReglasEvaluadas indice={evaluacion?.indice_cumplimiento} />
          <HistorialExpediente expedienteId={exp.id} documentos={todos} />
        </div>
      </div>

      {/* Columna lateral fija al desplazarse: el tablero del expediente
          (índice y acciones) acompaña a la lectura de la columna principal. */}
      <aside className="exp-detail-side">
        <div className="exp-lateral-bloque">
          <IndiceCumplimiento
            indice={evaluacion?.indice_cumplimiento}
            presentes={(evaluacion?.obligatorios || []).filter((o) => o.presente).length}
            obligatorios={(evaluacion?.obligatorios || []).length}
          />
        </div>
        <div className="exp-lateral-bloque">
          <AuditarPendientes exp={exp} iaOnline={iaOnline} onTerminado={onRefresh} />
        </div>
        <div className="exp-lateral-bloque">
          <CustodiarDocumento
            faltantes={faltantes.length}
            subiendo={subiendo}
            tipos={tiposCarga}
            onArchivo={(archivo, tipo) => onSubir(exp.id, archivo, tipo)}
          />
        </div>

        <div className="exp-lateral-bloque">
          <p className="eyebrow">Nombre del expediente</p>
          <p className="field-hint">{exp.nombre || 'Sin nombre descriptivo.'}</p>
          <RenombrarExpediente exp={exp} onRenombrado={onRefresh} />
        </div>

        <div className="exp-lateral-bloque">
          <p className="eyebrow">Dictamen de cumplimiento</p>
          <p className="field-hint">Reporte formal con documentos, evidencia de cada dictamen, alertas y bitácora.</p>
          <ExportarReporte ruta={`/reportes/expedientes/${exp.id}`} compacto />
        </div>
      </aside>
    </div>
  )
}
