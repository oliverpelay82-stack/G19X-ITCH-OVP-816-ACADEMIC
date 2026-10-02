import { useCallback, useMemo, useRef, useState } from 'react'
import { Loader2, Upload, X } from 'lucide-react'
import { Badge, Button, Field, IconButton, Select } from './ui/index.js'
import { MAX_FILE_SIZE_BYTES } from '../constants.js'
import useToast from '../hooks/useToast.js'
import { analizarNivel1, avisarCarga } from '../utils/nivel1.js'
import { estadoLote, resumenLote, revisarLote } from '../utils/lote.js'
import { formatBytes, hashCorto } from '../utils/format.js'

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

function OpcionesTipo({ tipos }) {
  return agruparPorSeccion(tipos).map(([seccion, opciones]) =>
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
  )
}

/** Veredicto del Nivel 1 de un archivo del lote, en una línea. */
function VeredictoLote({ analisis }) {
  if (!analisis) {
    return (
      <span className="lote-calculando">
        <Loader2 className="spin" size={12} />
        Calculando la huella…
      </span>
    )
  }
  if (!analisis.magic) return <Badge tono="bad">Firma no reconocida</Badge>
  if (!analisis.tamanioOk) return <Badge tono="bad">Fuera del límite</Badge>
  return (
    <Badge tono="vault" title={`SHA-256 ${analisis.hash}`}>
      {analisis.magic.label} · <span className="mono">{hashCorto(analisis.hash, 6, 4)}</span>
    </Badge>
  )
}

/**
 * Zona de carga con arrastrar y soltar. Al recibir un archivo ejecuta en el
 * navegador el Nivel 1 del pipeline (firma binaria, tamaño y SHA-256) y
 * muestra el veredicto antes de permitir el envío al core-service.
 *
 * Con varios archivos es una carga en lote (RF-02): cada archivo lleva su
 * propio tipo, sin tipo por omisión, y se envía uno a la vez con
 * `onArchivo(archivo, tipo, { enLote: true })`; quien carga devuelve el
 * documento sin avisar ni refrescar. Lo aceptado sale de la lista, lo
 * rechazado se queda con su motivo y al final se llama a `onLoteTerminado`.
 */
export default function DropZone({
  tipos,
  onArchivo,
  onLoteTerminado,
  subiendo = false,
  compacto = false,
  deshabilitado = false,
  motivoDeshabilitado,
  children,
  listoExtra = true,
}) {
  const toast = useToast()
  const [arrastrando, setArrastrando] = useState(false)
  const [elementos, setElementos] = useState([])
  const [tipo, setTipo] = useState(tipos?.[0]?.value || '')
  const [enviandoLote, setEnviandoLote] = useState(false)
  // Huellas que este lote ya custodió (huella → nombre); se olvidan al vaciar la lista.
  const [custodiadas, setCustodiadas] = useState(() => new Map())
  const inputRef = useRef(null)
  const contador = useRef(0)
  const siguienteId = useRef(0)

  // La lista de tipos puede encogerse conforme se cargan documentos, así que
  // el tipo elegido se revalida en cada render en lugar de quedar fijado.
  const tipoActivo = tipos?.some((t) => t.value === tipo) ? tipo : tipos?.[0]?.value || ''

  const actualizar = (id, cambios) => setElementos((lista) => lista.map((e) => (e.id === id ? { ...e, ...cambios } : e)))

  // Los archivos se agregan a la lista y se analizan uno a uno: cada análisis
  // lee el archivo completo a memoria para su huella.
  const recibir = useCallback(async (files) => {
    const nuevos = [...(files || [])].map((archivo) => ({ id: ++siguienteId.current, archivo, analisis: null, tipo: '' }))
    if (!nuevos.length) return
    setElementos((lista) => [...lista, ...nuevos])
    for (const e of nuevos) {
      const analisis = await analizarNivel1(e.archivo)
      setElementos((lista) => lista.map((x) => (x.id === e.id ? { ...x, analisis } : x)))
    }
  }, [])

  const quitar = (id) => {
    const restantes = elementos.filter((e) => e.id !== id)
    setElementos(restantes)
    if (!restantes.length) setCustodiadas(new Map())
    if (inputRef.current) inputRef.current.value = ''
  }

  const limpiar = () => {
    setElementos([])
    setCustodiadas(new Map())
    if (inputRef.current) inputRef.current.value = ''
  }

  // Tras enviar un lote, la lista sigue en modo lote aunque quede un archivo:
  // conserva el motivo del rechazo y la memoria de las huellas ya custodiadas.
  const enLote = elementos.length > 1 || custodiadas.size > 0 || elementos.some((e) => e.error)
  const unico = enLote ? null : elementos[0]
  const archivo = unico?.archivo || null
  const analisis = unico?.analisis || null
  const analizando = Boolean(unico && !unico.analisis)

  const revision = useMemo(() => revisarLote(elementos, custodiadas), [elementos, custodiadas])
  const lote = useMemo(() => estadoLote(elementos, revision), [elementos, revision])

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

  // Lote: uno a la vez y en el orden de la lista, como cargas individuales
  // sucesivas (el core serializa de todos modos las de un mismo expediente).
  const confirmarLote = async () => {
    setEnviandoLote(true)
    let custodiados = 0
    let rechazados = 0
    const nuevas = new Map(custodiadas)
    for (const e of lote.porEnviar) {
      actualizar(e.id, { enviando: true, error: null })
      try {
        const documento = await onArchivo(e.archivo, e.tipo, { enLote: true })
        custodiados += 1
        nuevas.set(e.analisis.hash, e.archivo.name)
        avisarCarga(toast, documento, null, e.archivo.name)
        setElementos((lista) => lista.filter((x) => x.id !== e.id))
      } catch (err) {
        rechazados += 1
        actualizar(e.id, { enviando: false, error: err.message })
      }
    }
    setEnviandoLote(false)
    setCustodiadas(rechazados || lote.omitidos ? nuevas : new Map())
    if (inputRef.current) inputRef.current.value = ''
    const detalle = resumenLote(custodiados, rechazados)
    if (rechazados) toast.alerta(custodiados ? 'Lote custodiado en parte' : 'Lote rechazado', detalle)
    else toast.exito('Lote custodiado', detalle)
    onLoteTerminado?.({ custodiados, rechazados })
  }

  const listo = Boolean(archivo && analisis?.conforme && tipoActivo && listoExtra && !deshabilitado)
  const listoLote = lote.listo && listoExtra && !deshabilitado && !enviandoLote

  const ayudaLote = [
    lote.sinTipo > 0 && `Elige el tipo de ${lote.sinTipo === 1 ? '1 archivo' : `${lote.sinTipo} archivos`}.`,
    lote.omitidos > 0 && `${lote.omitidos === 1 ? '1 archivo no se enviará' : `${lote.omitidos} archivos no se enviarán`}.`,
  ]
    .filter(Boolean)
    .join(' ')

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
          if (!enviandoLote) recibir(e.dataTransfer.files)
        }}
        onClick={() => !enviandoLote && inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            if (!enviandoLote) inputRef.current?.click()
          }
        }}
        role="button"
        tabIndex={0}
        aria-label="Seleccionar o arrastrar uno o varios documentos"
      >
        <Upload size={16} className="dropzone-icon" />
        <p className="dropzone-title">{arrastrando ? 'Suelta para analizar' : 'Arrastra archivos o haz clic'}</p>
        <p className="dropzone-hint">PDF, JPG o PNG · máx. {formatBytes(MAX_FILE_SIZE_BYTES)}</p>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.jpg,.jpeg,.png,application/pdf,image/jpeg,image/png"
          hidden
          onChange={(e) => recibir(e.target.files)}
        />
      </div>

      {analizando && (
        <div className="analysis analysis--loading">
          <Loader2 className="spin" size={14} />
          <span>Calculando la huella digital…</span>
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

      {enLote && (
        <ul className="lote" aria-label={`${elementos.length} archivos por custodiar`}>
          {elementos.map((e) => {
            const { duplicadoDe, sustituyeA } = revision.get(e.id) || {}
            const admitido = e.analisis?.conforme && !duplicadoDe
            return (
              <li key={e.id} className={`lote-item ${e.error ? 'is-error' : ''}`}>
                <div className="analysis-file">
                  <span className="analysis-file-name" title={e.archivo.name}>
                    {e.archivo.name}
                  </span>
                  <span className="analysis-file-size mono">{formatBytes(e.archivo.size)}</span>
                  {e.enviando ? (
                    <Loader2 className="spin lote-enviando" size={14} aria-label="Custodiando" />
                  ) : (
                    <IconButton etiqueta={`Quitar ${e.archivo.name} del lote`} compacto onClick={() => quitar(e.id)} disabled={enviandoLote}>
                      <X size={14} />
                    </IconButton>
                  )}
                </div>
                <div className="lote-item-fila">
                  <VeredictoLote analisis={e.analisis} />
                  {admitido && (
                    <Select
                      etiqueta={`Tipo de documento de ${e.archivo.name}`}
                      claseContenedor="lote-tipo"
                      value={e.tipo}
                      onChange={(ev) => actualizar(e.id, { tipo: ev.target.value, error: null })}
                      disabled={enviandoLote}
                    >
                      <option value="" disabled>
                        Elige el tipo…
                      </option>
                      <OpcionesTipo tipos={tipos || []} />
                    </Select>
                  )}
                </div>
                {duplicadoDe && (
                  <span className="field-feedback field-feedback--invalido">
                    Mismo archivo que «{duplicadoDe}»: no se enviará.
                  </span>
                )}
                {sustituyeA && (
                  <span className="field-feedback field-feedback--advertencia">
                    Mismo tipo que «{sustituyeA}»: este quedará como el vigente y el otro como versión anterior.
                  </span>
                )}
                {e.error && <span className="field-feedback field-feedback--invalido">{e.error}</span>}
              </li>
            )
          })}
        </ul>
      )}

      <div className="dropzone-controls">
        {!enLote && tipos?.length > 1 && (
          <Field etiqueta="Tipo de documento">
            <Select value={tipoActivo} onChange={(e) => setTipo(e.target.value)}>
              <OpcionesTipo tipos={tipos} />
            </Select>
          </Field>
        )}

        {children}

        {enLote ? (
          <>
            {ayudaLote && <p className="field-hint">{ayudaLote}</p>}
            <Button
              variante="primary"
              onClick={confirmarLote}
              cargando={enviandoLote}
              disabled={!listoLote}
              title={deshabilitado ? motivoDeshabilitado : undefined}
            >
              {lote.admisibles > 1 ? `Custodiar ${lote.admisibles} documentos` : 'Custodiar en bóveda'}
            </Button>
          </>
        ) : (
          <Button
            variante="primary"
            onClick={confirmar}
            cargando={subiendo}
            disabled={!listo}
            title={deshabilitado ? motivoDeshabilitado : undefined}
          >
            Custodiar en bóveda
          </Button>
        )}
      </div>
    </div>
  )
}
