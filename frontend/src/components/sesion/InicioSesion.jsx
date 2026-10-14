import { useRef, useState } from 'react'
import { iniciarSesionApi } from '../../services/api.js'
import { MOTIVO } from '../../services/sesion.js'
import useSesion from '../../hooks/useSesion.js'
import { Button, Field, Input } from '../ui/index.js'
import PantallaAcceso from './PantallaAcceso.jsx'

/**
 * Inicio de sesión (Módulo 7, HU-06; docs/uml/m7-secuencia-inicio-sesion.puml).
 *
 * Con la verificación en dos pasos (fase F3) el core responde `requiere_codigo`
 * sin token: el formulario pasa al código de la app y vuelve a enviar el correo y
 * la contraseña con él. Los mensajes de error son los del core (credenciales,
 * código, bloqueo por intentos), que ya están en lenguaje llano.
 */
export default function InicioSesion() {
  const { entrar, motivoCierre } = useSesion()
  const [email, setEmail] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [codigo, setCodigo] = useState('')
  const [pideCodigo, setPideCodigo] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const campoCodigo = useRef(null)

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError(null)
    try {
      const respuesta = await iniciarSesionApi(email.trim(), contrasena, pideCodigo ? codigo.trim() : undefined)
      if (respuesta?.requiere_codigo) {
        setPideCodigo(true)
        setTimeout(() => campoCodigo.current?.focus(), 0)
      } else {
        entrar(respuesta)
      }
    } catch (err) {
      setError(err.message)
      if (pideCodigo) setCodigo('')
    } finally {
      setEnviando(false)
    }
  }

  const volver = () => {
    setPideCodigo(false)
    setCodigo('')
    setError(null)
  }

  return (
    <PantallaAcceso
      titulo={pideCodigo ? 'Verificación en dos pasos' : 'Inicia sesión'}
      descripcion={
        pideCodigo
          ? 'Escribe el código de 6 dígitos que muestra tu app autenticadora.'
          : 'Usa la cuenta que te dio el administrador del sistema.'
      }
      aviso={!pideCodigo && motivoCierre === MOTIVO.EXPIRADA ? 'Tu sesión expiró. Vuelve a iniciar sesión.' : null}
      error={error}
    >
      <form className="acceso-form" onSubmit={enviar} noValidate>
        {!pideCodigo ? (
          <>
            <Field etiqueta="Correo">
              <Input
                type="email"
                autoComplete="username"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </Field>
            <Field etiqueta="Contraseña">
              <Input
                type="password"
                autoComplete="current-password"
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                required
              />
            </Field>
          </>
        ) : (
          <Field etiqueta="Código de verificación">
            <Input
              ref={campoCodigo}
              className="acceso-codigo tabular"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ''))}
              required
            />
          </Field>
        )}
        <Button
          type="submit"
          variante="primary"
          cargando={enviando}
          disabled={pideCodigo ? codigo.length !== 6 : !email.trim() || !contrasena}
        >
          {pideCodigo ? 'Verificar' : 'Entrar'}
        </Button>
        {pideCodigo && (
          <Button onClick={volver} disabled={enviando}>
            Usar otra cuenta
          </Button>
        )}
      </form>
      {!pideCodigo && (
        <p className="acceso-nota">¿Olvidaste tu contraseña o perdiste tu teléfono? Pide al administrador que la restablezca.</p>
      )}
    </PantallaAcceso>
  )
}
