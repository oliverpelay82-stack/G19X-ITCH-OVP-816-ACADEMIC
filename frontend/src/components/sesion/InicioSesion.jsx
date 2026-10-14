import { useRef, useState } from 'react'
import { ArrowLeft, EnvelopeSimple, ShieldCheck } from '../iconos.js'
import { iniciarSesionApi } from '../../services/api.js'
import { MOTIVO } from '../../services/sesion.js'
import useSesion from '../../hooks/useSesion.js'
import { Button, Field } from '../ui/index.js'
import { CampoContrasena, CampoIcono } from './Campos.jsx'
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
    // El botón siempre está disponible (acción principal sólida): lo que falta se dice en el aviso.
    const falta = pideCodigo
      ? codigo.length !== 6 && 'Escribe los 6 dígitos del código.'
      : (!email.trim() || !contrasena) && 'Escribe tu correo y tu contraseña.'
    if (falta) {
      setError({ texto: falta, clave: Date.now() })
      return
    }
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
      setError({ texto: err.message, clave: Date.now() })
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
      pie={
        !pideCodigo && '¿Olvidaste tu contraseña o perdiste tu teléfono? Pide al administrador que la restablezca.'
      }
    >
      <form className="acceso-form" onSubmit={enviar} noValidate>
        {!pideCodigo ? (
          <>
            <Field etiqueta="Correo">
              <CampoIcono
                icono={EnvelopeSimple}
                type="email"
                autoComplete="username"
                placeholder="nombre@empresa.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoFocus
              />
            </Field>
            <Field etiqueta="Contraseña">
              <CampoContrasena
                autoComplete="current-password"
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                required
              />
            </Field>
          </>
        ) : (
          <Field etiqueta="Código de verificación">
            <CampoIcono
              ref={campoCodigo}
              icono={ShieldCheck}
              className="acceso-codigo tabular"
              inputMode="numeric"
              autoComplete="one-time-code"
              pattern="[0-9]{6}"
              maxLength={6}
              placeholder="000000"
              value={codigo}
              onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ''))}
              required
            />
          </Field>
        )}
        <Button
          type="submit"
          variante="primary"
          className="acceso-enviar"
          cargando={enviando}
        >
          {enviando ? (pideCodigo ? 'Verificando…' : 'Entrando…') : pideCodigo ? 'Verificar' : 'Iniciar sesión'}
        </Button>
        {pideCodigo && (
          <Button icono={ArrowLeft} className="acceso-volver" onClick={volver} disabled={enviando}>
            Usar otra cuenta
          </Button>
        )}
      </form>
    </PantallaAcceso>
  )
}
