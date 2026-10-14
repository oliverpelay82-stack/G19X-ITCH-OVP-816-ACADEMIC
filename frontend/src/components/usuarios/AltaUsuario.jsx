import { useState } from 'react'
import { Button, Field, Input, Modal, Select } from '../ui/index.js'
import { crearUsuario } from '../../services/api.js'
import useToast from '../../hooks/useToast.js'
import { NOMBRE_ROL, ROL } from '../../utils/permisos.js'

const VACIO = { email: '', nombre_completo: '', rol: ROL.VALIDADOR, contrasena_temporal: '' }
const MINIMO = 10

/**
 * Alta de una cuenta (HU-05). La contraseña es temporal: la persona la cambia en
 * su primer acceso. El administrador se la comunica por un medio aparte.
 */
export default function AltaUsuario({ onCerrar, onCreado }) {
  const toast = useToast()
  const [form, setForm] = useState(VACIO)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })
  const listo = form.email.includes('@') && form.nombre_completo.trim() && form.contrasena_temporal.length >= MINIMO

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      const usuario = await crearUsuario({ ...form, email: form.email.trim() })
      toast.exito('Cuenta creada', `${usuario.nombre_completo} · ${NOMBRE_ROL[usuario.rol]}`)
      onCreado(usuario)
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal title="Nueva cuenta" subtitle="La persona cambiará la contraseña temporal en su primer acceso" onClose={onCerrar}>
      <form className="form-grid" onSubmit={enviar}>
        <Field etiqueta="Nombre completo">
          <Input value={form.nombre_completo} onChange={cambiar('nombre_completo')} maxLength={150} required autoFocus />
        </Field>
        <Field etiqueta="Correo institucional">
          <Input type="email" value={form.email} onChange={cambiar('email')} maxLength={150} required autoComplete="off" />
        </Field>
        <div className="field-row">
          <Field etiqueta="Rol">
            <Select value={form.rol} onChange={cambiar('rol')}>
              {Object.values(ROL).map((rol) => (
                <option key={rol} value={rol}>
                  {NOMBRE_ROL[rol]}
                </option>
              ))}
            </Select>
          </Field>
          <Field etiqueta="Contraseña temporal" ayuda={`Al menos ${MINIMO} caracteres.`}>
            <Input
              type="text"
              className="mono"
              value={form.contrasena_temporal}
              onChange={cambiar('contrasena_temporal')}
              required
              autoComplete="off"
              spellCheck="false"
            />
          </Field>
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-footer">
          <Button onClick={onCerrar}>Cancelar</Button>
          <Button type="submit" variante="primary" cargando={enviando} disabled={!listo}>
            Crear cuenta
          </Button>
        </div>
      </form>
    </Modal>
  )
}
