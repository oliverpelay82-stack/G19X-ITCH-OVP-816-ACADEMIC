import { useCallback, useRef, useState } from 'react'
import { Loader2, Upload, X } from 'lucide-react'
import { Badge, Button, Field, IconButton, Select } from './ui/index.js'
import { MAX_FILE_SIZE_BYTES } from '../constants.js'
import { analizarNivel1 } from '../utils/nivel1.js'
import { formatBytes } from '../utils/format.js'

/** Agrupa las opciones por `seccion` conservando su orden (sin sección, un solo grupo). */
function agruparPorSeccion(tipos) {
  const grupos = new Map()
  for (const t of tipos) {
    const clave = t.seccion || ''
    if (!grupos.has(clave)) grupos.set(clave, [])
    grupos.get(clave).push(t)
  }
  return [...grupos.entries()]
}

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

  // Si la carga falla, quien la hace ya avisó del error (onArchivo rechaza): el
  // archivo se conserva para reintentar y la promesa no queda sin capturar.
  const confirmar = async () => {
    if (!archivo || !tipoActivo) return
    try {
      await onArchivo(archivo, tipoActivo)
    } catch {
      return
    }
    limpiar()
  }

  const listo = Boolean(archivo && analisis?.conforme && tipoActivo && listoExtra && !deshabilitado)

  return (
    <div className={`dropzone-wrap ${compacto ? 'dropzone-wrap--compact' : ''}`}>
      <div
        className={`dropzone ${arrastrando ? 'is-dragging' : ''}`}
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
        <Upload size={18} className="dropzone-icon" />
        <p className="dropzone-title">{arrastrando ? 'Suelta para analizar' : 'Arrastra un archivo o haz clic'}</p>
        <p className="dropzone-hint">PDF, JPG o PNG · máx. {formatBytes(MAX_FILE_SIZE_BYTES)}</p>
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          hidden
          onChange={(e) => recibir(e.target.files?.[0])}
        />
      </div>

      {analizando && (
        <div className="analysis analysis--loading">
          <Loader2 className="spin" size={14} />
          <span>Calculando huella SHA-256…</span>
        </div>
      )}

      {archivo && analisis && !analizando && (
        <div className="analysis">
          <div className="analysis-file">
            <span className="analysis-file-name">{archivo.name}</span>
            <span className="analysis-file-size mono">{formatBytes(archivo.size)}</span>
            <IconButton etiqueta="Descartar archivo" compacto onClick={limpiar}>
              <X size={14} />
            </IconButton>
          </div>

          <div className="analysis-checks">
            <Badge tono={analisis.magic ? 'vault' : 'bad'}>
              {analisis.magic ? `${analisis.magic.label} verificado` : 'Firma no reconocida'}
            </Badge>
            <Badge tono={analisis.tamanioOk ? 'ok' : 'bad'}>{analisis.tamanioOk ? 'Tamaño admitido' : 'Fuera del límite'}</Badge>
          </div>

          <div className="analysis-hash">
            <span className="field-label">SHA-256</span>
            <code className="mono">{analisis.hash}</code>
          </div>
        </div>
      )}

      <div className="dropzone-controls">
        {tipos?.length > 1 && (
          <Field etiqueta="Tipo de documento">
            <Select value={tipoActivo} onChange={(e) => setTipo(e.target.value)}>
              {agruparPorSeccion(tipos).map(([seccion, opciones]) =>
                seccion ? (
                  <optgroup key={seccion} label={seccion}>
                    {opciones.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))}
                  </optgroup>
                ) : (
                  opciones.map((t) => (
                    <option key={t.value} value={t.value}>
                      {t.label}
                    </option>
                  ))
                )
              )}
            </Select>
          </Field>
        )}

        {children}

        <Button
          variante="primary"
          onClick={confirmar}
          cargando={subiendo}
          disabled={!listo}
          title={deshabilitado ? motivoDeshabilitado : undefined}
        >
          Custodiar en bóveda
        </Button>
      </div>
    </div>
  )
}
