import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { LucideProvider } from 'lucide-react'
import { ToastProvider } from './components/ToastProvider.jsx'
import App from './App.jsx'
import './index.css'

// Trazo fino por defecto para toda la iconografía (1.5 px). Un icono solo lo
// sobrescribe con 1.75 cuando es muy pequeño y necesita legibilidad.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <LucideProvider strokeWidth={1.5}>
      <ToastProvider>
        <App />
      </ToastProvider>
    </LucideProvider>
  </StrictMode>
)
