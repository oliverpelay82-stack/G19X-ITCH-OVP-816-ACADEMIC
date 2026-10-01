import { Fragment, useMemo, useState } from 'react'
import { ChevronRight, Loader2, Plus, Scale, SearchX, ServerOff } from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  EmptyRow,
  EmptyState,
  Field,
  Input,
  KeyValue,
  KeyValueList,
  Modal,
  SearchBox,
  Segmented,
  Select,
  Tag,
} from './ui/index.js'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { createRegla, toggleRegla } from '../services/api.js'
import { formatFecha } from '../utils/format.js'
import {
  FAMILIA_META,
  FAMILIAS_REGLA,
  getSeveridadMeta,
  SEVERIDADES,
  TIPO_DOCUMENTO_CORTO,
  TIPO_DOCUMENTO_LABEL,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_DOCUMENTO,
  TIPOS_EXPEDIENTE,
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
  tipo_expediente: '',
  documento_principal: '',
}

const COLUMNAS = 5

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

/**
 * Detalle de una regla al expandirla: la descripción y la acción completas
 * (en la fila se recortan a dos renglones) y el alcance en palabras.
 */
function DetalleRegla({ regla }) {
  const alcance = [
    regla.tipo_documento ? TIPO_DOCUMENTO_LABEL[regla.tipo_documento] || regla.tipo_documento : 'Todo el expediente',
    regla.tipo_expediente &&
      `expedientes de tipo ${(TIPO_EXPEDIENTE_LABEL[regla.tipo_expediente] || regla.tipo_expediente).toLowerCase()}`,
    regla.documento_principal &&
      `anexo obligatorio de ${TIPO_DOCUMENTO_LABEL[regla.documento_principal] || regla.documento_principal}`,
  ]
    .filter(Boolean)
    .join(' · ')
  const obligatoriedad = [
    regla.documento_obligatorio ? 'Documento obligatorio' : 'No exige el documento',
    regla.dias_maximos_vigencia != null && `vigencia máxima de ${regla.dias_maximos_vigencia} días`,
  ]
    .filter(Boolean)
    .join(' · ')
  return (
    <KeyValueList className="regla-detalle-grid">
      <KeyValue etiqueta="Descripción">{regla.descripcion || '—'}</KeyValue>
      <KeyValue etiqueta="Acción ante incumplimiento">{regla.accion || '—'}</KeyValue>
      <KeyValue etiqueta="Alcance">{alcance}</KeyValue>
      <KeyValue etiqueta="Obligatoriedad y vigencia">{obligatoriedad}</KeyValue>
      <KeyValue etiqueta="Alta en el catálogo">{regla.creado_en ? formatFecha(regla.creado_en) : '—'}</KeyValue>
    </KeyValueList>
  )
}

export default function ReglasTab({ reglas, loading, onRefresh, isOnline = true }) {
  const toast = useToast()
  const [filtroFamilia, setFiltroFamilia] = useState('TODAS')
  const [filtroSeveridad, setFiltroSeveridad] = useState('TODAS')
  const [filtroEstado, setFiltroEstado] = useState('TODAS')
  const [filtroTipoExp, setFiltroTipoExp] = useState('TODOS')
  const [busqueda, setBusqueda] = useState('')
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [togglingId, setTogglingId] = useState(null)
  // Familias plegadas o desplegadas a mano. Sin elección, se pliegan salvo que
  // haya una búsqueda o un filtro, para que los resultados queden a la vista.
  const [familiasAbiertas, setFamiliasAbiertas] = useState({})
  const [reglaAbierta, setReglaAbierta] = useState(null)

  const consulta = useDebounce(busqueda, 220)

  const filtradas = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return reglas.filter((r) => {
      const familiaOk = filtroFamilia === 'TODAS' || r.familia_regla === filtroFamilia
      const severidadOk = filtroSeveridad === 'TODAS' || r.severidad === filtroSeveridad
      const estadoOk = filtroEstado === 'TODAS' || (filtroEstado === 'ACTIVAS') === Boolean(r.activo)
      // Un tipo de expediente ve sus reglas y las generales (sin tipo), como el rules-service.
      const tipoExpOk = filtroTipoExp === 'TODOS' || !r.tipo_expediente || r.tipo_expediente === filtroTipoExp
      const busquedaOk =
        !q ||
        r.codigo_regla?.toLowerCase().includes(q) ||
        r.nombre_regla?.toLowerCase().includes(q) ||
        r.descripcion?.toLowerCase().includes(q) ||
        r.accion?.toLowerCase().includes(q)
      return familiaOk && severidadOk && estadoOk && tipoExpOk && busquedaOk
    })
  }, [reglas, filtroFamilia, filtroSeveridad, filtroEstado, filtroTipoExp, consulta])

  const filtrando =
    Boolean(consulta.trim()) ||
    filtroFamilia !== 'TODAS' ||
    filtroSeveridad !== 'TODAS' ||
    filtroEstado !== 'TODAS' ||
    filtroTipoExp !== 'TODOS'
  const familiaAbierta = (familia) => familiasAbiertas[familia] ?? filtrando
  const alternarFamilia = (familia) =>
    setFamiliasAbiertas((previo) => ({ ...previo, [familia]: !(previo[familia] ?? filtrando) }))
  const alternarRegla = (id) => setReglaAbierta((previa) => (previa === id ? null : id))

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

  // Pausar o activar una regla cambia la evaluación de todos los expedientes: se confirma antes.
  const [porConfirmar, setPorConfirmar] = useState(null)
  const confirmarCambio = () => {
    const regla = porConfirmar
    setPorConfirmar(null)
    handleToggle(regla)
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
      tipo_expediente: form.tipo_expediente || null,
      documento_principal: (!form.aplicaTodos && form.documento_principal) || null,
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
        <Card>
          <EmptyState
            icon={ServerOff}
            titulo="Catálogo de reglas fuera de línea"
            descripcion="El servicio del catálogo no responde: no es posible consultar, evaluar ni modificar las reglas. Empresas, Expedientes y Bóveda siguen operando."
          />
        </Card>
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

        <Button variante="primary" icono={Plus} className="toolbar-action" onClick={() => setModalAbierto(true)}>
          Nueva regla
        </Button>
      </div>

      {/* Los filtros secundarios van en su propio renglón, como en Expedientes: a
          1366 px (RNF-07) no caben en una sola línea con el buscador y la acción. */}
      <div className="toolbar toolbar--sub">
        <Segmented label="Filtrar por estado" valor={filtroEstado} onChange={setFiltroEstado} opciones={opcionesEstado} />

        <Select etiqueta="Filtrar por severidad" value={filtroSeveridad} onChange={(e) => setFiltroSeveridad(e.target.value)}>
          <option value="TODAS">Toda severidad</option>
          {SEVERIDADES.map((s) => (
            <option key={s} value={s}>
              {getSeveridadMeta(s).label}
            </option>
          ))}
        </Select>

        <Select etiqueta="Filtrar por tipo de expediente" value={filtroTipoExp} onChange={(e) => setFiltroTipoExp(e.target.value)}>
          <option value="TODOS">Todo tipo de expediente</option>
          {TIPOS_EXPEDIENTE.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </div>

      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table">
            <colgroup>
              <col style={{ width: '14%' }} />
              <col style={{ width: '44%' }} />
              <col style={{ width: '12%' }} />
              <col style={{ width: '22%' }} />
              <col style={{ width: '8%' }} />
            </colgroup>
            {/* Con todas las familias plegadas no hay columnas que titular. */}
            {(loading || porFamilia.some((g) => familiaAbierta(g.familia))) && (
              <thead>
                <tr>
                  <th>Código</th>
                  <th>Regla</th>
                  <th>Severidad</th>
                  <th>Alcance</th>
                  <th className="col-right">Activa</th>
                </tr>
              </thead>
            )}
            <tbody>
              {loading && <SkeletonRows rows={6} cols={COLUMNAS} />}

              {!loading && filtradas.length === 0 && (
                <EmptyRow
                  columnas={COLUMNAS}
                  icon={reglas.length === 0 ? Scale : SearchX}
                  titulo={reglas.length === 0 ? 'El catálogo está vacío' : 'Sin coincidencias'}
                  descripcion={
                    reglas.length === 0
                      ? 'Precarga el catálogo base de reglas o da de alta una regla nueva.'
                      : 'Ajusta la búsqueda o relaja los filtros de familia, estado y severidad.'
                  }
                />
              )}

              {!loading &&
                porFamilia.map((grupo) => (
                  <Fragment key={grupo.familia}>
                    <tr className="group-row">
                      <td colSpan={COLUMNAS}>
                        <button
                          type="button"
                          className={`group-toggle ${familiaAbierta(grupo.familia) ? 'is-open' : ''}`}
                          aria-expanded={familiaAbierta(grupo.familia)}
                          onClick={() => alternarFamilia(grupo.familia)}
                        >
                          <ChevronRight size={13} className="chevron" aria-hidden="true" />
                          <span className="mono group-code">{grupo.familia}</span>
                          <span className="group-name">{grupo.meta.nombre}</span>
                          <span className="group-meta">{grupo.meta.nivel}</span>
                          <span className="group-count tabular">
                            {grupo.items.length} {grupo.items.length === 1 ? 'regla' : 'reglas'} ·{' '}
                            {grupo.items.filter((r) => r.activo).length} activas
                          </span>
                        </button>
                      </td>
                    </tr>

                    {familiaAbierta(grupo.familia) &&
                      grupo.items.map((r) => {
                      const sev = getSeveridadMeta(r.severidad)
                      const abierta = reglaAbierta === r.id
                      return (
                        <Fragment key={r.id}>
                        <tr
                          className={`row-clickable ${!r.activo ? 'is-paused' : ''} ${abierta ? 'is-open' : ''}`}
                          onClick={() => alternarRegla(r.id)}
                        >
                          <td className="mono cell-mono cell-code" title={r.codigo_regla}>
                            {r.codigo_regla}
                          </td>
                          <td className="cell-wide">
                            <div className="cell-stack">
                              <button
                                type="button"
                                className="regla-toggle identity-name"
                                aria-expanded={abierta}
                                onClick={(e) => {
                                  e.stopPropagation()
                                  alternarRegla(r.id)
                                }}
                              >
                                {r.nombre_regla}
                              </button>
                              <span className="cell-sub cell-clamp" title={r.descripcion}>
                                {r.descripcion}
                              </span>
                            </div>
                          </td>
                          <td>
                            <Badge tono={sev.tono} punto>
                              {sev.label}
                            </Badge>
                          </td>
                          <td>
                            <div className="tag-row">
                              <Tag>
                                {r.tipo_documento
                                  ? TIPO_DOCUMENTO_CORTO[r.tipo_documento] || r.tipo_documento
                                  : 'Todo el expediente'}
                              </Tag>
                              {r.documento_principal && (
                                <Tag
                                  title={`Anexo obligatorio de ${TIPO_DOCUMENTO_LABEL[r.documento_principal] || r.documento_principal}`}
                                >
                                  Anexo de {TIPO_DOCUMENTO_CORTO[r.documento_principal] || r.documento_principal}
                                </Tag>
                              )}
                              {r.tipo_expediente && (
                                <Tag tipo>{TIPO_EXPEDIENTE_LABEL[r.tipo_expediente] || r.tipo_expediente}</Tag>
                              )}
                              {r.dias_maximos_vigencia != null && <Tag tabular>{r.dias_maximos_vigencia} días</Tag>}
                              {r.documento_obligatorio && <Tag>Obligatorio</Tag>}
                            </div>
                          </td>
                          <td className="col-right" onClick={(e) => e.stopPropagation()}>
                            <Switch
                              checked={r.activo}
                              onClick={() => setPorConfirmar(r)}
                              loading={togglingId === r.id}
                              label={`${r.activo ? 'Pausar' : 'Activar'} ${r.codigo_regla}`}
                            />
                          </td>
                        </tr>
                        {abierta && (
                          <tr className="regla-detalle">
                            <td colSpan={COLUMNAS}>
                              <DetalleRegla regla={r} />
                            </td>
                          </tr>
                        )}
                        </Fragment>
                      )
                    })}
                  </Fragment>
                ))}
            </tbody>
          </table>
        </div>
      </Card>

      {porConfirmar && (
        <Modal
          title={porConfirmar.activo ? 'Pausar regla' : 'Activar regla'}
          subtitle={`${porConfirmar.codigo_regla} · ${porConfirmar.nombre_regla}`}
          onClose={() => setPorConfirmar(null)}
        >
          <p className="confirmacion-texto">
            {porConfirmar.activo
              ? 'La regla dejará de evaluarse en todos los expedientes. El índice de cumplimiento y el semáforo pueden cambiar en la próxima evaluación.'
              : 'La regla volverá a evaluarse en todos los expedientes. El índice de cumplimiento y el semáforo pueden cambiar en la próxima evaluación.'}
          </p>
          <div className="modal-footer">
            <Button onClick={() => setPorConfirmar(null)}>Cancelar</Button>
            <Button variante="primary" onClick={confirmarCambio}>
              {porConfirmar.activo ? 'Pausar regla' : 'Activar regla'}
            </Button>
          </div>
        </Modal>
      )}

      {modalAbierto && (
        <Modal
          title="Nueva regla de validación"
          subtitle="Requisito nuevo del catálogo, sin modificar el sistema"
          onClose={cerrarModal}
        >
          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field-row">
              <Field etiqueta="Código base">
                <Input
                  className="mono"
                  required
                  minLength={3}
                  maxLength={20}
                  placeholder="RDS-04"
                  value={form.codigo_regla}
                  onChange={(e) => setForm({ ...form, codigo_regla: e.target.value.toUpperCase() })}
                />
              </Field>
              <Field etiqueta="Familia normativa">
                <Select value={form.familia_regla} onChange={(e) => setForm({ ...form, familia_regla: e.target.value })}>
                  {FAMILIAS_REGLA.map((f) => (
                    <option key={f} value={f}>
                      {f} — {FAMILIA_META[f].nombre}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            <Field etiqueta="Nombre de la regla">
              <Input
                required
                minLength={3}
                maxLength={150}
                placeholder="Ej. Vigencia de la opinión de cumplimiento"
                value={form.nombre_regla}
                onChange={(e) => setForm({ ...form, nombre_regla: e.target.value })}
              />
            </Field>

            <Field etiqueta="Descripción / criterio">
              <textarea
                required
                minLength={10}
                rows={3}
                placeholder="Criterio en lenguaje natural que evaluará el motor"
                value={form.descripcion}
                onChange={(e) => setForm({ ...form, descripcion: e.target.value })}
              />
            </Field>

            <div className="field-row">
              <Field etiqueta="Severidad">
                <Select value={form.severidad} onChange={(e) => setForm({ ...form, severidad: e.target.value })}>
                  {SEVERIDADES.map((s) => (
                    <option key={s} value={s}>
                      {getSeveridadMeta(s).label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field etiqueta="Vigencia máxima (días)">
                <Input
                  type="number"
                  min={0}
                  placeholder="Opcional"
                  value={form.dias_maximos_vigencia}
                  onChange={(e) => setForm({ ...form, dias_maximos_vigencia: e.target.value })}
                />
              </Field>
            </div>

            <Field etiqueta="Acción ante incumplimiento">
              <Input
                required
                maxLength={255}
                placeholder="Ej. Semáforo rojo y bloqueo del expediente"
                value={form.accion}
                onChange={(e) => setForm({ ...form, accion: e.target.value })}
              />
            </Field>

            <label className="checkbox-field">
              <input
                type="checkbox"
                checked={form.documento_obligatorio}
                onChange={(e) => setForm({ ...form, documento_obligatorio: e.target.checked })}
              />
              <span>Completitud obligatoria</span>
            </label>

            <Field as="div" etiqueta="Alcance de la regla">
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
                  {TIPOS_EXPEDIENTE.map((grupo) => (
                    <div className="type-picker-group" key={grupo.value}>
                      <span className="type-picker-label">{grupo.label}</span>
                      <div className="tag-row">
                        {TIPOS_DOCUMENTO.filter((t) => t.grupo === grupo.value).map((t) => {
                          const activo = form.tiposSeleccionados.includes(t.value)
                          return (
                            <button
                              type="button"
                              key={t.value}
                              className={`chip ${activo ? 'is-active' : ''}`}
                              onClick={() => toggleTipo(t.value)}
                              aria-pressed={activo}
                              title={t.label}
                            >
                              {t.corto}
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                  <p className="field-hint">
                    Se creará una regla por cada tipo seleccionado, con el código sufijado por documento.
                  </p>
                </div>
              )}
            </Field>

            <div className="field-row">
              <Field etiqueta="Tipo de expediente" ayuda="Solo se exige en expedientes de este tipo.">
                <Select value={form.tipo_expediente} onChange={(e) => setForm({ ...form, tipo_expediente: e.target.value })}>
                  <option value="">Todos los tipos</option>
                  {TIPOS_EXPEDIENTE.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field
                etiqueta="Anexo obligatorio de"
                ayuda={
                  form.aplicaTodos
                    ? 'Selecciona primero el documento del anexo.'
                    : 'Se exige solo si el expediente contiene ese documento.'
                }
              >
                <Select
                  value={form.documento_principal}
                  disabled={form.aplicaTodos}
                  onChange={(e) => setForm({ ...form, documento_principal: e.target.value })}
                >
                  <option value="">No es anexo</option>
                  {TIPOS_DOCUMENTO.filter((t) => !form.tiposSeleccionados.includes(t.value)).map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <Button onClick={cerrarModal}>Cancelar</Button>
              <Button type="submit" variante="primary" cargando={enviando}>
                Guardar regla
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
