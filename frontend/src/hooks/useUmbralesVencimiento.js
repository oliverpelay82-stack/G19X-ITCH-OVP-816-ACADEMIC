import { useCallback, useEffect, useState } from 'react'
import { getUmbralesVencimiento } from '../services/api.js'

/** Los de omisión del core (UMBRALES_ALERTA_VENCIMIENTO): se muestran mientras llega la respuesta. */
export const UMBRALES_OMISION = [30, 15, 5]

const INICIAL = { umbrales: UMBRALES_OMISION, configurado: false }

/**
 * Días de anticipación de las alertas de vencimiento (HU-14): los usan el detalle
 * de RCV-01 en Reglas y las franjas de la gráfica de vencimientos. Si el core no
 * responde, quedan los de omisión. `recargar` los vuelve a pedir tras un cambio.
 */
export default function useUmbralesVencimiento() {
  const [estado, setEstado] = useState(INICIAL)

  const recargar = useCallback(() => getUmbralesVencimiento().then(setEstado), [])

  useEffect(() => {
    let vigente = true
    getUmbralesVencimiento()
      .then((datos) => vigente && setEstado(datos))
      .catch(() => {})
    return () => {
      vigente = false
    }
  }, [])

  return { ...estado, recargar }
}
