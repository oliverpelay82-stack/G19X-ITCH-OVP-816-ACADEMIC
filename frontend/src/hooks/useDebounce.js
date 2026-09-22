import { useEffect, useState } from 'react'

/**
 * Devuelve el valor solo después de que haya dejado de cambiar durante
 * `delay` milisegundos. Se usa en los buscadores para no recalcular el
 * filtrado en cada pulsación de tecla.
 */
export default function useDebounce(value, delay = 250) {
  const [diferido, setDiferido] = useState(value)

  useEffect(() => {
    const id = setTimeout(() => setDiferido(value), delay)
    return () => clearTimeout(id)
  }, [value, delay])

  return diferido
}
