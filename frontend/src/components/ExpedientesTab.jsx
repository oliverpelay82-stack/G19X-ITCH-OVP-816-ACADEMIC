import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, FolderKanban, Loader2, Plus, SearchX } from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonCards } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import DropZone from './DropZone.jsx'
import ExportarReporte from './ExportarReporte.jsx'
import { ListaAlertas } from './Alertas.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { EmptyState, Segmented, SearchBox } from './ui.jsx'
import { createExpediente, uploadDocumento } from '../services/api.js'
import {
  ESTADO_DOCUMENTO,
  getEstadoBadge,
  getSeveridadMeta,
  TIPO_DOCUMENTO_LABEL,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_EXPEDIENTE,
  tiposParaCarga,
  tonoPorPorcentaje,
  VIGENCIA_META,
} from '../constants.js'
import { formatDia, formatRelativo, iniciales } from '../utils/format.js'

/** Estados de cumplimiento del expediente, en el orden del semáforo. */
const ESTADOS_FILTRO = ['CONFORME', 'EN_REVISION', 'NO_CONFORME']

/**
 * Día (AAAA-MM-DD) de una marca de tiempo del backend. Las columnas TIMESTAMP
 * llegan sin zona y en la hora de la base, la misma referencia con la que el
 * resto del panel las muestra, así que basta con su parte de fecha.
 */
const diaDe = (fecha) => (fecha ? String(fecha).slice(0, 10) : '')

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

/** Detalle desplegado: tabla de documentos requeridos, alertas, motivos, carga y exportación. */
function DetalleExpediente({ exp, subiendo, onSubir }) {
  const evaluacion = exp.evaluacion
  const filas = filasDetalle(evaluacion)
  const alertas = evaluacion?.alertas || []
  const faltantes = evaluacion?.faltantes || []
  const tiposCarga = tiposParaCarga(exp.tipo_expediente, faltantes)

  return (
    <div className="exp-detail">
      <div className="exp-detail-main">
        <div className="card table-card table-card--flat">
          <table className="data-table data-table--inner">
            <colgroup>
              <col style={{ width: '29%' }} />
              <col style={{ width: '20%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: '25%' }} />
              <col style={{ width: '16%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Documento requerido</th>
                <th>Regla</th>
                <th>Severidad</th>
                <th>Archivo vigente</th>
                <th className="col-right">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filas.length === 0 && (
                <tr className="empty-row">
                  <td colSpan={5} className="cell-muted">
                    El catálogo de reglas no declara documentos obligatorios.
                  </td>
                </tr>
              )}
              {filas.map((f) => {
                const meta = ESTADO_DOCUMENTO[f.estado] || ESTADO_DOCUMENTO.SIN_DICTAMEN
                const sev = f.severidad ? getSeveridadMeta(f.severidad) : null
                return (
                  <tr key={f.tipo}>
                    <td>
                      <span className="cell-stack">
                        <span className="identity-name">{TIPO_DOCUMENTO_LABEL[f.tipo] || f.tipo}</span>
                        {f.anexoDe && (
                          <span className="cell-sub">Anexo de {TIPO_DOCUMENTO_LABEL[f.anexoDe] || f.anexoDe}</span>
                        )}
                      </span>
                    </td>
                    <td className="mono cell-mono cell-code" title={f.regla || undefined}>
                      {f.regla || <span className="cell-muted">Opcional</span>}
                    </td>
                    <td>{sev ? <span className="cell-muted">{sev.label}</span> : <span className="cell-muted">—</span>}</td>
                    <td>
                      {f.doc ? (
                        <span className="cell-stack">
                          <span className="cell-ellipsis" title={f.doc.nombre_archivo_original}>
                            {f.doc.nombre_archivo_original}
                          </span>
                          <Vigencia doc={f.doc} />
                          {f.doc.revisado_por_humano && <span className="cell-sub">Ratificado por un analista</span>}
                          {f.doc.estado_integridad === 'ALTERADO' && <span className="cell-sub cell-bad">Alterado (RIE-03)</span>}
                        </span>
                      ) : (
                        <span className="cell-muted">No cargado</span>
                      )}
                    </td>
                    <td className="col-right">
                      <span className={`badge badge--${meta.tono}`}>
                        <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />
                        {f.doc?.vigencia === 'VENCIDO' ? 'Vencido' : meta.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {alertas.length > 0 && (
          <section className="exp-alertas" aria-label="Alertas del expediente">
            <p className="eyebrow">
              Alertas y recomendaciones <span className="tabular cell-muted">· {alertas.length}</span>
            </p>
            <ListaAlertas alertas={alertas} />
          </section>
        )}

        {evaluacion?.motivos?.length > 0 && (
          <details className="exp-motivos">
            <summary className="eyebrow">Motivos del semáforo</summary>
            <ul>
              {evaluacion.motivos.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </details>
        )}
        {evaluacion?.advertencia && <p className="notice notice--warn">{evaluacion.advertencia}</p>}
        {evaluacion?.sustituidos > 0 && (
          <p className="field-hint">
            {evaluacion.sustituidos} {evaluacion.sustituidos === 1 ? 'archivo sustituido' : 'archivos sustituidos'} por uno
            más reciente del mismo tipo; su historial se conserva en la bitácora.
          </p>
        )}
      </div>

      <aside className="exp-detail-side">
        <p className="eyebrow">Custodiar documento</p>
        <p className="field-hint">
          {faltantes.length === 0
            ? 'Obligatorios completos. Cargar otro archivo del mismo tipo sustituye al vigente.'
            : faltantes.length === 1
              ? 'Falta 1 documento obligatorio.'
              : `Faltan ${faltantes.length} documentos obligatorios.`}
        </p>
        <DropZone compacto subiendo={subiendo} tipos={tiposCarga} onArchivo={(archivo, tipo) => onSubir(exp.id, archivo, tipo)} />

        <div className="exp-export">
          <p className="eyebrow">Dictamen de cumplimiento</p>
          <p className="field-hint">Reporte formal con documentos, evidencia de cada dictamen, alertas y bitácora.</p>
          <ExportarReporte ruta={`/reportes/expedientes/${exp.id}`} compacto />
        </div>
      </aside>
    </div>
  )
}

/**
 * Expedientes como tarjetas: cabecera con titular, tipo, folio, semáforo
 * grande y completitud; al desplegarse, la tabla de documentos que exige el
 * rules-service para su tipo, con el estado y la vigencia de cada uno, las
 * alertas con su recomendación y la exportación del dictamen.
 *
 * `foco` es el expediente que debe abrirse al llegar desde Empresas o
 * Alertas; `apertura`, el titular para el que se pidió abrir un expediente.
 */
export default function ExpedientesTab({
  expedientes,
  titulares,
  loading,
  onRefresh,
  isOnline = true,
  foco = null,
  onFocoAtendido,
  apertura = null,
  onAperturaAtendida,
}) {
  const toast = useToast()
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState({ titularId: '', tipo: 'CORPORATIVO', nombre: '' })
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('TODOS')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [expandido, setExpandido] = useState(null)
  const [subiendoEn, setSubiendoEn] = useState(null)
  const tarjetas = useRef(new Map())

  const consulta = useDebounce(busqueda, 220)
  // El expediente enfocado desde otra vista se abre hasta que el operador interactúa.
  const abiertoId = foco ?? expandido

  useEffect(() => {
    if (foco && !loading) tarjetas.current.get(foco)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [foco, loading])

  // Apertura pedida desde Empresas: el modal llega con el titular preseleccionado.
  const [aperturaVista, setAperturaVista] = useState(null)
  if (apertura && apertura !== aperturaVista) {
    setAperturaVista(apertura)
    setForm({ titularId: apertura, tipo: 'CORPORATIVO', nombre: '' })
    setModalAbierto(true)
    onAperturaAtendida?.()
  }

  const opcionesEstado = useMemo(
    () => [
      { id: 'TODOS', label: 'Todos', conteo: expedientes.length },
      ...ESTADOS_FILTRO.map((estado) => ({
        id: estado,
        label: getEstadoBadge(estado).label,
        tono: getEstadoBadge(estado).tono,
        conteo: expedientes.filter((e) => e.estado_cumplimiento === estado).length,
      })),
    ],
    [expedientes]
  )

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return expedientes.filter((exp) => {
      const coincideEstado = filtroEstado === 'TODOS' || exp.estado_cumplimiento === filtroEstado
      const coincideTipo = filtroTipo === 'TODOS' || exp.tipo_expediente === filtroTipo
      const dia = diaDe(exp.creado_en)
      const coincideFecha = (!desde || (dia && dia >= desde)) && (!hasta || (dia && dia <= hasta))
      const coincideBusqueda =
        !q ||
        exp.codigo_expediente?.toLowerCase().includes(q) ||
        exp.nombre?.toLowerCase().includes(q) ||
        exp.titular?.razon_social?.toLowerCase().includes(q) ||
        exp.titular?.rfc?.toLowerCase().includes(q)
      return coincideEstado && coincideTipo && coincideFecha && coincideBusqueda
    })
  }, [expedientes, consulta, filtroEstado, filtroTipo, desde, hasta])

  const hayFiltros = filtroTipo !== 'TODOS' || desde || hasta

  const alternar = (id) => {
    setExpandido(abiertoId === id ? null : id)
    onFocoAtendido?.()
  }

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm({ titularId: '', tipo: 'CORPORATIVO', nombre: '' })
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.titularId) return
    setEnviando(true)
    setError('')
    try {
      const creado = await createExpediente({
        titular_id: form.titularId,
        tipo_expediente: form.tipo,
        nombre: form.nombre.trim() || null,
      })
      toast.exito('Expediente aperturado', `${creado?.codigo_expediente || 'Folio generado'} · ${TIPO_EXPEDIENTE_LABEL[form.tipo]}`)
      cerrarModal()
      await onRefresh()
      if (creado?.id) {
        setExpandido(creado.id)
        onFocoAtendido?.()
      }
    } catch (err) {
      setError(err.message)
      toast.error('No se pudo aperturar', err.message)
    } finally {
      setEnviando(false)
    }
  }

  /** Carga directa desde el detalle del expediente. */
  const subirDocumento = async (expedienteId, archivo, tipoDocumento) => {
    setSubiendoEn(expedienteId)
    try {
      const formData = new FormData()
      formData.append('expediente_id', expedienteId)
      formData.append('tipo_documento', tipoDocumento)
      formData.append('file', archivo)
      await uploadDocumento(formData)
      toast.exito('Documento custodiado', `${archivo.name} → bóveda criptográfica`)
      onRefresh()
    } catch (err) {
      toast.error('Carga rechazada', err.message)
    } finally {
      setSubiendoEn(null)
    }
  }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por folio, nombre, razón social o RFC…"
          label="Buscar expedientes"
        />
        <Segmented
          label="Filtrar por estado de cumplimiento"
          valor={filtroEstado}
          onChange={setFiltroEstado}
          opciones={opcionesEstado}
        />

        <button
          type="button"
          className="btn btn-primary toolbar-action"
          onClick={() => setModalAbierto(true)}
          disabled={titulares.length === 0 || !isOnline}
          title={titulares.length === 0 ? 'Primero registra una empresa' : undefined}
        >
          <Plus size={14} />
          Aperturar expediente
        </button>
      </div>

      <div className="toolbar toolbar--sub">
        <label className="select-inline">
          <span className="sr-only">Filtrar por tipo de expediente</span>
          <select value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
            <option value="TODOS">Todo tipo de expediente</option>
            {TIPOS_EXPEDIENTE.map((t) => (
              <option key={t.value} value={t.value}>
                {t.label} ({expedientes.filter((e) => e.tipo_expediente === t.value).length})
              </option>
            ))}
          </select>
        </label>
        <label className="date-inline">
          <span>Apertura desde</span>
          <input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label className="date-inline">
          <span>hasta</span>
          <input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} />
        </label>
        {hayFiltros && (
          <button
            type="button"
            className="btn btn-secondary btn-sm"
            onClick={() => {
              setFiltroTipo('TODOS')
              setDesde('')
              setHasta('')
            }}
          >
            Limpiar filtros
          </button>
        )}
      </div>

      {loading && <SkeletonCards count={3} height={72} />}

      {!loading && filtrados.length === 0 && (
        <div className="card">
          <EmptyState
            icon={expedientes.length === 0 ? FolderKanban : SearchX}
            titulo={expedientes.length === 0 ? 'Aún no hay expedientes aperturados' : 'Sin resultados'}
            descripcion={
              expedientes.length === 0
                ? 'Apertura un expediente para empezar a custodiar la documentación de un titular.'
                : 'Ajusta la búsqueda o los filtros de estado, tipo y fecha.'
            }
          />
        </div>
      )}

      {!loading && filtrados.length > 0 && (
        <div className="exp-list">
          {filtrados.map((exp) => {
            const meta = getEstadoBadge(exp.estado_cumplimiento)
            const progreso = Math.max(0, Math.min(100, Number(exp.porcentaje_completitud || 0)))
            const obligatorios = exp.evaluacion?.obligatorios || []
            const presentes = obligatorios.filter((o) => o.presente).length
            const nAlertas = exp.evaluacion?.alertas?.length || 0
            const abierto = abiertoId === exp.id
            return (
              <article
                key={exp.id}
                className={`card exp-card exp-card--${meta.tono} ${abierto ? 'is-open' : ''}`}
                ref={(el) => (el ? tarjetas.current.set(exp.id, el) : tarjetas.current.delete(exp.id))}
              >
                <button
                  type="button"
                  className="exp-summary"
                  onClick={() => alternar(exp.id)}
                  aria-expanded={abierto}
                  aria-label={`${exp.titular?.razon_social || exp.codigo_expediente}: ${meta.label}`}
                >
                  <span className="avatar" aria-hidden="true">
                    {iniciales(exp.titular?.razon_social || exp.codigo_expediente)}
                  </span>
                  <span className="exp-identity">
                    <span className="exp-identity-row">
                      <span className="identity-name">{exp.titular?.razon_social || 'Titular no disponible'}</span>
                      <span className="tag tag--type">{TIPO_EXPEDIENTE_LABEL[exp.tipo_expediente] || exp.tipo_expediente}</span>
                    </span>
                    <span className="cell-sub">
                      {exp.nombre && <span className="exp-nombre">{exp.nombre} · </span>}
                      <span className="mono">
                        {exp.codigo_expediente} · {exp.titular?.rfc || 'sin RFC'}
                      </span>
                      {nAlertas > 0 && (
                        <span className="exp-nalertas">
                          {' '}
                          · {nAlertas} {nAlertas === 1 ? 'alerta' : 'alertas'}
                        </span>
                      )}
                    </span>
                  </span>
                  <span className={`badge badge--lg badge--${meta.tono}`}>
                    <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />
                    {meta.label}
                  </span>
                  <span className="progress" title={`${presentes} de ${obligatorios.length} documentos obligatorios`}>
                    <span className="progress-track">
                      <span className={`progress-fill progress-fill--${tonoPorPorcentaje(progreso)}`} style={{ width: `${progreso}%` }} />
                    </span>
                    <span className="progress-value tabular">
                      {presentes}/{obligatorios.length}
                    </span>
                  </span>
                  <span className="exp-updated cell-muted tabular">{formatRelativo(exp.actualizado_en)}</span>
                  <span className="squircle exp-chevron" aria-hidden="true">
                    <ChevronDown size={14} className="chevron" />
                  </span>
                </button>

                {abierto && <DetalleExpediente exp={exp} subiendo={subiendoEn === exp.id} onSubir={subirDocumento} />}
              </article>
            )
          })}
        </div>
      )}

      {modalAbierto && (
        <Modal
          title="Aperturar expediente"
          subtitle="Vincula un nuevo fólder de cumplimiento a un titular existente"
          onClose={cerrarModal}
        >
          <form className="form-grid" onSubmit={handleSubmit}>
            <label className="field">
              <span className="field-label">Titular</span>
              <select required value={form.titularId} onChange={(e) => setForm({ ...form, titularId: e.target.value })}>
                <option value="" disabled>
                  Selecciona una empresa…
                </option>
                {titulares.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.razon_social} — {t.rfc}
                  </option>
                ))}
              </select>
            </label>

            <div className="field">
              <span className="field-label">Tipo de expediente</span>
              <div className="type-options" role="radiogroup" aria-label="Tipo de expediente">
                {TIPOS_EXPEDIENTE.map((t) => (
                  <label key={t.value} className={`type-option ${form.tipo === t.value ? 'is-active' : ''}`}>
                    <input
                      type="radio"
                      name="tipo_expediente"
                      value={t.value}
                      checked={form.tipo === t.value}
                      onChange={() => setForm({ ...form, tipo: t.value })}
                    />
                    <span className="type-option-label">{t.label}</span>
                    <span className="type-option-desc">{t.descripcion}</span>
                  </label>
                ))}
              </div>
              <span className="field-hint">El tipo decide qué documentos exige el catálogo de reglas (RF-06).</span>
            </div>

            <label className="field">
              <span className="field-label">Nombre descriptivo (opcional)</span>
              <input
                maxLength={150}
                placeholder="Ej. Contrato de mantenimiento 2026"
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </label>

            <p className="field-hint">El folio del expediente lo genera el core-service (:8001) al momento del alta.</p>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando || !form.titularId}>
                {enviando && <Loader2 className="spin" size={14} />}
                Crear expediente
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
