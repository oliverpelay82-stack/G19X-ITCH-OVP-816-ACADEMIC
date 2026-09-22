import { useCallback, useMemo, useRef, useState } from 'react'
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from 'lucide-react'
import { ToastContext } from './toast-context.js'

const ICONOS = {
  exito: CheckCircle2,
  error: XCircle,
  alerta: AlertTriangle,
  info: Info,
}

const DURACION = { exito: 3200, info: 3200, alerta: 4600, error: 5600 }

/**
 * Notificaciones flotantes de la esquina inferior derecha.
 * Se consumen con `const toast = useToast()` y luego
 * `toast.exito('Titular registrado')`.
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
    // Se marca como saliente para dejar correr la animación antes de quitarlo.
    setToasts((prev) => prev.map((x) => (x.id === id ? { ...x, saliendo: true } : x)))
    setTimeout(() => setToasts((prev) => prev.filter((x) => x.id !== id)), 220)
  }, [])

  const mostrar = useCallback(
    (tipo, titulo, detalle) => {
      siguienteId.current += 1
      const id = siguienteId.current
      setToasts((prev) => [...prev.slice(-3), { id, tipo, titulo, detalle, saliendo: false }])
      const temporizador = setTimeout(() => cerrar(id), DURACION[tipo] || 3600)
      temporizadores.current.set(id, temporizador)
      return id
    },
    [cerrar]
  )

  const api = useMemo(
    () => ({
      exito: (titulo, detalle) => mostrar('exito', titulo, detalle),
      error: (titulo, detalle) => mostrar('error', titulo, detalle),
      alerta: (titulo, detalle) => mostrar('alerta', titulo, detalle),
      info: (titulo, detalle) => mostrar('info', titulo, detalle),
      cerrar,
    }),
    [mostrar, cerrar]
  )

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="toast-stack" role="region" aria-label="Notificaciones">
        {toasts.map((t) => {
          const Icono = ICONOS[t.tipo] || Info
          return (
            <div
              key={t.id}
              className={`toast toast--${t.tipo} ${t.saliendo ? 'toast--saliendo' : ''}`}
              role={t.tipo === 'error' ? 'alert' : 'status'}
            >
              <span className="toast-icon">
                <Icono size={17} strokeWidth={2.4} />
              </span>
              <div className="toast-body">
                <p className="toast-title">{t.titulo}</p>
                {t.detalle && <p className="toast-detail">{t.detalle}</p>}
              </div>
              <button type="button" className="toast-close" onClick={() => cerrar(t.id)} aria-label="Cerrar aviso">
                <X size={14} strokeWidth={2.5} />
              </button>
            </div>
          )
        })}
      </div>
    </ToastContext.Provider>
  )
}
