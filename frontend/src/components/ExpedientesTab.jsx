import { useMemo, useState } from 'react'
import {
  CheckCircle2,
  ChevronDown,
  CircleDashed,
  FolderKanban,
  Loader2,
  Plus,
  Search,
  UploadCloud,
  X,
} from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonCards } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import DropZone from './DropZone.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { createExpediente, uploadDocumento } from '../services/api.js'
import { getEstadoBadge, TIPOS_DOCUMENTO, tonoPorPorcentaje } from '../constants.js'
import { formatRelativo, iniciales, tonoDesdeTexto } from '../utils/format.js'

export default function ExpedientesTab({
  expedientes,
  titulares,
  documentos,
  loading,
  onRefresh,
  isOnline = true,
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

  const consulta = useDebounce(busqueda, 220)

  /** Documentos ya custodiados, agrupados por expediente. */
  const docsPorExpediente = useMemo(() => {
    const mapa = new Map()
    for (const d of documentos || []) {
      if (!mapa.has(d.expediente_id)) mapa.set(d.expediente_id, [])
      mapa.get(d.expediente_id).push(d)
    }
    return mapa
  }, [documentos])

  const estadosDisponibles = useMemo(
    () => Array.from(new Set(expedientes.map((e) => e.estado_cumplimiento).filter(Boolean))),
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
        <label className="search-box">
          <Search size={15} strokeWidth={2.3} />
          <input
            type="search"
            placeholder="Buscar por folio, razón social o RFC…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar expedientes"
          />
          {busqueda && (
            <button type="button" className="search-clear" onClick={() => setBusqueda('')} aria-label="Limpiar búsqueda">
              <X size={13} strokeWidth={2.6} />
            </button>
          )}
        </label>

        {estadosDisponibles.length > 0 && (
          <div className="segmented" role="group" aria-label="Filtrar por estado de cumplimiento">
            <button
              type="button"
              className={`segmented-item ${filtroEstado === 'TODOS' ? 'segmented-item--active' : ''}`}
              onClick={() => setFiltroEstado('TODOS')}
              aria-pressed={filtroEstado === 'TODOS'}
            >
              Todos
              <span className="segmented-count mono">{expedientes.length}</span>
            </button>
            {estadosDisponibles.map((estado) => {
              const meta = getEstadoBadge(estado)
              return (
                <button
                  key={estado}
                  type="button"
                  className={`segmented-item ${filtroEstado === estado ? 'segmented-item--active' : ''}`}
                  onClick={() => setFiltroEstado(estado)}
                  aria-pressed={filtroEstado === estado}
                >
                  <span className={`dot dot--${meta.tono}`} aria-hidden="true" />
                  {meta.label}
                </button>
              )
            })}
          </div>
        )}

        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setModalAbierto(true)}
          disabled={titulares.length === 0 || !isOnline}
          title={titulares.length === 0 ? 'Primero registra una empresa' : undefined}
        >
          <Plus size={15} strokeWidth={2.6} />
          Aperturar expediente
        </button>
      </div>

      {loading && <SkeletonCards count={4} height={196} />}

      {!loading && filtrados.length === 0 && (
        <div className="surface-card">
          <div className="empty-state">
            <span className="empty-icon">
              <FolderKanban size={20} strokeWidth={2} />
            </span>
            <p className="empty-title">
              {expedientes.length === 0 ? 'Aún no hay expedientes aperturados' : 'Sin resultados'}
            </p>
            <p className="empty-desc">
              {expedientes.length === 0
                ? 'Apertura un expediente para empezar a custodiar la documentación de un titular.'
                : 'Ajusta la búsqueda o el filtro de estado.'}
            </p>
          </div>
        </div>
      )}

      <div className="folder-grid">
        {!loading &&
          filtrados.map((exp) => {
            const meta = getEstadoBadge(exp.estado_cumplimiento)
            const progreso = Math.max(0, Math.min(100, Number(exp.porcentaje_completitud || 0)))
            const tono = tonoPorPorcentaje(progreso)
            const abierto = expandido === exp.id
            const docs = docsPorExpediente.get(exp.id) || []
            const tiposCargados = new Set(docs.map((d) => d.tipo_documento))
            const entregados = TIPOS_DOCUMENTO.filter((t) => tiposCargados.has(t.value))
            const faltantes = TIPOS_DOCUMENTO.filter((t) => !tiposCargados.has(t.value))

            return (
              <article className={`folder-card ${abierto ? 'folder-card--open' : ''}`} key={exp.id}>
                <div className="folder-head">
                  <span
                    className="avatar avatar--sm"
                    style={{ '--avatar-h': tonoDesdeTexto(exp.titular?.rfc || exp.codigo_expediente) }}
                    aria-hidden="true"
                  >
                    {iniciales(exp.titular?.razon_social || exp.codigo_expediente)}
                  </span>
                  <div className="folder-head-body">
                    <h3 className="folder-titular">{exp.titular?.razon_social || 'Titular no disponible'}</h3>
                    <span className="mono folder-folio">{exp.codigo_expediente}</span>
                  </div>
                  <span className={`badge badge--${meta.tono}`}>
                    <span className={`dot dot--${meta.tono}`} aria-hidden="true" />
                    {meta.label}
                  </span>
                </div>

                <div className="meter">
                  <div className="meter-head">
                    <span className="meter-label">Completitud documental</span>
                    <span className="meter-value mono-tabular">{progreso.toFixed(0)}%</span>
                  </div>
                  <div className={`meter-track meter-track--${tono}`}>
                    <span className={`meter-fill meter-fill--${tono}`} style={{ width: `${progreso}%` }} />
                  </div>
                  <p className="meter-foot">
                    {entregados.length} de {TIPOS_DOCUMENTO.length} tipos obligatorios entregados
                    {docs.length > entregados.length && ` · ${docs.length} archivos en bóveda`}
                  </p>
                </div>

                <button
                  type="button"
                  className="folder-toggle"
                  onClick={() => setExpandido(abierto ? null : exp.id)}
                  aria-expanded={abierto}
                >
                  <ChevronDown size={14} strokeWidth={2.4} className="folder-toggle-chevron" />
                  {abierto ? 'Ocultar detalle' : 'Ver detalle y cargar documentos'}
                </button>

                {abierto && (
                  <div className="folder-detail">
                    <div className="checklist">
                      {TIPOS_DOCUMENTO.map((t) => {
                        const ok = tiposCargados.has(t.value)
                        return (
                          <div className={`checklist-item ${ok ? 'checklist-item--ok' : ''}`} key={t.value}>
                            {ok ? (
                              <CheckCircle2 size={14} strokeWidth={2.4} />
                            ) : (
                              <CircleDashed size={14} strokeWidth={2.2} />
                            )}
                            <span className="checklist-label">{t.label}</span>
                            <span className={`checklist-state ${ok ? 'checklist-state--ok' : ''}`}>
                              {ok ? 'Aprobado' : 'Pendiente'}
                            </span>
                          </div>
                        )
                      })}
                    </div>

                    {faltantes.length > 0 ? (
                      <DropZone
                        compacto
                        subiendo={subiendoEn === exp.id}
                        tipos={faltantes}
                        onArchivo={(archivo, tipo) => subirDocumento(exp.id, archivo, tipo)}
                      />
                    ) : (
                      <p className="folder-complete">
                        <CheckCircle2 size={14} strokeWidth={2.4} />
                        Expediente completo: los {TIPOS_DOCUMENTO.length} tipos obligatorios están custodiados.
                      </p>
                    )}
                  </div>
                )}

                <footer className="folder-foot cell-muted">
                  Actualizado {formatRelativo(exp.actualizado_en)}
                </footer>
              </article>
            )
          })}
      </div>

      {modalAbierto && (
        <Modal
          title="Aperturar expediente"
          subtitle="Vincula un nuevo fólder de cumplimiento a un titular existente"
          icon={FolderKanban}
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

            <p className="field-hint">
              El folio del expediente lo genera el core-service (:8001) al momento del alta.
            </p>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando || !titularId}>
                {enviando ? <Loader2 className="spin" size={15} /> : <UploadCloud size={15} strokeWidth={2.4} />}
                Crear expediente
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
