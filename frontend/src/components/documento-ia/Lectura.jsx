// Estado de la lectura del documento, fragmentos consultados y meta de cada respuesta.
import { useState } from 'react'
import { ClockCounterClockwise, FileText, Lightning, Quotes, SealCheck } from '../iconos.js'
import { useEvidencia } from '../evidencia-context.js'
import { Badge } from '../ui/index.js'
import { formatDuracion, nombreModelo } from './formato.js'

/**
 * Badges discretos sobre qué leyó el modelo: páginas pendientes (corte
 * temprano del OCR) o contexto recortado por falta de fragmentos relevantes.
 */
export function EstadoLectura({ lectura, contexto }) {
  const pendientes = lectura && !lectura.lectura_completa ? lectura.paginas_omitidas_ocr : 0
  const recortado = contexto?.estrategia_contexto === 'inicio'
  if (!pendientes && !recortado) return null

  return (
    <div className="badge-row">
      {pendientes > 0 && (
        <Badge
          title={`El OCR leyó ${lectura.total_paginas - pendientes} de ${lectura.total_paginas} páginas. ${
            lectura.lectura_completa_en_curso
              ? 'El resto se está reconociendo en segundo plano; vuelve a auditar o preguntar en unos momentos.'
              : 'El resto se reconocerá en la próxima consulta.'
          }`}
        >
          Lectura parcial: {pendientes === 1 ? 'falta 1 página' : `faltan ${pendientes} páginas`}{lectura.lectura_completa_en_curso ? ' (en curso)' : ''}
        </Badge>
      )}
      {recortado && <Badge title="Ningún fragmento coincidió con la consulta: el modelo vio el inicio del documento.">Se analizó el inicio del documento</Badge>}
    </div>
  )
}

/**
 * Chips de las cláusulas que el modelo leyó para responder: título en versales
 * y posición en el documento. Un clic despliega el inicio del fragmento.
 */
export function Citas({ contexto }) {
  const evidencia = useEvidencia()
  const [abierta, setAbierta] = useState(null)
  const fragmentos = contexto?.estrategia_contexto === 'fragmentos' ? contexto.fragmentos_relevantes || [] : []
  if (!fragmentos.length) return null
  const seleccionada = fragmentos.find((f) => `${f.posicion_pct}-${f.puntaje}` === abierta)
  return (
    <div className="citations-wrap">
      <ul className="citations" aria-label="Fragmentos consultados">
        {fragmentos.map((f) => {
          const clave = `${f.posicion_pct}-${f.puntaje}`
          const activa = abierta === clave
          return (
            <li key={clave}>
              <button
                type="button"
                className={`citation ${activa ? 'is-active' : ''}`}
                onClick={() => {
                  setAbierta(activa ? null : clave)
                  // Con el visor disponible, el fragmento se abre en su página del documento.
                  if (!activa && f.pagina && evidencia) evidencia.irAPagina(f.pagina)
                }}
                aria-expanded={activa}
                title={f.pagina ? `Ver la página ${f.pagina} en el documento` : undefined}
              >
                <FileText size={12} aria-hidden="true" />
                <span className="citation-title">{f.titulo || f.inicio || 'Fragmento'}</span>
                <span className="citation-pos tabular">{f.pagina ? `p. ${f.pagina}` : `${f.posicion_pct}%`}</span>
              </button>
            </li>
          )
        })}
      </ul>
      {seleccionada && (
        <blockquote className="citation-preview">
          <p>{seleccionada.inicio}…</p>
          <footer className="tabular">
            {seleccionada.pagina
              ? `Fragmento de la página ${seleccionada.pagina}`
              : `Fragmento ubicado al ${seleccionada.posicion_pct}% del documento`}
          </footer>
        </blockquote>
      )}
    </div>
  )
}

/**
 * Procedencia de una respuesta del chat que no consultó al modelo (origen_respuesta
 * del ai-service). Sin origen, o con MODELO, la meta es la de siempre: «análisis con IA».
 */
const PROCEDENCIA = {
  DATOS_DEL_DICTAMEN: {
    icono: SealCheck,
    texto: 'datos del dictamen',
    detalle: 'Respuesta armada con los datos que la auditoría del documento verificó; no se consultó al modelo.',
  },
  PASAJE_DEL_DOCUMENTO: {
    icono: Quotes,
    texto: 'texto del documento',
    detalle: 'Pasaje literal del documento, sin interpretación; no se consultó al modelo.',
  },
  CACHE: {
    icono: ClockCounterClockwise,
    texto: 'respuesta ya consultada',
    detalle:
      'La misma pregunta ya se respondió sobre este documento y su dictamen vigente; no se volvió a consultar al modelo.',
  },
}

/** Micro-meta de una respuesta: tiempo total y de dónde salió (el modelo, en el tooltip). */
export function MetaInferencia({ modelo, duracion, origen }) {
  const procedencia = PROCEDENCIA[origen]
  if (!procedencia) {
    return (
      <span className="inference-meta" title={nombreModelo(modelo)}>
        <Lightning size={12} aria-hidden="true" />
        <span className="tabular">{formatDuracion(duracion)}</span> · análisis con IA
      </span>
    )
  }
  const Icono = procedencia.icono
  return (
    <span className="inference-meta" title={procedencia.detalle}>
      <Icono size={12} aria-hidden="true" />
      <span className="tabular">{formatDuracion(duracion)}</span> · {procedencia.texto}
    </span>
  )
}
