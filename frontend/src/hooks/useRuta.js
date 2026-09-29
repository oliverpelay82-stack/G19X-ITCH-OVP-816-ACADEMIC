import { useCallback, useEffect, useState } from 'react'

/**
 * Navegación en la URL con hash, sin dependencias: #/expedientes,
 * #/expedientes/EXP-…-001 (el expediente desplegado), #/empresas, #/boveda,
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
const RUTA_POR_SECCION = Object.fromEntries(Object.entries(SECCION_POR_RUTA).map(([ruta, s]) => [s, ruta]))

/** Pantalla de inicio: Expedientes, el centro operativo del sistema. */
export const SECCION_INICIO = 'expedientes'

function leer() {
  const [segmento = '', folio = ''] = window.location.hash.replace(/^#\/?/, '').split('/')
  const seccion = SECCION_POR_RUTA[segmento] || SECCION_INICIO
  return { seccion, folio: seccion === 'expedientes' && folio ? decodeURIComponent(folio) : null }
}

export const hashDe = (seccion, folio) =>
  `#/${RUTA_POR_SECCION[seccion] || RUTA_POR_SECCION[SECCION_INICIO]}${folio ? `/${encodeURIComponent(folio)}` : ''}`

/**
 * [ruta, ir]: ruta = { seccion, folio }; ir(seccion, folio, { reemplazar })
 * navega. Con `reemplazar`, la entrada del historial se sustituye (abrir o
 * plegar un expediente no debe llenar el botón «Atrás»).
 */
export default function useRuta() {
  const [ruta, setRuta] = useState(leer)

  useEffect(() => {
    const alCambiar = () => setRuta(leer())
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [])

  const ir = useCallback((seccion, folio = null, { reemplazar = false } = {}) => {
    const destino = hashDe(seccion, folio)
    if (destino === window.location.hash) return
    if (reemplazar) {
      window.history.replaceState(null, '', destino)
      setRuta(leer())
    } else {
      window.location.hash = destino
    }
  }, [])

  return [ruta, ir]
}
