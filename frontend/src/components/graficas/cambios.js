/** Cambios del semáforo por día a partir de la bitácora (V4). Sin React: se prueba aparte. */

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
    const { estado_anterior: antes, estado_nuevo: despues, causa } = e.detalle || {}
    if (SIN_TENDENCIA.has(causa) || !(antes in RANGO) || !(despues in RANGO) || antes === despues) continue
    const fila = porDia.get(String(e.creado_en).slice(0, 10))
    if (!fila) continue
    if (RANGO[despues] > RANGO[antes]) fila.mejoras += 1
    else fila.deterioros -= 1
  }
  return dias
}
