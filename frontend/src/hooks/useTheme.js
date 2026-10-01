import { useCallback, useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { reducirMovimiento } from '../utils/movimiento.js'

// v2: el rediseño White & Warm hace del tema claro el predeterminado.
const STORAGE_KEY = 'plurione-theme-v2'

/** Lee el tema ya resuelto por el script de arranque de index.html. */
function temaInicial() {
  if (typeof document === 'undefined') return 'light'
  const actual = document.documentElement.getAttribute('data-theme')
  if (actual === 'dark' || actual === 'light') return actual
  try {
    const guardado = localStorage.getItem(STORAGE_KEY)
    if (guardado === 'dark' || guardado === 'light') return guardado
  } catch {
    /* almacenamiento bloqueado: se usa el tema por defecto */
  }
  return 'light'
}

/**
 * Tema persistente de la aplicación. El valor se escribe en
 * `document.documentElement[data-theme]`, que es lo que leen los tokens CSS,
 * y se guarda en localStorage para que sobreviva a la recarga.
 */
export default function useTheme() {
  const [theme, setTheme] = useState(temaInicial)

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    try {
      localStorage.setItem(STORAGE_KEY, theme)
    } catch {
      /* modo privado o almacenamiento lleno: el tema solo dura la sesión */
    }
  }, [theme])

  // Fundido entre temas con View Transitions (index.css fija su duración):
  // el tema se aplica dentro de la transición, junto con el icono del botón.
  // Sin la API o con «reducir movimiento», el cambio es instantáneo.
  const toggleTheme = useCallback(() => {
    const siguiente = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
    const aplicar = () => {
      document.documentElement.setAttribute('data-theme', siguiente)
      flushSync(() => setTheme(siguiente))
    }
    if (typeof document.startViewTransition === 'function' && !reducirMovimiento()) {
      document.startViewTransition(aplicar)
    } else {
      aplicar()
    }
  }, [])

  return { theme, setTheme, toggleTheme, isDark: theme === 'dark' }
}
