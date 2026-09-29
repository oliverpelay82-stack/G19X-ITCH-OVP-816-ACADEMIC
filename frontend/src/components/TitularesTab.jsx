import { useMemo, useState } from 'react'
import { Building2, ChevronRight, FolderOpen, FolderPlus, LayoutGrid, Plus, Rows3, SearchX } from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  CopyChip,
  EmptyRow,
  EmptyState,
  Field,
  IconButton,
  Input,
  KeyValue,
  KeyValueList,
  Modal,
  SearchBox,
  Segmented,
  Select,
  Tag,
} from './ui/index.js'
import { SkeletonCards, SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { createTitular } from '../services/api.js'
import { categoriaTitular, getEstadoBadge } from '../constants.js'
import { formatFechaCorta, iniciales, validarRfc } from '../utils/format.js'

const FORM_INICIAL = { rfc: '', razon_social: '', tipo_persona: 'MORAL', categoria: 'PROVEEDOR' }

const FILTROS_TIPO = [
  { id: 'TODOS', label: 'Todas' },
  { id: 'MORAL', label: 'Moral' },
  { id: 'FISICA', label: 'Física' },
]

/** Con pocas empresas una tabla queda desierta: hasta este número se muestran tarjetas de perfil. */
const MAX_TARJETAS_AUTO = 6

const COLUMNAS = 7

const tipoPersona = (t) => (t === 'FISICA' ? 'Persona física' : 'Persona moral')

/** Semáforo compacto del expediente más reciente del titular. */
function EstadoExpediente({ expediente }) {
  if (!expediente) return <span className="cell-muted">Sin expediente</span>
  const meta = getEstadoBadge(expediente.estado_cumplimiento)
  return (
    <Badge tono={meta.tono} punto>
      {meta.label}
    </Badge>
  )
}

/** Acción principal del titular: abrir su expediente o aperturar el primero. */
function AccionExpediente({ titular, expediente, onAbrir, onAperturar, isOnline, compacta = false }) {
  if (expediente) {
    return compacta ? (
      <IconButton
        etiqueta={`Abrir expediente ${expediente.codigo_expediente}`}
        compacto
        onClick={() => onAbrir(expediente.id)}
        title="Abrir expediente"
      >
        <ChevronRight size={14} />
      </IconButton>
    ) : (
      <Button compacto icono={FolderOpen} onClick={() => onAbrir(expediente.id)}>
        Abrir expediente
      </Button>
    )
  }
  const etiqueta = `Aperturar expediente para ${titular.razon_social}`
  return compacta ? (
    <IconButton etiqueta={etiqueta} compacto onClick={() => onAperturar(titular)} disabled={!isOnline} title="Aperturar expediente">
      <FolderPlus size={14} />
    </IconButton>
  ) : (
    <Button
      compacto
      icono={FolderPlus}
      onClick={() => onAperturar(titular)}
      disabled={!isOnline}
      aria-label={etiqueta}
      title="Aperturar expediente"
    >
      Aperturar expediente
    </Button>
  )
}

/** Tarjeta de perfil corporativo: identidad, datos regulatorios y su expediente. */
function TarjetaTitular({ titular, expedientes, ...acciones }) {
  const [ultimo] = expedientes
  return (
    <Card as="article" className="profile-card">
      <header className="profile-head">
        <span className="avatar avatar--lg" aria-hidden="true">
          {iniciales(titular.razon_social)}
        </span>
        <div className="profile-identity">
          <h3 className="profile-name" title={titular.razon_social}>
            {titular.razon_social}
          </h3>
          <p className="profile-sub">
            {tipoPersona(titular.tipo_persona)} · alta {formatFechaCorta(titular.creado_en)}
          </p>
        </div>
      </header>

      <KeyValueList className="profile-grid">
        <KeyValue etiqueta="RFC">
          <CopyChip valor={titular.rfc} etiqueta="RFC" />
        </KeyValue>
        <KeyValue etiqueta="Categoría regulatoria">
          <Tag>{categoriaTitular(titular.categoria)}</Tag>
        </KeyValue>
      </KeyValueList>

      <footer className="profile-foot">
        <div className="profile-exp">
          <EstadoExpediente expediente={ultimo} />
          {ultimo && (
            <span className="mono cell-muted profile-folio" title={ultimo.codigo_expediente}>
              {ultimo.codigo_expediente}
              {expedientes.length > 1 && ` +${expedientes.length - 1}`}
            </span>
          )}
        </div>
        <AccionExpediente titular={titular} expediente={ultimo} {...acciones} />
      </footer>
    </Card>
  )
}

/**
 * Directorio de titulares. Con pocas empresas se muestran tarjetas de perfil
 * corporativo (una tabla de una fila queda desierta); con muchas, la tabla
 * densa. El operador puede fijar cualquiera de las dos vistas.
 */
export default function TitularesTab({
  titulares,
  expedientes = [],
  onAbrirExpediente,
  onAperturarExpediente,
  loading,
  onRefresh,
  isOnline = true,
}) {
  const toast = useToast()
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  const [vistaElegida, setVistaElegida] = useState(null) // null: automática según el número de empresas

  const consulta = useDebounce(busqueda, 220)
  const rfcCheck = validarRfc(form.rfc, form.tipo_persona)
  const vista = vistaElegida || (titulares.length <= MAX_TARJETAS_AUTO ? 'tarjetas' : 'tabla')

  const conteos = useMemo(
    () => ({
      TODOS: titulares.length,
      MORAL: titulares.filter((t) => t.tipo_persona === 'MORAL').length,
      FISICA: titulares.filter((t) => t.tipo_persona === 'FISICA').length,
    }),
    [titulares]
  )

  /** Expedientes de cada titular, del más reciente al más antiguo (así llegan del core). */
  const expedientesPorTitular = useMemo(() => {
    const mapa = new Map()
    for (const e of expedientes) {
      if (!mapa.has(e.titular_id)) mapa.set(e.titular_id, [])
      mapa.get(e.titular_id).push(e)
    }
    return mapa
  }, [expedientes])

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return titulares.filter((t) => {
      const coincideTipo = filtroTipo === 'TODOS' || t.tipo_persona === filtroTipo
      const coincideBusqueda =
        !q ||
        t.rfc?.toLowerCase().includes(q) ||
        t.razon_social?.toLowerCase().includes(q) ||
        t.categoria?.toLowerCase().includes(q) ||
        categoriaTitular(t.categoria).toLowerCase().includes(q)
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

  // El tipo de expediente (RF-01) se elige en el modal de Expedientes, que
  // llega con este titular preseleccionado.
  const aperturar = (titular) => onAperturarExpediente?.(titular.id)

  const acciones = {
    onAbrir: (id) => onAbrirExpediente?.(id),
    onAperturar: aperturar,
    isOnline,
  }

  const vacio = !loading && filtrados.length === 0
  const vacioProps = {
    icon: titulares.length === 0 ? Building2 : SearchX,
    titulo: titulares.length === 0 ? 'Aún no hay empresas registradas' : 'Sin resultados',
    descripcion:
      titulares.length === 0
        ? 'Da de alta el primer titular para abrir su expediente de cumplimiento.'
        : 'Prueba con otro término o cambia el filtro de tipo de persona.',
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
        <Segmented
          label="Modo de vista"
          valor={vista}
          onChange={setVistaElegida}
          opciones={[
            { id: 'tarjetas', label: <LayoutGrid size={14} aria-label="Tarjetas" />, tooltip: 'Tarjetas de perfil' },
            { id: 'tabla', label: <Rows3 size={14} aria-label="Tabla" />, tooltip: 'Tabla densa' },
          ]}
        />

        <Button
          variante="primary"
          icono={Plus}
          className="toolbar-action"
          onClick={() => setModalAbierto(true)}
          disabled={!isOnline}
          title={!isOnline ? 'El core-service (:8001) no responde' : undefined}
        >
          Alta de empresa
        </Button>
      </div>

      {vista === 'tarjetas' ? (
        loading ? (
          <SkeletonCards count={3} height={176} />
        ) : vacio ? (
          <Card>
            <EmptyState {...vacioProps} />
          </Card>
        ) : (
          <div className="card-grid">
            {filtrados.map((t) => (
              <TarjetaTitular
                key={t.id}
                titular={t}
                expedientes={expedientesPorTitular.get(t.id) || []}
                {...acciones}
              />
            ))}
          </div>
        )
      ) : (
        <Card className="table-card">
          <div className="table-scroll">
            <table className="data-table">
              <colgroup>
                <col style={{ width: '31%' }} />
                <col style={{ width: '17%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '15%' }} />
                <col style={{ width: '14%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: 52 }} />
              </colgroup>
              <thead>
                <tr>
                  <th>Titular</th>
                  <th>RFC</th>
                  <th>Tipo</th>
                  <th>Categoría</th>
                  <th>Expediente</th>
                  <th className="col-right">Alta</th>
                  <th aria-label="Acciones" />
                </tr>
              </thead>
              <tbody>
                {loading && <SkeletonRows rows={5} cols={COLUMNAS} />}
                {vacio && <EmptyRow columnas={COLUMNAS} {...vacioProps} />}
                {!loading &&
                  filtrados.map((t) => {
                    const [ultimo] = expedientesPorTitular.get(t.id) || []
                    return (
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
                          <Badge>{t.tipo_persona === 'FISICA' ? 'Física' : 'Moral'}</Badge>
                        </td>
                        <td>
                          <Tag>{categoriaTitular(t.categoria)}</Tag>
                        </td>
                        <td>
                          <EstadoExpediente expediente={ultimo} />
                        </td>
                        <td className="col-right cell-muted tabular">{formatFechaCorta(t.creado_en)}</td>
                        <td className="col-action">
                          <AccionExpediente
                            titular={t}
                            expediente={ultimo}
                            compacta
                            {...acciones}
                          />
                        </td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </Card>
      )}

      {modalAbierto && (
        <Modal title="Alta de empresa" subtitle="Registra un nuevo titular de expediente" onClose={cerrarModal}>
          <form className="form-grid" onSubmit={handleSubmit}>
            <div className="field-row">
              <Field etiqueta="Tipo de persona">
                <Select value={form.tipo_persona} onChange={(e) => setForm({ ...form, tipo_persona: e.target.value })}>
                  <option value="MORAL">Moral (RFC de 12)</option>
                  <option value="FISICA">Física (RFC de 13)</option>
                </Select>
              </Field>

              <Field etiqueta="Categoría">
                <Select value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>
                  <option value="PROVEEDOR">Proveedor</option>
                  <option value="CLIENTE">Cliente</option>
                </Select>
              </Field>
            </div>

            <Field
              etiqueta={
                <>
                  RFC
                  <span className="field-counter mono">
                    {form.rfc.length}/{form.tipo_persona === 'FISICA' ? 13 : 12}
                  </span>
                </>
              }
              retro={rfcCheck.estado !== 'vacio' ? rfcCheck : null}
            >
              <Input
                estado={rfcCheck.estado}
                className="mono"
                required
                maxLength={13}
                placeholder={form.tipo_persona === 'FISICA' ? 'PEPJ850101H23' : 'PLU200115AB1'}
                value={form.rfc}
                onChange={(e) => setForm({ ...form, rfc: e.target.value.toUpperCase().replace(/\s/g, '') })}
                autoComplete="off"
                spellCheck="false"
              />
            </Field>

            <Field etiqueta="Razón social / Nombre completo">
              <Input
                required
                minLength={3}
                maxLength={200}
                placeholder="PluriOne S.A. de C.V."
                value={form.razon_social}
                onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
              />
            </Field>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <Button onClick={cerrarModal}>Cancelar</Button>
              <Button type="submit" variante="primary" cargando={enviando} disabled={rfcCheck.estado !== 'valido'}>
                Registrar titular
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
