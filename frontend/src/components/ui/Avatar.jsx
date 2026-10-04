import { iniciales } from '../../utils/format.js'
import { cx } from './clases.js'

/**
 * Iniciales de un titular (`.avatar`), decorativas: el nombre ya se lee al
 * lado, por eso el lector de pantalla las omite. `grande` es el de la
 * tarjeta de perfil y el detalle de la empresa.
 */
export default function Avatar({ nombre, grande = false, className }) {
  return (
    <span className={cx('avatar', grande && 'avatar--lg', className)} aria-hidden="true">
      {iniciales(nombre)}
    </span>
  )
}
