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

/** Resumen de una línea: el peor estado manda (sin respuesta, degradado, comprobando, en línea). */
function resumen(servicios) {
  const caidos = servicios.filter((x) => x.tono === 'bad').length
  if (caidos) return { tono: 'bad', texto: caidos === 1 ? '1 servicio sin respuesta' : `${caidos} servicios sin respuesta` }
  if (servicios.some((x) => x.tono === 'warn')) return { tono: 'warn', texto: 'Servicio degradado' }
  if (servicios.some((x) => x.tono === 'off')) return { tono: 'off', texto: 'Comprobando servicios…' }
  return { tono: 'ok', texto: 'Servicios en línea' }
}

/**
 * Salud del sistema en la cabecera: un solo indicador con el peor estado de
 * los tres microservicios. Al pasar el cursor o con el foco se abre el
 * detalle de cada uno (puerto, latencia medida en cada sondeo y modelo), y
 * el tooltip de cada fila conserva lo técnico (OCR, bandas de confianza,
 * reglas RCV activas). El contrato de /health no cambia.
 */
export default function SystemHealth({ health, reglas = [] }) {
  const servicios = SERVICIOS.map((s) => {
    const estado = health?.[s.key]
    return { s, estado, tono: tonoServicio(estado), puerto: PUERTOS[s.key] || s.puerto }
  })
  const general = resumen(servicios)
  return (
    <div className={`health health--${general.tono}`} tabIndex={0} aria-label={`Estado del sistema: ${general.texto}`}>
      <span className={`status-dot status-dot--${general.tono}`} aria-hidden="true" />
      <span className="health-resumen">{general.texto}</span>
      <ul className="health-detalle" aria-label="Estado de los microservicios">
        {servicios.map(({ s, estado, tono, puerto }) => {
          const modelo = s.key === 'ai' ? modeloCorto(estado?.payload?.motor_inferencia?.modelo_requerido) : null
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
    </div>
  )
}
