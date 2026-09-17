import { useMemo, useState } from 'react'
import { Plus, FolderKanban, Loader2, Search } from 'lucide-react'
import Modal from './Modal.jsx'
import { createExpediente } from '../services/api.js'
import { getEstadoBadge } from '../constants.js'

export default function ExpedientesTab({ expedientes, titulares, loading, onRefresh }) {
  const [modalAbierto, setModalAbierto] = useState(false)
  const [titularId, setTitularId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('TODOS')

  const estadosDisponibles = useMemo(
    () => Array.from(new Set(expedientes.map((e) => e.estado_cumplimiento).filter(Boolean))),
    [expedientes]
  )

  const expedientesFiltrados = useMemo(() => {
    const q = busqueda.trim().toLowerCase()
    return expedientes.filter((exp) => {
      const coincideEstado = filtroEstado === 'TODOS' || exp.estado_cumplimiento === filtroEstado
      const coincideBusqueda =
        !q ||
        exp.codigo_expediente.toLowerCase().includes(q) ||
        exp.titular?.razon_social?.toLowerCase().includes(q) ||
        exp.titular?.rfc?.toLowerCase().includes(q)
      return coincideEstado && coincideBusqueda
    })
  }, [expedientes, busqueda, filtroEstado])

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
      await createExpediente({ titular_id: titularId })
      cerrarModal()
      onRefresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tab-panel">
      <div className="tab-panel-header">
        <div>
          <h2 className="tab-panel-title">Fólders de Cumplimiento</h2>
          <p className="tab-panel-desc">Expedientes documentales agrupados por titular, con estado dinámico.</p>
        </div>
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => setModalAbierto(true)}
          disabled={titulares.length === 0}
          title={titulares.length === 0 ? 'Primero registra una empresa' : undefined}
        >
          <Plus size={16} strokeWidth={2.5} />
          Aperturar Expediente
        </button>
      </div>

      <div className="toolbar">
        <label className="search-box">
          <Search size={15} />
          <input
            type="text"
            placeholder="Buscar por RFC, razón social o folio…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
          />
        </label>
        {estadosDisponibles.length > 0 && (
          <div className="toolbar-filters">
            <button
              type="button"
              className={`chip ${filtroEstado === 'TODOS' ? 'chip--active' : ''}`}
              onClick={() => setFiltroEstado('TODOS')}
            >
              Todos
            </button>
            {estadosDisponibles.map((estado) => (
              <button
                key={estado}
                type="button"
                className={`chip ${filtroEstado === estado ? 'chip--active' : ''}`}
                onClick={() => setFiltroEstado(estado)}
              >
                {getEstadoBadge(estado).label}
              </button>
            ))}
          </div>
        )}
      </div>

      {loading && (
        <div className="table-empty standalone">
          <Loader2 className="spin" size={16} /> Cargando expedientes…
        </div>
      )}

      {!loading && expedientesFiltrados.length === 0 && (
        <div className="table-empty standalone">
          <FolderKanban size={16} />
          {expedientes.length === 0 ? 'Aún no hay expedientes aperturados.' : 'Sin resultados para esta búsqueda.'}
        </div>
      )}

      <div className="folder-grid">
        {expedientesFiltrados.map((exp) => {
          const badge = getEstadoBadge(exp.estado_cumplimiento)
          const progreso = Number(exp.porcentaje_completitud || 0)
          return (
            <div className="folder-card" key={exp.id}>
              <div className="folder-card-top">
                <span className="mono-chip">{exp.codigo_expediente}</span>
                <span className="badge" style={{ color: badge.fg, background: badge.bg }}>
                  <span
                    className="badge-dot"
                    style={{ background: badge.fg, boxShadow: `0 0 0 3px ${badge.bg}, 0 0 6px ${badge.fg}80` }}
                  />
                  {badge.label}
                </span>
              </div>

              <div className="folder-titular">
                <FolderKanban size={16} strokeWidth={2} />
                {exp.titular ? exp.titular.razon_social : 'Titular no disponible'}
              </div>

              <div className="folder-progress">
                <div className="folder-progress-label">
                  <span>Completitud documental</span>
                  <span className="mono">{progreso.toFixed(1)}%</span>
                </div>
                <div className="metric-progress-track">
                  <div
                    className="metric-progress-fill"
                    style={{ width: `${Math.min(100, progreso)}%`, background: badge.fg }}
                  />
                </div>
              </div>

              <div className="folder-footer cell-muted">
                Última actualización: {new Date(exp.actualizado_en).toLocaleString('es-MX')}
              </div>
            </div>
          )
        })}
      </div>

      {modalAbierto && (
        <Modal title="Aperturar Expediente" subtitle="Vincula un nuevo expediente a un titular existente" onClose={cerrarModal}>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label className="field">
              <span>Titular</span>
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

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando}>
                {enviando ? <Loader2 className="spin" size={16} /> : <Plus size={16} strokeWidth={2.5} />}
                Crear Expediente
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
