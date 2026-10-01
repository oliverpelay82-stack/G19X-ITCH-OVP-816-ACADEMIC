import { useEffect, useState } from 'react'
import { ChevronRight, Moon, RefreshCw, Sun } from 'lucide-react'
import SystemHealth from './SystemHealth.jsx'
import { IconButton } from './ui/index.js'

/** Si la página está desplazada: la cabecera fija marca entonces su borde con una sombra fina. */
function useDesplazado() {
  const [desplazado, setDesplazado] = useState(false)
  useEffect(() => {
    const revisar = () => setDesplazado(window.scrollY > 0)
    revisar()
    window.addEventListener('scroll', revisar, { passive: true })
    return () => window.removeEventListener('scroll', revisar)
  }, [])
  return desplazado
}

/** Antigüedad de los datos a la vista, en palabras; se recalcula cada 5 s. */
function Actualizado({ momento }) {
  const [ahora, setAhora] = useState(() => Date.now())
  useEffect(() => {
    const id = setInterval(() => setAhora(Date.now()), 5000)
    return () => clearInterval(id)
  }, [])
  if (!momento) return null
  const segundos = Math.max(0, Math.round((ahora - momento) / 1000))
  const texto =
    segundos < 10 ? 'Actualizado ahora' : segundos < 60 ? `Actualizado hace ${segundos} s` : `Actualizado hace ${Math.round(segundos / 60)} min`
  return (
    <span className="actualizado tabular" title={new Date(momento).toLocaleTimeString('es-MX')}>
      {texto}
    </span>
  )
}

/**
 * Cabecera ejecutiva: migas navegables (Cumplimiento › Sección), título H1,
 * la franja de salud de los tres microservicios y las acciones globales en
 * micro-squircles (refrescar y tema).
 */
export default function Header({
  titulo,
  migas = [],
  onNavigate,
  health,
  reglas,
  onRefresh,
  refrescando,
  actualizado,
  isDark,
  onToggleTheme,
}) {
  const desplazado = useDesplazado()
  // useTheme marca la raíz mientras dura la transición del tema.
  const claseIcono = typeof document !== 'undefined' && document.documentElement.dataset.transicionTema ? 'icono-tema' : undefined
  return (
    <header className={desplazado ? 'app-header is-desplazado' : 'app-header'}>
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

        <Actualizado momento={actualizado} />

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
          {/* La clave nueva vuelve a montar el icono y, solo durante el cambio de
              tema (no al cargar la página), gira al entrar. */}
          {isDark ? <Sun key="sol" size={15} className={claseIcono} /> : <Moon key="luna" size={15} className={claseIcono} />}
        </IconButton>
      </div>
    </header>
  )
}
