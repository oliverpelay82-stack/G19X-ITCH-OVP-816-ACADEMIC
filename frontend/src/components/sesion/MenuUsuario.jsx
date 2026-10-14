import { useEffect, useRef, useState } from 'react'
import { CaretDown, Key, ShieldCheck, SignOut } from '../iconos.js'
import useSesion from '../../hooks/useSesion.js'
import useToast from '../../hooks/useToast.js'
import { NOMBRE_ROL } from '../../utils/permisos.js'
import { Avatar, Modal } from '../ui/index.js'
import FormularioContrasena from './FormularioContrasena.jsx'
import VerificacionDosPasos from './VerificacionDosPasos.jsx'

/**
 * Identidad del usuario en la cabecera (HU-06): nombre y rol, y un menú con el
 * correo de la cuenta, el cambio de contraseña, la verificación en dos pasos
 * (fase F3) y el cierre de sesión. Se cierra con Escape o con un clic fuera.
 */
export default function MenuUsuario() {
  const { usuario, salir } = useSesion()
  const toast = useToast()
  const [abierto, setAbierto] = useState(false)
  const [contrasenaAbierta, setContrasenaAbierta] = useState(false)
  const [mfaAbierto, setMfaAbierto] = useState(false)
  const raiz = useRef(null)

  useEffect(() => {
    if (!abierto) return undefined
    const fuera = (e) => {
      if (!raiz.current?.contains(e.target)) setAbierto(false)
    }
    const escape = (e) => {
      if (e.key === 'Escape') setAbierto(false)
    }
    document.addEventListener('mousedown', fuera)
    document.addEventListener('keydown', escape)
    return () => {
      document.removeEventListener('mousedown', fuera)
      document.removeEventListener('keydown', escape)
    }
  }, [abierto])

  const elegir = (accion) => () => {
    setAbierto(false)
    accion()
  }

  return (
    <div className="menu-usuario" ref={raiz}>
      <button
        type="button"
        className="menu-usuario-boton"
        aria-haspopup="menu"
        aria-expanded={abierto}
        onClick={() => setAbierto((a) => !a)}
      >
        <Avatar nombre={usuario.nombre_completo} />
        <span className="menu-usuario-identidad">
          <span className="menu-usuario-nombre">{usuario.nombre_completo}</span>
          <span className="menu-usuario-rol">{NOMBRE_ROL[usuario.rol] || usuario.rol}</span>
        </span>
        <CaretDown size={12} aria-hidden="true" />
      </button>
      {abierto && (
        <div className="menu-usuario-lista" role="menu" aria-label="Cuenta">
          <p className="menu-usuario-correo">{usuario.email}</p>
          <button type="button" role="menuitem" className="menu-usuario-opcion" onClick={elegir(() => setContrasenaAbierta(true))}>
            <Key size={14} aria-hidden="true" />
            Cambiar contraseña
          </button>
          <button type="button" role="menuitem" className="menu-usuario-opcion" onClick={elegir(() => setMfaAbierto(true))}>
            <ShieldCheck size={14} aria-hidden="true" />
            Verificación en dos pasos
            <span className="menu-usuario-estado">{usuario.mfa_habilitado ? 'Activa' : 'Inactiva'}</span>
          </button>
          <button type="button" role="menuitem" className="menu-usuario-opcion" onClick={elegir(salir)}>
            <SignOut size={14} aria-hidden="true" />
            Cerrar sesión
          </button>
        </div>
      )}
      {mfaAbierto && <VerificacionDosPasos onCerrar={() => setMfaAbierto(false)} />}
      {contrasenaAbierta && (
        <Modal title="Cambiar contraseña" onClose={() => setContrasenaAbierta(false)}>
          <FormularioContrasena
            onListo={() => {
              setContrasenaAbierta(false)
              toast.exito('Contraseña actualizada', 'Úsala la próxima vez que inicies sesión.')
            }}
          />
        </Modal>
      )}
    </div>
  )
}
