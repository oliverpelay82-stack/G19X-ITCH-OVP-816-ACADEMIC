import { puede } from '../utils/permisos.js'
import useSesion from './useSesion.js'

/**
 * ¿El usuario en sesión puede hacer `permiso` (utils/permisos.js)? La interfaz
 * oculta lo que no puede; el servicio aplica la regla de todos modos (403).
 */
export default function usePermiso(permiso) {
  const { usuario } = useSesion()
  return puede(usuario?.rol, permiso)
}
