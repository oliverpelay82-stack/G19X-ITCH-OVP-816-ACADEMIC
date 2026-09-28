import { useEffect, useMemo, useRef, useState } from 'react'
import { Check, ChevronDown, FolderKanban, Loader2, Maximize2, Minus, Plus, SearchX, Sparkles, X } from 'lucide-react'
import { Badge, Button, Card, EmptyState, Field, Input, Modal, SearchBox, Segmented, Select, Tag } from './ui/index.js'
import { SkeletonCards } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import DropZone from './DropZone.jsx'
import ExportarReporte from './ExportarReporte.jsx'
import { ListaAlertasAgrupadas } from './Alertas.jsx'
import DetalleDocumentoModal from './DetalleDocumentoModal.jsx'
import HistorialExpediente from './HistorialExpediente.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { analizarDocumento, createExpediente, getExpedienteById, uploadDocumento } from '../services/api.js'
import {
  ESTADO_DOCUMENTO,
  getEstadoBadge,
  getSeveridadMeta,
  TIPO_DOCUMENTO_LABEL,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_EXPEDIENTE,
  tiposParaCarga,
  tonoPorPorcentaje,
  VIGENCIA_META,
} from '../constants.js'
import { formatDia, formatRelativo, iniciales } from '../utils/format.js'

/** Estados de cumplimiento del expediente, en el orden del semáforo. */
const ESTADOS_FILTRO = ['CONFORME', 'EN_REVISION', 'NO_CONFORME']

/**
 * Día (AAAA-MM-DD) de una marca de tiempo del backend. Las columnas TIMESTAMP
 * llegan sin zona y en la hora de la base, la misma referencia con la que el
 * resto del panel las muestra, así que basta con su parte de fecha.
 */
const diaDe = (fecha) => (fecha ? String(fecha).slice(0, 10) : '')

/**
 * Filas del detalle: cada documento que exige el catálogo de reglas (RIE-01),
 * los anexos que se volvieron exigibles (RIE-02) con el archivo vigente y su
 * estado, más los documentos opcionales cargados.
 */
function filasDetalle(evaluacion) {
  const obligatorios = evaluacion?.obligatorios || []
  const porTipo = new Map((evaluacion?.documentos || []).map((d) => [d.tipo_documento, d]))
  const filas = obligatorios.map((o) => {
    const doc = porTipo.get(o.tipo_documento)
    return {
      tipo: o.tipo_documento,
      regla: o.codigo_regla,
      severidad: o.severidad,
      anexoDe: o.documento_principal,
      obligatorio: true,
      doc,
      estado: o.presente ? doc?.estado || 'SIN_DICTAMEN' : 'FALTANTE',
    }
  })
  for (const d of evaluacion?.documentos || []) {
    if (!d.obligatorio) {
      filas.push({ tipo: d.tipo_documento, regla: null, severidad: null, obligatorio: false, doc: d, estado: d.estado })
    }
  }
  return filas
}

/** Línea de vigencia del archivo: estado a hoy y fecha en que vence o venció (RN-02). */
function Vigencia({ doc }) {
  if (!doc?.vigencia) return null
  const meta = VIGENCIA_META[doc.vigencia]
  const dias = doc.dias_para_vencer
  const texto =
    doc.vigencia === 'VENCIDO'
      ? `Venció el ${formatDia(doc.fecha_caducidad)}`
      : `Vence el ${formatDia(doc.fecha_caducidad)} · ${dias} ${dias === 1 ? 'día' : 'días'}`
  return <span className={`cell-sub cell-${meta?.tono === 'ok' ? 'muted' : meta?.tono}`}>{texto}</span>
}

/** Estado de un documento dentro de «Auditar pendientes». */
const PASO = {
  cola: { icono: null, texto: 'En cola' },
  auditando: { icono: Loader2, texto: 'Auditando…' },
  hecho: { icono: Check, texto: null },
  error: { icono: X, texto: null },
}

/**
 * Validación del expediente con un solo botón (HU-32): audita en secuencia,
 * con reglas e IA, los documentos vigentes que aún no tienen dictamen. Es una
 * ejecución manual: subir un archivo nunca lo analiza por sí solo. Un fallo en
 * un documento no detiene los demás (HU-33). Muestra el avance por documento
 * y, al terminar, el resultado consolidado: el semáforo antes y después y las
 * alertas que quedan.
 */
function AuditarPendientes({ exp, iaOnline, onTerminado }) {
  const [pasos, setPasos] = useState(null)
  const [resultado, setResultado] = useState(null)
  const pendientes = (exp.evaluacion?.documentos || []).filter(
    (d) => d.estado === 'SIN_DICTAMEN' && d.estado_integridad !== 'ALTERADO'
  )
  const enCurso = Boolean(pasos) && !resultado

  const auditar = async () => {
    const antes = { estado: exp.estado_cumplimiento, alertas: exp.evaluacion?.alertas?.length || 0 }
    const lista = pendientes.map((d) => ({ id: d.documento_id, nombre: d.nombre_archivo_original, estado: 'cola' }))
    setResultado(null)
    setPasos(lista)
    const marcar = (id, cambio) => setPasos((prev) => prev.map((p) => (p.id === id ? { ...p, ...cambio } : p)))
    let fallidos = 0
    for (const d of lista) {
      marcar(d.id, { estado: 'auditando' })
      try {
        const r = await analizarDocumento({
          documento_id: d.id,
          rfc_titular: exp.titular?.rfc || undefined,
          razon_social_titular: exp.titular?.razon_social || undefined,
        })
        marcar(d.id, { estado: 'hecho', dictamen: r?.estatus_preliminar })
      } catch (err) {
        fallidos += 1
        marcar(d.id, { estado: 'error', detalle: err?.message || 'Error del ai-service' })
      }
    }
    let despues = null
    try {
      const actualizado = await getExpedienteById(exp.id)
      despues = { estado: actualizado?.estado_cumplimiento, alertas: actualizado?.evaluacion?.alertas?.length || 0 }
    } catch {
      // El resultado se muestra sin el semáforo si el core-service no responde.
    }
    setResultado({ antes, despues, auditados: lista.length - fallidos, total: lista.length })
    onTerminado?.()
  }

  if (!pendientes.length && !pasos) return null
  return (
    <div className="exp-auditar">
      <p className="eyebrow">Validación del expediente</p>
      {!pasos && (
        <p className="field-hint">
          {pendientes.length} {pendientes.length === 1 ? 'documento sin auditar' : 'documentos sin auditar'}. Se validan
          con reglas e IA uno por uno.
        </p>
      )}
      {pasos && (
        <ol className="auditoria-pasos" aria-live="polite">
          {pasos.map((p) => {
            const meta = PASO[p.estado]
            const Icono = meta.icono
            const estatus = p.dictamen && getEstadoBadge(p.dictamen)
            return (
              <li key={p.id} className={`auditoria-paso auditoria-paso--${p.estado}`}>
                <span className="auditoria-paso-icono" aria-hidden="true">
                  {Icono ? <Icono size={12} className={p.estado === 'auditando' ? 'spin' : undefined} /> : <Minus size={12} />}
                </span>
                <span className="cell-ellipsis" title={p.nombre}>
                  {p.nombre}
                </span>
                <span className={`auditoria-paso-estado ${p.estado === 'error' ? 'cell-bad' : ''}`} title={p.detalle}>
                  {estatus ? estatus.label : p.estado === 'error' ? 'Error' : meta.texto}
                </span>
              </li>
            )
          })}
        </ol>
      )}
      {resultado && (
        <div className="auditoria-resultado" role="status">
          <p>
            <strong>
              {resultado.auditados} de {resultado.total}
            </strong>{' '}
            {resultado.total === 1 ? 'documento auditado' : 'documentos auditados'}.
          </p>
          {resultado.despues && (
            <p>
              Semáforo{' '}
              <Badge tono={getEstadoBadge(resultado.antes.estado).tono}>{getEstadoBadge(resultado.antes.estado).label}</Badge>{' '}
              →{' '}
              <Badge tono={getEstadoBadge(resultado.despues.estado).tono}>{getEstadoBadge(resultado.despues.estado).label}</Badge>
              {' · '}
              {resultado.despues.alertas} {resultado.despues.alertas === 1 ? 'alerta' : 'alertas'} (antes{' '}
              {resultado.antes.alertas})
            </p>
          )}
        </div>
      )}
      {(!pasos || resultado) && pendientes.length > 0 && (
        <Button
          variante="primary"
          icono={Sparkles}
          onClick={auditar}
          disabled={enCurso || !iaOnline}
          title={iaOnline ? undefined : 'El ai-service (:8003) no responde'}
        >
          Auditar pendientes
        </Button>
      )}
      {enCurso && (
        <Button variante="primary" cargando>
          Auditando…
        </Button>
      )}
    </div>
  )
}

/**
 * Los motivos del semáforo en palabras del analista (RNF-08): el motor los
 * redacta con los códigos del catálogo (ACTA_CONSTITUTIVA); aquí se leen con
 * el nombre del documento. No se calcula nada: es el mismo motivo del motor.
 */
const ESTATUS_LEGIBLE = { CONFORME: 'conforme', EN_REVISION: 'en revisión', NO_CONFORME: 'no conforme' }

function legible(motivo) {
  return motivo.replace(
    /\b[A-Z][A-Z0-9_]{3,}\b/g,
    (codigo) => TIPO_DOCUMENTO_LABEL[codigo] || ESTATUS_LEGIBLE[codigo] || codigo
  )
}

const TITULO_MOTIVOS = {
  CONFORME: 'Por qué está conforme',
  EN_REVISION: 'Por qué está en revisión',
  NO_CONFORME: 'Por qué no está conforme',
}

function MotivosSemaforo({ estado, motivos = [] }) {
  if (!motivos.length) return null
  const meta = getEstadoBadge(estado)
  return (
    <div className={`exp-motivos exp-motivos--${meta.tono}`}>
      <p className="exp-motivos-titulo">
        <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />
        {TITULO_MOTIVOS[estado] || 'Motivos del semáforo'}
      </p>
      <ul>
        {motivos.map((m) => (
          <li key={m}>{legible(m)}</li>
        ))}
      </ul>
    </div>
  )
}

/** Detalle desplegado: motivos, documentos requeridos, alertas, historial, carga y exportación. */
function DetalleExpediente({ exp, subiendo, onSubir, iaOnline, onRefresh, documentos, onAbrirDocumento }) {
  const evaluacion = exp.evaluacion
  const filas = filasDetalle(evaluacion)
  const alertas = evaluacion?.alertas || []
  const faltantes = evaluacion?.faltantes || []
  const tiposCarga = tiposParaCarga(exp.tipo_expediente, faltantes)
  const todos = documentos.filter((d) => d.expediente_id === exp.id)
  // Solo los documentos vigentes se navegan y auditan desde aquí: los sustituidos
  // por una versión más reciente siguen consultables en la Bóveda.
  const vigentes = new Set((evaluacion?.documentos || []).map((d) => d.documento_id))
  const delExpediente = todos.filter((d) => vigentes.has(d.id))

  return (
    <div className="exp-detail">
      <div className="exp-detail-main">
        <MotivosSemaforo estado={exp.estado_cumplimiento} motivos={evaluacion?.motivos} />

        <Card className="table-card table-card--flat">
          <table className="data-table data-table--inner">
            <colgroup>
              <col style={{ width: '32%' }} />
              <col style={{ width: '15%' }} />
              <col style={{ width: '10%' }} />
              <col />
              <col style={{ width: '132px' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Documento requerido</th>
                <th>Regla</th>
                <th>Severidad</th>
                <th>Archivo vigente</th>
                <th className="col-right">Estado</th>
              </tr>
            </thead>
            <tbody>
              {filas.length === 0 && (
                <tr className="empty-row">
                  <td colSpan={5} className="cell-muted">
                    El catálogo de reglas no declara documentos obligatorios.
                  </td>
                </tr>
              )}
              {filas.map((f) => {
                const meta = ESTADO_DOCUMENTO[f.estado] || ESTADO_DOCUMENTO.SIN_DICTAMEN
                const sev = f.severidad ? getSeveridadMeta(f.severidad) : null
                const nombreTipo = TIPO_DOCUMENTO_LABEL[f.tipo] || f.tipo
                const documento = f.doc && delExpediente.find((d) => d.id === f.doc.documento_id)
                return (
                  <tr key={f.tipo}>
                    <td>
                      <span className="cell-stack">
                        <span className="identity-name cell-ellipsis" title={nombreTipo}>
                          {nombreTipo}
                        </span>
                        {f.anexoDe && (
                          <span className="cell-sub">Anexo de {TIPO_DOCUMENTO_LABEL[f.anexoDe] || f.anexoDe}</span>
                        )}
                      </span>
                    </td>
                    <td className="mono cell-mono cell-code" title={f.regla || undefined}>
                      {f.regla || <span className="cell-muted">Opcional</span>}
                    </td>
                    <td>{sev ? <span className="cell-muted">{sev.label}</span> : <span className="cell-muted">—</span>}</td>
                    <td>
                      {f.doc ? (
                        <span className="cell-stack">
                          {documento ? (
                            <button
                              type="button"
                              className="enlace-archivo"
                              title={`Abrir ${f.doc.nombre_archivo_original}: auditoría y visor`}
                              onClick={() => onAbrirDocumento(documento, delExpediente)}
                            >
                              <span className="cell-ellipsis">{f.doc.nombre_archivo_original}</span>
                              <Maximize2 size={11} aria-hidden="true" />
                            </button>
                          ) : (
                            <span className="cell-ellipsis" title={f.doc.nombre_archivo_original}>
                              {f.doc.nombre_archivo_original}
                            </span>
                          )}
                          <Vigencia doc={f.doc} />
                          {f.doc.revisado_por_humano && <span className="cell-sub">Ratificado por un analista</span>}
                          {f.doc.estado_integridad === 'ALTERADO' && <span className="cell-sub cell-bad">Alterado (RIE-03)</span>}
                        </span>
                      ) : (
                        <span className="cell-muted">No cargado</span>
                      )}
                    </td>
                    <td className="col-right">
                      <Badge tono={meta.tono} punto>
                        {f.doc?.vigencia === 'VENCIDO' ? 'Vencido' : meta.label}
                      </Badge>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>

        {alertas.length > 0 && (
          <section className="exp-alertas" aria-label="Alertas del expediente">
            <p className="eyebrow">
              Alertas y recomendaciones <span className="tabular cell-muted">· {alertas.length}</span>
            </p>
            <ListaAlertasAgrupadas alertas={alertas} />
          </section>
        )}

        {evaluacion?.advertencia && <p className="notice notice--warn">{evaluacion.advertencia}</p>}
        {evaluacion?.sustituidos > 0 && (
          <p className="field-hint">
            {evaluacion.sustituidos} {evaluacion.sustituidos === 1 ? 'archivo sustituido' : 'archivos sustituidos'} por uno
            más reciente del mismo tipo; su historial se conserva en la bitácora.
          </p>
        )}

        <HistorialExpediente expedienteId={exp.id} documentos={todos} />
      </div>

      <aside className="exp-detail-side">
        <AuditarPendientes exp={exp} iaOnline={iaOnline} onTerminado={onRefresh} />
        <p className="eyebrow">Custodiar documento</p>
        <p className="field-hint">
          {faltantes.length === 0
            ? 'Obligatorios completos. Cargar otro archivo del mismo tipo sustituye al vigente.'
            : faltantes.length === 1
              ? 'Falta 1 documento obligatorio.'
              : `Faltan ${faltantes.length} documentos obligatorios.`}
        </p>
        <DropZone compacto subiendo={subiendo} tipos={tiposCarga} onArchivo={(archivo, tipo) => onSubir(exp.id, archivo, tipo)} />

        <div className="exp-export">
          <p className="eyebrow">Dictamen de cumplimiento</p>
          <p className="field-hint">Reporte formal con documentos, evidencia de cada dictamen, alertas y bitácora.</p>
          <ExportarReporte ruta={`/reportes/expedientes/${exp.id}`} compacto />
        </div>
      </aside>
    </div>
  )
}

/**
 * Expedientes como tarjetas: cabecera con titular, tipo, folio, semáforo
 * grande y completitud; al desplegarse, la tabla de documentos que exige el
 * rules-service para su tipo, con el estado y la vigencia de cada uno, las
 * alertas con su recomendación y la exportación del dictamen.
 *
 * `foco` es el expediente que debe abrirse al llegar desde Empresas o
 * Alertas; `apertura`, el titular para el que se pidió abrir un expediente.
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
  onFocoAtendido,
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
  // El expediente enfocado desde otra vista se abre hasta que el operador interactúa.
  const abiertoId = foco ?? expandido

  useEffect(() => {
    if (foco && !loading) tarjetas.current.get(foco)?.scrollIntoView({ block: 'center', behavior: 'smooth' })
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
    setExpandido(abiertoId === id ? null : id)
    onFocoAtendido?.()
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
        setExpandido(creado.id)
        onFocoAtendido?.()
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
      await uploadDocumento(formData)
      toast.exito('Documento custodiado', `${archivo.name} → bóveda criptográfica`)
      onRefresh()
    } catch (err) {
      toast.error('Carga rechazada', err.message)
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
        <label className="date-inline">
          <span>Apertura desde</span>
          <input type="date" value={desde} max={hasta || undefined} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label className="date-inline">
          <span>hasta</span>
          <input type="date" value={hasta} min={desde || undefined} onChange={(e) => setHasta(e.target.value)} />
        </label>
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
            const progreso = Math.max(0, Math.min(100, Number(exp.porcentaje_completitud || 0)))
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
                  <span className="progress" title={`${presentes} de ${obligatorios.length} documentos obligatorios`}>
                    <span className="progress-track">
                      <span className={`progress-fill progress-fill--${tonoPorPorcentaje(progreso)}`} style={{ width: `${progreso}%` }} />
                    </span>
                    <span className="progress-value tabular">
                      {presentes}/{obligatorios.length}
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

            <Field as="div" etiqueta="Tipo de expediente" ayuda="El tipo decide qué documentos exige el catálogo de reglas (RF-06).">
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

            <p className="field-hint">El folio del expediente lo genera el core-service (:8001) al momento del alta.</p>

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
