import { useEffect, useState } from 'react'
import { DURACION_LENTA, reducirMovimiento } from '../utils/movimiento.js'

/**
 * Presencia con salida animada: al ocultarse, el contenido sigue montado
 * `duracion` ms con `saliendo = true` (la clase de salida la pone quien lo
 * usa) y después se desmonta. Si vuelve a mostrarse durante la salida, se
 * queda. Con «reducir movimiento» se desmonta de inmediato.
 */
export default function usePresencia(visible, duracion = DURACION_LENTA) {
  const [montado, setMontado] = useState(visible)
  const [saliendo, setSaliendo] = useState(false)

  if (visible && (!montado || saliendo)) {
    setMontado(true)
    setSaliendo(false)
  } else if (!visible && montado && !saliendo) {
    if (reducirMovimiento()) setMontado(false)
    else setSaliendo(true)
  }

  useEffect(() => {
    if (!saliendo) return undefined
    const temporizador = window.setTimeout(() => {
      setMontado(false)
      setSaliendo(false)
    }, duracion)
    return () => window.clearTimeout(temporizador)
  }, [saliendo, duracion])

  return { montado, saliendo }
}
