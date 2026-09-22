import { useContext } from 'react'
import { ToastContext } from '../components/toast-context.js'

/** Acceso a las notificaciones flotantes desde cualquier componente. */
export default function useToast() {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast debe usarse dentro de <ToastProvider>')
  return ctx
}
