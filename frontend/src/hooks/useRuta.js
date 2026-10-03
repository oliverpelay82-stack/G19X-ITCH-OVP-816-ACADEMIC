import { useCallback, useEffect, useRef, useState } from 'react'
import { conTransicion } from '../utils/movimiento.js'

/**
 * Navegación en la URL con hash, sin dependencias: #/expedientes,
 * #/expedientes/EXP-…-001 (el expediente desplegado), #/empresas,
 * #/empresas/<RFC> (el detalle de la empresa), #/boveda,
 * #/alertas, #/reportes y #/reglas. Recargar conserva la vista y un enlace
 * lleva directo a un expediente. #/ui queda reservado al catálogo del sistema
 * de diseño en desarrollo (src/dev/RaizDesarrollo.jsx).
 */
const SECCION_POR_RUTA = {
  empresas: 'titulares',
  expedientes: 'expedientes',
  boveda: 'boveda',
  alertas: 'alertas',
  reportes: 'reportes',
  reglas: 'reglas',
}
// Secciones con detalle en el segundo segmento: el folio del expediente o el RFC de la empresa.
const CON_DETALLE = new Set(['expedientes', 'titulares'])
const RUTA_POR_SECCION = Object.fromEntries(Object.entries(SECCION_POR_RUTA).map(([ruta, s]) => [s, ruta]))

/** Pantalla de inicio: Expedientes, el centro operativo del sistema. */
const SECCION_INICIO = 'expedientes'

function leer() {
  const [segmento = '', folio = ''] = window.location.hash.replace(/^#\/?/, '').split('/')
  const seccion = SECCION_POR_RUTA[segmento] || SECCION_INICIO
  return { seccion, folio: CON_DETALLE.has(seccion) && folio ? decodeURIComponent(folio) : null }
}

const hashDe = (seccion, folio) =>
  `#/${RUTA_POR_SECCION[seccion] || RUTA_POR_SECCION[SECCION_INICIO]}${folio ? `/${encodeURIComponent(folio)}` : ''}`

/**
 * [ruta, ir]: ruta = { seccion, folio }, donde `folio` es el detalle abierto
 * (folio del expediente o RFC de la empresa); ir(seccion, folio, { reemplazar })
 * navega. Con `reemplazar`, la entrada del historial se sustituye (abrir o
 * plegar un expediente no debe llenar el botón «Atrás»).
 *
 * Cambiar de sección (no de detalle) funde la vista saliente con la nueva
 * (`conTransicion`, shell.css); abrir o plegar un expediente no la anima.
 */
export default function useRuta() {
  const [ruta, setRuta] = useState(leer)
  const seccionActual = useRef(ruta.seccion)

  const aplicar = useCallback(() => {
    const nueva = leer()
    const cambiaSeccion = nueva.seccion !== seccionActual.current
    seccionActual.current = nueva.seccion
    if (cambiaSeccion) conTransicion(() => setRuta(nueva))
    else setRuta(nueva)
  }, [])

  useEffect(() => {
    window.addEventListener('hashchange', aplicar)
    return () => window.removeEventListener('hashchange', aplicar)
  }, [aplicar])

  const ir = useCallback((seccion, folio = null, { reemplazar = false } = {}) => {
    const destino = hashDe(seccion, folio)
    if (destino === window.location.hash) return
    if (reemplazar) {
      window.history.replaceState(null, '', destino)
      aplicar()
    } else {
      window.location.hash = destino
    }
  }, [aplicar])

  return [ruta, ir]
}
