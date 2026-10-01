import { BellRing, Building2, FileBarChart2, FolderKanban, Scale, ShieldCheck, Vault } from 'lucide-react'

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
    label: 'Auditoría',
    items: [
      { id: 'alertas', label: 'Alertas', icon: BellRing },
      { id: 'reportes', label: 'Reportes', icon: FileBarChart2 },
    ],
  },
  {
    label: 'Configuración',
    items: [{ id: 'reglas', label: 'Reglas', icon: Scale }],
  },
]

/** Versión del motor que se muestra en el pie (catálogo DOC-05). */
const VERSION = 'Versión 1.0.0'

/**
 * Barra lateral esbelta: isotipo en micro-squircle, navegación agrupada en
 * versales y el ítem activo como tarjeta blanca elevada. Solo Alertas lleva
 * conteo, porque es lo único que pide acción; en tono de advertencia si hay
 * alertas críticas o altas.
 */
export default function Sidebar({ tabActiva, onTabChange, contadores }) {
  return (
    <aside className="sidebar">
      <div className="sidebar-brand">
        <span className="squircle squircle--lg squircle--brand" aria-hidden="true">
          <ShieldCheck size={16} />
        </span>
        <div className="brand-text">
          <span className="brand-name">PluriOne</span>
          <span className="brand-sub">Motor de Cumplimiento</span>
        </div>
      </div>

      <nav className="sidebar-nav" aria-label="Navegación principal">
        {GRUPOS.map((grupo) => (
          <div className="nav-group" key={grupo.label}>
            <p className="sidebar-label">{grupo.label}</p>
            {grupo.items.map(({ id, label, icon: Icono }) => {
              const activo = tabActiva === id
              const contador = contadores?.[id]
              return (
                <button
                  key={id}
                  type="button"
                  className={`nav-item ${activo ? 'is-active' : ''}`}
                  onClick={() => onTabChange(id)}
                  aria-current={activo ? 'page' : undefined}
                >
                  <span className="squircle" aria-hidden="true">
                    <Icono size={16} />
                  </span>
                  <span className="nav-label">{label}</span>
                  {contador?.total > 0 && (
                    <span className={contador.tono ? `nav-count nav-count--${contador.tono} tabular` : 'nav-count tabular'}>
                      {contador.total}
                    </span>
                  )}
                </button>
              )
            })}
          </div>
        ))}
      </nav>

      <div className="sidebar-foot">
        <span className="version-badge">{VERSION}</span>
      </div>
    </aside>
  )
}
