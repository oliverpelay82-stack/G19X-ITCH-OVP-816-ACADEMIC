/**
 * Genera src/components/iconos.js: los iconos de Phosphor que usa la interfaz,
 * solo con los pesos que se usan.
 *
 * Cada icono del paquete trae sus seis pesos (thin, light, regular, bold, fill
 * y duotone) aunque la vista use uno; con decenas de iconos eso sumaba unos
 * 27 KB comprimidos al paquete principal. El módulo generado reutiliza el
 * IconBase de Phosphor (mismo SVG, mismas props) con un mapa de pesos recortado.
 *
 * Qué entra:
 *   - los nombres importados de `iconos.js` en src/ (o, al migrar, de
 *     '@phosphor-icons/react');
 *   - el peso regular de cada uno, más los pesos que su archivo menciona en una
 *     prop `weight` (p. ej. weight={activo ? 'duotone' : 'regular'}).
 *
 * Además, como hacía Lucide, un icono sin `aria-label` sale con aria-hidden: es
 * decorativo y lo nombra el texto o la etiqueta de su control.
 *
 * Uso (desde frontend/): npm run iconos            regenera el módulo
 *                        npm run iconos -- --verificar  código 1 si está desactualizado
 */
import { readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { join, relative } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const RAIZ = fileURLToPath(new URL('..', import.meta.url))
const SRC = join(RAIZ, 'src')
const DESTINO = join(SRC, 'components', 'iconos.js')
const DEFS = join(RAIZ, 'node_modules', '@phosphor-icons', 'react', 'dist', 'defs')
const PESOS = ['thin', 'light', 'regular', 'bold', 'fill', 'duotone']

const IMPORTACION = /import\s*\{([^}]*)\}\s*from\s*'(?:@phosphor-icons\/react|(?:\.{1,2}\/)+(?:components\/)?iconos\.js)'/g
const PROP_PESO = /weight=(?:"([a-z]+)"|\{([^}]*)\})/g

function archivos(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? archivos(join(dir, e.name)) : /\.jsx?$/.test(e.name) ? [join(dir, e.name)] : []
  )
}

/** Nombre del icono -> pesos que necesita. */
function iconosUsados() {
  const usados = new Map()
  for (const ruta of archivos(SRC)) {
    if (ruta === DESTINO) continue
    const codigo = readFileSync(ruta, 'utf8')
    const nombres = [...codigo.matchAll(IMPORTACION)].flatMap((m) =>
      m[1].split(',').map((n) => n.trim()).filter(Boolean)
    )
    if (!nombres.length) continue
    const pesos = new Set(['regular'])
    for (const m of codigo.matchAll(PROP_PESO)) {
      const texto = m[1] ?? m[2]
      for (const p of PESOS) if (new RegExp(`\\b${p}\\b`).test(texto)) pesos.add(p)
    }
    for (const n of nombres) {
      if (!usados.has(n)) usados.set(n, new Set())
      for (const p of pesos) usados.get(n).add(p)
    }
  }
  return new Map([...usados].sort(([a], [b]) => a.localeCompare(b)))
}

async function trazos(nombre, peso) {
  const { default: pesos } = await import(pathToFileURL(join(DEFS, `${nombre}.es.js`)).href)
  const fragmento = pesos.get(peso)
  const hijos = [fragmento.props.children].flat().filter(Boolean)
  return hijos.map((h) => {
    if (h.type !== 'path') throw new Error(`${nombre} (${peso}): elemento <${h.type}> no previsto`)
    return h.props
  })
}

async function generar() {
  const lineas = [
    '// Generado por scripts/generar-iconos.mjs (npm run iconos): no editar a mano.',
    '// Iconos de Phosphor con solo los pesos que usa la interfaz.',
    "import { createElement as h, forwardRef } from 'react'",
    "import IconBase from '@phosphor-icons/react/dist/lib/IconBase'",
    '',
    'function icono(nombre, pesos) {',
    '  const weights = new Map(',
    '    Object.entries(pesos).map(([peso, trazos]) => [peso, trazos.map((t, i) => h(\'path\', { key: i, ...t }))])',
    '  )',
    '  const Icono = forwardRef(function Icono({ weight, ...props }, ref) {',
    '    return h(IconBase, {',
    '      ref,',
    "      'aria-hidden': props['aria-label'] ? undefined : true,",
    '      ...props,',
    "      weight: weights.has(weight) ? weight : 'regular',",
    '      weights,',
    '    })',
    '  })',
    '  Icono.displayName = nombre',
    '  return Icono',
    '}',
    '',
  ]
  for (const [nombre, pesos] of iconosUsados()) {
    const partes = []
    for (const peso of PESOS.filter((p) => pesos.has(p))) {
      partes.push(`${peso}: ${JSON.stringify(await trazos(nombre, peso))}`)
    }
    lineas.push(`export const ${nombre} = icono('${nombre}', { ${partes.join(', ')} })`)
  }
  return lineas.join('\n') + '\n'
}

const contenido = await generar()
const actual = (() => {
  try {
    return readFileSync(DESTINO, 'utf8')
  } catch {
    return ''
  }
})()
const destino = relative(RAIZ, DESTINO)
if (process.argv.includes('--verificar')) {
  if (actual !== contenido) {
    console.error(`${destino} está desactualizado: ejecuta npm run iconos.`)
    process.exit(1)
  }
  console.log(`${destino} al día.`)
} else {
  writeFileSync(DESTINO, contenido)
  console.log(`${destino}: ${contenido.match(/^export const/gm)?.length ?? 0} iconos.`)
}
