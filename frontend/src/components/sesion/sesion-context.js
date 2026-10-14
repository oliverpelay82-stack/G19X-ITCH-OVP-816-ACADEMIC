import { createContext } from 'react'

/**
 * Contexto de la sesión (Módulo 7). Vive en su propio módulo para que
 * `SesionProvider.jsx` exporte únicamente componentes y el refresco rápido de
 * Vite siga funcionando.
 */
export const SesionContext = createContext(null)
