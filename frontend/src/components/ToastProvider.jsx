import { useCallback, useMemo, useRef, useState } from 'react'
import { X } from './iconos.js'
import { ToastContext } from './toast-context.js'

/** Las notificaciones se retiran solas a los 4 segundos; las que ofrecen «Deshacer», a los 6. */
const DURACION = 4000
const DURACION_CON_ACCION = 6000

/** Duración del fundido de salida; debe coincidir con --dur en el CSS. */
const SALIDA = 150

/**
 * Notificaciones flotantes de la esquina inferior derecha.
 * Se consumen con `const toast = useToast()` y luego
 * `toast.exito('Titular registrado')`. Un cambio reversible ofrece su acción:
 * `toast.exito('Regla pausada', detalle, { accion: { etiqueta: 'Deshacer', alHacer } })`.
 * Mientras el puntero o el foco están sobre el aviso, no se retira.
 */
export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const temporizadores = useRef(new Map())
  const siguienteId = useRef(0)

  const cerrar = useCallback((id) => {
    const t = temporizadores.current.get(id)
    if (t) {
      clearTimeout(t)
      temporizadores.current.delete(id)
    }
    // Se marca como saliente para dejar correr el fundido antes de quitarlo.
    setToasts((prev) => prev.map((x) => (x.id === id ? { ...x, saliendo: true } : x)))
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), SALIDA)
  }, [])

  const programar = useCallback(
    (id, duracion) => {
      clearTimeout(temporizadores.current.get(id))
      temporizadores.current.set(id, setTimeout(() => cerrar(id), duracion))
    },
    [cerrar]
  )

  const mostrar = useCallback(
    (tipo, titulo, detalle, { accion } = {}) => {
      siguienteId.current += 1
      const id = siguienteId.current
      const duracion = accion ? DURACION_CON_ACCION : DURACION
      setToasts((prev) => [...prev.slice(-3), { id, tipo, titulo, detalle, accion, duracion, saliendo: false }])
      programar(id, duracion)
      return id
    },
    [programar]
  )

  // Leer o alcanzar «Deshacer» no debe ser una carrera contra el reloj (WCAG 2.2.1).
  const pausar = (id) => clearTimeout(temporizadores.current.get(id))

  const api = useMemo(
    () => ({
      exito: (titulo, detalle, opciones) => mostrar('exito', titulo, detalle, opciones),
      error: (titulo, detalle, opciones) => mostrar('error', titulo, detalle, opciones),
      alerta: (titulo, detalle, opciones) => mostrar('alerta', titulo, detalle, opciones),
      info: (titulo, detalle, opciones) => mostrar('info', titulo, detalle, opciones),
      cerrar,
    }),
    [mostrar, cerrar]
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="region" aria-label="Notificaciones">
        {toasts.map((t) => (
          <div
            key={t.id}
            className={`toast toast--${t.tipo} ${t.saliendo ? 'is-leaving' : ''}`}
            role={t.tipo === 'error' ? 'alert' : 'status'}
            onMouseEnter={() => pausar(t.id)}
            onMouseLeave={() => programar(t.id, t.duracion)}
            onFocus={() => pausar(t.id)}
            onBlur={() => programar(t.id, t.duracion)}
          >
            <span className="toast-dot" aria-hidden="true" />
            <div className="toast-body">
              <p className="toast-title">{t.titulo}</p>
              {t.detalle && <p className="toast-detail">{t.detalle}</p>}
            </div>
            {t.accion && (
              <button
                type="button"
                className="toast-accion"
                onClick={() => {
                  cerrar(t.id)
                  t.accion.alHacer()
                }}
              >
                {t.accion.etiqueta}
              </button>
            )}
            <button type="button" className="toast-close" onClick={() => cerrar(t.id)} aria-label="Cerrar aviso">
              <X size={14} />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}
