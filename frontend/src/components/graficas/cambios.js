/** Cambios del semáforo por día a partir de la bitácora (V4). Sin React: se prueba aparte. */
import { diaLocal } from '../../utils/format.js'

export const DIAS = 30
export const LIMITE = 500 // máximo del API de la bitácora
const RANGO = { NO_CONFORME: 0, EN_REVISION: 1, CONFORME: 2 }
// La apertura de un expediente fija su primer semáforo: no es una mejora ni un deterioro.
const SIN_TENDENCIA = new Set(['APERTURA_EXPEDIENTE'])

/** AAAA-MM-DD de una fecha en hora local. */
function claveDia(fecha) {
  const d = new Date(fecha.getTime() - fecha.getTimezoneOffset() * 60000)
  return d.toISOString().slice(0, 10)
}

export const diaCorto = (clave) => {
  const [a, m, d] = clave.split('-').map(Number)
  return new Date(a, m - 1, d).toLocaleDateString('es-MX', { day: 'numeric', month: 'short' }).replace('.', '')
}

/**
 * El evento cambió de verdad el semáforo: dos estados válidos y distintos, y no
 * es la apertura del expediente. La gráfica y la lista de últimos cambios usan
 * esta misma regla, para que nunca se contradigan.
 */
export function esCambioDeTendencia(evento) {
  const { estado_anterior: antes, estado_nuevo: despues, causa } = evento.detalle || {}
  return !SIN_TENDENCIA.has(causa) && antes in RANGO && despues in RANGO && antes !== despues
}

/** Cambios de semáforo por día: hacia mejor arriba, hacia peor abajo (RN-02, bitácora RF-27). */
export function agruparCambios(eventos, hoy = new Date()) {
  const dias = []
  for (let i = DIAS - 1; i >= 0; i -= 1) {
    const d = new Date(hoy)
    d.setDate(d.getDate() - i)
    dias.push({ dia: claveDia(d), mejoras: 0, deterioros: 0 })
  }
  const porDia = new Map(dias.map((d) => [d.dia, d]))
  for (const e of eventos) {
    if (!esCambioDeTendencia(e)) continue
    const { estado_anterior: antes, estado_nuevo: despues } = e.detalle
    const fila = porDia.get(diaLocal(e.creado_en))
    if (!fila) continue
    if (RANGO[despues] > RANGO[antes]) fila.mejoras += 1
    else fila.deterioros -= 1
  }
  return dias
}
