import { useMemo, useState } from 'react'
import { Buildings, CaretRight, FolderOpen, FolderPlus, MagnifyingGlass, Plus, Rows, SquaresFour, Warning } from './iconos.js'
import { EncabezadoOrdenable } from './OrdenTabla.jsx'
import useOrden, { RANGO_ESTADO } from '../hooks/useOrden.js'
import {
  Avatar,
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
  Tooltip,
} from './ui/index.js'
import { SkeletonCards, SkeletonRows } from './Skeleton.jsx'
import { CORE_FUERA_DE_LINEA, sinRespuesta } from './sinRespuesta.js'
import useToast from '../hooks/useToast.js'
import usePermiso from '../hooks/usePermiso.js'
import useDebounce from '../hooks/useDebounce.js'
import { coincideEn, normalizar } from '../utils/busqueda.js'
import useDesplazamiento from '../hooks/useDesplazamiento.js'
import { createTitular } from '../services/api.js'
import { categoriaTitular } from '../constants.js'
import { formatFechaCorta, rfcRegistrable, validarRfc } from '../utils/format.js'
import { formatIndice, indiceDe } from '../utils/indice.js'
import FolioExpediente from './FolioExpediente.jsx'
import EstadoBadge from './EstadoBadge.jsx'
import DetalleEmpresa, { EmpresaNoEncontrada } from './DetalleEmpresa.jsx'

const EXPLICACION_RFC = 'Es común en un RFC ficticio de prueba. Si el RFC es real, revisa que esté bien escrito.'

/**
 * M1: el dígito verificador del RFC no coincide (RFC de prueba o mal escrito);
 * se aceptó porque la validación estricta está desactivada. Etiqueta compacta de
 * advertencia (no de error) con la explicación al pasar el cursor o al enfocarla.
 */
function AvisoRfc({ titular }) {
  if (titular.rfc_verificacion !== 'DIGITO_NO_COINCIDE') return null
  return (
    <Tooltip texto={EXPLICACION_RFC}>
      <Badge tono="warn" className="rfc-aviso" tabIndex={0}>
        <Warning size={12} aria-hidden="true" />
        Dígito verificador no coincide (permitido en pruebas)
        <span className="sr-only">. {EXPLICACION_RFC}</span>
      </Badge>
    </Tooltip>
  )
}

/** Índice de cumplimiento del expediente junto a su semáforo: cuánto le falta, no solo su estado. */
function IndiceTarjeta({ expediente }) {
  const porcentaje = indiceDe(expediente)?.porcentaje
  if (porcentaje == null) return null
  return (
    <span className="profile-indice" title="Índice de cumplimiento: reglas cumplidas entre reglas evaluadas">
      <span className="metric-bar profile-indice-barra" aria-hidden="true">
        <span className="metric-bar-fill" style={{ width: `${Math.round(porcentaje)}%` }} />
      </span>
      <span>
        <span className="tabular">{formatIndice(porcentaje)}</span> cumplimiento
      </span>
    </span>
  )
}

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
  return <EstadoBadge estado={expediente.estado_cumplimiento} />
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
        <CaretRight size={14} />
      </IconButton>
    ) : (
      <Button compacto icono={FolderOpen} onClick={() => onAbrir(expediente.id)}>
        Abrir expediente
      </Button>
    )
  }
  // Módulo 7: el auditor no apertura expedientes.
  if (!onAperturar) return null
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
/** Razón social que abre el detalle de la empresa (#/empresas/<RFC>). */
function NombreEmpresa({ titular, onVer, className = '' }) {
  return (
    <button type="button" className={`enlace-empresa ${className}`} onClick={() => onVer(titular.rfc)} title={`Ver el detalle de ${titular.razon_social}`}>
      {titular.razon_social}
    </button>
  )
}

function TarjetaTitular({ titular, expedientes, indice = 0, ...acciones }) {
  const [ultimo] = expedientes
  return (
    <Card as="article" className="profile-card" data-flip={titular.id} style={{ '--i': indice }}>
      <header className="profile-head">
        <Avatar nombre={titular.razon_social} grande />
        <div className="profile-identity">
          <h3 className="profile-name">
            <NombreEmpresa titular={titular} onVer={acciones.onVer} />
          </h3>
          <p className="profile-sub">
            {tipoPersona(titular.tipo_persona)} · alta {formatFechaCorta(titular.creado_en)}
          </p>
          {ultimo && (
            <p className="mono cell-muted profile-folio">
              <FolioExpediente expediente={ultimo} />
              {expedientes.length > 1 && ` +${expedientes.length - 1}`}
            </p>
          )}
        </div>
      </header>

      <KeyValueList className="profile-grid">
        <KeyValue etiqueta="RFC">
          <CopyChip valor={titular.rfc} etiqueta="RFC" />
          <AvisoRfc titular={titular} />
        </KeyValue>
        <KeyValue etiqueta="Categoría">
          <Tag>{categoriaTitular(titular.categoria)}</Tag>
        </KeyValue>
      </KeyValueList>

      <footer className="profile-foot">
        <div className="profile-exp">
          <EstadoExpediente expediente={ultimo} />
          {ultimo && <IndiceTarjeta expediente={ultimo} />}
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
  rfcAbierto = null,
  onVerEmpresa,
  onVerAlertas,
  loading,
  onRefresh,
  isOnline = true,
}) {
  const toast = useToast()
  // Módulo 7 (PRD §5.1): registrar empresas y aperturar expedientes es de la operación.
  const operar = usePermiso('operar')
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
    const q = normalizar(consulta)
    return titulares.filter((t) => {
      const coincideTipo = filtroTipo === 'TODOS' || t.tipo_persona === filtroTipo
      const coincideBusqueda = coincideEn([t.rfc, t.razon_social, t.categoria, categoriaTitular(t.categoria)], q)
      return coincideTipo && coincideBusqueda
    })
  }, [titulares, consulta, filtroTipo])

  // Orden por columna de la tabla densa; el expediente ordena por su semáforo, de lo más grave a lo conforme.
  const clavesOrden = useMemo(
    () => ({
      titular: (t) => t.razon_social,
      rfc: (t) => t.rfc,
      tipo: (t) => t.tipo_persona,
      categoria: (t) => categoriaTitular(t.categoria),
      expediente: (t) => RANGO_ESTADO[(expedientesPorTitular.get(t.id) || [])[0]?.estado_cumplimiento],
      alta: (t) => t.creado_en,
    }),
    [expedientesPorTitular]
  )
  const { ordenada, orden, ordenar } = useOrden(filtrados, clavesOrden)
  const rejilla = useDesplazamiento()
  const filas = useDesplazamiento()

  const cerrarModal = () => {
    setModalAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!rfcRegistrable(rfcCheck)) {
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
  const aperturar = operar ? (titular) => onAperturarExpediente?.(titular.id) : null

  const acciones = {
    onAbrir: (id) => onAbrirExpediente?.(id),
    onAperturar: aperturar,
    onVer: (rfc) => onVerEmpresa?.(rfc),
    isOnline,
  }

  if (rfcAbierto && !loading) {
    const titular = titulares.find((t) => t.rfc === rfcAbierto)
    const volver = () => onVerEmpresa?.(null)
    return titular ? (
      <DetalleEmpresa
        titular={titular}
        expedientes={expedientesPorTitular.get(titular.id) || []}
        aviso={<AvisoRfc titular={titular} />}
        onAbrir={acciones.onAbrir}
        onAperturar={aperturar}
        onVerAlertas={onVerAlertas}
        onRefresh={onRefresh}
        isOnline={isOnline}
      />
    ) : (
      <EmpresaNoEncontrada rfc={rfcAbierto} onVolver={volver} />
    )
  }

  const vacio = !loading && filtrados.length === 0
  // Sin respuesta del core y sin datos que mostrar: no es una lista vacía (null = aún sin sondear).
  const caido = isOnline === false && titulares.length === 0
  const vacioProps = caido
    ? sinRespuesta(
        CORE_FUERA_DE_LINEA,
        'El sistema de expedientes no responde: no es posible consultar ni registrar empresas. La lista se actualiza sola cuando vuelva a responder.'
      )
    : {
        icon: titulares.length === 0 ? Buildings : MagnifyingGlass,
        titulo: titulares.length === 0 ? 'Aún no hay empresas registradas' : 'Sin resultados',
        descripcion:
          titulares.length === 0
            ? 'Da de alta el primer titular para abrir su expediente de cumplimiento.'
            : 'Prueba con otro término o cambia el filtro de tipo de persona.',
        children:
          titulares.length === 0 ? (
            operar && (
              <Button variante="primary" compacto icono={Plus} onClick={() => setModalAbierto(true)} disabled={!isOnline}>
                Alta de empresa
              </Button>
            )
          ) : (
            <Button
              compacto
              onClick={() => {
                setBusqueda('')
                setFiltroTipo('TODOS')
              }}
            >
              Limpiar búsqueda
            </Button>
          ),
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
            { id: 'tarjetas', label: <SquaresFour size={14} aria-label="Tarjetas" />, tooltip: 'Tarjetas de perfil' },
            { id: 'tabla', label: <Rows size={14} aria-label="Tabla" />, tooltip: 'Tabla densa' },
          ]}
        />

        {operar && (
          <Button
            variante="primary"
            icono={Plus}
            className="toolbar-action"
            onClick={() => setModalAbierto(true)}
            disabled={!isOnline}
            title={!isOnline ? 'El sistema de expedientes no responde' : undefined}
          >
            Alta de empresa
          </Button>
        )}
      </div>

      {vista === 'tarjetas' ? (
        loading ? (
          <SkeletonCards count={3} height={176} />
        ) : vacio ? (
          <Card>
            <EmptyState {...vacioProps} />
          </Card>
        ) : (
          <div className="card-grid" ref={rejilla}>
            {filtrados.map((t, i) => (
              <TarjetaTitular
                key={t.id}
                indice={i}
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
                  <EncabezadoOrdenable columna="titular" orden={orden} onOrdenar={ordenar}>
                    Titular
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="rfc" orden={orden} onOrdenar={ordenar}>
                    RFC
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="tipo" orden={orden} onOrdenar={ordenar}>
                    Tipo
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="categoria" orden={orden} onOrdenar={ordenar}>
                    Categoría
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="expediente" orden={orden} onOrdenar={ordenar}>
                    Expediente
                  </EncabezadoOrdenable>
                  <EncabezadoOrdenable columna="alta" orden={orden} onOrdenar={ordenar} inicial="desc" className="col-right">
                    Alta
                  </EncabezadoOrdenable>
                  <th aria-label="Acciones" />
                </tr>
              </thead>
              <tbody ref={filas}>
                {loading && <SkeletonRows rows={5} cols={COLUMNAS} />}
                {vacio && <EmptyRow columnas={COLUMNAS} {...vacioProps} />}
                {!loading &&
                  ordenada.map((t, i) => {
                    const [ultimo] = expedientesPorTitular.get(t.id) || []
                    return (
                      <tr key={t.id} data-flip={t.id} style={{ '--i': i }}>
                        <td>
                          <div className="identity">
                            <Avatar nombre={t.razon_social} />
                            <NombreEmpresa titular={t} onVer={acciones.onVer} className="identity-name" />
                          </div>
                        </td>
                        <td>
                          <CopyChip valor={t.rfc} etiqueta="RFC" />
                          <AvisoRfc titular={t} />
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
                        <td className="col-right cell-num tabular">{formatFechaCorta(t.creado_en)}</td>
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
              <Button type="submit" variante="primary" cargando={enviando} disabled={!rfcRegistrable(rfcCheck)}>
                Registrar titular
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
