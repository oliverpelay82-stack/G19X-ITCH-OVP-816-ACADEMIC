import { useCallback, useEffect, useState } from 'react'
import { flushSync } from 'react-dom'
import { reducirMovimiento } from '../utils/movimiento.js'

/** Duración del cambio de tema: el triple de --dur-slow (240 ms), como en index.css. */
const DURACION_TEMA = 720

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

  // Cambio de tema con View Transitions: el tema nuevo se revela en un
  // círculo que nace del botón pulsado y cubre la pantalla, mientras lo que
  // queda del tema anterior pasa por un atardecer (o un amanecer) en
  // index.css. Sin la API o con «reducir movimiento», el cambio es instantáneo.
  const toggleTheme = useCallback((evento) => {
    const raiz = document.documentElement
    const siguiente = raiz.getAttribute('data-theme') === 'dark' ? 'light' : 'dark'
    const aplicar = () => {
      raiz.setAttribute('data-theme', siguiente)
      flushSync(() => setTheme(siguiente))
    }
    if (typeof document.startViewTransition !== 'function' || reducirMovimiento()) {
      aplicar()
      return
    }
    // Centro del círculo: el botón pulsado (o la esquina superior derecha).
    const caja = evento?.currentTarget?.getBoundingClientRect?.()
    const x = caja ? caja.left + caja.width / 2 : window.innerWidth - 40
    const y = caja ? caja.top + caja.height / 2 : 30
    const radio = Math.hypot(Math.max(x, window.innerWidth - x), Math.max(y, window.innerHeight - y))

    raiz.dataset.transicionTema = siguiente === 'dark' ? 'anochecer' : 'amanecer'
    const transicion = document.startViewTransition(aplicar)
    transicion.ready.then(() => {
      raiz.animate(
        { clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radio}px at ${x}px ${y}px)`] },
        { duration: DURACION_TEMA, easing: 'cubic-bezier(0.65, 0, 0.35, 1)', pseudoElement: '::view-transition-new(root)' }
      )
    })
    transicion.finished.finally(() => delete raiz.dataset.transicionTema)
  }, [])

  return { theme, setTheme, toggleTheme, isDark: theme === 'dark' }
}
