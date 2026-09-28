import { ChevronRight, Moon, RefreshCw, Sun } from 'lucide-react'
import SystemHealth from './SystemHealth.jsx'
import { IconButton } from './ui/index.js'

/**
 * Cabecera ejecutiva: migas navegables (Cumplimiento › Sección), título H1,
 * la franja de salud de los tres microservicios y las acciones globales en
 * micro-squircles (refrescar y tema).
 */
export default function Header({ titulo, migas = [], onNavigate, health, reglas, onRefresh, refrescando, isDark, onToggleTheme }) {
  return (
    <header className="app-header">
      <div className="app-header-heading">
        {migas.length > 0 && (
          <nav className="breadcrumbs" aria-label="Ruta">
            <ol>
              {migas.map((m, i) => {
                const ultima = i === migas.length - 1
                return (
                  <li key={m.label}>
                    {ultima || !m.id ? (
                      <span aria-current={ultima ? 'page' : undefined}>{m.label}</span>
                    ) : (
                      <button type="button" onClick={() => onNavigate(m.id)}>
                        {m.label}
                      </button>
                    )}
                    {!ultima && <ChevronRight size={12} aria-hidden="true" />}
                  </li>
                )
              })}
            </ol>
          </nav>
        )}
        <h1 className="app-title">{titulo}</h1>
      </div>

      <div className="app-header-tools">
        <SystemHealth health={health} reglas={reglas} />

        <span className="header-divider" aria-hidden="true" />

        <IconButton etiqueta="Actualizar datos" tooltip ocupado={refrescando} onClick={onRefresh} disabled={refrescando}>
          <RefreshCw size={15} className="refresh-icon" />
        </IconButton>

        <IconButton
          etiqueta={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
          data-tooltip={isDark ? 'Modo claro' : 'Modo oscuro'}
          onClick={onToggleTheme}
          role="switch"
          aria-checked={!isDark}
        >
          {isDark ? <Sun size={15} /> : <Moon size={15} />}
        </IconButton>
      </div>
    </header>
  )
}
