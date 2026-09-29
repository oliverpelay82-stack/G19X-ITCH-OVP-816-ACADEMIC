import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { LucideProvider } from 'lucide-react'
import { ToastProvider } from './components/ToastProvider.jsx'
import App from './App.jsx'
import './index.css'

// Con `npm run dev` la raíz añade el catálogo del sistema de diseño en #/ui. El
// único acceso a ese código es el import() de la rama DEV: en el build de
// producción la condición es false, Vite elimina la rama completa y ni el
// catálogo ni su enrutador llegan al bundle (un import estático no basta: el
// módulo se conservaría aunque no se usara). El árbol se repite en cada rama a
// propósito, para que el código de producción sea idéntico al de antes del
// catálogo, byte a byte.
//
// Trazo fino por defecto para toda la iconografía (1.5 px). Un icono solo lo
// sobrescribe con 1.75 cuando es muy pequeño y necesita legibilidad.
if (import.meta.env.DEV) {
  import('./dev/RaizDesarrollo.jsx').then(({ default: RaizDesarrollo }) =>
    createRoot(document.getElementById('root')).render(
      <StrictMode>
        <LucideProvider strokeWidth={1.5}>
          <ToastProvider>
            <RaizDesarrollo />
          </ToastProvider>
        </LucideProvider>
      </StrictMode>
    )
  )
} else {
  createRoot(document.getElementById('root')).render(
    <StrictMode>
      <LucideProvider strokeWidth={1.5}>
        <ToastProvider>
          <App />
        </ToastProvider>
      </LucideProvider>
    </StrictMode>
  )
}
