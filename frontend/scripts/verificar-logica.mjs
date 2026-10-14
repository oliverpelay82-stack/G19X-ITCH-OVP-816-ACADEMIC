/**
 * Pruebas de la lógica sin React del frontend (src/utils/), con Node y sin
 * dependencias. Cada caso protege una corrección contra su regresión.
 *
 * Uso: npm run test:ui (desde frontend/), que la corre después de la prueba de
 * equivalencia del marcado.
 */
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const SRC = fileURLToPath(new URL('../src', import.meta.url))

// Las fechas se prueban en la zona de México: en UTC (la de la CI), leer una
// hora sin zona como local o como UTC da lo mismo y el error no se vería.
process.env.TZ = 'America/Mexico_City'

// Contexto no seguro (la interfaz abierta por IP, sin HTTPS): el navegador no
// ofrece crypto.randomUUID. Se simula antes de cargar los módulos.
Object.defineProperty(globalThis.crypto, 'randomUUID', { value: undefined, configurable: true })

const { idAleatorio } = await import('../src/utils/id.js')
const { aFecha, diaLocal, formatRelativo } = await import('../src/utils/format.js')
const { agruparCambios } = await import('../src/components/graficas/cambios.js')
const { valorTrasCarga } = await import('../src/utils/carga.js')

/** Marca de tiempo como la devuelve la API: UTC sin zona, con microsegundos. */
const comoApi = (fecha) => `${fecha.toISOString().slice(0, -1)}123`

function archivos(dir) {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre)
    return statSync(ruta).isDirectory() ? archivos(ruta) : /\.(jsx?|mjs)$/.test(nombre) ? [ruta] : []
  })
}

const CASOS = [
  {
    nombre: 'Una hora del backend sin zona se lee como UTC',
    probar: () =>
      aFecha('2026-10-14T15:00:00.123456').toISOString() === '2026-10-14T15:00:00.123Z' &&
      aFecha('2026-10-14T15:00:00+00:00').toISOString() === '2026-10-14T15:00:00.000Z' &&
      aFecha('2026-10-01').toISOString() === '2026-10-01T00:00:00.000Z',
  },
  {
    nombre: 'Las 03:30 UTC del 15 de octubre son el 14 en México',
    probar: () => diaLocal('2026-10-15T03:30:00.000001') === '2026-10-14' && diaLocal('') === '',
  },
  {
    nombre: '«hace 2 h» para un evento de hace dos horas (no «hace instantes»)',
    probar: () =>
      formatRelativo(comoApi(new Date(Date.now() - 2 * 3600e3))) === 'hace 2 h' &&
      formatRelativo(comoApi(new Date())) === 'hace instantes',
  },
  {
    nombre: 'La tendencia del semáforo cuenta un cambio de las 21:30 en su día local',
    probar: () => {
      const evento = {
        creado_en: '2026-10-15T03:30:00.000001',
        detalle: { estado_anterior: 'EN_REVISION', estado_nuevo: 'CONFORME', causa: 'DICTAMEN_IA' },
      }
      const dias = agruparCambios([evento], new Date(2026, 9, 14, 23, 0))
      return dias.find((d) => d.dia === '2026-10-14')?.mejoras === 1
    },
  },
  {
    nombre: 'Una lista que no llegó conserva la anterior (también las reglas)',
    probar: () => {
      const previo = [{ id: 'r1' }]
      return (
        valorTrasCarga({ status: 'rejected', reason: new Error('caído') }, previo) === previo &&
        valorTrasCarga({ status: 'fulfilled', value: null }, previo).length === 0 &&
        readFileSync(join(SRC, 'App.jsx'), 'utf8').includes('setReglas((previo) => valorTrasCarga(r, previo))')
      )
    },
  },
  {
    nombre: 'Los espaciados de las hojas de estilo usan la escala --s-* (sin 4, 6, 8, 10… px escritos)',
    probar: () => {
      const declaracion = /^\s*(?:padding|margin|gap|row-gap|column-gap)[a-z-]*\s*:([^;]*);/gm
      const enEscala = /(?<![-0-9.])(4|6|8|10|12|16|20|24|32|40)px\b/
      const hojas = readdirSync(join(SRC, 'styles')).map((h) => join(SRC, 'styles', h))
      const literales = [join(SRC, 'index.css'), ...hojas].flatMap((ruta) =>
        [...readFileSync(ruta, 'utf8').matchAll(declaracion)]
          .filter((m) => enEscala.test(m[1]))
          .map((m) => `${relative(SRC, ruta)}: ${m[0].trim()}`)
      )
      for (const l of literales) console.log(`          ${l}`)
      return literales.length === 0
    },
  },
  {
    nombre: 'idAleatorio funciona sin crypto.randomUUID (HTTP sin SSL)',
    probar: () => {
      const a = idAleatorio()
      const b = idAleatorio()
      return /^[0-9a-f]{16}$/.test(a) && a !== b
    },
  },
  {
    nombre: 'Ningún componente llama a crypto.randomUUID (usar utils/id.js)',
    probar: () => {
      const usos = archivos(SRC).filter((ruta) => readFileSync(ruta, 'utf8').includes('randomUUID('))
      for (const ruta of usos) console.log(`          ${relative(SRC, ruta)}`)
      return usos.length === 0
    },
  },
]

let fallos = 0
for (const caso of CASOS) {
  let ok = false
  try {
    ok = caso.probar()
  } catch (err) {
    console.log(`          ${err?.message || err}`)
  }
  if (!ok) fallos += 1
  console.log(`${ok ? 'OK      ' : 'FALLA   '}  ${caso.nombre}`)
}
console.log(`\n${CASOS.length - fallos} de ${CASOS.length} pruebas de lógica`)
process.exit(fallos ? 1 : 0)
