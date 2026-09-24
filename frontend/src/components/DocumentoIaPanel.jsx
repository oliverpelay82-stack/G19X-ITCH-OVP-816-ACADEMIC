import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Loader2 } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import useToast from '../hooks/useToast.js'
import { analizarDocumento, prepararDocumento, preguntarSobreDocumento } from '../services/api.js'
import { formatFechaCorta } from '../utils/format.js'

const MODELO_POR_DEFECTO = 'Groq Qwen 27B'

/** Catálogo del Nivel 4 (espejo de TIPOS_DOCUMENTALES en analisis_semantico.py). */
const TIPO_IA_LABEL = {
  CONSTANCIA_SITUACION_FISCAL: 'Constancia de Situación Fiscal',
  OPINION_CUMPLIMIENTO: 'Opinión de Cumplimiento (32-D)',
  COMPROBANTE_DOMICILIO: 'Comprobante de Domicilio',
  ACTA_CONSTITUTIVA: 'Acta Constitutiva',
  ESTADO_CUENTA: 'Estado de Cuenta Bancario',
  CONTRATO: 'Contrato',
  POLIZA: 'Póliza de Seguro',
  LICENCIA: 'Licencia',
  CERTIFICACION: 'Certificación',
  IDENTIFICACION_OFICIAL: 'Identificación Oficial',
  OTRO: 'No clasificado',
}

const ESTATUS_IA = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  EN_REVISION: { tono: 'warn', label: 'En Revisión' },
  NO_CONFORME: { tono: 'bad', label: 'No Conforme' },
}

const PREGUNTAS_SUGERIDAS = [
  '¿Cuándo vence este documento?',
  '¿A qué empresa o persona pertenece?',
  '¿Resume los datos clave de este archivo?',
]

/** Etapas visibles de la auditoría; cada una corresponde a una petición real. */
const ETAPAS = [
  { id: 'leyendo', label: 'Leyendo documento…' },
  { id: 'analizando', label: 'Analizando con Groq…' },
  { id: 'listo', label: 'Dictamen listo' },
]

/** Cuántos turnos previos viajan como historial para no inflar el contexto. */
const MAX_TURNOS_HISTORIAL = 6

/** Nombre legible del modelo: "qwen/qwen3.8-27b" → "Groq Qwen 3.8 (27B)". */
function nombreModelo(modelo) {
  if (!modelo) return MODELO_POR_DEFECTO
  // Groq antepone el proveedor del modelo ("qwen/"); para mostrarlo sobra.
  const id = modelo.split('/').pop()
  const partes = /^([a-z]+)-?([\d.]+)-(\d+b)$/i.exec(id)
  if (!partes) return `Groq ${id}`
  const [, familia, version, tamanio] = partes
  return `Groq ${familia.charAt(0).toUpperCase()}${familia.slice(1)} ${version} (${tamanio.toUpperCase()})`
}

/** Traduce los fallos del ai-service a un toast accionable para el operador. */
function avisarFallo(toast, err, contexto) {
  if (err?.status === 0) {
    toast.error('ai-service sin respuesta', 'El microservicio de IA (:8003) no está disponible. Verifica que esté corriendo.')
  } else if (err?.status === 503) {
    toast.alerta('Groq no disponible', err.message)
  } else if (err?.status === 502) {
    toast.alerta('Respuesta inválida del modelo', `${err.message} Intenta de nuevo en unos segundos.`)
  } else {
    toast.error(contexto, err?.message || 'Error inesperado del ai-service.')
  }
}

/** Días restantes: se prefiere el cálculo del backend y se recalcula solo si falta. */
function diasRestantes(dictamen) {
  if (Number.isInteger(dictamen.dias_para_vencimiento)) return dictamen.dias_para_vencimiento
  if (!dictamen.fecha_vencimiento) return null
  const vence = new Date(`${dictamen.fecha_vencimiento}T00:00:00`)
  if (Number.isNaN(vence.getTime())) return null
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  return Math.round((vence - hoy) / 86_400_000)
}

/** Ejecuta la petición y devuelve su resultado junto con el tiempo de respuesta. */
async function cronometrar(peticion) {
  const inicio = performance.now()
  const resultado = await peticion()
  return { resultado, duracion: performance.now() - inicio }
}

function formatDuracion(ms) {
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

/**
 * Badges discretos sobre qué leyó el modelo: si faltan páginas por reconocer
 * (lectura parcial por el corte temprano del OCR) y si el contexto se armó con
 * fragmentos relevantes o se recortó.
 */
function EstadoLectura({ lectura, contexto }) {
  const pendientes = lectura && !lectura.lectura_completa ? lectura.paginas_omitidas_ocr : 0
  const fragmentos = contexto?.estrategia_contexto === 'fragmentos' ? contexto.fragmentos_relevantes?.length : 0
  const recortado = contexto?.estrategia_contexto === 'inicio'
  if (!pendientes && !fragmentos && !recortado) return null

  return (
    <div className="badge-row">
      {pendientes > 0 && (
        <span
          className="badge"
          title={`El OCR leyó ${lectura.total_paginas - pendientes} de ${lectura.total_paginas} páginas. ${
            lectura.lectura_completa_en_curso
              ? 'El resto se está reconociendo en segundo plano; vuelve a auditar o preguntar en unos momentos.'
              : 'El resto se reconocerá en la próxima consulta.'
          }`}
        >
          Lectura parcial · {pendientes} págs. pendientes{lectura.lectura_completa_en_curso ? ' (completándose)' : ''}
        </span>
      )}
      {fragmentos > 0 && (
        <span
          className="badge badge--brand"
          title={`El documento tiene ${contexto.caracteres_documento.toLocaleString('es-MX')} caracteres: el modelo vio el encabezado y los ${fragmentos} fragmentos más relevantes.`}
        >
          {fragmentos} fragmentos relevantes
        </span>
      )}
      {recortado && (
        <span className="badge" title="Ningún fragmento coincidió con la consulta: el modelo vio el inicio del documento.">
          Contexto recortado
        </span>
      )}
    </div>
  )
}

/** Indicador de etapas de la auditoría. */
function Etapas({ actual }) {
  const indice = ETAPAS.findIndex((e) => e.id === actual)
  return (
    <ol className="stepper" role="status" aria-live="polite">
      {ETAPAS.map((etapa, i) => {
        const estado = i < indice || actual === 'listo' ? 'is-done' : i === indice ? 'is-active' : ''
        return (
          <li key={etapa.id} className={`stepper-item ${estado}`}>
            <span className="stepper-dot" aria-hidden="true">
              {estado === 'is-active' && <Loader2 className="spin" size={10} />}
            </span>
            {etapa.label}
          </li>
        )
      })}
    </ol>
  )
}

const TONO_VIGENCIA = { VENCIDO: 'bad', PROXIMO_A_VENCER: 'warn', INDETERMINADO: 'warn', VIGENTE: 'ok' }

/**
 * Vigencia según las reglas RCV del rules-service (Nivel 2), con la regla que
 * decidió el resultado. Devuelve null si ninguna regla de vigencia aplicó, para
 * mostrar entonces solo los días hasta el vencimiento.
 */
function vigenciaSegunReglas(vigencia, textoVencimiento) {
  if (vigencia?.disponible === false) return { tono: 'warn', texto: 'Reglas de vigencia no disponibles' }
  if (!vigencia?.resultado || !TONO_VIGENCIA[vigencia.resultado]) return null
  const decisiva =
    vigencia.evaluaciones?.find((e) => e.resultado === vigencia.resultado && e.criterio === 'ANTIGUEDAD_DESDE_EMISION') ||
    vigencia.evaluaciones?.find((e) => e.resultado === vigencia.resultado)
  if (!decisiva) return null
  let texto = textoVencimiento
  if (vigencia.resultado === 'INDETERMINADO') texto = 'No verificable'
  else if (decisiva.criterio === 'ANTIGUEDAD_DESDE_EMISION') {
    texto = `${decisiva.dias_calculados.toLocaleString('es-MX')} días desde la emisión (máx. ${decisiva.limite_dias})`
  }
  return { tono: TONO_VIGENCIA[vigencia.resultado], texto: `${texto} · ${decisiva.codigo_regla}` }
}

/** Dato del dictamen: etiqueta tenue arriba, valor debajo. */
function Dato({ label, children, ancho = false }) {
  return (
    <div className={`detail-item ${ancho ? 'detail-item--full' : ''}`}>
      <dt>{label}</dt>
      <dd>{children}</dd>
    </div>
  )
}

/* ── Dictamen ───────────────────────────────────────────────────── */
function DictamenIa({ dictamen, rfcTitular, duracion }) {
  const estatus = ESTATUS_IA[dictamen.estatus_preliminar] || {
    tono: 'neutral',
    label: dictamen.estatus_preliminar || 'Sin dictamen',
  }
  const tipo = TIPO_IA_LABEL[dictamen.tipo_documento_detectado] || TIPO_IA_LABEL.OTRO
  const confianza = Math.round((dictamen.nivel_confianza || 0) * 100)
  const tonoConfianza =
    dictamen.nivel_confianza >= (dictamen.umbral_confianza_conforme ?? 0.85)
      ? 'ok'
      : dictamen.nivel_confianza >= (dictamen.umbral_confianza_hitl ?? 0.7)
        ? 'warn'
        : 'bad'
  const dias = diasRestantes(dictamen)
  const textoVencimiento =
    dias === null
      ? 'Sin fecha de vencimiento'
      : dias < 0
        ? `Vencido hace ${Math.abs(dias)} ${Math.abs(dias) === 1 ? 'día' : 'días'}`
        : dias === 0
          ? 'Vence hoy'
          : `${dias} ${dias === 1 ? 'día restante' : 'días restantes'}`
  const segunReglas = vigenciaSegunReglas(dictamen.vigencia_nivel_2, textoVencimiento)
  const tonoVigencia =
    segunReglas?.tono ?? (dias === null ? 'neutral' : dias < 0 ? 'bad' : dias <= 30 ? 'warn' : 'ok')
  const textoVigencia = segunReglas?.texto ?? textoVencimiento

  const titular = !rfcTitular
    ? { tono: 'neutral', label: 'Sin RFC de referencia' }
    : dictamen.match_titular
      ? { tono: 'ok', label: 'Coincide con el titular' }
      : { tono: 'bad', label: 'Titular ajeno' }

  return (
    <div className="verdict">
      <div className="verdict-head">
        <div>
          <p className="eyebrow">Dictamen preliminar · Nivel 4</p>
          <span className={`badge badge--${estatus.tono}`}>{estatus.label}</span>
        </div>
        <div className="verdict-score">
          <span className={`score score--${tonoConfianza} tabular`}>{confianza}%</span>
          <span className="eyebrow">Confianza</span>
        </div>
      </div>

      <dl className="detail-grid">
        <Dato label="Tipo detectado">{tipo}</Dato>
        <Dato label="Cotejo de titular">
          <span className={`badge badge--${titular.tono}`}>{titular.label}</span>
        </Dato>
        <Dato label="RFC detectado">
          <span className={`mono ${dictamen.rfc_detectado ? '' : 'cell-muted'}`}>
            {dictamen.rfc_detectado || 'No localizado'}
          </span>
          {dictamen.rfc_detectado && !dictamen.rfc_estructura_valida && (
            <span className="badge badge--warn badge--inline">Estructura SAT inválida</span>
          )}
        </Dato>
        <Dato label="RFC del titular">
          <span className={`mono ${rfcTitular ? '' : 'cell-muted'}`}>{rfcTitular || 'Sin RFC'}</span>
        </Dato>
        {dictamen.razon_social_detectada && (
          <Dato label="Razón social detectada" ancho>
            {dictamen.razon_social_detectada}
          </Dato>
        )}
        <Dato label="Emisión">
          <span className="tabular">
            {formatFechaCorta(dictamen.fecha_emision && `${dictamen.fecha_emision}T00:00:00`)}
          </span>
        </Dato>
        <Dato label="Vencimiento">
          <span className="tabular">
            {formatFechaCorta(dictamen.fecha_vencimiento && `${dictamen.fecha_vencimiento}T00:00:00`)}
          </span>
        </Dato>
        <Dato label="Vigencia" ancho>
          <span className={`badge badge--${tonoVigencia}`}>{textoVigencia}</span>
        </Dato>
      </dl>

      {dictamen.observaciones?.length > 0 && (
        <div className="observations">
          <p className="eyebrow">Observaciones</p>
          <ul>
            {dictamen.observaciones.map((obs, i) => (
              <li key={i}>{obs}</li>
            ))}
          </ul>
        </div>
      )}

      <EstadoLectura lectura={dictamen.extraccion_nivel_3} contexto={dictamen.contexto_llm} />

      <p className="verdict-foot">
        <span>{nombreModelo(dictamen.modelo_utilizado)} · temperatura 0.0</span>
        {dictamen.extraccion_nivel_3?.metodo_extraccion && (
          <span>Nivel 3: {dictamen.extraccion_nivel_3.metodo_extraccion}</span>
        )}
        {duracion !== null && <span>{formatDuracion(duracion)}</span>}
        {dictamen.requiere_revision_humana && <span className="verdict-hitl">Turnado a revisión humana (Nivel 5)</span>}
      </p>
    </div>
  )
}

/* ── Auditoría ──────────────────────────────────────────────────── */
function AuditoriaIa({ doc, expediente, iaOnline }) {
  const toast = useToast()
  const [etapa, setEtapa] = useState(null)
  const analizando = etapa === 'leyendo' || etapa === 'analizando'
  const [dictamen, setDictamen] = useState(null)
  const [duracion, setDuracion] = useState(null)
  const rfcTitular = expediente?.titular?.rfc || null

  const auditar = async () => {
    const inicio = performance.now()
    try {
      // Etapa 1: el texto queda resuelto (memoria, disco u OCR) antes de llamar al modelo.
      setEtapa('leyendo')
      await prepararDocumento(doc.id)
      // Etapa 2: el análisis reutiliza ese texto sin volver a extraerlo.
      setEtapa('analizando')
      const resultado = await analizarDocumento({
        documento_id: doc.id,
        rfc_titular: rfcTitular || undefined,
        razon_social_titular: expediente?.titular?.razon_social || undefined,
      })
      setDictamen(resultado)
      setDuracion(performance.now() - inicio)
      setEtapa('listo')
      setTimeout(() => setEtapa((actual) => (actual === 'listo' ? null : actual)), 1200)
      const meta = ESTATUS_IA[resultado?.estatus_preliminar]
      toast.info('Dictamen de IA generado', `${doc.nombre_archivo_original} · ${meta?.label || resultado?.estatus_preliminar}`)
    } catch (err) {
      setEtapa(null)
      avisarFallo(toast, err, 'No se pudo auditar el documento')
    }
  }

  return (
    <div className="ai-view">
      <div className="ai-cta">
        <p className="ai-cta-desc">
          Clasifica el documento, coteja el RFC contra el titular y calcula su vigencia. Solo se envía a Groq el texto
          extraído, nunca el archivo.
        </p>
        <button
          type="button"
          className="btn btn-primary"
          onClick={auditar}
          disabled={analizando || !iaOnline}
          title={iaOnline ? undefined : 'El ai-service (:8003) no responde'}
        >
          {analizando && <Loader2 className="spin" size={14} />}
          {analizando
            ? ETAPAS.find((e) => e.id === etapa).label
            : dictamen
              ? 'Volver a auditar'
              : `Auditar con ${MODELO_POR_DEFECTO}`}
        </button>
      </div>

      {!iaOnline && !dictamen && (
        <p className="field-hint">El ai-service (:8003) no responde; la auditoría no está disponible.</p>
      )}

      {etapa && <Etapas actual={etapa} />}

      {analizando && (
        <div className="ai-loading" aria-hidden="true">
          <Skeleton w="82%" />
          <Skeleton w="64%" />
          <Skeleton w="46%" />
        </div>
      )}

      {!analizando && dictamen && <DictamenIa dictamen={dictamen} rfcTitular={rfcTitular} duracion={duracion} />}
    </div>
  )
}

/* ── Chat ───────────────────────────────────────────────────────── */
function ChatDocumento({ doc, iaOnline }) {
  const toast = useToast()
  const [mensajes, setMensajes] = useState([])
  const [borrador, setBorrador] = useState('')
  const [pensando, setPensando] = useState(false)
  const hilo = useRef(null)

  useEffect(() => {
    const el = hilo.current
    if (el) el.scrollTo({ top: el.scrollHeight, behavior: 'smooth' })
  }, [mensajes, pensando])

  const preguntar = async (texto) => {
    const pregunta = texto.trim()
    if (pregunta.length < 3 || pensando) return

    const historial = mensajes
      .filter((m) => !m.error)
      .slice(-MAX_TURNOS_HISTORIAL)
      .map((m) => ({ rol: m.rol, contenido: m.contenido }))

    setMensajes((prev) => [...prev, { id: crypto.randomUUID(), rol: 'usuario', contenido: pregunta }])
    setBorrador('')
    setPensando(true)
    try {
      // Solo viaja el documento_id: el servidor sirve el texto desde memoria o
      // disco (nunca repite el OCR) y, si la lectura completa terminó en segundo
      // plano, busca fragmentos en todas las páginas y no solo en las primeras.
      const { resultado: r, duracion } = await cronometrar(() =>
        preguntarSobreDocumento({ documento_id: doc.id, pregunta, historial })
      )
      setMensajes((prev) => [
        ...prev,
        {
          id: crypto.randomUUID(),
          rol: 'asistente',
          contenido: r?.respuesta || 'El modelo no devolvió contenido.',
          modelo: r?.modelo_utilizado,
          duracion,
          lectura: r?.extraccion_nivel_3,
          contexto: r?.contexto_llm,
        },
      ])
    } catch (err) {
      avisarFallo(toast, err, 'No se pudo consultar el documento')
      setMensajes((prev) => [
        ...prev,
        { id: crypto.randomUUID(), rol: 'asistente', contenido: err?.message || 'Error del ai-service.', error: true },
      ])
    } finally {
      setPensando(false)
    }
  }

  const alEnviar = (e) => {
    e.preventDefault()
    preguntar(borrador)
  }

  const alTeclear = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      preguntar(borrador)
    }
  }

  const deshabilitado = !iaOnline || pensando

  return (
    <div className="ai-view chat">
      <div className="chat-thread" ref={hilo} aria-live="polite">
        {mensajes.length === 0 && !pensando && (
          <div className="empty-state">
            <p className="empty-title">Pregunta sobre este documento</p>
            <p className="empty-desc">
              El modelo responde solo con lo que contiene el archivo y lo dice cuando no encuentra el dato.
            </p>
          </div>
        )}

        {mensajes.map((m) =>
          m.rol === 'usuario' ? (
            <div key={m.id} className="bubble bubble--user">
              {m.contenido}
            </div>
          ) : (
            <div key={m.id} className={`bubble ${m.error ? 'bubble--error' : 'bubble--bot'}`}>
              <p className="bubble-text">{m.contenido}</p>
              {!m.error && (
                <>
                  <p className="bubble-meta">
                    {nombreModelo(m.modelo)} · {formatDuracion(m.duracion)}
                  </p>
                  <EstadoLectura lectura={m.lectura} contexto={m.contexto} />
                </>
              )}
            </div>
          )
        )}

        {pensando && (
          <div className="bubble bubble--bot typing" role="status" aria-label="El modelo está respondiendo">
            <span />
            <span />
            <span />
          </div>
        )}
      </div>

      <div className="chat-suggestions" role="group" aria-label="Preguntas sugeridas">
        {PREGUNTAS_SUGERIDAS.map((p) => (
          <button key={p} type="button" className="chip" onClick={() => preguntar(p)} disabled={deshabilitado}>
            {p}
          </button>
        ))}
      </div>

      <form className="composer" onSubmit={alEnviar}>
        <textarea
          rows={1}
          value={borrador}
          onChange={(e) => setBorrador(e.target.value)}
          onKeyDown={alTeclear}
          placeholder={iaOnline ? 'Escribe una pregunta sobre el documento…' : 'El ai-service (:8003) no responde'}
          disabled={!iaOnline}
          aria-label="Pregunta sobre el documento"
        />
        <button
          type="submit"
          className="btn btn-primary btn-icon"
          disabled={deshabilitado || borrador.trim().length < 3}
          aria-label="Enviar pregunta"
        >
          {pensando ? <Loader2 className="spin" size={14} /> : <ArrowUp size={14} strokeWidth={2.2} />}
        </button>
      </form>
    </div>
  )
}

/**
 * Panel del Nivel 4 dentro del detalle de un documento: dictamen semántico
 * y conversación en lenguaje natural contra el ai-service (:8003), que a su
 * vez consulta Groq Cloud.
 *
 * El padre debe montarlo con `key={doc.id}` para que el dictamen y el hilo
 * se reinicien al cambiar de documento.
 */
export default function DocumentoIaPanel({ doc, expediente, iaOnline = true }) {
  const [vista, setVista] = useState('auditoria')

  return (
    <section className="ai-panel" aria-label="Análisis con inteligencia artificial">
      <header className="ai-panel-head">
        <div>
          <h4 className="section-title">Inteligencia documental</h4>
          <p className="section-desc">Nivel 4 · Groq Cloud</p>
        </div>
        <div className="segmented" role="tablist">
          <button
            type="button"
            role="tab"
            aria-selected={vista === 'auditoria'}
            className={`segmented-item ${vista === 'auditoria' ? 'is-active' : ''}`}
            onClick={() => setVista('auditoria')}
          >
            Auditoría
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={vista === 'chat'}
            className={`segmented-item ${vista === 'chat' ? 'is-active' : ''}`}
            onClick={() => setVista('chat')}
          >
            Chat
          </button>
        </div>
      </header>

      {/* Ambas vistas permanecen montadas para no perder el dictamen ni el hilo al alternar. */}
      <div hidden={vista !== 'auditoria'}>
        <AuditoriaIa doc={doc} expediente={expediente} iaOnline={iaOnline} />
      </div>
      <div hidden={vista !== 'chat'}>
        <ChatDocumento doc={doc} iaOnline={iaOnline} />
      </div>
    </section>
  )
}
