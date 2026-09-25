import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, FolderKanban, Loader2, Plus, SearchX } from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonCards } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import DropZone from './DropZone.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { EmptyState, Segmented, SearchBox } from './ui.jsx'
import { createExpediente, uploadDocumento } from '../services/api.js'
import {
  ESTADO_DOCUMENTO,
  getEstadoBadge,
  getSeveridadMeta,
  TIPO_DOCUMENTO_LABEL,
  TIPOS_DOCUMENTO,
  tonoPorPorcentaje,
} from '../constants.js'
import { formatRelativo, iniciales } from '../utils/format.js'

/** Estados de cumplimiento del expediente, en el orden del semáforo. */
const ESTADOS_FILTRO = ['CONFORME', 'EN_REVISION', 'NO_CONFORME']

/**
 * Filas del detalle: cada documento que exige el catálogo de reglas (RIE-01)
 * con el archivo vigente y su estado, más los documentos opcionales cargados.
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

/** Detalle desplegado: tabla de documentos requeridos, motivos del semáforo y carga. */
function DetalleExpediente({ exp, subiendo, onSubir }) {
  const evaluacion = exp.evaluacion
  const filas = filasDetalle(evaluacion)
  const faltantes = new Set(evaluacion?.faltantes || [])
  // Los faltantes primero; el resto sigue disponible para sustituir al vigente.
  const tiposCarga = [...TIPOS_DOCUMENTO].sort(
    (a, b) => Number(!faltantes.has(a.value)) - Number(!faltantes.has(b.value))
  )

  return (
    <div className="exp-detail">
      <div className="exp-detail-main">
        <div className="card table-card table-card--flat">
          <table className="data-table data-table--inner">
            <colgroup>
              <col style={{ width: '32%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '12%' }} />
              <col style={{ width: '26%' }} />
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
                      <span className="identity-name">{TIPO_DOCUMENTO_LABEL[f.tipo] || f.tipo}</span>
                    </td>
                    <td className="mono cell-mono">{f.regla || <span className="cell-muted">Opcional</span>}</td>
                    <td>{sev ? <span className="cell-muted">{sev.label}</span> : <span className="cell-muted">—</span>}</td>
                    <td>
                      {f.doc ? (
                        <span className="cell-stack">
                          <span className="cell-ellipsis" title={f.doc.nombre_archivo_original}>
                            {f.doc.nombre_archivo_original}
                          </span>
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
                        {meta.label}
                      </span>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>

        {evaluacion?.motivos?.length > 0 && (
          <div className="exp-motivos">
            <p className="eyebrow">Motivos del semáforo</p>
            <ul>
              {evaluacion.motivos.map((m) => (
                <li key={m}>{m}</li>
              ))}
            </ul>
          </div>
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
          {faltantes.size === 0
            ? 'Obligatorios completos. Cargar otro archivo del mismo tipo sustituye al vigente.'
            : `Faltan ${faltantes.size} ${faltantes.size === 1 ? 'documento obligatorio' : 'documentos obligatorios'}.`}
        </p>
        <DropZone compacto subiendo={subiendo} tipos={tiposCarga} onArchivo={(archivo, tipo) => onSubir(exp.id, archivo, tipo)} />
      </aside>
    </div>
  )
}

/**
 * Expedientes como tarjetas: cabecera con titular, folio, semáforo grande y
 * completitud; al desplegarse, la tabla de documentos que exige el
 * rules-service con el estado de cada uno y los motivos del semáforo.
 *
 * `foco` es el expediente que debe abrirse al llegar desde Empresas.
 */
export default function ExpedientesTab({
  expedientes,
  titulares,
  loading,
  onRefresh,
  isOnline = true,
  foco = null,
  onFocoAtendido,
}) {
  const toast = useToast()
  const [modalAbierto, setModalAbierto] = useState(false)
  const [titularId, setTitularId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('TODOS')
  const [expandido, setExpandido] = useState(null)
  const [subiendoEn, setSubiendoEn] = useState(null)
  const tarjetas = useRef(new Map())

  const consulta = useDebounce(busqueda, 220)
  // El expediente enfocado desde Empresas se abre hasta que el operador interactúa.
  const abiertoId = foco ?? expandido

  useEffect(() => {
    if (foco && !loading) tarjetas.current.get(foco)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [foco, loading])

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
      const coincideBusqueda =
        !q ||
        exp.codigo_expediente?.toLowerCase().includes(q) ||
        exp.titular?.razon_social?.toLowerCase().includes(q) ||
        exp.titular?.rfc?.toLowerCase().includes(q)
      return coincideEstado && coincideBusqueda
    })
  }, [expedientes, consulta, filtroEstado])

  const alternar = (id) => {
    setExpandido(abiertoId === id ? null : id)
    onFocoAtendido?.()
  }

  const cerrarModal = () => {
    setModalAbierto(false)
    setTitularId('')
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!titularId) return
    setEnviando(true)
    setError('')
    try {
      const creado = await createExpediente({ titular_id: titularId })
      toast.exito('Expediente aperturado', creado?.codigo_expediente || 'Folio generado')
      cerrarModal()
      onRefresh()
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
          placeholder="Buscar por folio, razón social o RFC…"
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

      {loading && <SkeletonCards count={3} height={72} />}

      {!loading && filtrados.length === 0 && (
        <div className="card">
          <EmptyState
            icon={expedientes.length === 0 ? FolderKanban : SearchX}
            titulo={expedientes.length === 0 ? 'Aún no hay expedientes aperturados' : 'Sin resultados'}
            descripcion={
              expedientes.length === 0
                ? 'Apertura un expediente para empezar a custodiar la documentación de un titular.'
                : 'Ajusta la búsqueda o el filtro de estado.'
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
                    <span className="identity-name">{exp.titular?.razon_social || 'Titular no disponible'}</span>
                    <span className="cell-sub mono">
                      {exp.codigo_expediente} · {exp.titular?.rfc || 'sin RFC'}
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
              <select required value={titularId} onChange={(e) => setTitularId(e.target.value)}>
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

            <p className="field-hint">El folio del expediente lo genera el core-service (:8001) al momento del alta.</p>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando || !titularId}>
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
