import { useState } from 'react'
import { Plus, FolderKanban, Loader2 } from 'lucide-react'
import Modal from './Modal.jsx'
import { createExpediente } from '../services/api.js'
import { getEstadoBadge } from '../constants.js'

export default function ExpedientesTab({ expedientes, titulares, loading, onRefresh }) {
  const [modalAbierto, setModalAbierto] = useState(false)
  const [titularId, setTitularId] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

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

      {loading && (
        <div className="table-empty standalone">
          <Loader2 className="spin" size={16} /> Cargando expedientes…
        </div>
      )}

      {!loading && expedientes.length === 0 && (
        <div className="table-empty standalone">
          <FolderKanban size={16} /> Aún no hay expedientes aperturados.
        </div>
      )}

      <div className="folder-grid">
        {expedientes.map((exp) => {
          const badge = getEstadoBadge(exp.estado_cumplimiento)
          const progreso = Number(exp.porcentaje_completitud || 0)
          return (
            <div className="folder-card" key={exp.id}>
              <div className="folder-card-top">
                <span className="folder-code mono">{exp.codigo_expediente}</span>
                <span className="badge" style={{ color: badge.fg, background: badge.bg }}>
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
