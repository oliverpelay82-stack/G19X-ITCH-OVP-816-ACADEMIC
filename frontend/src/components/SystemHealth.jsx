import { SERVICIOS } from '../constants.js'
import { AI_BASE_URL, CORE_BASE_URL, RULES_BASE_URL } from '../services/api.js'

/** Puerto real de cada servicio, según la URL con la que se construyó el frontend. */
const PUERTOS = Object.fromEntries(
  [
    ['core', CORE_BASE_URL],
    ['rules', RULES_BASE_URL],
    ['ai', AI_BASE_URL],
  ].map(([clave, url]) => {
    try {
      return [clave, new URL(url).port]
    } catch {
      return [clave, null]
    }
  })
)

/** Tono del punto de salud: sin respuesta, degradado (sin BD o sin capacidades) o en línea. */
function tonoServicio(estado) {
  if (estado?.online === null || estado?.online === undefined) return 'off' // aún sin sondear
  if (!estado.online) return 'bad'
  const p = estado.payload
  if (p?.conexion_bd === false || p?.capacidades_operativas === false) return 'warn'
  return 'ok'
}

/** "qwen/qwen3.8-27b" → "qwen3.8-27b"; el proveedor va en el tooltip (RNF-08: no en la etiqueta). */
const modeloCorto = (modelo) => (modelo ? modelo.split('/').pop() : null)

/** Detalle del tooltip: lo que antes ocupaba el panel del motor de IA. */
function detalle(servicio, estado, tono, reglas) {
  if (tono === 'off') return `${servicio.nombre} (:${servicio.puerto}) · comprobando…`
  if (tono === 'bad') return `${servicio.nombre} (:${servicio.puerto}) sin respuesta`
  const lineas = [`${servicio.nombre} · ${servicio.alcance}`, `Latencia ${estado.latencia} ms`]
  const p = estado.payload || {}
  if (servicio.key === 'core' || servicio.key === 'rules') {
    lineas.push(p.conexion_bd === false ? 'PostgreSQL sin conexión' : 'PostgreSQL conectado')
  }
  if (servicio.key === 'rules') {
    const rcv = reglas.filter((r) => r.familia_regla === 'RCV' && r.activo).map((r) => r.codigo_regla)
    if (rcv.length) lineas.push(`Vigencia activa: ${rcv.join(', ')}`)
  }
  if (servicio.key === 'ai') {
    const inf = p.motor_inferencia
    const ocr = p.motor_ocr
    const bandas = p.bandas_confianza
    if (inf) lineas.push(`${inf.proveedor || 'Groq Cloud'} · ${inf.modelo_requerido} · ${inf.modelo_disponible ? 'disponible' : 'no disponible'}`)
    if (ocr) lineas.push(ocr.disponible ? `OCR ${ocr.proveedor} ${ocr.version} (${ocr.idiomas_disponibles?.join(', ')})` : 'OCR no disponible')
    if (bandas) {
      lineas.push(
        `Confianza: conforme ≥ ${Math.round(bandas.conforme_desde * 100)}% · revisión humana desde ${Math.round(bandas.revision_humana_desde * 100)}%`
      )
    }
  }
  if (tono === 'warn') lineas.push('Estado degradado')
  return lineas.join('\n')
}

/**
 * System Health Strip: una sola línea con los tres microservicios, su latencia
 * medida en cada ciclo de sondeo y el modelo de lenguaje en servicio. Sustituye
 * al panel flotante del motor de IA; el detalle (OCR, bandas de confianza,
 * reglas RCV activas) vive en el tooltip de cada segmento.
 */
export default function SystemHealth({ health, reglas = [] }) {
  return (
    <ul className="health-strip" aria-label="Estado de los microservicios">
      {SERVICIOS.map((s) => {
        const estado = health?.[s.key]
        const tono = tonoServicio(estado)
        const modelo = s.key === 'ai' ? modeloCorto(estado?.payload?.motor_inferencia?.modelo_requerido) : null
        const puerto = PUERTOS[s.key] || s.puerto
        return (
          <li key={s.key} className={`health-item health-item--${tono}`} title={detalle({ ...s, puerto }, estado, tono, reglas)}>
            <span className={`status-dot status-dot--${tono}`} aria-hidden="true" />
            <span className="health-name">{s.etiqueta}</span>
            <span className="health-port mono">:{puerto}</span>
            <span className="health-metric mono">{tono === 'off' ? '…' : tono === 'bad' ? 'caído' : `${estado.latencia} ms`}</span>
            {modelo && <span className="health-model mono">{modelo}</span>}
          </li>
        )
      })}
    </ul>
  )
}
