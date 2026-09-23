import { Moon, RefreshCw, Sun } from 'lucide-react'

/** Barra superior: título de la sección activa, recarga manual y cambio de tema. */
export default function Header({ titulo, onRefresh, refrescando, isDark, onToggleTheme }) {
  return (
    <header className="app-header">
      <h1 className="app-title">{titulo}</h1>

      <div className="app-header-tools">
        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          disabled={refrescando}
          data-tooltip="Actualizar datos"
          aria-label="Actualizar datos"
        >
          <RefreshCw size={15} strokeWidth={2} className={refrescando ? 'spin' : ''} />
        </button>

        <button
          type="button"
          className="icon-button"
          onClick={onToggleTheme}
          role="switch"
          aria-checked={isDark}
          data-tooltip={isDark ? 'Modo claro' : 'Modo oscuro'}
          aria-label={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
        >
          {isDark ? <Sun size={15} strokeWidth={2} /> : <Moon size={15} strokeWidth={2} />}
        </button>
      </div>
    </header>
  )
}
