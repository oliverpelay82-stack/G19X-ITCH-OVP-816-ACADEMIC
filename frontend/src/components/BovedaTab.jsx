import { useCallback, useState } from 'react'
import { UploadCloud, FileCheck2, AlertTriangle, Copy, Check, Loader2, Vault, ShieldCheck } from 'lucide-react'
import { uploadDocumento } from '../services/api.js'
import { MAGIC_BYTES, MAX_FILE_SIZE_BYTES, TIPOS_DOCUMENTO } from '../constants.js'

function bytesToHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

async function calcularSha256(file) {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return bytesToHex(digest)
}

async function detectarMagicBytes(file) {
  const cabecera = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  return MAGIC_BYTES.find((firma) =>
    firma.signature.every((byte, i) => cabecera[i] === byte)
  )
}

function CopyHash({ hash }) {
  const [copiado, setCopiado] = useState(false)
  const copiar = async () => {
    try {
      await navigator.clipboard.writeText(hash)
      setCopiado(true)
      setTimeout(() => setCopiado(false), 1500)
    } catch {
      /* portapapeles no disponible: se ignora silenciosamente */
    }
  }
  return (
    <button type="button" className="copy-hash" onClick={copiar} title="Copiar hash SHA-256">
      <span className="mono-chip">{hash.slice(0, 16)}…{hash.slice(-8)}</span>
      {copiado ? <Check size={14} color="var(--conforme-fg)" /> : <Copy size={14} />}
    </button>
  )
}

export default function BovedaTab({ documentos, expedientes, loading, onRefresh }) {
  const [arrastrando, setArrastrando] = useState(false)
  const [archivo, setArchivo] = useState(null)
  const [analizando, setAnalizando] = useState(false)
  const [analisis, setAnalisis] = useState(null) // { hash, magic, sizeOk }
  const [expedienteId, setExpedienteId] = useState('')
  const [tipoDocumento, setTipoDocumento] = useState(TIPOS_DOCUMENTO[0].value)
  const [subiendo, setSubiendo] = useState(false)
  const [error, setError] = useState('')

  const analizarArchivo = useCallback(async (file) => {
    setArchivo(file)
    setAnalisis(null)
    setError('')
    setAnalizando(true)
    try {
      const [hash, magic] = await Promise.all([calcularSha256(file), detectarMagicBytes(file)])
      setAnalisis({
        hash,
        magic,
        sizeOk: file.size > 0 && file.size <= MAX_FILE_SIZE_BYTES,
      })
    } finally {
      setAnalizando(false)
    }
  }, [])

  const handleDrop = (e) => {
    e.preventDefault()
    setArrastrando(false)
    const file = e.dataTransfer.files?.[0]
    if (file) analizarArchivo(file)
  }

  const handleInputChange = (e) => {
    const file = e.target.files?.[0]
    if (file) analizarArchivo(file)
  }

  const limpiar = () => {
    setArchivo(null)
    setAnalisis(null)
    setError('')
  }

  const handleUpload = async () => {
    if (!archivo || !expedienteId) return
    setSubiendo(true)
    setError('')
    try {
      const formData = new FormData()
      formData.append('expediente_id', expedienteId)
      formData.append('tipo_documento', tipoDocumento)
      formData.append('file', archivo)
      await uploadDocumento(formData)
      limpiar()
      onRefresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setSubiendo(false)
    }
  }

  const mapaExpedientes = Object.fromEntries(expedientes.map((e) => [e.id, e.codigo_expediente]))
  const listo = analisis && analisis.magic && analisis.sizeOk && expedienteId

  return (
    <div className="tab-panel">
      <div className="tab-panel-header">
        <div>
          <h2 className="tab-panel-title">Bóveda Criptográfica</h2>
          <p className="tab-panel-desc">
            Carga de documentos con validación Nivel 1: Magic Bytes, tamaño y huella SHA-256 (NOM-151-SCFI-2016).
          </p>
        </div>
      </div>

      <div className="vault-layout">
        <div className="vault-upload-card">
          <div
            className={`dropzone ${arrastrando ? 'dropzone--active' : ''}`}
            onDragOver={(e) => {
              e.preventDefault()
              setArrastrando(true)
            }}
            onDragLeave={() => setArrastrando(false)}
            onDrop={handleDrop}
          >
            <div className="dropzone-icon">
              {arrastrando ? <UploadCloud size={26} strokeWidth={2} /> : <ShieldCheck size={26} strokeWidth={2} />}
            </div>
            <p className="dropzone-title">Arrastra el archivo aquí</p>
            <p className="dropzone-hint">PDF, JPG o PNG · máx. 15 MB</p>
            <label className="btn btn-ghost dropzone-browse">
              Elegir archivo
              <input type="file" accept=".pdf,.jpg,.jpeg,.png" hidden onChange={handleInputChange} />
            </label>
          </div>

          {analizando && (
            <div className="analysis-box">
              <Loader2 className="spin" size={16} /> Calculando huella SHA-256 y leyendo Magic Bytes…
            </div>
          )}

          {archivo && analisis && !analizando && (
            <div className="analysis-box">
              <div className="analysis-row">
                <span className="analysis-label">Archivo</span>
                <span className="cell-strong">{archivo.name}</span>
              </div>
              <div className="analysis-row">
                <span className="analysis-label">Magic Bytes</span>
                {analisis.magic ? (
                  <span className="badge" style={{ color: 'var(--boveda-fg)', background: 'var(--boveda-bg)' }}>
                    <FileCheck2 size={13} /> {analisis.magic.label} válido
                  </span>
                ) : (
                  <span className="badge" style={{ color: 'var(--rechazado-fg)', background: 'var(--rechazado-bg)' }}>
                    <AlertTriangle size={13} /> Firma no reconocida
                  </span>
                )}
              </div>
              <div className="analysis-row">
                <span className="analysis-label">Tamaño</span>
                <span className={analisis.sizeOk ? 'cell-muted' : 'form-error inline'}>
                  {(archivo.size / 1024).toFixed(1)} KB {!analisis.sizeOk && '(excede 15 MB o está vacío)'}
                </span>
              </div>
              <div className="analysis-row analysis-row--hash">
                <span className="analysis-label">SHA-256</span>
                <span className="mono hash-preview">{analisis.hash}</span>
              </div>
            </div>
          )}

          <div className="form-grid" style={{ marginTop: 16 }}>
            <label className="field">
              <span>Expediente Destino</span>
              <select value={expedienteId} onChange={(e) => setExpedienteId(e.target.value)}>
                <option value="" disabled>
                  Selecciona un expediente…
                </option>
                {expedientes.map((e) => (
                  <option key={e.id} value={e.id}>
                    {e.codigo_expediente}
                  </option>
                ))}
              </select>
            </label>

            <label className="field">
              <span>Tipo de Documento</span>
              <select value={tipoDocumento} onChange={(e) => setTipoDocumento(e.target.value)}>
                {TIPOS_DOCUMENTO.map((t) => (
                  <option key={t.value} value={t.value}>
                    {t.label}
                  </option>
                ))}
              </select>
            </label>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer" style={{ padding: 0 }}>
              {archivo && (
                <button type="button" className="btn btn-ghost" onClick={limpiar}>
                  Descartar
                </button>
              )}
              <button type="button" className="btn btn-primary" disabled={!listo || subiendo} onClick={handleUpload}>
                {subiendo ? <Loader2 className="spin" size={16} /> : <UploadCloud size={16} />}
                Subir a la Bóveda
              </button>
            </div>
          </div>
        </div>

        <div className="table-card vault-table-card">
          <table className="data-table">
            <thead>
              <tr>
                <th>Documento</th>
                <th>Tipo</th>
                <th>Expediente</th>
                <th>Hash SHA-256</th>
                <th>Tamaño</th>
              </tr>
            </thead>
            <tbody>
              {loading && (
                <tr>
                  <td colSpan={5} className="table-empty">
                    <Loader2 className="spin" size={16} /> Cargando bóveda…
                  </td>
                </tr>
              )}
              {!loading && documentos.length === 0 && (
                <tr>
                  <td colSpan={5} className="table-empty">
                    <Vault size={16} /> La bóveda no tiene documentos aún.
                  </td>
                </tr>
              )}
              {documentos.map((doc) => (
                <tr key={doc.id}>
                  <td className="cell-strong">{doc.nombre_archivo_original}</td>
                  <td>
                    <span className="tag">{doc.tipo_documento}</span>
                  </td>
                  <td>
                    {mapaExpedientes[doc.expediente_id] ? (
                      <span className="mono-chip">{mapaExpedientes[doc.expediente_id]}</span>
                    ) : (
                      <span className="cell-muted">—</span>
                    )}
                  </td>
                  <td>
                    <CopyHash hash={doc.hash_sha256} />
                  </td>
                  <td className="cell-muted">{(doc.tamanio_bytes / 1024).toFixed(1)} KB</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
