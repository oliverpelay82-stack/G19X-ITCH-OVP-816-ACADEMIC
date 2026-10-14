import { useState } from 'react'
import { BellRinging, Buildings, ChartBar, FolderOpen, ListChecks, Vault } from './iconos.js'
import LogoMotor from './LogoMotor.jsx'

// Iconos del menú en peso regular y duotone en el ítem activo.
const GRUPOS = [
  {
    label: 'Cumplimiento',
    items: [
      { id: 'titulares', label: 'Empresas', icon: Buildings },
      { id: 'expedientes', label: 'Expedientes', icon: FolderOpen },
      { id: 'boveda', label: 'Bóveda', icon: Vault },
    ],
  },
  {
    label: 'Auditoría',
    items: [
      { id: 'alertas', label: 'Alertas', icon: BellRinging },
      { id: 'reportes', label: 'Reportes', icon: ChartBar },
    ],
  },
  {
    label: 'Configuración',
    items: [{ id: 'reglas', label: 'Reglas', icon: ListChecks }],
  },
]

/**
 * Conteo del menú. Cuando cambia (no al cargar la primera vez) late una sola
 * vez: la clave nueva remonta el elemento y repite la animación (shell.css).
 */
function Contador({ total, tono }) {
  const [previo, setPrevio] = useState(total)
  const [latidos, setLatidos] = useState(0)
  if (previo !== total) {
    setPrevio(total)
    setLatidos((n) => n + 1)
  }
  return (
    <span key={latidos} className={`nav-count${tono ? ` nav-count--${tono}` : ''} tabular${latidos ? ' is-latido' : ''}`}>
      {total}
    </span>
  )
}

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
          <LogoMotor size={16} />
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
                    <Icono size={16} weight={activo ? 'duotone' : 'regular'} />
                  </span>
                  <span className="nav-label">{label}</span>
                  {contador?.total > 0 && <Contador total={contador.total} tono={contador.tono} />}
                </button>
              )
            })}
          </div>
        ))}
      </nav>
    </aside>
  )
}
