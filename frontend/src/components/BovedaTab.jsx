import { useMemo, useState } from 'react'
import { Check, Copy, Search, X } from 'lucide-react'
import Modal from './Modal.jsx'
import DropZone from './DropZone.jsx'
import DocumentoIaPanel from './DocumentoIaPanel.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import useDebounce from '../hooks/useDebounce.js'
import { uploadDocumento } from '../services/api.js'
import { TIPO_DOCUMENTO_CORTO, TIPO_DOCUMENTO_LABEL, TIPOS_DOCUMENTO } from '../constants.js'
import { copiarAlPortapapeles, formatBytes, formatFecha, hashCorto } from '../utils/format.js'

/** Etiqueta de la firma binaria a partir del MIME devuelto por el backend. */
function firmaDeMime(mime) {
  if (mime === 'application/pdf') return { label: 'PDF', firma: '%PDF-' }
  if (mime === 'image/png') return { label: 'PNG', firma: '89 50 4E 47' }
  if (mime === 'image/jpeg') return { label: 'JPEG', firma: 'FF D8 FF' }
  return { label: mime || 'Desconocido', firma: '—' }
}

/** Hash en tipografía monoespaciada con copiado de un clic. */
function HashCell({ hash, completo = false }) {
  const [copiado, setCopiado] = useState(false)
  const toast = useToast()

  const copiar = async (e) => {
    e.stopPropagation()
    const ok = await copiarAlPortapapeles(hash)
    if (ok) {
      setCopiado(true)
      toast.exito('Hash SHA-256 copiado', hashCorto(hash, 16, 10))
      setTimeout(() => setCopiado(false), 1500)
    } else {
      toast.error('No se pudo copiar', 'El navegador bloqueó el portapapeles.')
    }
  }

  return (
    <button
      type="button"
      className={`copy-chip ${completo ? 'copy-chip--full' : ''}`}
      onClick={copiar}
      data-tooltip={copiado ? 'Copiado' : 'Copiar hash SHA-256'}
    >
      <span className="mono">{completo ? hash : hashCorto(hash, 8, 6)}</span>
      {copiado ? <Check size={12} strokeWidth={2.4} className="copy-ok" /> : <Copy size={12} strokeWidth={2} />}
    </button>
  )
}

export default function BovedaTab({ documentos, expedientes, loading, onRefresh, isOnline = true, iaOnline = true }) {
  const toast = useToast()
  const [expedienteId, setExpedienteId] = useState('')
  const [subiendo, setSubiendo] = useState(false)
  const [busqueda, setBusqueda] = useState('')
  const [detalle, setDetalle] = useState(null)

  const consulta = useDebounce(busqueda, 220)

  const mapaExpedientes = useMemo(
    () => Object.fromEntries(expedientes.map((e) => [e.id, e])),
    [expedientes]
  )

  const filtrados = useMemo(() => {
    const q = consulta.trim().toLowerCase()
    if (!q) return documentos
    return documentos.filter(
      (d) =>
        d.nombre_archivo_original?.toLowerCase().includes(q) ||
        d.hash_sha256?.toLowerCase().includes(q) ||
        d.tipo_documento?.toLowerCase().includes(q) ||
        mapaExpedientes[d.expediente_id]?.codigo_expediente?.toLowerCase().includes(q)
    )
  }, [documentos, consulta, mapaExpedientes])

  const totalBytes = useMemo(
    () => documentos.reduce((acc, d) => acc + Number(d.tamanio_bytes || 0), 0),
    [documentos]
  )

  const subir = async (archivo, tipo) => {
    setSubiendo(true)
    try {
      const formData = new FormData()
      formData.append('expediente_id', expedienteId)
      formData.append('tipo_documento', tipo)
      formData.append('file', archivo)
      await uploadDocumento(formData)
      toast.exito('Documento custodiado', `${archivo.name} · huella registrada en la bóveda`)
      onRefresh()
    } catch (err) {
      toast.error('Carga rechazada', err.message)
      throw err
    } finally {
      setSubiendo(false)
    }
  }

  return (
    <div className="tab-panel">
      <div className="vault-layout">
        <section className="card vault-upload">
          <header className="section-head">
            <div>
              <h2 className="section-title">Ingesta custodiada</h2>
              <p className="section-desc">Nivel 1: firma binaria, límite de tamaño y huella SHA-256.</p>
            </div>
          </header>

          <DropZone
            tipos={TIPOS_DOCUMENTO}
            onArchivo={subir}
            subiendo={subiendo}
            listoExtra={Boolean(expedienteId)}
            deshabilitado={!isOnline}
            motivoDeshabilitado="El core-service (:8001) no responde"
          >
            <label className="field">
              <span className="field-label">Expediente destino</span>
              <select value={expedienteId} onChange={(e) => setExpedienteId(e.target.value)} required>
                <option value="" disabled>
                  Selecciona un expediente…
                </option>
                {expedientes.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.codigo_expediente} — {e.titular?.razon_social || 'Sin titular'}
                  </option>
                ))}
              </select>
            </label>
          </DropZone>

          {!expedienteId && <p className="field-hint">Elige el expediente destino para habilitar la custodia.</p>}
        </section>

        <section className="card table-card vault-console">
          <header className="section-head section-head--padded">
            <div>
              <h2 className="section-title">Consola de custodia</h2>
              <p className="section-desc">
                {documentos.length} {documentos.length === 1 ? 'documento' : 'documentos'} · {formatBytes(totalBytes)} ·
                NOM-151-SCFI-2016
              </p>
            </div>
            <label className="search-box search-box--sm">
              <Search size={14} strokeWidth={2} />
              <input
                type="search"
                placeholder="Archivo, folio o hash…"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                aria-label="Buscar en la bóveda"
              />
              {busqueda && (
                <button type="button" className="search-clear" onClick={() => setBusqueda('')} aria-label="Limpiar">
                  <X size={12} strokeWidth={2} />
                </button>
              )}
            </label>
          </header>

          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Tipo</th>
                  <th>Expediente</th>
                  <th>SHA-256</th>
                  <th>Firma</th>
                  <th className="col-right">Tamaño</th>
                </tr>
              </thead>
              <tbody>
                {loading && <SkeletonRows rows={6} cols={6} />}

                {!loading && filtrados.length === 0 && (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty-state">
                        <p className="empty-title">
                          {documentos.length === 0 ? 'La bóveda está vacía' : 'Sin coincidencias'}
                        </p>
                        <p className="empty-desc">
                          {documentos.length === 0
                            ? 'Carga el primer documento para generar su huella criptográfica inmutable.'
                            : 'Ningún documento coincide con la búsqueda.'}
                        </p>
                      </div>
                    </td>
                  </tr>
                )}

                {!loading &&
                  filtrados.map((doc) => {
                    const exp = mapaExpedientes[doc.expediente_id]
                    const firma = firmaDeMime(doc.mime_type)
                    return (
                      <tr key={doc.id} className="row-clickable" onClick={() => setDetalle(doc)}>
                        <td>
                          <div className="cell-stack">
                            <span className="identity-name">{doc.nombre_archivo_original}</span>
                            <span className="cell-sub">{formatFecha(doc.creado_en)}</span>
                          </div>
                        </td>
                        <td>
                          <span className="tag" title={TIPO_DOCUMENTO_LABEL[doc.tipo_documento]}>
                            {TIPO_DOCUMENTO_CORTO[doc.tipo_documento] || doc.tipo_documento}
                          </span>
                        </td>
                        <td className="mono cell-mono">{exp ? exp.codigo_expediente : <span className="cell-muted">—</span>}</td>
                        <td>
                          <HashCell hash={doc.hash_sha256} />
                        </td>
                        <td>
                          <span className="badge badge--vault" data-tooltip={`Magic Bytes ${firma.firma}`}>
                            {firma.label}
                          </span>
                        </td>
                        <td className="col-right cell-muted tabular">{formatBytes(doc.tamanio_bytes)}</td>
                      </tr>
                    )
                  })}
              </tbody>
            </table>
          </div>
        </section>
      </div>

      {detalle && (
        <Modal
          title={detalle.nombre_archivo_original}
          subtitle="Metadatos de custodia criptográfica"
          onClose={() => setDetalle(null)}
        >
          <dl className="detail-grid">
            <div className="detail-item">
              <dt>Tipo documental</dt>
              <dd>{TIPO_DOCUMENTO_LABEL[detalle.tipo_documento] || detalle.tipo_documento}</dd>
            </div>
            <div className="detail-item">
              <dt>Expediente</dt>
              <dd className="mono">{mapaExpedientes[detalle.expediente_id]?.codigo_expediente || '—'}</dd>
            </div>
            <div className="detail-item">
              <dt>Titular</dt>
              <dd>{mapaExpedientes[detalle.expediente_id]?.titular?.razon_social || '—'}</dd>
            </div>
            <div className="detail-item">
              <dt>Firma binaria</dt>
              <dd>
                <span className="badge badge--vault">
                  {firmaDeMime(detalle.mime_type).label} · {firmaDeMime(detalle.mime_type).firma}
                </span>
              </dd>
            </div>
            <div className="detail-item">
              <dt>Tamaño</dt>
              <dd className="tabular">{formatBytes(detalle.tamanio_bytes)}</dd>
            </div>
            <div className="detail-item">
              <dt>Ingesta</dt>
              <dd>{formatFecha(detalle.creado_en)}</dd>
            </div>
            <div className="detail-item detail-item--full">
              <dt>Huella SHA-256</dt>
              <dd>
                <HashCell hash={detalle.hash_sha256} completo />
              </dd>
            </div>
          </dl>

          <p className="detail-note">
            La huella se calculó al ingresar el archivo y es inmutable. Cualquier modificación posterior del binario
            produciría un hash distinto y sería detectada por la regla RIE-03.
          </p>

          <DocumentoIaPanel
            key={detalle.id}
            doc={detalle}
            expediente={mapaExpedientes[detalle.expediente_id]}
            iaOnline={iaOnline}
          />
        </Modal>
      )}
    </div>
  )
}
