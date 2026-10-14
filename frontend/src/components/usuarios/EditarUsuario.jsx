import { useState } from 'react'
import { Button, Field, Input, Modal, Select } from '../ui/index.js'
import { actualizarUsuario } from '../../services/api.js'
import useToast from '../../hooks/useToast.js'
import { NOMBRE_ROL, ROL } from '../../utils/permisos.js'

const MINIMO = 10

/**
 * Cambios de una cuenta (HU-05): nombre y rol; desactivar o reactivar (sin
 * borrado, RN-04); restablecer la contraseña, que también la desbloquea, y quitar
 * la verificación en dos pasos (teléfono perdido). Cada acción se guarda sola y
 * queda en la bitácora con el valor anterior y el nuevo.
 *
 * En la cuenta propia no se ofrece cambiar el rol ni desactivarla: así siempre
 * queda un administrador activo (el core también lo impide).
 */
export default function EditarUsuario({ usuario, esPropia, onCerrar, onActualizado }) {
  const toast = useToast()
  const [nombre, setNombre] = useState(usuario.nombre_completo)
  const [rol, setRol] = useState(usuario.rol)
  const [temporal, setTemporal] = useState('')
  const [ocupado, setOcupado] = useState(null)
  const [error, setError] = useState('')

  const guardar = async (accion, cambios, aviso) => {
    setOcupado(accion)
    setError('')
    try {
      const actualizado = await actualizarUsuario(usuario.id, cambios)
      onActualizado(actualizado)
      toast.exito(aviso, actualizado.nombre_completo)
      return true
    } catch (err) {
      setError(err.message)
      return false
    } finally {
      setOcupado(null)
    }
  }

  const datosCambiados = nombre.trim() !== usuario.nombre_completo || rol !== usuario.rol

  return (
    <Modal title={usuario.nombre_completo} subtitle={usuario.email} onClose={onCerrar}>
      <div className="form-grid">
        <div className="field-row">
          <Field etiqueta="Nombre completo">
            <Input value={nombre} onChange={(e) => setNombre(e.target.value)} maxLength={150} />
          </Field>
          <Field etiqueta="Rol" ayuda={esPropia ? 'No puedes cambiar tu propio rol.' : undefined}>
            <Select value={rol} onChange={(e) => setRol(e.target.value)} disabled={esPropia}>
              {Object.values(ROL).map((r) => (
                <option key={r} value={r}>
                  {NOMBRE_ROL[r]}
                </option>
              ))}
            </Select>
          </Field>
        </div>
        <div className="modal-footer">
          <Button
            variante="primary"
            cargando={ocupado === 'datos'}
            disabled={!datosCambiados || !nombre.trim()}
            onClick={() => guardar('datos', { nombre_completo: nombre.trim(), rol }, 'Cuenta actualizada')}
          >
            Guardar cambios
          </Button>
        </div>

        <Field etiqueta="Restablecer contraseña" ayuda={`Temporal, de al menos ${MINIMO} caracteres. También desbloquea la cuenta.`}>
          <Input
            className="mono"
            value={temporal}
            onChange={(e) => setTemporal(e.target.value)}
            autoComplete="off"
            spellCheck="false"
          />
        </Field>
        <div className="modal-footer">
          <Button
            cargando={ocupado === 'contrasena'}
            disabled={temporal.length < MINIMO}
            onClick={async () => {
              if (await guardar('contrasena', { contrasena_temporal: temporal }, 'Contraseña restablecida')) setTemporal('')
            }}
          >
            Restablecer
          </Button>
        </div>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-footer">
          {usuario.mfa_habilitado && (
            <Button
              cargando={ocupado === 'mfa'}
              onClick={() => guardar('mfa', { restablecer_mfa: true }, 'Verificación en dos pasos quitada')}
            >
              Quitar verificación en dos pasos
            </Button>
          )}
          {!esPropia && (
            <Button
              cargando={ocupado === 'estado'}
              onClick={() =>
                guardar('estado', { activo: !usuario.activo }, usuario.activo ? 'Cuenta desactivada' : 'Cuenta reactivada')
              }
            >
              {usuario.activo ? 'Desactivar cuenta' : 'Reactivar cuenta'}
            </Button>
          )}
        </div>
      </div>
    </Modal>
  )
}
