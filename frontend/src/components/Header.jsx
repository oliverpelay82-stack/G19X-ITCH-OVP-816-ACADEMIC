import { Moon, RefreshCw, Sun } from 'lucide-react'
import { SERVICIOS } from '../constants.js'

/** Une el estado de un servicio en el texto del tooltip. */
function descripcionServicio(servicio, estado) {
  if (!estado?.online) {
    return `${servicio.nombre} (:${servicio.puerto}) · sin respuesta — el resto del sistema sigue operando`
  }
  const bd = estado.payload?.conexion_bd
  const partes = [`${servicio.nombre} (:${servicio.puerto}) · en línea`, `latencia ${estado.latencia} ms`]
  if (bd !== undefined) partes.push(bd ? 'PostgreSQL conectado' : 'PostgreSQL sin conexión')
  return partes.join(' · ')
}

/**
 * Barra superior fija: título de la sección activa, monitor en vivo de los
 * tres microservicios con su latencia, recarga manual y cambio de tema.
 */
export default function Header({ titulo, descripcion, health, onRefresh, refrescando, isDark, onToggleTheme }) {
  return (
    <header className="app-header">
      <div className="app-header-titles">
        <h1 className="app-header-title">{titulo}</h1>
        <p className="app-header-desc">{descripcion}</p>
      </div>

      <div className="app-header-tools">
        <div className="health-monitor" role="group" aria-label="Estado de los microservicios">
          {SERVICIOS.map((s) => {
            const estado = health[s.key]
            const online = Boolean(estado?.online)
            const degradado = online && estado?.payload?.conexion_bd === false
            const tono = !online ? 'off' : degradado ? 'warn' : 'ok'
            return (
              <span
                key={s.key}
                className={`health-pill health-pill--${tono}`}
                data-tooltip={descripcionServicio(s, estado)}
                tabIndex={0}
              >
                <span className={`pulse-dot pulse-dot--${tono}`} aria-hidden="true" />
                <span className="health-pill-name">{s.corto}</span>
                <span className="health-pill-latency mono">{online ? `${estado.latencia}ms` : '—'}</span>
              </span>
            )
          })}
        </div>

        <button
          type="button"
          className="icon-button"
          onClick={onRefresh}
          disabled={refrescando}
          data-tooltip="Actualizar datos"
          aria-label="Actualizar datos"
        >
          <RefreshCw size={16} strokeWidth={2.3} className={refrescando ? 'spin' : ''} />
        </button>

        <button
          type="button"
          className="theme-switch"
          onClick={onToggleTheme}
          role="switch"
          aria-checked={isDark}
          data-tooltip={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
          aria-label={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'}
        >
          <span className="theme-switch-track">
            <span className="theme-switch-thumb">
              {isDark ? <Moon size={12} strokeWidth={2.5} /> : <Sun size={12} strokeWidth={2.5} />}
            </span>
          </span>
        </button>
      </div>
    </header>
  )
}
