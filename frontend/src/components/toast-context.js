import { createContext } from 'react'

/**
 * Contexto de las notificaciones flotantes. Vive en su propio módulo para que
 * `ToastProvider.jsx` exporte únicamente componentes y el refresco rápido de
 * Vite siga funcionando.
 */
export const ToastContext = createContext(null)
