import { useMemo, useState } from 'react'
import { Plus, ToggleLeft, ToggleRight, Loader2, Scale, X } from 'lucide-react'
import Modal from './Modal.jsx'
import { createRegla, toggleRegla } from '../services/api.js'
import { FAMILIAS_REGLA, SEVERIDADES, TIPOS_DOCUMENTO } from '../constants.js'

const FORM_INICIAL = {
  codigo_regla: '',
  nombre_regla: '',
  familia_regla: 'RDS',
  descripcion: '',
  severidad: 'MEDIA',
  accion: '',
  documento_obligatorio: true,
  dias_maximos_vigencia: '',
  aplicaTodos: true,
  tiposSeleccionados: [],
}

const SEVERIDAD_BADGE = {
  CRITICA: { fg: '#DC2626', bg: '#FEF2F2' },
  ALTA: { fg: '#D97706', bg: '#FFFBEB' },
  MEDIA_ALTA: { fg: '#D97706', bg: '#FFFBEB' },
  MEDIA: { fg: '#2563EB', bg: '#EFF6FF' },
}

export default function ReglasTab({ reglas, loading, onRefresh }) {
  const [filtroFamilia, setFiltroFamilia] = useState('TODAS')
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState(null)

  const reglasFiltradas = useMemo(
    () => (filtroFamilia === 'TODAS' ? reglas : reglas.filter((r) => r.familia_regla === filtroFamilia)),
    [reglas, filtroFamilia]
  )

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const handleToggle = async (regla) => {
    setTogglingId(regla.id)
    try {
      await toggleRegla(regla.id, !regla.activo)
      onRefresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setTogglingId(null)
    }
  }

  const toggleTipoSeleccionado = (tipo) => {
    setForm((prev) => ({
      ...prev,
      tiposSeleccionados: prev.tiposSeleccionados.includes(tipo)
        ? prev.tiposSeleccionados.filter((t) => t !== tipo)
        : [...prev.tiposSeleccionados, tipo],
    }))
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')

    const base = {
      nombre_regla: form.nombre_regla,
      familia_regla: form.familia_regla,
      descripcion: form.descripcion,
      severidad: form.severidad,
      accion: form.accion,
      documento_obligatorio: form.documento_obligatorio,
      dias_maximos_vigencia: form.dias_maximos_vigencia === '' ? null : Number(form.dias_maximos_vigencia),
    }

    try {
      if (form.aplicaTodos || form.tiposSeleccionados.length === 0) {
        // Regla de alcance general (sin tipo de documento específico)
        await createRegla({ ...base, codigo_regla: form.codigo_regla, tipo_documento: null })
      } else {
        // Soporte multi-documento: una fila por cada tipo seleccionado,
        // manteniendo único el codigo_regla exigido por el backend.
        for (const tipo of form.tiposSeleccionados) {
          await createRegla({
            ...base,
            codigo_regla: `${form.codigo_regla}-${tipo}`,
            tipo_documento: tipo,
          })
        }
      }
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
          <h2 className="tab-panel-title">Catálogo de Reglas de Validación</h2>
          <p className="tab-panel-desc">Motor determinista Nivel 2 (DOC-05): RIE, RCV, RSC y RDS.</p>
        </div>
        <button type="button" className="btn btn-primary" onClick={() => setModalAbierto(true)}>
          <Plus size={16} strokeWidth={2.5} />
          Nueva Regla
        </button>
      </div>

      <div className="chip-filter-row">
        <button
          type="button"
          className={`chip ${filtroFamilia === 'TODAS' ? 'chip--active' : ''}`}
          onClick={() => setFiltroFamilia('TODAS')}
        >
          Todas
        </button>
        {FAMILIAS_REGLA.map((f) => (
          <button
            key={f}
            type="button"
            className={`chip ${filtroFamilia === f ? 'chip--active' : ''}`}
            onClick={() => setFiltroFamilia(f)}
          >
            {f}
          </button>
        ))}
      </div>

      {error && <p className="form-error" style={{ marginBottom: 12 }}>{error}</p>}

      <div className="table-card">
        <table className="data-table">
          <thead>
            <tr>
              <th>Código</th>
              <th>Regla</th>
              <th>Familia</th>
              <th>Documento</th>
              <th>Severidad</th>
              <th>Acción ante Incumplimiento</th>
              <th>Estado</th>
            </tr>
          </thead>
          <tbody>
            {loading && (
              <tr>
                <td colSpan={7} className="table-empty">
                  <Loader2 className="spin" size={16} /> Cargando catálogo…
                </td>
              </tr>
            )}
            {!loading && reglasFiltradas.length === 0 && (
              <tr>
                <td colSpan={7} className="table-empty">
                  <Scale size={16} /> No hay reglas en esta familia.
                </td>
              </tr>
            )}
            {reglasFiltradas.map((r) => {
              const sev = SEVERIDAD_BADGE[r.severidad] || { fg: '#475569', bg: '#F1F5F9' }
              return (
                <tr key={r.id} className={!r.activo ? 'row-muted' : ''}>
                  <td className="mono cell-code">{r.codigo_regla}</td>
                  <td>
                    <div className="cell-strong">{r.nombre_regla}</div>
                    <div className="cell-muted rule-desc">{r.descripcion}</div>
                  </td>
                  <td>
                    <span className="tag">{r.familia_regla}</span>
                  </td>
                  <td className="cell-muted">{r.tipo_documento || 'Todos'}</td>
                  <td>
                    <span className="badge" style={{ color: sev.fg, background: sev.bg }}>
                      {r.severidad}
                    </span>
                  </td>
                  <td className="cell-muted">{r.accion}</td>
                  <td>
                    <button
                      type="button"
                      className="toggle-button"
                      onClick={() => handleToggle(r)}
                      disabled={togglingId === r.id}
                      title={r.activo ? 'Desactivar regla' : 'Activar regla'}
                    >
                      {togglingId === r.id ? (
                        <Loader2 className="spin" size={20} />
                      ) : r.activo ? (
                        <ToggleRight size={26} color="var(--conforme-fg)" />
                      ) : (
                        <ToggleLeft size={26} color="var(--text-muted)" />
                      )}
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>

      {modalAbierto && (
        <Modal title="Nueva Regla de Validación" subtitle="Alta dinámica de requisitos (RDS-01)" onClose={cerrarModal} width={620}>
          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field-row">
              <label className="field">
                <span>Código Base</span>
                <input
                  className="mono"
                  required
                  placeholder="RDS-04"
                  value={form.codigo_regla}
                  onChange={(e) => setForm({ ...form, codigo_regla: e.target.value.toUpperCase() })}
                />
              </label>
              <label className="field">
                <span>Familia</span>
                <select
                  value={form.familia_regla}
                  onChange={(e) => setForm({ ...form, familia_regla: e.target.value })}
                >
                  {FAMILIAS_REGLA.map((f) => (
                    <option key={f} value={f}>
                      {f}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span>Nombre de la Regla</span>
              <input
                required
                minLength={3}
                placeholder="Ej. Vigencia de Opinión de Cumplimiento"
                value={form.nombre_regla}
                onChange={(e) => setForm({ ...form, nombre_regla: e.target.value })}
              />
            </label>

            <label className="field">
              <span>Descripción / Criterio</span>
              <textarea
                required
                minLength={10}
                rows={3}
                placeholder="Criterio en lenguaje natural que evaluará el motor (RDS-02)"
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              />
            </label>

            <div className="field-row">
              <label className="field">
                <span>Severidad</span>
                <select value={form.severidad} onChange={(e) => setForm({ ...form, severidad: e.target.value })}>
                  {SEVERIDADES.map((s) => (
                    <option key={s} value={s}>
                      {s}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span>Vigencia Máxima (días)</span>
                <input
                  type="number"
                  min={0}
                  placeholder="Opcional"
                  value={form.dias_maximos_vigencia}
                  onChange={(e) => setForm({ ...form, dias_maximos_vigencia: e.target.value })}
                />
              </label>
            </div>

            <label className="field">
              <span>Acción ante Incumplimiento</span>
              <input
                required
                placeholder="Ej. Semáforo Rojo y bloqueo del expediente"
                value={form.accion}
                onChange={(e) => setForm({ ...form, accion: e.target.value })}
              />
            </label>

            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.documento_obligatorio}
                onChange={(e) => setForm({ ...form, documento_obligatorio: e.target.checked })}
              />
              <span>Completitud obligatoria (RIE-01 / HU-09)</span>
            </label>

            <div className="field">
              <span>Alcance de la Regla</span>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={form.aplicaTodos}
                  onChange={(e) => setForm({ ...form, aplicaTodos: e.target.checked, tiposSeleccionados: [] })}
                />
                <span>Aplica a todo el expediente (sin documento específico)</span>
              </label>

              {!form.aplicaTodos && (
                <div className="doc-type-picker">
                  {TIPOS_DOCUMENTO.map((t) => {
                    const activo = form.tiposSeleccionados.includes(t.value)
                    return (
                      <button
                        type="button"
                        key={t.value}
                        className={`chip ${activo ? 'chip--active' : ''}`}
                        onClick={() => toggleTipoSeleccionado(t.value)}
                      >
                        {activo && <X size={12} />} {t.value}
                      </button>
                    )
                  })}
                  <p className="field-hint">
                    Se creará una regla por cada tipo seleccionado (código sufijado por documento).
                  </p>
                </div>
              )}
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-ghost" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando}>
                {enviando ? <Loader2 className="spin" size={16} /> : <Plus size={16} strokeWidth={2.5} />}
                Guardar Regla
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
