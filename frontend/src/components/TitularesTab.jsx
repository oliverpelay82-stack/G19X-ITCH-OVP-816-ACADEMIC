import { useMemo, useState } from 'react'
import { Check, Copy, Loader2, Plus, Search, X } from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { createTitular } from '../services/api.js'
import { copiarAlPortapapeles, formatFecha, iniciales, validarRfc } from '../utils/format.js'

const FORM_INICIAL = { rfc: '', razon_social: '', tipo_persona: 'MORAL', categoria: 'PROVEEDOR' }

const FILTROS_TIPO = [
  { id: 'TODOS', label: 'Todas' },
  { id: 'MORAL', label: 'Moral' },
  { id: 'FISICA', label: 'Física' },
]

/** Botón de copiado con confirmación visual y aviso flotante. */
function CopyRfc({ rfc }) {
  const [copiado, setCopiado] = useState(false)
  const toast = useToast()

  const copiar = async () => {
    const ok = await copiarAlPortapapeles(rfc)
    if (ok) {
      setCopiado(true)
      toast.exito('RFC copiado', rfc)
      setTimeout(() => setCopiado(false), 1400)
    } else {
      toast.error('No se pudo copiar', 'El navegador bloqueó el portapapeles.')
    }
  }

  return (
    <button type="button" className="copy-chip" onClick={copiar} data-tooltip="Copiar RFC">
      <span className="mono">{rfc}</span>
      {copiado ? <Check size={12} strokeWidth={2.4} className="copy-ok" /> : <Copy size={12} strokeWidth={2} />}
    </button>
  )
}

export default function TitularesTab({ titulares, loading, onRefresh, isOnline = true }) {
  const toast = useToast()
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')

  const consulta = useDebounce(busqueda, 220)
  const rfcCheck = validarRfc(form.rfc, form.tipo_persona)

  const conteos = useMemo(
    () => ({
      TODOS: titulares.length,
      MORAL: titulares.filter((t) => t.tipo_persona === 'MORAL').length,
      FISICA: titulares.filter((t) => t.tipo_persona === 'FISICA').length,
    }),
    [titulares]
  )

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return titulares.filter((t) => {
      const coincideTipo = filtroTipo === 'TODOS' || t.tipo_persona === filtroTipo
      const coincideBusqueda =
        !q ||
        t.rfc?.toLowerCase().includes(q) ||
        t.razon_social?.toLowerCase().includes(q) ||
        t.categoria?.toLowerCase().includes(q)
      return coincideTipo && coincideBusqueda
    })
  }, [titulares, consulta, filtroTipo])

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (rfcCheck.estado !== 'valido') {
      setError('Corrige el RFC antes de continuar.')
      return
    }
    setEnviando(true)
    setError('')
    try {
      await createTitular(form)
      toast.exito('Empresa registrada', `${form.razon_social} · ${form.rfc}`)
      cerrarModal()
      onRefresh()
    } catch (err) {
      setError(err.message)
      toast.error('No se pudo registrar', err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <label className="search-box">
          <Search size={14} strokeWidth={2} />
          <input
            type="search"
            placeholder="Buscar por razón social, RFC o categoría…"
            value={busqueda}
            onChange={(e) => setBusqueda(e.target.value)}
            aria-label="Buscar empresas"
          />
          {busqueda && (
            <button type="button" className="search-clear" onClick={() => setBusqueda('')} aria-label="Limpiar búsqueda">
              <X size={12} strokeWidth={2} />
            </button>
          )}
        </label>

        <div className="segmented" role="group" aria-label="Filtrar por tipo de persona">
          {FILTROS_TIPO.map((f) => (
            <button
              key={f.id}
              type="button"
              className={`segmented-item ${filtroTipo === f.id ? 'is-active' : ''}`}
              onClick={() => setFiltroTipo(f.id)}
              aria-pressed={filtroTipo === f.id}
            >
              {f.label}
              <span className="segmented-count mono">{conteos[f.id]}</span>
            </button>
          ))}
        </div>

        <button
          type="button"
          className="btn btn-primary toolbar-action"
          onClick={() => setModalAbierto(true)}
          disabled={!isOnline}
          title={!isOnline ? 'El core-service (:8001) no responde' : undefined}
        >
          <Plus size={14} strokeWidth={2} />
          Alta de empresa
        </button>
      </div>

      <div className="card table-card">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th>Titular</th>
                <th>RFC</th>
                <th>Tipo</th>
                <th>Categoría</th>
                <th className="col-right">Alta en sistema</th>
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows rows={5} cols={5} />}

              {!loading && filtrados.length === 0 && (
                <tr>
                  <td colSpan={5}>
                    <div className="empty-state">
                      <p className="empty-title">
                        {titulares.length === 0 ? 'Aún no hay empresas registradas' : 'Sin resultados'}
                      </p>
                      <p className="empty-desc">
                        {titulares.length === 0
                          ? 'Da de alta el primer titular para abrir su expediente de cumplimiento.'
                          : 'Prueba con otro término o cambia el filtro de tipo de persona.'}
                      </p>
                    </div>
                  </td>
                </tr>
              )}

              {!loading &&
                filtrados.map((t) => (
                  <tr key={t.id}>
                    <td>
                      <div className="identity">
                        <span className="avatar" aria-hidden="true">
                          {iniciales(t.razon_social)}
                        </span>
                        <span className="identity-name">{t.razon_social}</span>
                      </div>
                    </td>
                    <td>
                      <CopyRfc rfc={t.rfc} />
                    </td>
                    <td>
                      <span className={`badge badge--${t.tipo_persona === 'FISICA' ? 'vault' : 'brand'}`}>
                        {t.tipo_persona === 'FISICA' ? 'Física' : 'Moral'}
                      </span>
                    </td>
                    <td>
                      <span className="tag">{t.categoria}</span>
                    </td>
                    <td className="col-right cell-muted tabular">{formatFecha(t.creado_en)}</td>
                  </tr>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {modalAbierto && (
        <Modal title="Alta de empresa" subtitle="Registra un nuevo titular de expediente" onClose={cerrarModal}>
          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field-row">
              <label className="field">
                <span className="field-label">Tipo de persona</span>
                <select
                  value={form.tipo_persona}
                  onChange={(e) => setForm({ ...form, tipo_persona: e.target.value })}
                >
                  <option value="MORAL">Moral (RFC de 12)</option>
                  <option value="FISICA">Física (RFC de 13)</option>
                </select>
              </label>

              <label className="field">
                <span className="field-label">Categoría</span>
                <select value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>
                  <option value="PROVEEDOR">Proveedor</option>
                  <option value="CLIENTE">Cliente</option>
                </select>
              </label>
            </div>

            <label className="field">
              <span className="field-label">
                RFC
                <span className="field-counter mono">
                  {form.rfc.length}/{form.tipo_persona === 'FISICA' ? 13 : 12}
                </span>
              </span>
              <input
                className={`mono input--${rfcCheck.estado}`}
                required
                maxLength={13}
                placeholder={form.tipo_persona === 'FISICA' ? 'PEPJ850101H23' : 'PLU200115AB1'}
                value={form.rfc}
                onChange={(e) => setForm({ ...form, rfc: e.target.value.toUpperCase().replace(/\s/g, '') })}
                autoComplete="off"
                spellCheck="false"
              />
              {rfcCheck.estado !== 'vacio' && (
                <span className={`field-feedback field-feedback--${rfcCheck.estado}`}>{rfcCheck.mensaje}</span>
              )}
            </label>

            <label className="field">
              <span className="field-label">Razón social / Nombre completo</span>
              <input
                required
                minLength={3}
                maxLength={200}
                placeholder="PluriOne S.A. de C.V."
                value={form.razon_social}
                onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              />
            </label>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando || rfcCheck.estado !== 'valido'}>
                {enviando && <Loader2 className="spin" size={14} />}
                Registrar titular
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
