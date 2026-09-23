import { SERVICIOS } from '../constants.js'

const NAV_ITEMS = [
  { id: 'titulares', label: 'Empresas' },
  { id: 'expedientes', label: 'Expedientes' },
  { id: 'boveda', label: 'Bóveda' },
  { id: 'reglas', label: 'Reglas' },
]

/** Tono del punto de salud: apagado, degradado (sin BD) o en línea. */
function tonoServicio(estado) {
  if (!estado?.online) return 'off'
  return estado.payload?.conexion_bd === false ? 'warn' : 'ok'
}

/**
 * Barra lateral fija: marca, navegación principal y estado en vivo de los
 * tres microservicios con su latencia medida.
 */
export default function Sidebar({ tabActiva, onTabChange, health, contadores }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">PluriOne</div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {NAV_ITEMS.map((item) => {
          const activo = tabActiva === item.id
          const total = contadores?.[item.id]
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activo ? 'is-active' : ''}`}
              onClick={() => onTabChange(item.id)}
              aria-current={activo ? 'page' : undefined}
            >
              <span>{item.label}</span>
              {total !== undefined && <span className="nav-count mono">{total}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-services">
        <p className="sidebar-label">Servicios</p>
        {SERVICIOS.map((s) => {
          const estado = health[s.key]
          const tono = tonoServicio(estado)
          return (
            <div className="service-row" key={s.key} title={`${s.nombre} (:${s.puerto}) · ${s.alcance}`}>
              <span className={`status-dot status-dot--${tono}`} aria-hidden="true" />
              <span className="service-name">{s.corto}</span>
              <span className="service-latency mono">{estado?.online ? `${estado.latencia}ms` : 'offline'}</span>
            </div>
          )
        })}
      </div>
    </aside>
  )
}
