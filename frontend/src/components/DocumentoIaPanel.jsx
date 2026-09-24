import { useEffect, useRef, useState } from 'react'
import { ArrowUp, Check, Equal, FileText, Loader2, MessageSquareText, Sparkles, TriangleAlert, X, Zap } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import { EmptyState, Segmented } from './ui.jsx'
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
  EN_REVISION: { tono: 'warn', label: 'En revisión' },
  NO_CONFORME: { tono: 'bad', label: 'No conforme' },
}

const PREGUNTAS_SUGERIDAS = [
  '¿Cuándo vence este documento?',
  '¿A qué empresa o persona pertenece?',
  '¿Resume los datos clave de este archivo?',
]

const FUENTE_TEXTO = { memoria: 'desde memoria', persistencia: 'desde disco', extraccion: 'extraído ahora' }

const RESULTADO_VIGENCIA = {
  VIGENTE: { tono: 'ok', label: 'vigente' },
  PROXIMO_A_VENCER: { tono: 'warn', label: 'próximo a vencer' },
  VENCIDO: { tono: 'bad', label: 'vencido' },
  INDETERMINADO: { tono: 'warn', label: 'no verificable' },
}

/**
 * Etapas de la auditoría en el orden real del pipeline: la lectura es una
 * petición propia (preparar) y el análisis semántico y las reglas de vigencia
 * viajan en la misma petición, porque las reglas necesitan las fechas que
 * extrae el modelo.
 */
const ETAPAS = [
  { id: 'lectura', label: 'Lectura', nivel: 'Nivel 3' },
  { id: 'analisis', label: 'Análisis semántico', nivel: 'Nivel 4' },
  { id: 'reglas', label: 'Reglas de vigencia', nivel: 'Nivel 2' },
]

const ETAPAS_INICIALES = Object.fromEntries(ETAPAS.map((e) => [e.id, { estado: 'pendiente', detalle: '' }]))

/** Cuántos turnos previos viajan como historial para no inflar el contexto. */
const MAX_TURNOS_HISTORIAL = 6

/* ── Utilidades ─────────────────────────────────────────────────── */

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
  if (ms === null || ms === undefined) return '—'
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

const numero = (n) => Number(n).toLocaleString('es-MX')
const fechaIso = (iso) => formatFechaCorta(iso && `${iso}T00:00:00`)

/** La regla RCV que decidió el resultado de vigencia (la de antigüedad, si aplicó). */
function reglaDecisiva(vigencia) {
  const evaluaciones = vigencia?.evaluaciones || []
  return (
    evaluaciones.find((e) => e.resultado === vigencia.resultado && e.criterio === 'ANTIGUEDAD_DESDE_EMISION') ||
    evaluaciones.find((e) => e.resultado === vigencia.resultado) ||
    null
  )
}

/**
 * Vigencia según las reglas RCV del rules-service (Nivel 2), con la regla que
 * decidió el resultado. Devuelve null si ninguna regla de vigencia aplicó, para
 * mostrar entonces solo los días hasta el vencimiento.
 */
function vigenciaSegunReglas(vigencia, textoVencimiento) {
  if (vigencia?.disponible === false) return { tono: 'warn', texto: 'Reglas de vigencia no disponibles' }
  const meta = RESULTADO_VIGENCIA[vigencia?.resultado]
  const decisiva = meta && reglaDecisiva(vigencia)
  if (!decisiva) return null
  let texto = textoVencimiento
  if (vigencia.resultado === 'INDETERMINADO') texto = 'No verificable'
  else if (decisiva.criterio === 'ANTIGUEDAD_DESDE_EMISION') {
    texto = `${numero(decisiva.dias_calculados)} días desde emisión (máx. ${decisiva.limite_dias})`
  }
  return { tono: meta.tono, texto: `${texto} · ${decisiva.codigo_regla}` }
}

/** Traza compacta de la etapa 3 a partir de la respuesta del análisis. */
function detalleReglas(vigencia) {
  if (vigencia?.disponible === false) return { estado: 'error', detalle: 'rules-service sin respuesta' }
  const decisiva = vigencia?.resultado && reglaDecisiva(vigencia)
  if (!decisiva) return { estado: 'hecho', detalle: 'Sin reglas aplicables al tipo' }
  const meta = RESULTADO_VIGENCIA[vigencia.resultado]
  return { estado: 'hecho', detalle: `${decisiva.codigo_regla} · ${meta?.label || vigencia.resultado.toLowerCase()}` }
}

/**
 * Separa la observación que motiva el dictamen ("Dictamen X: motivo.") del
 * resto, para mostrarla junto al veredicto.
 */
function separarMotivo(observaciones = []) {
  const i = observaciones.findIndex((o) => /^Dictamen [A-Z_]+:/.test(o))
  if (i === -1) return { motivo: null, resto: observaciones }
  const texto = observaciones[i].replace(/^Dictamen [A-Z_]+:\s*/, '')
  return {
    motivo: texto.charAt(0).toUpperCase() + texto.slice(1),
    resto: observaciones.filter((_, j) => j !== i),
  }
}

/* ── Piezas visuales ────────────────────────────────────────────── */

/**
 * Stepper de tres etapas. Mientras corre muestra la etapa activa; al terminar
 * queda como traza compacta del pipeline con el detalle de cada etapa.
 */
function Stepper({ etapas, compacto }) {
  return (
    <ol className={`stepper ${compacto ? 'stepper--compact' : ''}`} role="status" aria-live="polite">
      {ETAPAS.map((e, i) => {
        const { estado, detalle } = etapas[e.id]
        return (
          <li key={e.id} className={`step step--${estado}`}>
            <span className="step-marker" aria-hidden="true">
              {estado === 'activo' && <Loader2 className="spin" size={11} strokeWidth={2.4} />}
              {estado === 'hecho' && <Check size={11} strokeWidth={2.6} />}
              {estado === 'error' && <X size={11} strokeWidth={2.6} />}
              {(estado === 'pendiente' || estado === 'espera') && <span className="step-num">{i + 1}</span>}
            </span>
            <span className="step-body">
              <span className="step-label">
                {e.label}
                <span className="step-level">{e.nivel}</span>
              </span>
              <span className="step-detail">{detalle || (estado === 'pendiente' ? 'En cola' : ' ')}</span>
            </span>
          </li>
        )
      })}
    </ol>
  )
}

/** Barra de confianza de 3 px con el porcentaje y la banda a la que pertenece. */
function Confianza({ dictamen }) {
  const valor = dictamen.nivel_confianza || 0
  const conforme = dictamen.umbral_confianza_conforme ?? 0.85
  const hitl = dictamen.umbral_confianza_hitl ?? 0.7
  const tono = valor >= conforme ? 'ok' : valor >= hitl ? 'warn' : 'bad'
  return (
    <div className="confidence">
      <div className="confidence-head">
        <span className="eyebrow">Confianza</span>
        <span className={`confidence-value confidence-value--${tono} tabular`}>{Math.round(valor * 100)}%</span>
      </div>
      <span className="confidence-bar" aria-hidden="true">
        <span className={`confidence-fill confidence-fill--${tono}`} style={{ width: `${valor * 100}%` }} />
        <span className="confidence-mark" style={{ left: `${conforme * 100}%` }} />
      </span>
      <span className="confidence-foot">Conforme desde {Math.round(conforme * 100)}%</span>
    </div>
  )
}

/** RFC extraído del documento frente al RFC registrado del titular. */
function CotejoRfc({ dictamen, rfcTitular }) {
  const tono = !rfcTitular || !dictamen.rfc_detectado ? 'neutral' : dictamen.match_titular ? 'ok' : 'bad'
  const Icono = tono === 'ok' ? Equal : tono === 'bad' ? X : TriangleAlert
  const leyenda = !rfcTitular
    ? 'Sin RFC de referencia'
    : !dictamen.rfc_detectado
      ? 'RFC no localizado'
      : dictamen.match_titular
        ? 'Coincide con el titular'
        : 'Titular ajeno'
  return (
    <div className={`rfc-match rfc-match--${tono}`}>
      <div className="rfc-side">
        <span className="eyebrow">RFC del documento</span>
        <span className={`mono rfc-value ${dictamen.rfc_detectado ? '' : 'cell-muted'}`}>
          {dictamen.rfc_detectado || 'No localizado'}
        </span>
        {dictamen.rfc_detectado && !dictamen.rfc_estructura_valida && (
          <span className="rfc-warning">Estructura SAT inválida</span>
        )}
      </div>
      <span className="rfc-link" data-tooltip={leyenda}>
        <Icono size={12} strokeWidth={2.4} aria-label={leyenda} />
      </span>
      <div className="rfc-side rfc-side--end">
        <span className="eyebrow">RFC del titular</span>
        <span className={`mono rfc-value ${rfcTitular ? '' : 'cell-muted'}`}>{rfcTitular || 'Sin RFC'}</span>
      </div>
    </div>
  )
}

/**
 * Badges discretos sobre qué leyó el modelo: páginas pendientes (corte
 * temprano del OCR) o contexto recortado por falta de fragmentos relevantes.
 */
function EstadoLectura({ lectura, contexto }) {
  const pendientes = lectura && !lectura.lectura_completa ? lectura.paginas_omitidas_ocr : 0
  const recortado = contexto?.estrategia_contexto === 'inicio'
  if (!pendientes && !recortado) return null

  return (
    <div className="badge-row">
      {pendientes > 0 && (
        <span
          className="badge badge--neutral"
          title={`El OCR leyó ${lectura.total_paginas - pendientes} de ${lectura.total_paginas} páginas. ${
            lectura.lectura_completa_en_curso
              ? 'El resto se está reconociendo en segundo plano; vuelve a auditar o preguntar en unos momentos.'
              : 'El resto se reconocerá en la próxima consulta.'
          }`}
        >
          Lectura parcial · {pendientes} págs. pendientes{lectura.lectura_completa_en_curso ? ' (completándose)' : ''}
        </span>
      )}
      {recortado && (
        <span className="badge badge--neutral" title="Ningún fragmento coincidió con la consulta: el modelo vio el inicio del documento.">
          Contexto recortado
        </span>
      )}
    </div>
  )
}

/** Chips de las cláusulas que el modelo leyó para responder, con su posición en el documento. */
function Citas({ contexto }) {
  const fragmentos = contexto?.estrategia_contexto === 'fragmentos' ? contexto.fragmentos_relevantes || [] : []
  if (!fragmentos.length) return null
  return (
    <ul className="citations" aria-label="Fragmentos consultados">
      {fragmentos.map((f) => (
        <li key={`${f.posicion_pct}-${f.puntaje}`} className="citation" title={f.inicio}>
          <FileText size={11} strokeWidth={2} aria-hidden="true" />
          <span className="citation-title">{f.titulo || f.inicio}</span>
          <span className="citation-pos tabular">{f.posicion_pct}%</span>
        </li>
      ))}
    </ul>
  )
}

/** Micro-meta de una respuesta: tiempo total y proveedor, con el modelo en el tooltip. */
function MetaInferencia({ modelo, duracion }) {
  return (
    <span className="inference-meta" title={nombreModelo(modelo)}>
      <Zap size={11} strokeWidth={2.2} aria-hidden="true" />
      <span className="tabular">{formatDuracion(duracion)}</span> · Groq LPU
    </span>
  )
}

/* ── Dictamen ───────────────────────────────────────────────────── */
function DictamenIa({ dictamen, rfcTitular, duracion }) {
  const estatus = ESTATUS_IA[dictamen.estatus_preliminar] || {
    tono: 'neutral',
    label: dictamen.estatus_preliminar || 'Sin dictamen',
  }
  const { motivo, resto } = separarMotivo(dictamen.observaciones)
  const dias = diasRestantes(dictamen)
  const textoVencimiento =
    dias === null
      ? 'Sin fecha de vencimiento'
      : dias < 0
        ? `Vencido hace ${numero(Math.abs(dias))} ${Math.abs(dias) === 1 ? 'día' : 'días'}`
        : dias === 0
          ? 'Vence hoy'
          : `${numero(dias)} ${dias === 1 ? 'día restante' : 'días restantes'}`
  const segunReglas = vigenciaSegunReglas(dictamen.vigencia_nivel_2, textoVencimiento)
  const tonoVigencia = segunReglas?.tono ?? (dias === null ? 'neutral' : dias < 0 ? 'bad' : dias <= 30 ? 'warn' : 'ok')

  return (
    <div className="dictamen">
      <div className={`verdict verdict--${estatus.tono}`}>
        <div className="verdict-main">
          <p className="eyebrow">Dictamen preliminar</p>
          <p className="verdict-word">{estatus.label}</p>
          {motivo && <p className="verdict-reason">{motivo}</p>}
          <div className="badge-row">
            <span className={`badge badge--${tonoVigencia}`}>
              <span className={`status-dot status-dot--${tonoVigencia}`} aria-hidden="true" />
              {segunReglas?.texto ?? textoVencimiento}
            </span>
            {dictamen.requiere_revision_humana && <span className="badge badge--warn">Revisión humana · Nivel 5</span>}
          </div>
        </div>
        <Confianza dictamen={dictamen} />
      </div>

      <CotejoRfc dictamen={dictamen} rfcTitular={rfcTitular} />

      <dl className="detail-grid detail-grid--4">
        <div className="detail-item">
          <dt>Tipo detectado</dt>
          <dd>{TIPO_IA_LABEL[dictamen.tipo_documento_detectado] || TIPO_IA_LABEL.OTRO}</dd>
        </div>
        <div className="detail-item">
          <dt>Razón social</dt>
          <dd className={dictamen.razon_social_detectada ? '' : 'cell-muted'}>
            {dictamen.razon_social_detectada || 'No localizada'}
          </dd>
        </div>
        <div className="detail-item">
          <dt>Emisión</dt>
          <dd className="tabular">{fechaIso(dictamen.fecha_emision)}</dd>
        </div>
        <div className="detail-item">
          <dt>Vencimiento</dt>
          <dd className="tabular">{fechaIso(dictamen.fecha_vencimiento)}</dd>
        </div>
      </dl>

      {resto.length > 0 && (
        <div className="observations">
          <p className="eyebrow">Observaciones</p>
          <ul>
            {resto.map((obs, i) => (
              <li key={i}>{obs}</li>
            ))}
          </ul>
        </div>
      )}

      <EstadoLectura lectura={dictamen.extraccion_nivel_3} contexto={dictamen.contexto_llm} />

      <p className="verdict-foot">
        <MetaInferencia modelo={dictamen.modelo_utilizado} duracion={duracion} />
        <span>{nombreModelo(dictamen.modelo_utilizado)} · temperatura 0.0</span>
      </p>
    </div>
  )
}

/* ── Auditoría ──────────────────────────────────────────────────── */
function AuditoriaIa({ doc, expediente, iaOnline }) {
  const toast = useToast()
  const [etapas, setEtapas] = useState(null)
  const [dictamen, setDictamen] = useState(null)
  const [duracion, setDuracion] = useState(null)
  const rfcTitular = expediente?.titular?.rfc || null
  const analizando = Boolean(etapas) && Object.values(etapas).some((e) => e.estado === 'activo')

  const marcar = (cambios) => setEtapas((prev) => ({ ...prev, ...cambios }))

  const auditar = async () => {
    const inicio = performance.now()
    let actual = 'lectura'
    setEtapas({ ...ETAPAS_INICIALES, lectura: { estado: 'activo', detalle: 'Resolviendo el texto del documento…' } })
    try {
      // Etapa 1: el texto queda resuelto (memoria, disco u OCR) antes de llamar al modelo.
      const { resultado: prep, duracion: msLectura } = await cronometrar(() => prepararDocumento(doc.id))
      const n3 = prep?.extraccion_nivel_3 || {}
      actual = 'analisis'
      marcar({
        lectura: {
          estado: 'hecho',
          detalle: [
            n3.metodo_extraccion,
            n3.total_paginas && `${n3.total_paginas} págs.`,
            FUENTE_TEXTO[prep?.fuente_texto],
            formatDuracion(msLectura),
          ]
            .filter(Boolean)
            .join(' · '),
        },
        analisis: { estado: 'activo', detalle: 'Extrayendo datos con Groq…' },
        reglas: { estado: 'espera', detalle: 'Espera las fechas extraídas' },
      })

      // Etapas 2 y 3: el análisis reutiliza ese texto y el servicio consulta las reglas RCV.
      const resultado = await analizarDocumento({
        documento_id: doc.id,
        rfc_titular: rfcTitular || undefined,
        razon_social_titular: expediente?.titular?.razon_social || undefined,
      })
      marcar({
        analisis: {
          estado: 'hecho',
          detalle: `${nombreModelo(resultado?.modelo_utilizado)} · ${formatDuracion(resultado?.tiempos_ms?.inferencia)}`,
        },
        reglas: detalleReglas(resultado?.vigencia_nivel_2),
      })
      setDictamen(resultado)
      setDuracion(performance.now() - inicio)
      const meta = ESTATUS_IA[resultado?.estatus_preliminar]
      toast.info('Dictamen de IA generado', `${doc.nombre_archivo_original} · ${meta?.label || resultado?.estatus_preliminar}`)
    } catch (err) {
      marcar({ [actual]: { estado: 'error', detalle: err?.message || 'Error del ai-service' } })
      avisarFallo(toast, err, 'No se pudo auditar el documento')
    }
  }

  return (
    <div className="ai-view">
      <div className="ai-cta">
        <p className="ai-cta-desc">
          Clasifica el documento, coteja el RFC contra el titular y verifica su vigencia con las reglas RCV. A Groq solo
          viaja el texto extraído, nunca el archivo.
        </p>
        <button
          type="button"
          className={`btn ${dictamen ? 'btn-secondary' : 'btn-primary'}`}
          onClick={auditar}
          disabled={analizando || !iaOnline}
          title={iaOnline ? undefined : 'El ai-service (:8003) no responde'}
        >
          {analizando ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} strokeWidth={2} />}
          {analizando ? 'Auditando…' : dictamen ? 'Volver a auditar' : 'Auditar documento'}
        </button>
      </div>

      {!iaOnline && !dictamen && (
        <p className="field-hint">El ai-service (:8003) no responde; la auditoría no está disponible.</p>
      )}

      {etapas && <Stepper etapas={etapas} compacto={!analizando} />}

      {analizando && (
        <div className="ai-loading" aria-hidden="true">
          <Skeleton w="30%" h={24} />
          <Skeleton w="72%" />
          <Skeleton w="100%" h={3} r="var(--r-full)" />
          <Skeleton w="54%" />
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
          <EmptyState
            icon={MessageSquareText}
            titulo="Pregunta sobre este documento"
            descripcion="El modelo responde solo con lo que contiene el archivo, cita las cláusulas que leyó y lo dice cuando no encuentra el dato."
          />
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
                  <Citas contexto={m.contexto} />
                  <EstadoLectura lectura={m.lectura} contexto={m.contexto} />
                  <MetaInferencia modelo={m.modelo} duracion={m.duracion} />
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

const VISTAS = [
  { id: 'auditoria', label: 'Auditoría' },
  { id: 'chat', label: 'Chat' },
]

/**
 * Panel de inteligencia documental dentro del detalle de un documento:
 * dictamen (Niveles 2 a 4) y conversación en lenguaje natural contra el
 * ai-service (:8003), que a su vez consulta Groq Cloud.
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
          <p className="section-desc">Groq LPU · solo texto extraído</p>
        </div>
        <Segmented role="tablist" label="Vista del panel de IA" valor={vista} onChange={setVista} opciones={VISTAS} />
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
