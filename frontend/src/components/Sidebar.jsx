import { useState } from 'react'
import { BellRing, Building2, FileBarChart2 } from 'lucide-react'
import { IconoBoveda, IconoExpediente, IconoReglas } from './IconosMotor.jsx'
import LogoMotor from './LogoMotor.jsx'

const GRUPOS = [
  {
    label: 'Cumplimiento',
    items: [
      { id: 'titulares', label: 'Empresas', icon: Building2 },
      { id: 'expedientes', label: 'Expedientes', icon: IconoExpediente },
      { id: 'boveda', label: 'Bóveda', icon: IconoBoveda },
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
    items: [{ id: 'reglas', label: 'Reglas', icon: IconoReglas }],
  },
]

/** Versión del motor que se muestra en el pie (catálogo DOC-05). */
const VERSION = 'Versión 1.0.0'

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
                    <Icono size={16} />
                  </span>
                  <span className="nav-label">{label}</span>
                  {contador?.total > 0 && <Contador total={contador.total} tono={contador.tono} />}
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
