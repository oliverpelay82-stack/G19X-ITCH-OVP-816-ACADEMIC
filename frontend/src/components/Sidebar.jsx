import { ShieldCheck, Building2, FolderKanban, Vault, Scale, Lock, Cpu } from 'lucide-react'

const NAV_ITEMS = [
  { id: 'titulares', label: 'Empresas', icon: Building2 },
  { id: 'expedientes', label: 'Expedientes', icon: FolderKanban },
  { id: 'boveda', label: 'Bóveda Digital', icon: Vault },
  { id: 'reglas', label: 'Reglas', icon: Scale },
]

/**
 * Barra lateral izquierda fija: branding corporativo, navegación vertical
 * principal y estado en vivo de conectividad con PostgreSQL.
 */
export default function Sidebar({ tabActiva, onTabChange, backendOnline }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <div className="sidebar-logo">
          <ShieldCheck size={20} strokeWidth={2.25} />
        </div>
        <div className="sidebar-titles">
          <span className="sidebar-title">PluriOne</span>
          <span className="sidebar-subtitle">Motor de Cumplimiento</span>
        </div>
      </div>

      <nav className="sidebar-nav">
        <span className="sidebar-nav-label">Navegación</span>
        {NAV_ITEMS.map((item) => (
          <button
            key={item.id}
            type="button"
            className={`sidebar-nav-item ${tabActiva === item.id ? 'sidebar-nav-item--active' : ''}`}
            onClick={() => onTabChange(item.id)}
          >
            <item.icon size={18} strokeWidth={2.25} />
            {item.label}
          </button>
        ))}
      </nav>

      <div className="sidebar-footer">
        <div className="sidebar-status-card">
          <span className={`status-pill ${backendOnline ? 'status-pill--ok' : 'status-pill--off'}`}>
            <span className={`status-dot ${backendOnline ? 'status-dot--ok' : 'status-dot--off'}`} />
            {backendOnline ? 'PostgreSQL 17 Conectado' : 'Backend Desconectado'}
          </span>

          <div className="sidebar-status-row">
            <Lock size={13} strokeWidth={2.25} className="sidebar-status-icon" />
            <span className="sidebar-status-label">Bóveda Criptográfica</span>
            <span className="sidebar-status-value sidebar-status-value--accent">NOM-151 Ready</span>
          </div>

          <div className="sidebar-status-row">
            <Cpu size={13} strokeWidth={2.25} className="sidebar-status-icon" />
            <span className="sidebar-status-label">Motor de Validación</span>
            <span className="sidebar-status-value">v1.0</span>
          </div>
        </div>
      </div>
    </aside>
  )
}
