// Estado de la lectura del documento, fragmentos consultados y meta de cada respuesta.
import { useState } from 'react'
import { FileText, Zap } from 'lucide-react'
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
                <FileText size={11} strokeWidth={1.75} aria-hidden="true" />
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

/** Micro-meta de una respuesta: tiempo total, con el modelo en el tooltip. */
export function MetaInferencia({ modelo, duracion }) {
  return (
    <span className="inference-meta" title={nombreModelo(modelo)}>
      <Zap size={11} strokeWidth={1.75} aria-hidden="true" />
      <span className="tabular">{formatDuracion(duracion)}</span> · análisis con IA
    </span>
  )
}
