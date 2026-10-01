import { useEffect, useMemo, useRef, useState } from 'react'
import { ChevronDown, FolderKanban, Lock, Plus, SearchX } from 'lucide-react'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, SearchBox, Segmented, Select, Tag } from './ui/index.js'
import { SkeletonCards } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import DetalleDocumentoModal from './DetalleDocumentoModal.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { createExpediente, uploadDocumento } from '../services/api.js'
import { avisarCarga } from '../utils/nivel1.js'
import { getEstadoBadge, TIPO_EXPEDIENTE_LABEL, TIPOS_EXPEDIENTE } from '../constants.js'
import { formatRelativo, iniciales } from '../utils/format.js'
import { formatIndice, indiceDe } from '../utils/indice.js'
import { DetalleExpediente } from './expedientes/DetalleExpediente.jsx'

/** Estados de cumplimiento del expediente, en el orden del semáforo. */
const ESTADOS_FILTRO = ['CONFORME', 'EN_REVISION', 'NO_CONFORME']

/**
 * Día (AAAA-MM-DD) de una marca de tiempo del backend. Las columnas TIMESTAMP
 * llegan sin zona y en la hora de la base, la misma referencia con la que el
 * resto del panel las muestra, así que basta con su parte de fecha.
 */
const diaDe = (fecha) => (fecha ? String(fecha).slice(0, 10) : '')

/**
 * Expedientes como tarjetas: cabecera con titular, tipo, folio, semáforo
 * grande y completitud; al desplegarse, la tabla de documentos que exige el
 * rules-service para su tipo, con el estado y la vigencia de cada uno, las
 * alertas con su recomendación y la exportación del dictamen.
 *
 * `foco` es el expediente desplegado, que decide la URL (#/expedientes/<folio>):
 * al llegar desde Empresas, Alertas o un enlace se despliega y se desplaza
 * hasta él. Desplegar o plegar avisa con `onAlternar`; sin ese manejador, la
 * vista guarda el expediente abierto por su cuenta. `apertura` es el titular
 * para el que se pidió abrir un expediente.
 */
export default function ExpedientesTab({
  expedientes,
  titulares,
  loading,
  onRefresh,
  isOnline = true,
  iaOnline = true,
  documentos = [],
  foco = null,
  onAlternar,
  apertura = null,
  onAperturaAtendida,
}) {
  const toast = useToast()
  const [modalAbierto, setModalAbierto] = useState(false)
  const [form, setForm] = useState({ titularId: '', tipo: 'CORPORATIVO', nombre: '' })
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const [busqueda, setBusqueda] = useState('')
  const [filtroEstado, setFiltroEstado] = useState('TODOS')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  const [desde, setDesde] = useState('')
  const [hasta, setHasta] = useState('')
  const [expandido, setExpandido] = useState(null)
  const [subiendoEn, setSubiendoEn] = useState(null)
  const tarjetas = useRef(new Map())
  // Documento abierto desde la tabla del expediente, con la lista de ese expediente para navegar.
  const [documentoAbierto, setDocumentoAbierto] = useState(null)

  const consulta = useDebounce(busqueda, 220)
  const abiertoId = onAlternar ? foco : expandido
  // Lo que el operador desplegó con un clic ya está a la vista: solo se
  // desplaza la página cuando el foco llega de fuera (otra vista o un enlace).
  const ultimoClic = useRef(null)

  useEffect(() => {
    if (foco && !loading && foco !== ultimoClic.current) {
      tarjetas.current.get(foco)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }
  }, [foco, loading])

  // Apertura pedida desde Empresas: el modal llega con el titular preseleccionado.
  const [aperturaVista, setAperturaVista] = useState(null)
  if (apertura && apertura !== aperturaVista) {
    setAperturaVista(apertura)
    setForm({ titularId: apertura, tipo: 'CORPORATIVO', nombre: '' })
    setModalAbierto(true)
    onAperturaAtendida?.()
  }

  const opcionesEstado = useMemo(
    () => [
      { id: 'TODOS', label: 'Todos', conteo: expedientes.length },
      ...ESTADOS_FILTRO.map((estado) => ({
        id: estado,
        label: getEstadoBadge(estado).label,
        tono: getEstadoBadge(estado).tono,
        conteo: expedientes.filter((e) => e.estado_cumplimiento === estado).length,
      })),
    ],
    [expedientes]
  )

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return expedientes.filter((exp) => {
      const coincideEstado = filtroEstado === 'TODOS' || exp.estado_cumplimiento === filtroEstado
      const coincideTipo = filtroTipo === 'TODOS' || exp.tipo_expediente === filtroTipo
      const dia = diaDe(exp.creado_en)
      const coincideFecha = (!desde || (dia && dia >= desde)) && (!hasta || (dia && dia <= hasta))
      const coincideBusqueda =
        !q ||
        exp.codigo_expediente?.toLowerCase().includes(q) ||
        exp.nombre?.toLowerCase().includes(q) ||
        exp.titular?.razon_social?.toLowerCase().includes(q) ||
        exp.titular?.rfc?.toLowerCase().includes(q)
      return coincideEstado && coincideTipo && coincideFecha && coincideBusqueda
    })
  }, [expedientes, consulta, filtroEstado, filtroTipo, desde, hasta])

  const hayFiltros = filtroTipo !== 'TODOS' || desde || hasta

  const alternar = (id) => {
    const siguiente = abiertoId === id ? null : id
    ultimoClic.current = siguiente
    if (onAlternar) onAlternar(siguiente)
    else setExpandido(siguiente)
  }

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm({ titularId: '', tipo: 'CORPORATIVO', nombre: '' })
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!form.titularId) return
    setEnviando(true)
    setError('')
    try {
      const creado = await createExpediente({
        titular_id: form.titularId,
        tipo_expediente: form.tipo,
        nombre: form.nombre.trim() || null,
      })
      toast.exito('Expediente aperturado', `${creado?.codigo_expediente || 'Folio generado'} · ${TIPO_EXPEDIENTE_LABEL[form.tipo]}`)
      cerrarModal()
      await onRefresh()
      if (creado?.id) {
        // El expediente nuevo se despliega y se lleva a la vista.
        ultimoClic.current = null
        if (onAlternar) onAlternar(creado.id, creado.codigo_expediente)
        else setExpandido(creado.id)
      }
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
      const documento = await uploadDocumento(formData)
      avisarCarga(toast, documento, `${archivo.name} → bóveda criptográfica`)
      onRefresh()
    } catch (err) {
      toast.error('Carga rechazada', err.message)
      throw err // DropZone conserva el archivo para reintentar, igual que en la Bóveda
    } finally {
      setSubiendoEn(null)
    }
  }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por folio, nombre, razón social o RFC…"
          label="Buscar expedientes"
        />
        <Segmented
          label="Filtrar por estado de cumplimiento"
          valor={filtroEstado}
          onChange={setFiltroEstado}
          opciones={opcionesEstado}
        />

        <Button
          variante="primary"
          icono={Plus}
          className="toolbar-action"
          onClick={() => setModalAbierto(true)}
          disabled={titulares.length === 0 || !isOnline}
          title={titulares.length === 0 ? 'Primero registra una empresa' : undefined}
        >
          Aperturar expediente
        </Button>
      </div>

      <div className="toolbar toolbar--sub">
        <Select etiqueta="Filtrar por tipo de expediente" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
          <option value="TODOS">Todo tipo de expediente</option>
          {TIPOS_EXPEDIENTE.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label} ({expedientes.filter((e) => e.tipo_expediente === t.value).length})
            </option>
          ))}
        </Select>
        <div className="date-range" role="group" aria-label="Fecha de apertura">
          <span>Apertura</span>
          <input
            type="date"
            aria-label="Apertura desde"
            value={desde}
            max={hasta || undefined}
            onChange={(e) => setDesde(e.target.value)}
          />
          <span aria-hidden="true">–</span>
          <input
            type="date"
            aria-label="Apertura hasta"
            value={hasta}
            min={desde || undefined}
            onChange={(e) => setHasta(e.target.value)}
          />
        </div>
        {hayFiltros && (
          <Button
            compacto
            onClick={() => {
              setFiltroTipo('TODOS')
              setDesde('')
              setHasta('')
            }}
          >
            Limpiar filtros
          </Button>
        )}
      </div>

      {loading && <SkeletonCards count={3} height={72} />}

      {!loading && filtrados.length === 0 && (
        <Card>
          <EmptyState
            icon={expedientes.length === 0 ? FolderKanban : SearchX}
            titulo={expedientes.length === 0 ? 'Aún no hay expedientes aperturados' : 'Sin resultados'}
            descripcion={
              expedientes.length === 0
                ? 'Apertura un expediente para empezar a custodiar la documentación de un titular.'
                : 'Ajusta la búsqueda o los filtros de estado, tipo y fecha.'
            }
          />
        </Card>
      )}

      {!loading && filtrados.length > 0 && (
        <div className="exp-list">
          {filtrados.map((exp) => {
            const meta = getEstadoBadge(exp.estado_cumplimiento)
            const indice = indiceDe(exp)
            const obligatorios = exp.evaluacion?.obligatorios || []
            const presentes = obligatorios.filter((o) => o.presente).length
            const nAlertas = exp.evaluacion?.alertas?.length || 0
            const abierto = abiertoId === exp.id
            return (
              <Card
                as="article"
                key={exp.id}
                className={`exp-card exp-card--${meta.tono} ${abierto ? 'is-open' : ''}`}
                ref={(el) => (el ? tarjetas.current.set(exp.id, el) : tarjetas.current.delete(exp.id))}
              >
                <button
                  type="button"
                  className="exp-summary"
                  onClick={() => alternar(exp.id)}
                  aria-expanded={abierto}
                  aria-label={`${exp.titular?.razon_social || exp.codigo_expediente}: ${meta.label}`}
                >
                  <span className="avatar" aria-hidden="true">
                    {iniciales(exp.titular?.razon_social || exp.codigo_expediente)}
                  </span>
                  <span className="exp-identity">
                    <span className="exp-identity-row">
                      <span className="identity-name">{exp.titular?.razon_social || 'Titular no disponible'}</span>
                      <Tag tipo>{TIPO_EXPEDIENTE_LABEL[exp.tipo_expediente] || exp.tipo_expediente}</Tag>
                    </span>
                    <span className="cell-sub">
                      {exp.nombre && <span className="exp-nombre">{exp.nombre} · </span>}
                      <span className="mono">
                        {exp.codigo_expediente} · {exp.titular?.rfc || 'sin RFC'}
                      </span>
                      {nAlertas > 0 && (
                        <span className="exp-nalertas">
                          {' '}
                          · {nAlertas} {nAlertas === 1 ? 'alerta' : 'alertas'}
                        </span>
                      )}
                    </span>
                  </span>
                  <Badge tono={meta.tono} punto grande>
                    {meta.label}
                  </Badge>
                  <span
                    className="exp-indice"
                    title={
                      indice?.bloqueado
                        ? `Bloqueado: ${indice.bloqueos.join(' ')}`
                        : 'Índice de cumplimiento: reglas cumplidas entre reglas aplicables'
                    }
                  >
                    <span className="exp-indice-valor tabular">
                      {indice?.bloqueado && <Lock size={11} strokeWidth={1.75} aria-label="Bloqueado" />}
                      {formatIndice(indice?.porcentaje)}
                      <span className="cell-muted"> cumplimiento</span>
                    </span>
                    <span className="cell-sub tabular">
                      {presentes}/{obligatorios.length} obligatorios
                    </span>
                  </span>
                  <span className="exp-updated cell-muted tabular">{formatRelativo(exp.actualizado_en)}</span>
                  <span className="squircle exp-chevron" aria-hidden="true">
                    <ChevronDown size={14} className="chevron" />
                  </span>
                </button>

                {abierto && (
                  <DetalleExpediente
                    exp={exp}
                    subiendo={subiendoEn === exp.id}
                    onSubir={subirDocumento}
                    iaOnline={iaOnline}
                    onRefresh={onRefresh}
                    documentos={documentos}
                    onAbrirDocumento={(documento, lista) => setDocumentoAbierto({ documento, lista })}
                  />
                )}
              </Card>
            )
          })}
        </div>
      )}

      {modalAbierto && (
        <Modal
          title="Aperturar expediente"
          subtitle="Vincula un nuevo fólder de cumplimiento a un titular existente"
          onClose={cerrarModal}
        >
          <form className="form-grid" onSubmit={handleSubmit}>
            <Field etiqueta="Titular">
              <Select required value={form.titularId} onChange={(e) => setForm({ ...form, titularId: e.target.value })}>
                <option value="" disabled>
                  Selecciona una empresa…
                </option>
                {titulares.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.razon_social} — {t.rfc}
                  </option>
                ))}
              </Select>
            </Field>

            <Field as="div" etiqueta="Tipo de expediente" ayuda="El tipo decide qué documentos exige el catálogo de reglas.">
              <div className="type-options" role="radiogroup" aria-label="Tipo de expediente">
                {TIPOS_EXPEDIENTE.map((t) => (
                  <label key={t.value} className={`type-option ${form.tipo === t.value ? 'is-active' : ''}`}>
                    <input
                      type="radio"
                      name="tipo_expediente"
                      value={t.value}
                      checked={form.tipo === t.value}
                      onChange={() => setForm({ ...form, tipo: t.value })}
                    />
                    <span className="type-option-label">{t.label}</span>
                    <span className="type-option-desc">{t.descripcion}</span>
                  </label>
                ))}
              </div>
            </Field>

            <Field etiqueta="Nombre descriptivo (opcional)">
              <Input
                maxLength={150}
                placeholder="Ej. Contrato de mantenimiento 2026"
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </Field>

            <p className="field-hint">El folio del expediente se genera automáticamente al crearlo.</p>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <Button onClick={cerrarModal}>Cancelar</Button>
              <Button type="submit" variante="primary" cargando={enviando} disabled={!form.titularId}>
                Crear expediente
              </Button>
            </div>
          </form>
        </Modal>
      )}

      {documentoAbierto && (
        <DetalleDocumentoModal
          documento={documentoAbierto.documento}
          lista={documentoAbierto.lista}
          expediente={expedientes.find((e) => e.id === documentoAbierto.documento.expediente_id)}
          iaOnline={iaOnline}
          onRefresh={onRefresh}
          onCambiar={(documento) => setDocumentoAbierto((previo) => ({ ...previo, documento }))}
          onCerrar={() => setDocumentoAbierto(null)}
        />
      )}
    </div>
  )
}
