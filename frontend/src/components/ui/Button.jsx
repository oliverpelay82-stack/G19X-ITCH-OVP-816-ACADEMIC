import { CircleNotch } from '../iconos.js'
import { cx } from './clases.js'

/**
 * Botón de texto (`.btn`). Variantes: `primary` (una acción principal por
 * vista) y `secondary`. No hay variante de peligro: el sistema no tiene
 * acciones destructivas (la bitácora y los dictámenes son inmutables).
 *
 * `cargando` deshabilita el botón y sustituye el icono por el indicador de
 * giro, como en «Auditando…»; `soloIcono` lo vuelve cuadrado (`.btn-icon`).
 */
export function Button({
  variante = 'secondary',
  compacto = false,
  soloIcono = false,
  cargando = false,
  icono: Icono,
  className,
  children,
  type = 'button',
  disabled,
  ...props
}) {
  return (
    <button
      type={type}
      className={cx('btn', `btn-${variante}`, compacto && 'btn-sm', soloIcono && 'btn-icon', className)}
      disabled={disabled || cargando}
      aria-busy={cargando || undefined}
      {...props}
    >
      {cargando ? <CircleNotch className="spin" size={14} aria-hidden="true" /> : Icono && <Icono size={14} aria-hidden="true" />}
      {children}
    </button>
  )
}

/**
 * Botón de solo icono dentro de un micro-squircle (`.icon-button`). La
 * `etiqueta` es obligatoria: es el nombre accesible del botón y, con
 * `tooltip`, también el texto del tooltip. El icono va como hijo para
 * conservar su tamaño y clases (p. ej. el giro del refresco).
 */
export function IconButton({
  etiqueta,
  compacto = false,
  ocupado = false,
  tooltip = false,
  className,
  children,
  type = 'button',
  ...props
}) {
  return (
    <button
      type={type}
      className={cx('icon-button', compacto && 'icon-button--sm', ocupado && 'is-busy', className)}
      aria-label={etiqueta}
      aria-busy={ocupado || undefined}
      data-tooltip={tooltip ? etiqueta : undefined}
      {...props}
    >
      {children}
    </button>
  )
}
