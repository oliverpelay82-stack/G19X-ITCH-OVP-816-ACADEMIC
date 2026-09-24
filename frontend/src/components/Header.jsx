import { ChevronRight, Moon, RefreshCw, Sun } from 'lucide-react'
import { SERVICIOS } from '../constants.js'

/** Tono del punto de salud: apagado, degradado (sin BD o sin capacidades) o en línea. */
function tonoServicio(estado) {
  if (!estado?.online) return 'off'
  const p = estado.payload
  if (p?.conexion_bd === false || p?.capacidades_operativas === false) return 'warn'
  return 'ok'
}

function detalleServicio(servicio, estado, tono) {
  if (tono === 'off') return `${servicio.nombre} sin respuesta`
  const base = `${servicio.nombre} · ${estado.latencia} ms`
  return tono === 'warn' ? `${base} · degradado` : base
}

/**
 * Barra superior: migas de la jerarquía (ancestros navegables), título de la
 * sección, estado en vivo de los tres microservicios y acciones globales.
 */
export default function Header({ titulo, migas = [], onNavigate, health, onRefresh, refrescando, isDark, onToggleTheme }) {
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
                    {!ultima && <ChevronRight size={12} strokeWidth={2} aria-hidden="true" />}
                  </li>
                )
              })}
            </ol>
          </nav>
        )}
        <h1 className="app-title">{titulo}</h1>
      </div>

      <div className="app-header-tools">
        <ul className="service-badges" aria-label="Estado de los microservicios">
          {SERVICIOS.map((s) => {
            const estado = health?.[s.key]
            const tono = tonoServicio(estado)
            return (
              <li key={s.key} className={`service-badge service-badge--${tono}`} data-tooltip={detalleServicio(s, estado, tono)}>
                <span className={`live-dot live-dot--${tono}`} aria-hidden="true" />
                <span className="service-badge-name">{s.etiqueta}</span>
                <span className="service-badge-port tabular">:{s.puerto}</span>
              </li>
            )
          })}
        </ul>

        <span className="header-divider" aria-hidden="true" />

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
