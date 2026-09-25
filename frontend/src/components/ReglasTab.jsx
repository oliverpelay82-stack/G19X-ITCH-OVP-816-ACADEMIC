import { Fragment, useMemo, useState } from 'react'
import { Loader2, Plus, Scale, SearchX, ServerOff } from 'lucide-react'
import Modal from './Modal.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { EmptyRow, EmptyState, Segmented, SearchBox } from './ui.jsx'
import { createRegla, toggleRegla } from '../services/api.js'
import {
  FAMILIA_META,
  FAMILIAS_REGLA,
  getSeveridadMeta,
  SEVERIDADES,
  TIPO_DOCUMENTO_CORTO,
  TIPOS_DOCUMENTO,
} from '../constants.js'

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

const COLUMNAS = 6

/** Interruptor para activar o pausar una regla del catálogo. */
function Switch({ checked, onClick, loading, label }) {
  return (
    <button
      type="button"
      className={`switch ${checked ? 'is-on' : ''}`}
      onClick={onClick}
      disabled={loading}
      role="switch"
      aria-checked={checked}
      aria-label={label}
      data-tooltip={checked ? 'Pausar regla' : 'Activar regla'}
    >
      <span className="switch-thumb">{loading && <Loader2 className="spin" size={9} strokeWidth={1.75} />}</span>
    </button>
  )
}

export default function ReglasTab({ reglas, loading, onRefresh, isOnline = true }) {
  const toast = useToast()
  const [filtroFamilia, setFiltroFamilia] = useState('TODAS')
  const [filtroSeveridad, setFiltroSeveridad] = useState('TODAS')
  const [filtroEstado, setFiltroEstado] = useState('TODAS')
  const [busqueda, setBusqueda] = useState('')
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState(null)

  const consulta = useDebounce(busqueda, 220)

  const filtradas = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return reglas.filter((r) => {
      const familiaOk = filtroFamilia === 'TODAS' || r.familia_regla === filtroFamilia
      const severidadOk = filtroSeveridad === 'TODAS' || r.severidad === filtroSeveridad
      const estadoOk = filtroEstado === 'TODAS' || (filtroEstado === 'ACTIVAS') === Boolean(r.activo)
      const busquedaOk =
        !q ||
        r.codigo_regla?.toLowerCase().includes(q) ||
        r.nombre_regla?.toLowerCase().includes(q) ||
        r.descripcion?.toLowerCase().includes(q) ||
        r.accion?.toLowerCase().includes(q)
      return familiaOk && severidadOk && estadoOk && busquedaOk
    })
  }, [reglas, filtroFamilia, filtroSeveridad, filtroEstado, consulta])

  /** Agrupadas por familia normativa, en el orden oficial del DOC-05. */
  const porFamilia = useMemo(() => {
    const grupos = FAMILIAS_REGLA.map((f) => ({
      familia: f,
      meta: FAMILIA_META[f],
      items: filtradas.filter((r) => r.familia_regla === f),
    })).filter((g) => g.items.length > 0)

    const otras = filtradas.filter((r) => !FAMILIAS_REGLA.includes(r.familia_regla))
    if (otras.length > 0) {
      grupos.push({ familia: 'OTRAS', meta: { nombre: 'Sin familia asignada', nivel: '—', clase: 'neutral' }, items: otras })
    }
    return grupos
  }, [filtradas])

  const opcionesFamilia = useMemo(
    () => [
      { id: 'TODAS', label: 'Todas', conteo: reglas.length },
      ...FAMILIAS_REGLA.map((f) => ({
        id: f,
        label: f,
        conteo: reglas.filter((r) => r.familia_regla === f).length,
        tooltip: `${FAMILIA_META[f].nombre} · ${FAMILIA_META[f].nivel}`,
      })),
    ],
    [reglas]
  )

  const opcionesEstado = useMemo(() => {
    const activas = reglas.filter((r) => r.activo).length
    return [
      { id: 'TODAS', label: 'Todas' },
      { id: 'ACTIVAS', label: 'Activas', tono: 'ok', conteo: activas },
      { id: 'PAUSADAS', label: 'Pausadas', tono: 'off', conteo: reglas.length - activas },
    ]
  }, [reglas])

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const handleToggle = async (regla) => {
    setTogglingId(regla.id)
    try {
      await toggleRegla(regla.id, !regla.activo)
      toast.exito(
        regla.activo ? 'Regla pausada' : 'Regla activada',
        `${regla.codigo_regla} · ${regla.nombre_regla}`
      )
      onRefresh()
    } catch (err) {
      toast.error('No se pudo cambiar el estado', err.message)
    } finally {
      setTogglingId(null)
    }
  }

  const toggleTipo = (tipo) => {
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
        await createRegla({ ...base, codigo_regla: form.codigo_regla, tipo_documento: null })
      } else {
        // Una fila por tipo seleccionado, manteniendo único el codigo_regla
        // que exige el backend.
        for (const tipo of form.tiposSeleccionados) {
          await createRegla({ ...base, codigo_regla: `${form.codigo_regla}-${tipo}`, tipo_documento: tipo })
        }
      }
      toast.exito('Regla registrada', `${form.codigo_regla} · familia ${form.familia_regla}`)
      cerrarModal()
      onRefresh()
    } catch (err) {
      setError(err.message)
      toast.error('No se pudo guardar la regla', err.message)
    } finally {
      setEnviando(false)
    }
  }

  if (!isOnline) {
    return (
      <div className="tab-panel">
        <div className="card">
          <EmptyState
            icon={ServerOff}
            titulo="Microservicio de reglas (:8002) fuera de línea"
            descripcion="El rules-service no responde: no es posible consultar, evaluar ni modificar el catálogo normativo. Empresas, Expedientes y Bóveda siguen operando gracias a la arquitectura de microservicios desacoplados."
          />
        </div>
      </div>
    )
  }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Código, nombre, criterio o acción…"
          label="Buscar reglas"
        />
        <Segmented label="Filtrar por familia normativa" valor={filtroFamilia} onChange={setFiltroFamilia} opciones={opcionesFamilia} />
        <Segmented label="Filtrar por estado" valor={filtroEstado} onChange={setFiltroEstado} opciones={opcionesEstado} />

        <label className="select-inline">
          <span className="sr-only">Filtrar por severidad</span>
          <select value={filtroSeveridad} onChange={(e) => setFiltroSeveridad(e.target.value)}>
            <option value="TODAS">Toda severidad</option>
            {SEVERIDADES.map((s) => (
              <option key={s} value={s}>
                {getSeveridadMeta(s).label}
              </option>
            ))}
          </select>
        </label>

        <button type="button" className="btn btn-primary toolbar-action" onClick={() => setModalAbierto(true)}>
          <Plus size={14} />
          Nueva regla
        </button>
      </div>

      <div className="card table-card">
        <div className="table-scroll">
          <table className="data-table">
            <colgroup>
              <col style={{ width: '10%' }} />
              <col style={{ width: '34%' }} />
              <col style={{ width: '11%' }} />
              <col style={{ width: '20%' }} />
              <col style={{ width: '17%' }} />
              <col style={{ width: '8%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Código</th>
                <th>Regla</th>
                <th>Severidad</th>
                <th>Alcance</th>
                <th>Acción</th>
                <th className="col-right">Activa</th>
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows rows={6} cols={COLUMNAS} />}

              {!loading && filtradas.length === 0 && (
                <EmptyRow
                  columnas={COLUMNAS}
                  icon={reglas.length === 0 ? Scale : SearchX}
                  titulo={reglas.length === 0 ? 'El catálogo está vacío' : 'Sin coincidencias'}
                  descripcion={
                    reglas.length === 0
                      ? 'Precarga el catálogo del DOC-05 o da de alta una regla dinámica (RDS-01).'
                      : 'Ajusta la búsqueda o relaja los filtros de familia, estado y severidad.'
                  }
                />
              )}

              {!loading &&
                porFamilia.map((grupo) => (
                  <Fragment key={grupo.familia}>
                    <tr className="group-row">
                      <td colSpan={COLUMNAS}>
                        <span className="mono group-code">{grupo.familia}</span>
                        <span className="group-name">{grupo.meta.nombre}</span>
                        <span className="group-meta">{grupo.meta.nivel}</span>
                        <span className="group-count tabular">
                          {grupo.items.filter((r) => r.activo).length}/{grupo.items.length} activas
                        </span>
                      </td>
                    </tr>

                    {grupo.items.map((r) => {
                      const sev = getSeveridadMeta(r.severidad)
                      return (
                        <tr className={!r.activo ? 'is-paused' : ''} key={r.id}>
                          <td className="mono cell-mono">{r.codigo_regla}</td>
                          <td className="cell-wide">
                            <div className="cell-stack">
                              <span className="identity-name">{r.nombre_regla}</span>
                              <span className="cell-sub cell-clamp" title={r.descripcion}>
                                {r.descripcion}
                              </span>
                            </div>
                          </td>
                          <td>
                            <span className={`badge badge--${sev.tono}`}>
                              <span className={`status-dot status-dot--${sev.tono}`} aria-hidden="true" />
                              {sev.label}
                            </span>
                          </td>
                          <td>
                            <div className="tag-row">
                              <span className="tag">
                                {r.tipo_documento
                                  ? TIPO_DOCUMENTO_CORTO[r.tipo_documento] || r.tipo_documento
                                  : 'Todo el expediente'}
                              </span>
                              {r.dias_maximos_vigencia != null && (
                                <span className="tag tabular">{r.dias_maximos_vigencia} días</span>
                              )}
                              {r.documento_obligatorio && <span className="tag">Obligatorio</span>}
                            </div>
                          </td>
                          <td className="cell-muted cell-action-text">
                            <span className="cell-clamp" title={r.accion}>
                              {r.accion}
                            </span>
                          </td>
                          <td className="col-right">
                            <Switch
                              checked={r.activo}
                              onClick={() => handleToggle(r)}
                              loading={togglingId === r.id}
                              label={`${r.activo ? 'Pausar' : 'Activar'} ${r.codigo_regla}`}
                            />
                          </td>
                        </tr>
                      )
                    })}
                  </Fragment>
                ))}
            </tbody>
          </table>
        </div>
      </div>

      {modalAbierto && (
        <Modal
          title="Nueva regla de validación"
          subtitle="Alta dinámica de requisitos (RDS-01 / RDS-02)"
          onClose={cerrarModal}
        >
          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field-row">
              <label className="field">
                <span className="field-label">Código base</span>
                <input
                  className="mono"
                  required
                  minLength={3}
                  maxLength={20}
                  placeholder="RDS-04"
                  value={form.codigo_regla}
                  onChange={(e) => setForm({ ...form, codigo_regla: e.target.value.toUpperCase() })}
                />
              </label>
              <label className="field">
                <span className="field-label">Familia normativa</span>
                <select
                  value={form.familia_regla}
                  onChange={(e) => setForm({ ...form, familia_regla: e.target.value })}
                >
                  {FAMILIAS_REGLA.map((f) => (
                    <option key={f} value={f}>
                      {f} — {FAMILIA_META[f].nombre}
                    </option>
                  ))}
                </select>
              </label>
            </div>

            <label className="field">
              <span className="field-label">Nombre de la regla</span>
              <input
                required
                minLength={3}
                maxLength={150}
                placeholder="Ej. Vigencia de la opinión de cumplimiento"
                value={form.nombre_regla}
                onChange={(e) => setForm({ ...form, nombre_regla: e.target.value })}
              />
            </label>

            <label className="field">
              <span className="field-label">Descripción / criterio</span>
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
                <span className="field-label">Severidad</span>
                <select value={form.severidad} onChange={(e) => setForm({ ...form, severidad: e.target.value })}>
                  {SEVERIDADES.map((s) => (
                    <option key={s} value={s}>
                      {getSeveridadMeta(s).label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="field">
                <span className="field-label">Vigencia máxima (días)</span>
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
              <span className="field-label">Acción ante incumplimiento</span>
              <input
                required
                maxLength={255}
                placeholder="Ej. Semáforo rojo y bloqueo del expediente"
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
              <span>Completitud obligatoria (RIE-01)</span>
            </label>

            <div className="field">
              <span className="field-label">Alcance de la regla</span>
              <label className="checkbox-field">
                <input
                  type="checkbox"
                  checked={form.aplicaTodos}
                  onChange={(e) => setForm({ ...form, aplicaTodos: e.target.checked, tiposSeleccionados: [] })}
                />
                <span>Aplica a todo el expediente (sin documento específico)</span>
              </label>

              {!form.aplicaTodos && (
                <div className="type-picker">
                  {TIPOS_DOCUMENTO.map((t) => {
                    const activo = form.tiposSeleccionados.includes(t.value)
                    return (
                      <button
                        type="button"
                        key={t.value}
                        className={`chip ${activo ? 'is-active' : ''}`}
                        onClick={() => toggleTipo(t.value)}
                        aria-pressed={activo}
                      >
                        {t.corto}
                      </button>
                    )
                  })}
                  <p className="field-hint">
                    Se creará una regla por cada tipo seleccionado, con el código sufijado por documento.
                  </p>
                </div>
              )}
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <button type="button" className="btn btn-secondary" onClick={cerrarModal}>
                Cancelar
              </button>
              <button type="submit" className="btn btn-primary" disabled={enviando}>
                {enviando && <Loader2 className="spin" size={14} />}
                Guardar regla
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
