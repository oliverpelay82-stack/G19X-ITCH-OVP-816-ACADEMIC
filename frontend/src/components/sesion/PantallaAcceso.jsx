import { AnimatePresence, LazyMotion, MotionConfig, domAnimation, m } from 'motion/react'
import { Check, ClockCountdown, WarningCircle } from '../iconos.js'
import LogoMotor from '../LogoMotor.jsx'
import { SALIDA_EXPONENCIAL } from '../../utils/movimiento.js'
import EstadoServicios from './EstadoServicios.jsx'

/** Cómo entra y sale cada paso: llega desde abajo con calma y se va hacia arriba, rápido. */
const PASO = {
  oculto: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.5, ease: SALIDA_EXPONENCIAL, staggerChildren: 0.07, delayChildren: 0.04 },
  },
  salida: { opacity: 0, y: -28, transition: { duration: 0.18, ease: [0.4, 0, 1, 1] } },
}

/** Cada pieza del paso (icono, pregunta, respuesta, acciones) llega un instante después de la anterior. */
const PIEZA = {
  oculto: { opacity: 0, y: 18 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.5, ease: SALIDA_EXPONENCIAL } },
}

/** Aviso bajo la respuesta: por qué se está aquí (aviso) o qué falló (error, con una sacudida). */
function Aviso({ tono, children }) {
  const Icono = tono === 'error' ? WarningCircle : ClockCountdown
  const error = tono === 'error'
  return (
    <m.p
      className={`acceso-alerta acceso-alerta--${tono}`}
      role={error ? 'alert' : 'status'}
      initial={{ opacity: 0, y: -4 }}
      animate={error ? { opacity: 1, y: 0, x: [0, -4, 4, -3, 3, 0] } : { opacity: 1, y: 0 }}
      exit={{ opacity: 0, transition: { duration: 0.15 } }}
      transition={{ duration: 0.3, ease: SALIDA_EXPONENCIAL, x: { duration: 0.2, ease: 'linear', delay: 0.1 } }}
    >
      <Icono size={16} aria-hidden="true" />
      <span>{children}</span>
    </m.p>
  )
}

/** Los pasos del acceso como una secuencia: hechos (con su palomita), el actual y los que faltan. */
function Pasos({ pasos, actual }) {
  return (
    <ol className="acceso-pasos" aria-label={`Paso ${actual + 1} de ${pasos.length}`}>
      {pasos.map((nombre, i) => {
        const estado = i < actual ? 'hecho' : i === actual ? 'actual' : 'pendiente'
        return (
          <li key={nombre} className={`acceso-paso is-${estado}`} aria-current={estado === 'actual' ? 'step' : undefined}>
            <span className="acceso-paso-marca" aria-hidden="true">
              {estado === 'hecho' ? <Check size={12} weight="bold" /> : i + 1}
            </span>
            <span className="acceso-paso-nombre">{nombre}</span>
            {i < pasos.length - 1 && (
              <span className="acceso-paso-tramo" aria-hidden="true">
                <m.span
                  className="acceso-paso-relleno"
                  initial={false}
                  animate={{ scaleX: i < actual ? 1 : 0 }}
                  transition={{ duration: 0.5, ease: SALIDA_EXPONENCIAL }}
                />
              </span>
            )}
          </li>
        )
      })}
    </ol>
  )
}

/**
 * Marco de las pantallas sin sesión (Módulo 7, HU-06): una pregunta a la vez, a
 * pantalla completa. Arriba, la marca y la secuencia de pasos; al centro, el paso
 * actual (su icono, la pregunta como título y la respuesta); abajo, el estado real
 * de los servicios y la ayuda.
 *
 * Cada paso entra y sale con Motion (motion/react, solo en components/sesion;
 * excepción registrada en CLAUDE.md): llega desde abajo con salida exponencial y
 * sus piezas se escalonan; se va hacia arriba en 180 ms. `clave` identifica el
 * paso: al cambiar, el anterior sale y el nuevo entra. MotionConfig respeta
 * «reducir movimiento». Los iconos siguen la escala del sistema (12, 14 y 16 px).
 *
 * `aviso` explica por qué se está aquí (sesión expirada); `error` es la respuesta
 * al último intento, { texto, clave }.
 */
export default function PantallaAcceso({
  clave = 'unico',
  icono: Icono,
  titulo,
  descripcion,
  pasos,
  pasoActual = 0,
  aviso,
  error,
  pie,
  children,
}) {
  return (
    <MotionConfig reducedMotion="user">
      <LazyMotion features={domAnimation} strict>
        <div className="acceso">
          <header className="acceso-barra">
            <span className="acceso-marca">
              <LogoMotor size={16} />
              <span>PluriOne</span>
            </span>
            {pasos && <Pasos pasos={pasos} actual={pasoActual} />}
          </header>

          <main className="acceso-escena">
            <AnimatePresence mode="wait" initial={true}>
              <m.section
                key={clave}
                className="acceso-paso-contenido"
                aria-labelledby="acceso-titulo"
                variants={PASO}
                initial="oculto"
                animate="visible"
                exit="salida"
              >
                {Icono && (
                  <m.span className="acceso-icono" variants={PIEZA} aria-hidden="true">
                    <Icono size={16} />
                  </m.span>
                )}
                <m.h1 id="acceso-titulo" className="acceso-titulo" variants={PIEZA}>
                  {titulo}
                </m.h1>
                {descripcion && (
                  <m.p className="acceso-descripcion" variants={PIEZA}>
                    {descripcion}
                  </m.p>
                )}
                <m.div className="acceso-cuerpo" variants={PIEZA}>
                  {children}
                </m.div>
                <AnimatePresence initial={false}>
                  {aviso && (
                    <Aviso key="aviso" tono="aviso">
                      {aviso}
                    </Aviso>
                  )}
                  {/* La clave nueva vuelve a montar el aviso: un segundo error igual también se sacude. */}
                  {error && (
                    <Aviso key={`error-${error.clave}`} tono="error">
                      {error.texto}
                    </Aviso>
                  )}
                </AnimatePresence>
              </m.section>
            </AnimatePresence>
          </main>

          <footer className="acceso-pie">
            <EstadoServicios />
            {pie && <p className="acceso-ayuda">{pie}</p>}
          </footer>
        </div>
      </LazyMotion>
    </MotionConfig>
  )
}
