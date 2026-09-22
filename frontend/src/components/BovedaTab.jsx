import { useMemo, useState } from 'react'
import {
  BadgeCheck,
  Check,
  Copy,
  FileText,
  Fingerprint,
  Lock,
  Search,
  Vault,
  X,
} from 'lucide-react'
import Modal from './Modal.jsx'
import DropZone from './DropZone.jsx'
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
      className={`hash-chip ${copiado ? 'hash-chip--copiado' : ''}`}
      onClick={copiar}
      data-tooltip={copiado ? '¡Copiado!' : 'Copiar hash SHA-256'}
    >
      <Fingerprint size={12} strokeWidth={2.3} className="hash-chip-icon" />
      <span className="mono">{completo ? hash : hashCorto(hash, 8, 6)}</span>
      {copiado ? <Check size={12} strokeWidth={3} className="hash-chip-ok" /> : <Copy size={12} strokeWidth={2.2} />}
    </button>
  )
}

export default function BovedaTab({ documentos, expedientes, loading, onRefresh, isOnline = true }) {
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
        <section className="surface-card vault-upload">
          <header className="card-head">
            <span className="card-head-icon card-head-icon--vault">
              <Lock size={15} strokeWidth={2.4} />
            </span>
            <div>
              <h3 className="card-title">Ingesta custodiada</h3>
              <p className="card-desc">Nivel 1 del pipeline: firma binaria, límite de tamaño y huella SHA-256.</p>
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
            <label className="field field--inline">
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

          {!expedienteId && (
            <p className="field-hint field-hint--warn">
              Elige el expediente destino para habilitar la custodia.
            </p>
          )}
        </section>

        <section className="surface-card vault-console">
          <header className="card-head">
            <span className="card-head-icon card-head-icon--vault">
              <Vault size={15} strokeWidth={2.4} />
            </span>
            <div>
              <h3 className="card-title">Consola de custodia</h3>
              <p className="card-desc">
                {documentos.length} {documentos.length === 1 ? 'documento' : 'documentos'} · {formatBytes(totalBytes)} bajo
                resguardo NOM-151-SCFI-2016
              </p>
            </div>
            <label className="search-box search-box--sm">
              <Search size={14} strokeWidth={2.3} />
              <input
                type="search"
                placeholder="Archivo, folio o hash…"
                value={busqueda}
                onChange={(e) => setBusqueda(e.target.value)}
                aria-label="Buscar en la bóveda"
              />
              {busqueda && (
                <button type="button" className="search-clear" onClick={() => setBusqueda('')} aria-label="Limpiar">
                  <X size={12} strokeWidth={2.6} />
                </button>
              )}
            </label>
          </header>

          <div className="table-scroll">
            <table className="data-table data-table--console">
              <thead>
                <tr>
                  <th>Documento</th>
                  <th>Tipo</th>
                  <th>Expediente</th>
                  <th>Huella SHA-256</th>
                  <th className="col-center">Integridad</th>
                  <th className="col-right">Tamaño</th>
                </tr>
              </thead>
              <tbody>
                {loading && <SkeletonRows rows={6} cols={6} />}

                {!loading && filtrados.length === 0 && (
                  <tr>
                    <td colSpan={6}>
                      <div className="empty-state">
                        <span className="empty-icon empty-icon--vault">
                          <Vault size={20} strokeWidth={2} />
                        </span>
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
                          <div className="identity">
                            <span className="file-icon">
                              <FileText size={14} strokeWidth={2.2} />
                            </span>
                            <span className="identity-body">
                              <span className="identity-name">{doc.nombre_archivo_original}</span>
                              <span className="identity-sub">{formatFecha(doc.creado_en)}</span>
                            </span>
                          </div>
                        </td>
                        <td>
                          <span className="tag" title={TIPO_DOCUMENTO_LABEL[doc.tipo_documento]}>
                            {TIPO_DOCUMENTO_CORTO[doc.tipo_documento] || doc.tipo_documento}
                          </span>
                        </td>
                        <td>
                          {exp ? (
                            <span className="mono folder-folio">{exp.codigo_expediente}</span>
                          ) : (
                            <span className="cell-muted">—</span>
                          )}
                        </td>
                        <td>
                          <HashCell hash={doc.hash_sha256} />
                        </td>
                        <td className="col-center">
                          <span className="badge badge--vault" data-tooltip={`Magic Bytes ${firma.firma}`}>
                            <BadgeCheck size={11} strokeWidth={2.6} />
                            {firma.label}
                          </span>
                        </td>
                        <td className="col-right cell-muted mono-tabular">{formatBytes(doc.tamanio_bytes)}</td>
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
          icon={FileText}
          onClose={() => setDetalle(null)}
          width={620}
        >
          <dl className="detail-grid">
            <div className="detail-row">
              <dt>Tipo documental</dt>
              <dd>{TIPO_DOCUMENTO_LABEL[detalle.tipo_documento] || detalle.tipo_documento}</dd>
            </div>
            <div className="detail-row">
              <dt>Expediente</dt>
              <dd className="mono">{mapaExpedientes[detalle.expediente_id]?.codigo_expediente || '—'}</dd>
            </div>
            <div className="detail-row">
              <dt>Titular</dt>
              <dd>{mapaExpedientes[detalle.expediente_id]?.titular?.razon_social || '—'}</dd>
            </div>
            <div className="detail-row">
              <dt>Firma binaria</dt>
              <dd>
                <span className="badge badge--vault">
                  <BadgeCheck size={11} strokeWidth={2.6} />
                  {firmaDeMime(detalle.mime_type).label} · {firmaDeMime(detalle.mime_type).firma}
                </span>
              </dd>
            </div>
            <div className="detail-row">
              <dt>Tamaño</dt>
              <dd className="mono-tabular">{formatBytes(detalle.tamanio_bytes)}</dd>
            </div>
            <div className="detail-row">
              <dt>Ingesta</dt>
              <dd>{formatFecha(detalle.creado_en)}</dd>
            </div>
            <div className="detail-row detail-row--full">
              <dt>Huella SHA-256</dt>
              <dd>
                <HashCell hash={detalle.hash_sha256} completo />
              </dd>
            </div>
          </dl>

          <p className="detail-note">
            <Lock size={13} strokeWidth={2.4} />
            La huella se calculó al ingresar el archivo y es inmutable. Cualquier modificación posterior del binario
            produciría un hash distinto y sería detectada por la regla RIE-03.
          </p>
        </Modal>
      )}
    </div>
  )
}
