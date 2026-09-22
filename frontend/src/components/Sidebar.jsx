import { Building2, FolderKanban, Scale, ShieldCheck, Vault } from 'lucide-react'
import { SERVICIOS } from '../constants.js'

const NAV_ITEMS = [
  { id: 'titulares', label: 'Empresas', icon: Building2, hint: 'Titulares de expediente' },
  { id: 'expedientes', label: 'Expedientes', icon: FolderKanban, hint: 'Fólders de cumplimiento' },
  { id: 'boveda', label: 'Bóveda Digital', icon: Vault, hint: 'Custodia criptográfica' },
  { id: 'reglas', label: 'Reglas', icon: Scale, hint: 'Catálogo normativo' },
]

/**
 * Barra lateral fija: identidad corporativa, navegación principal y detalle
 * en vivo de los tres microservicios con su latencia medida.
 */
export default function Sidebar({ tabActiva, onTabChange, health, contadores }) {
  const enLinea = SERVICIOS.filter((s) => health[s.key]?.online).length

  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="sidebar-logo">
          <ShieldCheck size={19} strokeWidth={2.3} />
        </span>
        <span className="sidebar-titles">
          <span className="sidebar-title">PluriOne</span>
          <span className="sidebar-subtitle">Motor de Cumplimiento</span>
        </span>
      </div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        <span className="sidebar-section-label">Operación</span>
        {NAV_ITEMS.map((item) => {
          const activo = tabActiva === item.id
          const total = contadores?.[item.id]
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-item ${activo ? 'nav-item--active' : ''}`}
              onClick={() => onTabChange(item.id)}
              aria-current={activo ? 'page' : undefined}
            >
              <span className="nav-item-glow" aria-hidden="true" />
              <item.icon size={17} strokeWidth={2.2} className="nav-item-icon" />
              <span className="nav-item-label">
                {item.label}
                <small>{item.hint}</small>
              </span>
              {total !== undefined && <span className="nav-item-count mono">{total}</span>}
            </button>
          )
        })}
      </nav>

      <div className="sidebar-footer">
        <div className="service-panel">
          <div className="service-panel-head">
            <span className="sidebar-section-label">Microservicios</span>
            <span className="mono service-panel-count">{enLinea}/{SERVICIOS.length}</span>
          </div>

          {SERVICIOS.map((s) => {
            const estado = health[s.key]
            const online = Boolean(estado?.online)
            const degradado = online && estado?.payload?.conexion_bd === false
            const tono = !online ? 'off' : degradado ? 'warn' : 'ok'
            return (
              <div className="service-row" key={s.key}>
                <span className={`pulse-dot pulse-dot--${tono}`} aria-hidden="true" />
                <span className="service-row-body">
                  <span className="service-row-name">{s.corto}</span>
                  <span className="service-row-scope">{s.alcance}</span>
                </span>
                <span className={`service-row-state service-row-state--${tono}`}>
                  {online ? <span className="mono">{estado.latencia}ms</span> : 'Offline'}
                </span>
              </div>
            )
          })}
        </div>

        <div className="compliance-note">
          <ShieldCheck size={13} strokeWidth={2.4} />
          <span>
            Bóveda NOM-151-SCFI-2016
            <small>Huella SHA-256 inmutable</small>
          </span>
        </div>
      </div>
    </aside>
  )
}
