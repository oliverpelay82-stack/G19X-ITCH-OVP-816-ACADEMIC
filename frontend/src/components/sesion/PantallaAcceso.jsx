import { ClockCountdown, Question, WarningCircle } from '../iconos.js'
import LogoMotor from '../LogoMotor.jsx'
import EstadoServicios from './EstadoServicios.jsx'
import Vitrina from './Vitrina.jsx'

/** Aviso de la pantalla de acceso como tarjeta: por qué se está aquí o qué falló. */
function Alerta({ tono, children }) {
  const Icono = tono === 'error' ? WarningCircle : ClockCountdown
  return (
    <div className={`acceso-alerta acceso-alerta--${tono}`} role={tono === 'error' ? 'alert' : 'status'}>
      <Icono size={16} weight="regular" aria-hidden="true" />
      <p>{children}</p>
    </div>
  )
}

/**
 * Marco de las pantallas sin sesión (inicio de sesión, segundo paso y cambio
 * obligatorio de contraseña): un escenario centrado en la ventana con dos
 * columnas, la vitrina del motor (solo en pantallas anchas) y la tarjeta de
 * acceso, y el estado real de los servicios en la esquina. La ayuda
 * (`pie`) cierra la tarjeta. Los elementos de la tarjeta entran
 * escalonados (marca, título, campos y botón); «reducir movimiento» lo anula.
 *
 * La rejilla del fondo es la única excepción a «sin gradientes» del sistema,
 * aprobada solo para esta pantalla (CLAUDE.md).
 *
 * `aviso` explica por qué se está aquí (sesión expirada); `error` es la respuesta
 * del servidor al último intento, { texto, clave }.
 */
export default function PantallaAcceso({ titulo, descripcion, aviso, error, pie, children }) {
  return (
    <div className="acceso">
      <EstadoServicios />
      <div className="acceso-escenario">
        <Vitrina />
        <main className="acceso-panel">
          <section className="acceso-tarjeta" aria-labelledby="acceso-titulo">
            <div className="acceso-marca">
              <span className="acceso-logo" aria-hidden="true">
                <LogoMotor size={16} />
              </span>
              <div className="brand-text">
                <span className="brand-name">PluriOne</span>
                <span className="brand-sub">Motor de Cumplimiento</span>
              </div>
            </div>
            <header className="acceso-encabezado">
              <h1 id="acceso-titulo" className="acceso-titulo">
                {titulo}
              </h1>
              {descripcion && <p className="acceso-descripcion">{descripcion}</p>}
            </header>
            {aviso && <Alerta tono="aviso">{aviso}</Alerta>}
            {/* La clave nueva vuelve a montar el aviso: un segundo error igual también se anima. */}
            {error && (
              <Alerta key={error.clave} tono="error">
                {error.texto}
              </Alerta>
            )}
            {children}
            {pie && (
              <p className="acceso-pie">
                <Question size={14} aria-hidden="true" />
                <span>{pie}</span>
              </p>
            )}
          </section>
        </main>
      </div>
    </div>
  )
}
