import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/** Elementos que pueden recibir el foco con Tab dentro del panel. */
const ENFOCABLES = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled]):not([type="hidden"])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function enfocables(panel) {
  return [...panel.querySelectorAll(ENFOCABLES)].filter((el) => el.getClientRects().length > 0)
}

/**
 * Modal genérico: cierra con Escape o clic en el velo, bloquea el scroll
 * de fondo y lleva el foco al panel al abrirse.
 *
 * Accesibilidad (WCAG 2.1.2 y 2.4.3): Tab y Shift+Tab recorren solo los
 * controles del panel (trampa de foco) y, al cerrarse, el foco vuelve al
 * elemento que lo abrió.
 *
 * El efecto se monta una sola vez y lee `onClose` desde una referencia: los
 * consumidores pasan funciones nuevas en cada render, y reejecutarlo con cada
 * tecla devolvía el foco al panel mientras se escribía en un campo.
 *
 * Se monta en un portal sobre <body> a propósito: un ancestro animado con
 * transform establecería un bloque contenedor que dejaría el velo
 * `position: fixed` recortado al tamaño de la pestaña.
 *
 * `size`: 'md' para formularios, 'lg' para el detalle de un documento, 'xl' con el visor.
 * `acciones`: controles de la cabecera junto al botón de cerrar (p. ej. navegación).
 */
export default function Modal({ title, subtitle, onClose, children, footer, size = 'md', acciones }) {
  const panel = useRef(null)
  const cerrar = useRef(onClose)

  useEffect(() => {
    cerrar.current = onClose
  })

  useEffect(() => {
    const origen = document.activeElement

    const alPulsar = (e) => {
      if (e.key === 'Escape') {
        cerrar.current()
        return
      }
      if (e.key !== 'Tab' || !panel.current) return
      const lista = enfocables(panel.current)
      if (lista.length === 0) {
        e.preventDefault()
        panel.current.focus()
        return
      }
      const primero = lista[0]
      const ultimo = lista[lista.length - 1]
      const dentro = panel.current.contains(document.activeElement)
      if (e.shiftKey && (!dentro || document.activeElement === primero || document.activeElement === panel.current)) {
        e.preventDefault()
        ultimo.focus()
      } else if (!e.shiftKey && (!dentro || document.activeElement === ultimo)) {
        e.preventDefault()
        primero.focus()
      }
    }

    document.addEventListener('keydown', alPulsar)
    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()
    return () => {
      document.removeEventListener('keydown', alPulsar)
      document.body.style.overflow = overflowPrevio
      if (origen instanceof HTMLElement && origen.isConnected) origen.focus()
    }
  }, [])

  return createPortal(
    <div className="modal-overlay" onMouseDown={() => cerrar.current()}>
      <div
        className={`modal modal--${size}`}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panel}
      >
        <header className="modal-header">
          <div className="modal-heading">
            <h3 className="modal-title">{title}</h3>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <div className="modal-acciones">
            {acciones}
            <button type="button" className="icon-button icon-button--sm" onClick={() => cerrar.current()} aria-label="Cerrar">
              <X size={16} />
            </button>
          </div>
        </header>

        <div className="modal-body">{children}</div>
        {footer}
      </div>
    </div>,
    document.body
  )
}
