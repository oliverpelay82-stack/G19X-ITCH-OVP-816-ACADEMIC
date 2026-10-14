// Chat documental: preguntas sobre el documento con citas verificadas.
import { useEffect, useRef, useState } from 'react'
import { ArrowUp, ChatText } from '../iconos.js'
import { useEvidencia } from '../evidencia-context.js'
import { Badge, Button, EmptyState } from '../ui/index.js'
import useToast from '../../hooks/useToast.js'
import { preguntarSobreDocumento } from '../../services/api.js'
import { Citas, EstadoLectura, MetaInferencia } from './Lectura.jsx'
import { avisarFallo, cronometrar } from './formato.js'
import { idAleatorio } from '../../utils/id.js'

const PREGUNTAS_SUGERIDAS = [
  '¿Qué le falta a este documento?',
  '¿Qué recomiendas corregir?',
  '¿Cuándo vence este documento?',
  'Resume los datos clave de este archivo',
]

/** Cuántos turnos previos viajan como historial para no inflar el contexto. */
const MAX_TURNOS_HISTORIAL = 6

/* ── Utilidades ─────────────────────────────────────────────────── */

/** Interpreta las **negritas** de Markdown de la respuesta del modelo como nodos de React. */
function Negritas({ texto }) {
  const partes = String(texto).split(/\*\*(.+?)\*\*/g)
  return partes.map((parte, i) => (i % 2 === 1 ? <strong key={i}>{parte}</strong> : parte))
}

/**
 * Respuesta del modelo con sus citas «…». El ai-service contrasta cada cita
 * con el texto del documento; la que no aparece literalmente se marca para
 * que no se lea como evidencia.
 */
function TextoModelo({ texto, citas = [] }) {
  const evidencia = useEvidencia()
  const porTexto = new Map(citas.map((c) => [c.texto, c]))
  const partes = String(texto).split(/«([^»]+)»/g)
  return partes.map((parte, i) => {
    if (i % 2 === 0) return <Negritas key={i} texto={parte} />
    const cita = porTexto.get(parte.trim())
    const ok = cita?.verificada
    const titulo =
      ok === false
        ? 'Esta cita no aparece literalmente en el documento ni en su dictamen'
        : cita?.fuente === 'sistema'
          ? 'Tomada del dictamen y del catálogo de reglas, no del documento'
          : ok
            ? 'Cita verificada en el documento'
            : undefined
    const contenido = (
      <q className={`chat-cita ${ok === false ? 'chat-cita--sin-verificar' : ''}`} title={titulo}>
        <Negritas texto={parte} />
        {ok === false && (
          <Badge tono="warn" className="chat-cita-badge">
            Sin verificar
          </Badge>
        )}
      </q>
    )
    // Solo una cita del documento tiene dónde resaltarse; la del dictamen o el catálogo, no.
    if (!evidencia || cita?.fuente === 'sistema') return <span key={i}>{contenido}</span>
    const abrir = () => evidencia.mostrar({ cita: parte, tono: ok === false ? 'warn' : 'ok' })
    // Un <button> no fluye con el texto (Chrome lo trata como inline-block): la
    // cita del chat es un span con rol de botón, operable con Enter o espacio.
    return (
      <span
        key={i}
        role="button"
        tabIndex={0}
        className="cita-enlace"
        onClick={abrir}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault()
            abrir()
          }
        }}
        title={`${titulo ? `${titulo}. ` : ''}Clic para verla en el documento`}
      >
        {contenido}
      </span>
    )
  })
}

export function ChatDocumento({ doc, iaOnline }) {
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

    setMensajes((prev) => [...prev, { id: idAleatorio(), rol: 'usuario', contenido: pregunta }])
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
          id: idAleatorio(),
          rol: 'asistente',
          contenido: r?.respuesta || 'El modelo no devolvió contenido.',
          modelo: r?.modelo_utilizado,
          // Procedencia de la respuesta (modelo, dictamen, pasaje o respuesta ya consultada).
          origen: r?.origen_respuesta,
          duracion,
          lectura: r?.extraccion_nivel_3,
          contexto: r?.contexto_llm,
          citas: r?.citas,
        },
      ])
    } catch (err) {
      avisarFallo(toast, err, 'No se pudo consultar el documento')
      setMensajes((prev) => [
        ...prev,
        { id: idAleatorio(), rol: 'asistente', contenido: err?.message || 'Error del servicio de análisis con IA.', error: true },
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
            icon={ChatText}
            titulo="Pregunta sobre este documento"
            descripcion="El modelo responde con lo que contiene el archivo y su dictamen en el sistema, cita las cláusulas que leyó y lo dice cuando no encuentra el dato."
          />
        )}

        {mensajes.map((m) =>
          m.rol === 'usuario' ? (
            <div key={m.id} className="bubble bubble--user">
              {m.contenido}
            </div>
          ) : (
            <div key={m.id} className={`bubble ${m.error ? 'bubble--error' : 'bubble--bot'}`}>
              <p className="bubble-text">
                <TextoModelo texto={m.contenido} citas={m.citas} />
              </p>
              {!m.error && (
                <>
                  <Citas contexto={m.contexto} />
                  <div className="bubble-pie">
                    <EstadoLectura lectura={m.lectura} contexto={m.contexto} />
                    <MetaInferencia modelo={m.modelo} duracion={m.duracion} origen={m.origen} />
                  </div>
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
          placeholder={iaOnline ? 'Escribe una pregunta sobre el documento…' : 'El servicio de análisis con IA no responde'}
          disabled={!iaOnline}
          aria-label="Pregunta sobre el documento"
        />
        <Button
          type="submit"
          variante="primary"
          soloIcono
          icono={ArrowUp}
          cargando={pensando}
          disabled={deshabilitado || borrador.trim().length < 3}
          aria-label="Enviar pregunta"
        />
      </form>
    </div>
  )
}
