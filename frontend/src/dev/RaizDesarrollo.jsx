import { lazy, Suspense, useEffect, useState } from 'react'
import App from '../App.jsx'

const CatalogoUI = lazy(() => import('./CatalogoUI.jsx'))

/**
 * Raíz de la aplicación en desarrollo: la misma App, más el catálogo del
 * sistema de diseño en #/ui. main.jsx solo la usa cuando import.meta.env.DEV
 * es verdadero; en producción no se importa en ningún sitio y Vite la elimina
 * del bundle junto con el catálogo.
 */
export default function RaizDesarrollo() {
  const [ruta, setRuta] = useState(window.location.hash)
  useEffect(() => {
    const alCambiar = () => setRuta(window.location.hash)
    window.addEventListener('hashchange', alCambiar)
    return () => window.removeEventListener('hashchange', alCambiar)
  }, [])
  if (ruta !== '#/ui') return <App />
  return (
    <Suspense fallback={null}>
      <CatalogoUI />
    </Suspense>
  )
}
