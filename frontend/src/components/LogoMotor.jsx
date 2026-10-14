import { SealCheck } from './iconos.js'

/**
 * Marca del Motor de Validación: el sello de validación de Phosphor (SealCheck,
 * relleno), con el check calado sobre el fondo de su contenedor. Toma el color
 * de su contenedor en ambos temas. Es la marca del sistema, no el logotipo de
 * PluriOne. El favicon (public/favicon.svg) dibuja la misma figura.
 */
export default function LogoMotor({ size = 16 }) {
  return <SealCheck size={size} weight="fill" aria-hidden="true" />
}
