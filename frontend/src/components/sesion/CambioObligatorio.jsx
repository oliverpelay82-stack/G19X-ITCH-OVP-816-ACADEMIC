import useSesion from '../../hooks/useSesion.js'
import { Button } from '../ui/index.js'
import FormularioContrasena from './FormularioContrasena.jsx'
import PantallaAcceso from './PantallaAcceso.jsx'

/**
 * Primer acceso con una contraseña temporal (alta o restablecimiento del
 * administrador): hasta cambiarla, el core solo admite este paso (403 en lo
 * demás), así que la interfaz no muestra nada más.
 */
export default function CambioObligatorio() {
  const { usuario, salir } = useSesion()
  return (
    <PantallaAcceso
      titulo="Cambia tu contraseña"
      descripcion={`${usuario.nombre_completo}, tu contraseña es temporal. Elige una nueva para continuar.`}
    >
      <FormularioContrasena temporal acciones={<Button onClick={salir}>Cerrar sesión</Button>} />
    </PantallaAcceso>
  )
}
