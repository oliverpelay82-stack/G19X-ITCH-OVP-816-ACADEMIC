import { useEffect, useState } from 'react'
import { getHealthAi, getHealthCore, getHealthRules } from '../../services/api.js'

const INTERVALO_MS = 30000

/** Lo que dice el indicador según cuántos servicios respondieron. */
function estadoDe(enLinea) {
  if (enLinea === null) return { tono: 'neutral', texto: 'Comprobando servicios…' }
  if (enLinea === 3) return { tono: 'ok', texto: 'Servicios en línea' }
  if (enLinea === 0) return { tono: 'bad', texto: 'Sin conexión con el servidor' }
  return { tono: 'warn', texto: 'Servicio parcial' }
}

/**
 * Indicador de la esquina de la pantalla de acceso: consulta de verdad la salud
 * de los tres servicios (rutas públicas) al abrir y cada 30 s. «Conexión cifrada»
 * solo aparece si la página llegó por HTTPS: el TLS del despliegue (RNF-05) lo
 * pone el proxy de PluriOne, no la aplicación.
 */
export default function EstadoServicios() {
  const [enLinea, setEnLinea] = useState(null)

  useEffect(() => {
    let vigente = true
    const sondear = async () => {
      const resultados = await Promise.allSettled([getHealthCore(), getHealthRules(), getHealthAi()])
      if (vigente) setEnLinea(resultados.filter((r) => r.status === 'fulfilled').length)
    }
    sondear()
    const id = setInterval(sondear, INTERVALO_MS)
    return () => {
      vigente = false
      clearInterval(id)
    }
  }, [])

  const { tono, texto } = estadoDe(enLinea)
  const cifrada = typeof window !== 'undefined' && window.location.protocol === 'https:'
  return (
    <p className={`acceso-estado acceso-estado--${tono}`} role="status">
      <span className="acceso-estado-punto" aria-hidden="true" />
      {texto}
      {cifrada && <span className="acceso-estado-extra"> · Conexión cifrada</span>}
    </p>
  )
}
