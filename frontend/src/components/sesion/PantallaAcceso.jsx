import LogoMotor from '../LogoMotor.jsx'

/**
 * Marco de las pantallas sin sesión (inicio de sesión y cambio obligatorio de
 * contraseña): la marca, un título, una línea de ayuda y el formulario en una
 * tarjeta centrada. `aviso` explica por qué se está aquí (sesión expirada);
 * `error` es la respuesta del servidor al último intento.
 */
export default function PantallaAcceso({ titulo, descripcion, aviso, error, children }) {
  return (
    <main className="acceso">
      <section className="acceso-tarjeta" aria-labelledby="acceso-titulo">
        <div className="acceso-marca">
          <span className="squircle squircle--lg squircle--brand" aria-hidden="true">
            <LogoMotor size={16} />
          </span>
          <div className="brand-text">
            <span className="brand-name">PluriOne</span>
            <span className="brand-sub">Motor de Cumplimiento</span>
          </div>
        </div>
        <h1 id="acceso-titulo" className="acceso-titulo">
          {titulo}
        </h1>
        {descripcion && <p className="acceso-descripcion">{descripcion}</p>}
        {aviso && (
          <p className="acceso-aviso" role="status">
            {aviso}
          </p>
        )}
        {error && (
          <p className="acceso-error" role="alert">
            {error}
          </p>
        )}
        {children}
      </section>
    </main>
  )
}
