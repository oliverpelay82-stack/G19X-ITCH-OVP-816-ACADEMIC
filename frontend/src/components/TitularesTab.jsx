import { useState } from 'react'
import { Plus, Building2, Loader2 } from 'lucide-react'
import Modal from './Modal.jsx'
import { createTitular } from '../services/api.js'

const FORM_INICIAL = { rfc: '', razon_social: '', tipo_persona: 'MORAL', categoria: 'PROVEEDOR' }

export default function TitularesTab({ titulares, loading, onRefresh }) {
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      await createTitular(form)
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
          <h2 className="tab-panel-title">Directorio de Empresas</h2>
          <p className="tab-panel-desc">Titulares de expediente: clientes y proveedores evaluados por el motor.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setModalAbierto(true)}>
          <Plus size={16} strokeWidth={2.5} />
          Alta de Empresa
        </button>
      </div>

      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Razón Social</th>
              <th>RFC</th>
              <th>Tipo</th>
              <th>Categoría</th>
              <th>Alta en Sistema</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={5} className="table-empty">
                  <Loader2 className="spin" size={16} /> Cargando titulares…
                </td>
              </tr>
            )}
            {!loading && titulares.length === 0 && (
              <tr>
                <td colSpan={5} className="table-empty">
                  <Building2 size={16} /> Aún no hay empresas registradas.
                </td>
              </tr>
            )}
            {titulares.map((t) => (
              <tr key={t.id}>
                <td className="cell-strong">{t.razon_social}</td>
                <td className="mono cell-code">{t.rfc}</td>
                <td>{t.tipo_persona}</td>
                <td>
                  <span className="tag">{t.categoria}</span>
                </td>
                <td className="cell-muted">{new Date(t.creado_en).toLocaleString('es-MX')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {modalAbierto && (
        <Modal title="Alta de Empresa" subtitle="Registra un nuevo titular de expediente" onClose={cerrarModal}>
          <form className="form-grid" onSubmit={handleSubmit}>
            <label className="field">
              <span>RFC</span>
              <input
                className="mono"
                required
                minLength={12}
                maxLength={13}
                placeholder="XAXX010101000"
                value={form.rfc}
                onChange={(e) => setForm({ ...form, rfc: e.target.value.toUpperCase() })}
              />
            </label>

            <label className="field">
              <span>Razón Social / Nombre Completo</span>
              <input
                required
                minLength={3}
                placeholder="Empresa S.A. de C.V."
                value={form.razon_social}
                onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Tipo de Persona</span>
                <select
                  value={form.tipo_persona}
                  onChange={(e) => setForm({ ...form, tipo_persona: e.target.value })}
                >
                  <option value="MORAL">Moral</option>
                  <option value="FISICA">Física</option>
                </select>
              </label>

              <label className="field">
                <span>Categoría</span>
                <select
                  value={form.categoria}
                  onChange={(e) => setForm({ ...form, categoria: e.target.value })}
                >
                  <option value="PROVEEDOR">Proveedor</option>
                  <option value="CLIENTE">Cliente</option>
                </select>
              </label>
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando}>
                {enviando ? <Loader2 className="spin" size={16} /> : <Plus size={16} strokeWidth={2.5} />}
                Registrar Titular
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
