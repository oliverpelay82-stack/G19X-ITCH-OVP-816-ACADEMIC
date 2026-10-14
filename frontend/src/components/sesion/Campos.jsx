import { useState } from 'react'
import { Eye, EyeSlash, LockKey } from '../iconos.js'
import { Input } from '../ui/index.js'
import { cx } from '../ui/clases.js'

/**
 * Campo de texto con un icono a la izquierda y, si se da, un control a la derecha
 * (`accion`). El icono es decorativo: el nombre accesible lo pone el Field que lo
 * envuelve. Se usa en el inicio de sesión, el cambio de contraseña y el alta de
 * cuentas (Módulo 7). Al enfocar el campo, el icono toma el color del texto.
 */
export function CampoIcono({ icono: Icono, accion, className, ...props }) {
  return (
    <span className={cx('campo-icono', accion && 'campo-icono--accion')}>
      <Icono size={16} className="campo-icono-icono" aria-hidden="true" />
      <Input className={className} {...props} />
      {accion && <span className="campo-icono-accion">{accion}</span>}
    </span>
  )
}

/** Contraseña con candado y un botón para mostrarla u ocultarla mientras se escribe. */
export function CampoContrasena({ icono = LockKey, ...props }) {
  const [visible, setVisible] = useState(false)
  return (
    <CampoIcono
      icono={icono}
      type={visible ? 'text' : 'password'}
      spellCheck="false"
      autoCapitalize="none"
      accion={
        <button
          type="button"
          className="campo-icono-boton"
          onClick={() => setVisible((v) => !v)}
          aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
          aria-pressed={visible}
          data-tooltip={visible ? 'Ocultar' : 'Mostrar'}
        >
          {visible ? <EyeSlash size={16} /> : <Eye size={16} />}
        </button>
      }
      {...props}
    />
  )
}
