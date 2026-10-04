import { useCallback, useMemo, useState } from 'react'
import { FileLock2, ScanSearch, SearchX, Upload } from 'lucide-react'
import { EncabezadoOrdenable } from './OrdenTabla.jsx'
import useOrden, { RANGO_ESTADO } from '../hooks/useOrden.js'
import { Badge, Button, Card, CopyChip, EmptyRow, Field, IconButton, Modal, SearchBox, Segmented, Select, Tag } from './ui/index.js'
import DropZone from './DropZone.jsx'
import DetalleDocumentoModal from './DetalleDocumentoModal.jsx'
import { firmaDeMime, tipoCorto } from '../utils/documentos.js'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import useDesplazamiento from '../hooks/useDesplazamiento.js'
import { custodiarArchivo } from '../services/api.js'
import { avisarCarga } from '../utils/nivel1.js'
import { ESTADO_DOCUMENTO, TIPO_DOCUMENTO_LABEL, TIPO_EXPEDIENTE_LABEL, TIPOS_DOCUMENTO, tiposParaCarga } from '../constants.js'
import { formatBytes, formatFecha, formatFechaCorta, hashCorto } from '../utils/format.js'
import FolioExpediente from './FolioExpediente.jsx'

const COLUMNAS = 7

/**
 * Estado del documento en la Bóveda: el de su dictamen si es la versión
 * vigente de su tipo en el expediente, o «Sustituido» si hay una posterior
 * (se conserva con sus dictámenes, RF-04). Sin evaluación del expediente, «—».
 */
function EstadoEnBoveda({ estado, evaluado }) {
  if (estado) {
    const meta = ESTADO_DOCUMENTO[estado] || ESTADO_DOCUMENTO.SIN_DICTAMEN
    return (
      <Badge tono={meta.tono} punto>
        {meta.label}
      </Badge>
    )
  }
  if (!evaluado) return <span className="cell-muted">—</span>
  return (
    <Tag title="Una versión más reciente del mismo tipo es la vigente; esta se conserva con sus dictámenes">
      Sustituido
    </Tag>
  )
}

/**
 * Consola de custodia (Nivel 1): documentos con su huella SHA-256, filtro
 * por tipo documental, ingesta en un modal y, en el detalle de cada
 * documento, el panel de inteligencia documental (Niveles 2 a 4).
 */
export default function BovedaTab({ documentos, expedientes, loading, onRefresh, isOnline = true, iaOnline = true }) {
  const toast = useToast()
  const [expedienteId, setExpedienteId] = useState('')
  const [subiendo, setSubiendo] = useState(false)
  const [ingestaAbierta, setIngestaAbierta] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  // Por defecto solo los documentos vigentes: los sustituidos (RF-04) se
  // conservan, pero en la vista diaria opacaban a los activos.
  const [alcance, setAlcance] = useState('VIGENTES')
  const [detalle, setDetalle] = useState(null)

  const consulta = useDebounce(busqueda, 220)

  const mapaExpedientes = useMemo(() => Object.fromEntries(expedientes.map((e) => [e.id, e])), [expedientes])

  // Estado de cada documento vigente según la evaluación de su expediente; un
  // documento que no figura ahí fue sustituido por una versión posterior de su tipo.
  const estadoVigente = useMemo(
    () =>
      new Map(expedientes.flatMap((e) => (e.evaluacion?.documentos || []).map((d) => [d.documento_id, d.estado]))),
    [expedientes]
  )

  // Sin evaluación del expediente no se sabe si fue sustituido: se muestra como vigente.
  const esVigente = useCallback(
    (d) => estadoVigente.has(d.id) || !mapaExpedientes[d.expediente_id]?.evaluacion,
    [estadoVigente, mapaExpedientes]
  )
  const vigentes = useMemo(() => documentos.filter(esVigente), [documentos, esVigente])
  const enAlcance = alcance === 'VIGENTES' ? vigentes : documentos

  const opcionesAlcance = [
    { id: 'VIGENTES', label: 'Vigentes', conteo: vigentes.length, tooltip: 'La versión vigente de cada tipo en su expediente' },
    { id: 'HISTORICO', label: 'Histórico completo', conteo: documentos.length, tooltip: 'Incluye las versiones sustituidas, con sus dictámenes' },
  ]

  /** Solo se ofrecen como filtro los tipos que realmente hay en el alcance elegido. */
  const opcionesTipo = useMemo(() => {
    const conteo = new Map()
    for (const d of enAlcance) conteo.set(d.tipo_documento, (conteo.get(d.tipo_documento) || 0) + 1)
    const orden = [...TIPOS_DOCUMENTO.map((t) => t.value), 'OTRO']
    const tipos = [...conteo.keys()].sort((a, b) => orden.indexOf(a) - orden.indexOf(b))
    return [
      { id: 'TODOS', label: 'Todos', conteo: enAlcance.length },
      ...tipos.map((t) => ({ id: t, label: tipoCorto(t), conteo: conteo.get(t), tooltip: TIPO_DOCUMENTO_LABEL[t] })),
    ]
  }, [enAlcance])

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return enAlcance.filter((d) => {
      const tipoOk = filtroTipo === 'TODOS' || d.tipo_documento === filtroTipo
      const busquedaOk =
        !q ||
        d.nombre_archivo_original?.toLowerCase().includes(q) ||
        d.hash_sha256?.toLowerCase().includes(q) ||
        mapaExpedientes[d.expediente_id]?.codigo_expediente?.toLowerCase().includes(q) ||
        mapaExpedientes[d.expediente_id]?.titular?.razon_social?.toLowerCase().includes(q)
      return tipoOk && busquedaOk
    })
  }, [enAlcance, consulta, filtroTipo, mapaExpedientes])

  // Orden por columna: sin elegir, el de la lista; el estado ordena de lo más grave a lo conforme.
  const clavesOrden = useMemo(
    () => ({
      documento: (d) => d.nombre_archivo_original,
      tipo: (d) => tipoCorto(d.tipo_documento),
      expediente: (d) => mapaExpedientes[d.expediente_id]?.codigo_expediente,
      estado: (d) => RANGO_ESTADO[estadoVigente.get(d.id)],
      ingesta: (d) => d.creado_en,
    }),
    [mapaExpedientes, estadoVigente]
  )
  const { ordenada, orden, ordenar } = useOrden(filtrados, clavesOrden)
  const filas = useDesplazamiento()

  // En un lote (RF-02) la zona de carga avisa y lleva el progreso; aquí solo se envía.
  const subir = async (archivo, tipo, { enLote = false } = {}) => {
    if (enLote) return custodiarArchivo(expedienteId, archivo, tipo)
    setSubiendo(true)
    try {
      const documento = await custodiarArchivo(expedienteId, archivo, tipo)
      avisarCarga(toast, documento, `${archivo.name} · huella registrada en la bóveda`)
      setIngestaAbierta(false)
      onRefresh()
    } catch (err) {
      toast.error('Carga rechazada', err.message)
      throw err
    } finally {
      setSubiendo(false)
    }
  }

  const expDetalle = detalle ? mapaExpedientes[detalle.expediente_id] : null

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Archivo, folio, titular o hash…"
          label="Buscar en la bóveda"
        />
        <Segmented label="Versiones a mostrar" valor={alcance} onChange={setAlcance} opciones={opcionesAlcance} />
        <Button
          variante="primary"
          icono={Upload}
          className="toolbar-action"
          onClick={() => setIngestaAbierta(true)}
          disabled={!isOnline || expedientes.length === 0}
          title={!isOnline ? 'El sistema de expedientes no responde' : undefined}
        >
          Custodiar documento
        </Button>
      </div>

      <div className="toolbar toolbar--sub">
        <Segmented label="Filtrar por tipo documental" valor={filtroTipo} onChange={setFiltroTipo} opciones={opcionesTipo} />
      </div>

      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table data-table--boveda">
            {/* El folio completo (EXP-XXXX-AAAAMMDDhhmm) cabe a 1366 px: su final es lo que distingue
                un expediente de otro. El hash ya va abreviado y la fecha es corta. */}
            <colgroup>
              <col style={{ width: '27%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: '19%' }} />
              <col style={{ width: '13%' }} />
              <col style={{ width: '17%' }} />
              <col style={{ width: '9%' }} />
              <col style={{ width: 52 }} />
            </colgroup>
            <thead>
              <tr>
                <EncabezadoOrdenable columna="documento" orden={orden} onOrdenar={ordenar}>
                  Documento
                </EncabezadoOrdenable>
                <EncabezadoOrdenable columna="tipo" orden={orden} onOrdenar={ordenar}>
                  Tipo
                </EncabezadoOrdenable>
                <EncabezadoOrdenable columna="expediente" orden={orden} onOrdenar={ordenar}>
                  Expediente
                </EncabezadoOrdenable>
                <EncabezadoOrdenable columna="estado" orden={orden} onOrdenar={ordenar}>
                  Estado
                </EncabezadoOrdenable>
                <th>SHA-256</th>
                <EncabezadoOrdenable columna="ingesta" orden={orden} onOrdenar={ordenar} inicial="desc" className="col-right">
                  Ingesta
                </EncabezadoOrdenable>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody ref={filas}>
              {loading && <SkeletonRows rows={6} cols={COLUMNAS} />}

              {!loading && filtrados.length === 0 && (
                <EmptyRow
                  columnas={COLUMNAS}
                  icon={documentos.length === 0 ? FileLock2 : SearchX}
                  titulo={documentos.length === 0 ? 'La bóveda está vacía' : 'Sin coincidencias'}
                  descripcion={
                    documentos.length === 0
                      ? 'Custodia el primer documento para generar su huella criptográfica inmutable.'
                      : alcance === 'VIGENTES' && vigentes.length === 0
                        ? 'No hay documentos vigentes; el histórico completo conserva las versiones sustituidas.'
                        : 'Ningún documento coincide con la búsqueda o el tipo elegido.'
                  }
                >
                  {documentos.length > 0 && (busqueda || filtroTipo !== 'TODOS') && (
                    <Button
                      compacto
                      onClick={() => {
                        setBusqueda('')
                        setFiltroTipo('TODOS')
                      }}
                    >
                      Limpiar búsqueda
                    </Button>
                  )}
                </EmptyRow>
              )}

              {!loading &&
                ordenada.map((doc, i) => {
                  const exp = mapaExpedientes[doc.expediente_id]
                  const firma = firmaDeMime(doc.mime_type)
                  return (
                    <tr
                      key={doc.id}
                      data-flip={doc.id}
                      style={{ '--i': i }}
                      className={`row-clickable ${esVigente(doc) ? '' : 'is-sustituido'}`}
                      onClick={() => setDetalle(doc)}
                    >
                      <td>
                        <div className="cell-stack">
                          <span className="identity-name">
                            {doc.nombre_archivo_original}
                            {doc.estado_integridad === 'ALTERADO' && (
                              <Badge tono="bad" className="badge--inline" title="La huella digital ya no coincide con la registrada al custodiarlo">
                                Alterado
                              </Badge>
                            )}
                          </span>
                          <span className="cell-sub">
                            {firma.label} · {formatBytes(doc.tamanio_bytes)} · {exp?.titular?.razon_social || 'Sin titular'}
                          </span>
                        </div>
                      </td>
                      <td>
                        <Tag tipo title={TIPO_DOCUMENTO_LABEL[doc.tipo_documento]}>
                          {tipoCorto(doc.tipo_documento)}
                        </Tag>
                      </td>
                      <td className="mono cell-mono">{exp ? <FolioExpediente expediente={exp} /> : <span className="cell-muted">—</span>}</td>
                      <td>
                        <EstadoEnBoveda estado={estadoVigente.get(doc.id)} evaluado={Boolean(exp?.evaluacion)} />
                      </td>
                      <td>
                        <CopyChip valor={doc.hash_sha256} visible={hashCorto(doc.hash_sha256, 8, 6)} etiqueta="hash SHA-256" />
                      </td>
                      <td className="col-right mono cell-num" title={formatFecha(doc.creado_en)}>
                        {formatFechaCorta(doc.creado_en)}
                      </td>
                      <td className="col-action">
                        <IconButton
                          etiqueta={`Inspeccionar ${doc.nombre_archivo_original}: custodia y auditoría`}
                          compacto
                          onClick={(e) => {
                            e.stopPropagation()
                            setDetalle(doc)
                          }}
                          title="Abrir auditoría y visor"
                        >
                          <ScanSearch size={14} />
                        </IconButton>
                      </td>
                    </tr>
                  )
                })}
            </tbody>
          </table>
        </div>
      </Card>

      {ingestaAbierta && (
        <Modal
          title="Custodiar documento"
          subtitle="Se verifica el formato y el tamaño, y se calcula la huella digital del archivo"
          onClose={() => setIngestaAbierta(false)}
        >
          <DropZone
            tipos={
              mapaExpedientes[expedienteId]
                ? tiposParaCarga(
                    mapaExpedientes[expedienteId].tipo_expediente,
                    mapaExpedientes[expedienteId].evaluacion?.faltantes
                  )
                : TIPOS_DOCUMENTO
            }
            onArchivo={subir}
            onLoteTerminado={({ custodiados, rechazados }) => {
              if (custodiados) onRefresh()
              if (!rechazados) setIngestaAbierta(false)
            }}
            subiendo={subiendo}
            listoExtra={Boolean(expedienteId)}
            deshabilitado={!isOnline}
            motivoDeshabilitado="El sistema de expedientes no responde"
          >
            <Field etiqueta="Expediente destino">
              <Select value={expedienteId} onChange={(e) => setExpedienteId(e.target.value)} required>
                <option value="" disabled>
                  Selecciona un expediente…
                </option>
                {expedientes.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.codigo_expediente} — {e.titular?.razon_social || 'Sin titular'} ({TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente})
                  </option>
                ))}
              </Select>
            </Field>
          </DropZone>
          {!expedienteId && <p className="field-hint">Elige el expediente destino para habilitar la custodia.</p>}
        </Modal>
      )}

      {detalle && (
        <DetalleDocumentoModal
          documento={detalle}
          lista={filtrados}
          expediente={expDetalle}
          iaOnline={iaOnline}
          onRefresh={onRefresh}
          onCambiar={setDetalle}
          onCerrar={() => setDetalle(null)}
        />
      )}
    </div>
  )
}
