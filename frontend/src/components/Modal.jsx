import { useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { X } from 'lucide-react'

/**
 * Modal genérico: cierra con Escape o clic en el velo, bloquea el scroll
 * de fondo y lleva el foco al panel al abrirse.
 *
 * Se monta en un portal sobre <body> a propósito: un ancestro animado con
 * transform establecería un bloque contenedor que dejaría el velo
 * `position: fixed` recortado al tamaño de la pestaña.
 *
 * `size`: 'md' para formularios, 'lg' para el detalle de un documento.
 */
export default function Modal({ title, subtitle, onClose, children, footer, size = 'md' }) {
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
          <button type="button" className="icon-button icon-button--sm" onClick={onClose} aria-label="Cerrar">
            <X size={15} strokeWidth={2} />
          </button>
        </header>

        <div className="modal-body">{children}</div>
        {footer}
      </div>
    </div>,
    document.body
  )
}
