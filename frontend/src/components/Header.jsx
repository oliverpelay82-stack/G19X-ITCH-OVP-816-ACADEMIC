import { useEffect, useState } from 'react'
import { ArrowsClockwise, CaretRight, MagnifyingGlass, Moon, Sun } from './iconos.js'
import SystemHealth from './SystemHealth.jsx'
import MenuUsuario from './sesion/MenuUsuario.jsx'
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

// Lo que dura a la vista la confirmación de «Actualizar datos».
const AVISO_ACTUALIZADO_MS = 3000

/**
 * Confirmación breve de «Actualizar datos»: aparece al terminar y se desvanece.
 * El espacio queda reservado para que los botones no se muevan.
 */
function Actualizado({ momento }) {
  // Último momento cuya confirmación ya se desvaneció.
  const [vencido, setVencido] = useState(null)
  useEffect(() => {
    if (!momento) return undefined
    const id = setTimeout(() => setVencido(momento), AVISO_ACTUALIZADO_MS)
    return () => clearTimeout(id)
  }, [momento])
  const visible = Boolean(momento) && vencido !== momento
  return (
    <span className={visible ? 'actualizado is-visible' : 'actualizado'} aria-hidden={!visible}>
      Actualizado ahora
    </span>
  )
}

/**
 * Cabecera ejecutiva: migas navegables (Cumplimiento › Sección), título H1,
 * la franja de salud de los tres microservicios, las acciones globales en
 * micro-squircles (buscar, refrescar y tema) y el menú del usuario en sesión.
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
  onAbrirPaleta,
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
                    {!ultima && <CaretRight size={12} aria-hidden="true" />}
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

        {/* D1: la paleta de comandos también se abre con Ctrl+K (⌘K en Mac). La consulta no la tiene. */}
        {onAbrirPaleta && (
          <IconButton etiqueta="Buscar (Ctrl+K)" data-tooltip="Buscar · Ctrl+K" aria-haspopup="dialog" onClick={onAbrirPaleta}>
            <MagnifyingGlass size={16} />
          </IconButton>
        )}

        <IconButton etiqueta="Actualizar datos" tooltip ocupado={refrescando} onClick={onRefresh} disabled={refrescando}>
          <ArrowsClockwise size={16} className="refresh-icon" />
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
          {isDark ? <Sun key="sol" size={16} className={claseIcono} /> : <Moon key="luna" size={16} className={claseIcono} />}
        </IconButton>

        <span className="header-divider" aria-hidden="true" />

        {/* Módulo 7 (HU-06): quién está en sesión, con qué rol, y la salida. */}
        <MenuUsuario />
      </div>
    </header>
  )
}
