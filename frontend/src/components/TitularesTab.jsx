import { useMemo, useState } from 'react'
import { Building2, Loader2, Plus, SearchX } from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import { CopyChip, EmptyRow, Segmented, SearchBox } from './ui.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { createTitular } from '../services/api.js'
import { formatFechaCorta, iniciales, validarRfc } from '../utils/format.js'

const FORM_INICIAL = { rfc: '', razon_social: '', tipo_persona: 'MORAL', categoria: 'PROVEEDOR' }

const FILTROS_TIPO = [
  { id: 'TODOS', label: 'Todas' },
  { id: 'MORAL', label: 'Moral' },
  { id: 'FISICA', label: 'Física' },
]

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
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por razón social, RFC o categoría…"
          label="Buscar empresas"
        />
        <Segmented
          label="Filtrar por tipo de persona"
          valor={filtroTipo}
          onChange={setFiltroTipo}
          opciones={FILTROS_TIPO.map((f) => ({ ...f, conteo: conteos[f.id] }))}
        />

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
            <colgroup>
              <col style={{ width: '38%' }} />
              <col style={{ width: '20%' }} />
              <col style={{ width: '12%' }} />
              <col style={{ width: '14%' }} />
              <col style={{ width: '16%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Titular</th>
                <th>RFC</th>
                <th>Tipo</th>
                <th>Categoría</th>
                <th className="col-right">Alta</th>
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows rows={5} cols={5} />}

              {!loading && filtrados.length === 0 && (
                <EmptyRow
                  columnas={5}
                  icon={titulares.length === 0 ? Building2 : SearchX}
                  titulo={titulares.length === 0 ? 'Aún no hay empresas registradas' : 'Sin resultados'}
                  descripcion={
                    titulares.length === 0
                      ? 'Da de alta el primer titular para abrir su expediente de cumplimiento.'
                      : 'Prueba con otro término o cambia el filtro de tipo de persona.'
                  }
                />
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
                      <CopyChip valor={t.rfc} etiqueta="RFC" />
                    </td>
                    <td>
                      <span className={`badge badge--${t.tipo_persona === 'FISICA' ? 'vault' : 'neutral'}`}>
                        {t.tipo_persona === 'FISICA' ? 'Física' : 'Moral'}
                      </span>
                    </td>
                    <td>
                      <span className="tag">{t.categoria}</span>
                    </td>
                    <td className="col-right cell-muted tabular">{formatFechaCorta(t.creado_en)}</td>
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
