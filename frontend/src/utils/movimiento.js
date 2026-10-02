import { flushSync } from 'react-dom'

/**
 * Preferencia del sistema «reducir movimiento». Las animaciones CSS ya la
 * respetan (index.css); las que se hacen desde JavaScript (conteo de cifras,
 * indicador deslizante, fundido del tema, salidas y desplazamientos) la
 * consultan aquí y no corren.
 */
export function reducirMovimiento() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}

/** Duraciones y curva del sistema, iguales a --dur, --dur-slow y --ease (index.css). */
export const DURACION = 150
export const DURACION_LENTA = 240
export const CURVA = 'cubic-bezier(0.2, 0, 0, 1)'

/**
 * Salida animada de un elemento que React ya está desmontando: deja en su
 * lugar una copia inerte con `clase` (la animación de salida, en CSS) y la
 * retira al terminar. Así el modal se desvanece sin que cada vista tenga que
 * retrasar su cierre. La copia no recibe foco ni clics, y conserva el
 * desplazamiento y lo escrito en los campos para que no parpadee.
 */
export function animarSalida(nodo, clase, duracion = DURACION) {
  if (!nodo || reducirMovimiento()) return
  const copia = nodo.cloneNode(true)
  const campos = nodo.querySelectorAll('input, textarea, select')
  copia.querySelectorAll('input, textarea, select').forEach((campo, i) => {
    campo.value = campos[i]?.value ?? campo.value
  })
  copia.removeAttribute('id')
  copia.setAttribute('inert', '')
  copia.setAttribute('aria-hidden', 'true')
  copia.classList.add(clase)
  const desplazamiento = nodo.scrollTop
  // Se decide tras el commit: si el nodo sigue en el documento no hubo cierre
  // (el doble montaje de StrictMode en desarrollo) y no se agrega la copia.
  queueMicrotask(() => {
    if (nodo.isConnected) return
    document.body.appendChild(copia)
    copia.scrollTop = desplazamiento
    const retirar = () => copia.remove()
    copia.addEventListener('animationend', (e) => e.target === copia && retirar())
    window.setTimeout(retirar, duracion + 150) // respaldo si la animación no llega a correr
  })
}

/**
 * Cambio de vista con fundido (View Transitions API del navegador): la vista
 * saliente se desvanece mientras entra la nueva. Sin soporte del navegador o
 * con «reducir movimiento», el cambio es inmediato.
 */
export function conTransicion(cambio) {
  if (typeof document === 'undefined' || !document.startViewTransition || reducirMovimiento()) {
    cambio()
    return
  }
  try {
    document.startViewTransition(() => flushSync(cambio))
  } catch {
    cambio()
  }
}
