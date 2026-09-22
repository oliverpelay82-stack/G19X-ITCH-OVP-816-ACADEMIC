import { useCallback, useRef, useState } from 'react'
import {
  AlertTriangle,
  FileCheck2,
  FileText,
  Fingerprint,
  Loader2,
  ShieldCheck,
  Trash2,
  UploadCloud,
} from 'lucide-react'
import { MAX_FILE_SIZE_BYTES } from '../constants.js'
import { analizarNivel1 } from '../utils/nivel1.js'
import { formatBytes } from '../utils/format.js'

/**
 * Zona de carga con arrastrar y soltar. Al recibir el archivo ejecuta en el
 * navegador el Nivel 1 del pipeline (firma binaria, tamaño y SHA-256) y
 * muestra el veredicto antes de permitir el envío al core-service.
 */
export default function DropZone({
  tipos,
  onArchivo,
  subiendo = false,
  compacto = false,
  deshabilitado = false,
  motivoDeshabilitado,
  children,
  listoExtra = true,
}) {
  const [arrastrando, setArrastrando] = useState(false)
  const [archivo, setArchivo] = useState(null)
  const [analisis, setAnalisis] = useState(null)
  const [analizando, setAnalizando] = useState(false)
  const [tipo, setTipo] = useState(tipos?.[0]?.value || '')
  const inputRef = useRef(null)
  const contador = useRef(0)

  // La lista de tipos puede encogerse conforme se cargan documentos, así que
  // el tipo elegido se revalida en cada render en lugar de quedar fijado.
  const tipoActivo = tipos?.some((t) => t.value === tipo) ? tipo : tipos?.[0]?.value || ''

  const recibir = useCallback(async (file) => {
    if (!file) return
    setArchivo(file)
    setAnalisis(null)
    setAnalizando(true)
    try {
      setAnalisis(await analizarNivel1(file))
    } finally {
      setAnalizando(false)
    }
  }, [])

  const limpiar = () => {
    setArchivo(null)
    setAnalisis(null)
    if (inputRef.current) inputRef.current.value = ''
  }

  const confirmar = async () => {
    if (!archivo || !tipoActivo) return
    await onArchivo(archivo, tipoActivo)
    limpiar()
  }

  const listo = Boolean(archivo && analisis?.conforme && tipoActivo && listoExtra && !deshabilitado)

  return (
    <div className={`dropzone-wrap ${compacto ? 'dropzone-wrap--compact' : ''}`}>
      <div
        className={`dropzone ${arrastrando ? 'dropzone--active' : ''} ${archivo ? 'dropzone--filled' : ''}`}
        onDragEnter={(e) => {
          e.preventDefault()
          contador.current += 1
          setArrastrando(true)
        }}
        onDragOver={(e) => e.preventDefault()}
        onDragLeave={(e) => {
          e.preventDefault()
          contador.current -= 1
          if (contador.current <= 0) {
            contador.current = 0
            setArrastrando(false)
          }
        }}
        onDrop={(e) => {
          e.preventDefault()
          contador.current = 0
          setArrastrando(false)
          recibir(e.dataTransfer.files?.[0])
        }}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            inputRef.current?.click()
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Seleccionar o arrastrar un documento"
      >
        <span className="dropzone-ring" aria-hidden="true" />
        <span className="dropzone-icon">
          {arrastrando ? (
            <UploadCloud size={compacto ? 19 : 24} strokeWidth={2} />
          ) : (
            <ShieldCheck size={compacto ? 19 : 24} strokeWidth={2} />
          )}
        </span>
        <p className="dropzone-title">
          {arrastrando ? 'Suelta para analizar' : 'Arrastra el documento o haz clic aquí'}
        </p>
        <p className="dropzone-hint">
          PDF, JPG o PNG · máximo {formatBytes(MAX_FILE_SIZE_BYTES)} · se calcula el SHA-256 en tu equipo
        </p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          hidden
          onChange={(e) => recibir(e.target.files?.[0])}
        />
      </div>

      {analizando && (
        <div className="analysis">
          <Loader2 className="spin" size={15} />
          <span>Leyendo firma binaria y calculando la huella SHA-256…</span>
        </div>
      )}

      {archivo && analisis && !analizando && (
        <div className="analysis analysis--result">
          <div className="analysis-file">
            <span className="analysis-file-icon">
              <FileText size={15} strokeWidth={2.2} />
            </span>
            <span className="analysis-file-body">
              <span className="analysis-file-name">{archivo.name}</span>
              <span className="analysis-file-meta mono">{formatBytes(archivo.size)}</span>
            </span>
            <button type="button" className="icon-button icon-button--sm" onClick={limpiar} aria-label="Descartar archivo">
              <Trash2 size={14} strokeWidth={2.2} />
            </button>
          </div>

          <div className="analysis-checks">
            <span className={`badge badge--${analisis.magic ? 'vault' : 'bad'}`}>
              {analisis.magic ? <FileCheck2 size={11} strokeWidth={2.6} /> : <AlertTriangle size={11} strokeWidth={2.6} />}
              {analisis.magic ? `${analisis.magic.label} verificado` : 'Firma no reconocida'}
            </span>
            <span className={`badge badge--${analisis.tamanioOk ? 'ok' : 'bad'}`}>
              {analisis.tamanioOk ? <FileCheck2 size={11} strokeWidth={2.6} /> : <AlertTriangle size={11} strokeWidth={2.6} />}
              {analisis.tamanioOk ? 'Tamaño admitido' : 'Fuera del límite'}
            </span>
          </div>

          <div className="analysis-hash">
            <span className="analysis-hash-label">
              <Fingerprint size={12} strokeWidth={2.4} />
              SHA-256
            </span>
            <code className="analysis-hash-value">{analisis.hash}</code>
          </div>
        </div>
      )}

      <div className="dropzone-controls">
        {tipos?.length > 1 && (
          <label className="field field--inline">
            <span className="field-label">Tipo de documento</span>
            <select value={tipoActivo} onChange={(e) => setTipo(e.target.value)}>
              {tipos.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </label>
        )}

        {children}

        <button
          type="button"
          className="btn btn-primary"
          onClick={confirmar}
          disabled={!listo || subiendo}
          title={deshabilitado ? motivoDeshabilitado : undefined}
        >
          {subiendo ? <Loader2 className="spin" size={15} /> : <UploadCloud size={15} strokeWidth={2.4} />}
          Custodiar en bóveda
        </button>
      </div>
    </div>
  )
}
