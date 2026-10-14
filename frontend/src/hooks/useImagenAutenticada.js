import { useEffect, useState } from 'react'
import { getPaginaDocumento } from '../services/api.js'

/**
 * Imagen que exige la sesión (Módulo 7): un <img src> no puede enviar el token
 * Bearer, así que la imagen se pide con fetch y se muestra desde una URL de
 * objeto, que se libera al cambiar de imagen o al desmontar. Una petición vieja
 * se cancela para que la página anterior no aparezca tarde.
 *
 * Devuelve { src, error } de la `url` pedida; con `url` nula, nada.
 */
export default function useImagenAutenticada(url) {
  const [estado, setEstado] = useState({ url: null, src: null, error: false })

  useEffect(() => {
    if (!url) return undefined
    const control = new AbortController()
    let objeto = null
    getPaginaDocumento(url, control.signal)
      .then((blob) => {
        objeto = URL.createObjectURL(blob)
        setEstado({ url, src: objeto, error: false })
      })
      .catch((err) => {
        if (err?.name !== 'AbortError') setEstado({ url, src: null, error: true })
      })
    return () => {
      control.abort()
      if (objeto) URL.revokeObjectURL(objeto)
    }
  }, [url])

  return estado.url === url ? estado : { src: null, error: false }
}
