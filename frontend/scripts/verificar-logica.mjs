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

// Contexto no seguro (la interfaz abierta por IP, sin HTTPS): el navegador no
// ofrece crypto.randomUUID. Se simula antes de cargar los módulos.
Object.defineProperty(globalThis.crypto, 'randomUUID', { value: undefined, configurable: true })

const { idAleatorio } = await import('../src/utils/id.js')

function archivos(dir) {
  return readdirSync(dir).flatMap((nombre) => {
    const ruta = join(dir, nombre)
    return statSync(ruta).isDirectory() ? archivos(ruta) : /\.(jsx?|mjs)$/.test(nombre) ? [ruta] : []
  })
}

const CASOS = [
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
