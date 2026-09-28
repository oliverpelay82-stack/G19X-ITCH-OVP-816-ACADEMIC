/**
 * Prueba de equivalencia del sistema de diseño (src/components/ui/).
 *
 * Renderiza en el servidor, con el mismo Vite del proyecto, cada caso de
 * equivalencia-ui.jsx: el marcado actual de una vista y el componente que lo
 * reemplaza. El HTML debe ser idéntico (con los atributos de cada etiqueta
 * en orden alfabético), salvo los atributos de accesibilidad que los
 * componentes añaden a propósito, que se listan en la salida.
 *
 * Complementa a scripts/regresion_visual.py: esa prueba compara píxeles de
 * lo que ya está en pantalla; esta demuestra que un componente genera las
 * mismas clases antes de que una vista lo adopte.
 *
 * Uso: npm run test:ui (desde frontend/).
 */
import { fileURLToPath } from 'node:url'
import { createServer } from 'vite'
import { renderToStaticMarkup } from 'react-dom/server'

// Atributos que un componente puede añadir sin cambiar lo que se ve.
const ACCESIBILIDAD = [
  / aria-busy="true"/g,
  / aria-invalid="true"/g,
  / aria-describedby="[^"]*"/g,
  / id="[^"]*-(ayuda|retro)"/g,
]

/** Ordena los atributos de cada etiqueta para comparar HTML sin depender del orden de las props. */
function normalizar(html) {
  return html.replace(/<([a-z][a-z0-9]*)((?:\s+[a-z:-]+(?:="[^"]*")?)*)\s*(\/?)>/gi, (_, tag, attrs, cierre) => {
    const lista = attrs.match(/[a-z:-]+(?:="[^"]*")?/gi) || []
    return `<${tag}${lista.length ? ' ' + lista.sort().join(' ') : ''}${cierre}>`
  })
}

function quitarAccesibilidad(html) {
  const anadidos = []
  let limpio = html
  for (const patron of ACCESIBILIDAD) {
    limpio = limpio.replace(patron, (m) => {
      anadidos.push(m.trim())
      return ''
    })
  }
  return { limpio, anadidos }
}

const servidor = await createServer({
  root: fileURLToPath(new URL('..', import.meta.url)),
  server: { middlewareMode: true },
  appType: 'custom',
  logLevel: 'error',
})

let fallos = 0
try {
  const { CASOS } = await servidor.ssrLoadModule('/scripts/equivalencia-ui.jsx')
  for (const caso of CASOS) {
    const actual = normalizar(renderToStaticMarkup(caso.actual))
    const { limpio, anadidos } = quitarAccesibilidad(renderToStaticMarkup(caso.nuevo))
    const nuevo = normalizar(limpio)
    if (actual === nuevo) {
      console.log(`IGUAL     ${caso.nombre}${anadidos.length ? `  (+ ${anadidos.join(', ')})` : ''}`)
    } else {
      fallos++
      console.log(`DISTINTO  ${caso.nombre}\n  actual: ${actual}\n  nuevo:  ${nuevo}`)
    }
  }
  console.log(`\n${CASOS.length - fallos} de ${CASOS.length} casos equivalentes`)
} finally {
  await servidor.close()
}
process.exit(fallos ? 1 : 0)
