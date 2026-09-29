import { useMemo, useState } from 'react'
import { FileLock2, ScanSearch, SearchX, Upload } from 'lucide-react'
import { Badge, Button, Card, CopyChip, EmptyRow, Field, IconButton, Modal, SearchBox, Segmented, Select, Tag } from './ui/index.js'
import DropZone from './DropZone.jsx'
import DetalleDocumentoModal from './DetalleDocumentoModal.jsx'
import { firmaDeMime, tipoCorto } from '../utils/documentos.js'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { uploadDocumento } from '../services/api.js'
import { avisarCarga } from '../utils/nivel1.js'
import { TIPO_DOCUMENTO_LABEL, TIPO_EXPEDIENTE_LABEL, TIPOS_DOCUMENTO, tiposParaCarga } from '../constants.js'
import { formatBytes, formatFecha, formatFechaCorta, hashCorto } from '../utils/format.js'

const COLUMNAS = 7

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
  const [detalle, setDetalle] = useState(null)

  const consulta = useDebounce(busqueda, 220)

  const mapaExpedientes = useMemo(() => Object.fromEntries(expedientes.map((e) => [e.id, e])), [expedientes])

  /** Solo se ofrecen como filtro los tipos que realmente hay en la bóveda. */
  const opcionesTipo = useMemo(() => {
    const conteo = new Map()
    for (const d of documentos) conteo.set(d.tipo_documento, (conteo.get(d.tipo_documento) || 0) + 1)
    const orden = [...TIPOS_DOCUMENTO.map((t) => t.value), 'OTRO']
    const tipos = [...conteo.keys()].sort((a, b) => orden.indexOf(a) - orden.indexOf(b))
    return [
      { id: 'TODOS', label: 'Todos', conteo: documentos.length },
      ...tipos.map((t) => ({ id: t, label: tipoCorto(t), conteo: conteo.get(t), tooltip: TIPO_DOCUMENTO_LABEL[t] })),
    ]
  }, [documentos])

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    return documentos.filter((d) => {
      const tipoOk = filtroTipo === 'TODOS' || d.tipo_documento === filtroTipo
      const busquedaOk =
        !q ||
        d.nombre_archivo_original?.toLowerCase().includes(q) ||
        d.hash_sha256?.toLowerCase().includes(q) ||
        mapaExpedientes[d.expediente_id]?.codigo_expediente?.toLowerCase().includes(q) ||
        mapaExpedientes[d.expediente_id]?.titular?.razon_social?.toLowerCase().includes(q)
      return tipoOk && busquedaOk
    })
  }, [documentos, consulta, filtroTipo, mapaExpedientes])

  const subir = async (archivo, tipo) => {
    setSubiendo(true)
    try {
      const formData = new FormData()
      formData.append('expediente_id', expedienteId)
      formData.append('tipo_documento', tipo)
      formData.append('file', archivo)
      const documento = await uploadDocumento(formData)
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
        <Segmented label="Filtrar por tipo documental" valor={filtroTipo} onChange={setFiltroTipo} opciones={opcionesTipo} />
        <Button
          variante="primary"
          icono={Upload}
          className="toolbar-action"
          onClick={() => setIngestaAbierta(true)}
          disabled={!isOnline || expedientes.length === 0}
          title={!isOnline ? 'El core-service (:8001) no responde' : undefined}
        >
          Custodiar documento
        </Button>
      </div>

      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table">
            <colgroup>
              <col style={{ width: '30%' }} />
              <col style={{ width: '11%' }} />
              <col style={{ width: '17%' }} />
              <col style={{ width: '19%' }} />
              <col style={{ width: '9%' }} />
              <col style={{ width: '10%' }} />
              <col style={{ width: 52 }} />
            </colgroup>
            <thead>
              <tr>
                <th>Documento</th>
                <th>Tipo</th>
                <th>Expediente</th>
                <th>SHA-256</th>
                <th className="col-right">Tamaño</th>
                <th className="col-right">Ingesta</th>
                <th aria-label="Acciones" />
              </tr>
            </thead>
            <tbody>
              {loading && <SkeletonRows rows={6} cols={COLUMNAS} />}

              {!loading && filtrados.length === 0 && (
                <EmptyRow
                  columnas={COLUMNAS}
                  icon={documentos.length === 0 ? FileLock2 : SearchX}
                  titulo={documentos.length === 0 ? 'La bóveda está vacía' : 'Sin coincidencias'}
                  descripcion={
                    documentos.length === 0
                      ? 'Custodia el primer documento para generar su huella criptográfica inmutable.'
                      : 'Ningún documento coincide con la búsqueda o el tipo elegido.'
                  }
                />
              )}

              {!loading &&
                filtrados.map((doc) => {
                  const exp = mapaExpedientes[doc.expediente_id]
                  const firma = firmaDeMime(doc.mime_type)
                  return (
                    <tr key={doc.id} className="row-clickable" onClick={() => setDetalle(doc)}>
                      <td>
                        <div className="cell-stack">
                          <span className="identity-name">
                            {doc.nombre_archivo_original}
                            {doc.estado_integridad === 'ALTERADO' && (
                              <Badge tono="bad" className="badge--inline" title="La huella SHA-256 no coincide con la registrada (RIE-03)">
                                Alterado
                              </Badge>
                            )}
                          </span>
                          <span className="cell-sub">
                            {firma.label} · {exp?.titular?.razon_social || 'Sin titular'}
                          </span>
                        </div>
                      </td>
                      <td>
                        <Tag tipo title={TIPO_DOCUMENTO_LABEL[doc.tipo_documento]}>
                          {tipoCorto(doc.tipo_documento)}
                        </Tag>
                      </td>
                      <td className="mono cell-mono">{exp ? exp.codigo_expediente : <span className="cell-muted">—</span>}</td>
                      <td>
                        <CopyChip valor={doc.hash_sha256} visible={hashCorto(doc.hash_sha256, 8, 6)} etiqueta="hash SHA-256" />
                      </td>
                      <td className="col-right mono cell-num">{formatBytes(doc.tamanio_bytes)}</td>
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
                          title="Inspeccionar"
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
          subtitle="Nivel 1: firma binaria, límite de tamaño y huella SHA-256"
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
            subiendo={subiendo}
            listoExtra={Boolean(expedienteId)}
            deshabilitado={!isOnline}
            motivoDeshabilitado="El core-service (:8001) no responde"
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
