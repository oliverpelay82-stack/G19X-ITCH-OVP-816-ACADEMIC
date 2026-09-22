import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/**
 * Modal genérico: cierra con Escape o clic en el velo, bloquea el scroll
 * de fondo y lleva el foco al panel al abrirse.
 *
 * Se monta en un portal sobre <body> a propósito. Las pestañas se animan con
 * `fade-up`, y un ancestro con una animación de transform establece un bloque
 * contenedor que dejaría el velo `position: fixed` recortado al tamaño de la
 * pestaña en vez de cubrir toda la ventana.
 */
export default function Modal({ title, subtitle, icon: Icon, onClose, children, width = 540, footer }) {
  const panel = useRef(null)

  useEffect(() => {
    const alPulsar = (e) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', alPulsar)
    const overflowPrevio = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    panel.current?.focus()
    return () => {
      document.removeEventListener('keydown', alPulsar)
      document.body.style.overflow = overflowPrevio
    }
  }, [onClose])

  return createPortal(
    <div className="modal-overlay" onMouseDown={onClose}>
      <div
        className="modal-panel"
        style={{ maxWidth: width }}
        onMouseDown={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-label={title}
        tabIndex={-1}
        ref={panel}
      >
        <header className="modal-header">
          {Icon && (
            <span className="modal-icon">
              <Icon size={17} strokeWidth={2.3} />
            </span>
          )}
          <div className="modal-heading">
            <h3 className="modal-title">{title}</h3>
            {subtitle && <p className="modal-subtitle">{subtitle}</p>}
          </div>
          <button type="button" className="icon-button" onClick={onClose} aria-label="Cerrar">
            <X size={16} strokeWidth={2.4} />
          </button>
        </header>

        <div className="modal-body">{children}</div>
        {footer}
      </div>
    </div>,
    document.body
  )
}
