import { Building2, FolderKanban, Scale, ShieldCheck, Vault } from 'lucide-react'

const GRUPOS = [
  {
    label: 'Cumplimiento',
    items: [
      { id: 'titulares', label: 'Empresas', icon: Building2 },
      { id: 'expedientes', label: 'Expedientes', icon: FolderKanban },
      { id: 'boveda', label: 'Bóveda', icon: Vault },
    ],
  },
  {
    label: 'Configuración',
    items: [{ id: 'reglas', label: 'Reglas', icon: Scale }],
  },
]

/**
 * Barra lateral delgada: marca y navegación agrupada con iconos discretos,
 * indicador de sección activa y el conteo de registros de cada vista.
 */
export default function Sidebar({ tabActiva, onTabChange, contadores }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="brand-mark" aria-hidden="true">
          <ShieldCheck size={14} strokeWidth={2} />
        </span>
        <div className="brand-text">
          <span className="brand-name">PluriOne</span>
          <span className="brand-sub">Motor de validación</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {GRUPOS.map((grupo) => (
          <div className="nav-group" key={grupo.label}>
            <p className="sidebar-label">{grupo.label}</p>
            {grupo.items.map(({ id, label, icon: Icono }) => {
              const activo = tabActiva === id
              const total = contadores?.[id]
              return (
                <button
                  key={id}
                  type="button"
                  className={`nav-item ${activo ? 'is-active' : ''}`}
                  onClick={() => onTabChange(id)}
                  aria-current={activo ? 'page' : undefined}
                >
                  <Icono size={15} strokeWidth={1.75} className="nav-icon" aria-hidden="true" />
                  <span className="nav-label">{label}</span>
                  {total !== undefined && <span className="nav-count tabular">{total}</span>}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      <p className="sidebar-foot">DOC-05 · Pipeline de 5 niveles</p>
    </aside>
  )
}
