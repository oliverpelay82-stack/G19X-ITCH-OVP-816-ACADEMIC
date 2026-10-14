import { useState } from 'react'
import { cambiarContrasena } from '../../services/api.js'
import useSesion from '../../hooks/useSesion.js'
import { WarningCircle } from '../iconos.js'
import { Button, Field } from '../ui/index.js'
import { CampoContrasena } from './Campos.jsx'

/** Mínimo del core (config/seguridad.py, LONGITUD_MINIMA_CONTRASENA). */
const MINIMO = 10

/**
 * Cambio de la contraseña propia (POST /auth/cambiar-contrasena). Lo usan la
 * pantalla obligatoria tras una contraseña temporal y el menú de usuario. La
 * validación de aquí solo adelanta lo que el core también exige.
 */
export default function FormularioContrasena({ temporal = false, onListo, acciones }) {
  const { refrescarPerfil } = useSesion()
  const [actual, setActual] = useState('')
  const [nueva, setNueva] = useState('')
  const [confirmacion, setConfirmacion] = useState('')
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)

  const problema =
    nueva && nueva.length < MINIMO
      ? `Usa al menos ${MINIMO} caracteres.`
      : nueva && nueva === actual
        ? 'La contraseña nueva debe ser distinta de la actual.'
        : confirmacion && confirmacion !== nueva
          ? 'Las dos contraseñas nuevas no coinciden.'
          : null
  const lista = actual && nueva && confirmacion && !problema

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const usuario = await cambiarContrasena(actual, nueva)
      refrescarPerfil(usuario)
      onListo?.()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="acceso-form" onSubmit={enviar} noValidate>
      {error && (
        <div className="acceso-alerta acceso-alerta--error" role="alert">
          <WarningCircle size={16} aria-hidden="true" />
          <p>{error}</p>
        </div>
      )}
      <Field etiqueta={temporal ? 'Contraseña temporal' : 'Contraseña actual'}>
        <CampoContrasena
          autoComplete="current-password"
          value={actual}
          onChange={(e) => setActual(e.target.value)}
          required
          autoFocus
        />
      </Field>
      <Field etiqueta="Contraseña nueva" ayuda={`Al menos ${MINIMO} caracteres.`}>
        <CampoContrasena autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} required />
      </Field>
      <Field
        etiqueta="Repite la contraseña nueva"
        retro={problema ? { estado: 'invalido', mensaje: problema } : null}
      >
        <CampoContrasena
          autoComplete="new-password"
          value={confirmacion}
          estado={problema ? 'invalido' : undefined}
          onChange={(e) => setConfirmacion(e.target.value)}
          required
        />
      </Field>
      <Button type="submit" variante="primary" cargando={enviando} disabled={!lista}>
        Guardar contraseña
      </Button>
      {acciones}
    </form>
  )
}
