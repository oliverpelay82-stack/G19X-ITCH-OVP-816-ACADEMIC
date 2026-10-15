import { useEffect, useRef, useState } from 'react'
import { ArrowLeft, ArrowRight, EnvelopeSimple, Eye, EyeSlash, KeyReturn, LockKey, ShieldCheck } from '../iconos.js'
import { iniciarSesionApi } from '../../services/api.js'
import { MOTIVO } from '../../services/sesion.js'
import useSesion from '../../hooks/useSesion.js'
import { Button } from '../ui/index.js'
import PantallaAcceso from './PantallaAcceso.jsx'

/** Las preguntas del acceso, una por pantalla. */
const PASOS = {
  correo: {
    icono: EnvelopeSimple,
    titulo: '¿Cuál es tu correo?',
    descripcion: 'El de la cuenta que te dio el administrador del sistema.',
    falta: 'Escribe tu correo.',
    accion: 'Continuar',
  },
  contrasena: {
    icono: LockKey,
    titulo: 'Escribe tu contraseña',
    falta: 'Escribe tu contraseña.',
    accion: 'Iniciar sesión',
  },
  codigo: {
    icono: ShieldCheck,
    titulo: 'Verificación en dos pasos',
    descripcion: 'Escribe el código de 6 dígitos que muestra tu app autenticadora.',
    falta: 'Escribe los 6 dígitos del código.',
    accion: 'Verificar',
  },
}

const INDICE = { correo: 0, contrasena: 1, codigo: 2 }

/**
 * Inicio de sesión (Módulo 7, HU-06; docs/uml/m7-secuencia-inicio-sesion.puml),
 * una pregunta a la vez: el correo, la contraseña y, si la cuenta tiene la
 * verificación en dos pasos, el código. Se avanza con Enter o con el botón.
 *
 * El correo no se valida contra el servidor por separado (no se revela qué cuentas
 * existen): las credenciales viajan juntas al enviar la contraseña. Con la
 * verificación en dos pasos el core responde `requiere_codigo` sin token, y el
 * último paso vuelve a enviar el correo y la contraseña con el código. Los
 * mensajes de error son los del core, ya en lenguaje llano.
 */
export default function InicioSesion() {
  const { entrar, motivoCierre } = useSesion()
  const [paso, setPaso] = useState('correo')
  const [email, setEmail] = useState('')
  const [contrasena, setContrasena] = useState('')
  const [codigo, setCodigo] = useState('')
  const [visible, setVisible] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState(null)
  const campo = useRef(null)
  const actual = PASOS[paso]

  // Cada pregunta recibe el foco en cuanto termina de entrar.
  useEffect(() => {
    const id = setTimeout(() => campo.current?.focus(), 60)
    return () => clearTimeout(id)
  }, [paso])

  const fallo = (texto) => setError({ texto, clave: Date.now() })

  const autenticar = async (conCodigo) => {
    setEnviando(true)
    setError(null)
    try {
      const respuesta = await iniciarSesionApi(email.trim(), contrasena, conCodigo ? codigo.trim() : undefined)
      if (respuesta?.requiere_codigo) setPaso('codigo')
      else entrar(respuesta)
    } catch (err) {
      fallo(err.message)
      if (conCodigo) setCodigo('')
      campo.current?.select?.()
    } finally {
      setEnviando(false)
    }
  }

  const enviar = (e) => {
    e.preventDefault()
    if (enviando) return
    if (paso === 'correo') {
      if (!email.trim()) return fallo(actual.falta)
      setError(null)
      setPaso('contrasena')
    } else if (paso === 'contrasena') {
      if (!contrasena) return fallo(actual.falta)
      autenticar(false)
    } else {
      if (codigo.length !== 6) return fallo(actual.falta)
      autenticar(true)
    }
  }

  const volver = () => {
    setError(null)
    setCodigo('')
    setContrasena('')
    setVisible(false)
    setPaso('correo')
  }

  return (
    <PantallaAcceso
      clave={paso}
      icono={actual.icono}
      titulo={actual.titulo}
      descripcion={actual.descripcion}
      pasos={paso === 'codigo' ? ['Correo', 'Contraseña', 'Código'] : ['Correo', 'Contraseña']}
      pasoActual={INDICE[paso]}
      aviso={paso === 'correo' && motivoCierre === MOTIVO.EXPIRADA ? 'Tu sesión expiró. Vuelve a iniciar sesión.' : null}
      error={error}
      pie={
        paso === 'contrasena' &&
        '¿Olvidaste tu contraseña o perdiste tu teléfono? Pide al administrador que la restablezca.'
      }
    >
      <form className="acceso-form" onSubmit={enviar} noValidate>
        {paso === 'correo' && (
          <input
            ref={campo}
            className="acceso-respuesta"
            type="email"
            aria-label="Correo"
            autoComplete="username"
            placeholder="nombre@empresa.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            spellCheck="false"
            autoCapitalize="none"
          />
        )}

        {paso === 'contrasena' && (
          <>
            <p className="acceso-cuenta">
              Entrando como <strong>{email.trim()}</strong>
            </p>
            {/* Para el gestor de contraseñas del navegador: el usuario y la contraseña en el mismo formulario. */}
            <input type="email" autoComplete="username" value={email.trim()} readOnly hidden />
            <span className="acceso-respuesta-grupo">
              <input
                ref={campo}
                className="acceso-respuesta"
                type={visible ? 'text' : 'password'}
                aria-label="Contraseña"
                autoComplete="current-password"
                value={contrasena}
                onChange={(e) => setContrasena(e.target.value)}
                spellCheck="false"
                autoCapitalize="none"
              />
              <button
                type="button"
                className="acceso-ver"
                onClick={() => setVisible((v) => !v)}
                aria-label={visible ? 'Ocultar contraseña' : 'Mostrar contraseña'}
                aria-pressed={visible}
              >
                {visible ? <EyeSlash size={16} /> : <Eye size={16} />}
              </button>
            </span>
          </>
        )}

        {paso === 'codigo' && (
          <input
            ref={campo}
            className="acceso-respuesta acceso-respuesta--codigo tabular"
            aria-label="Código de verificación"
            inputMode="numeric"
            autoComplete="one-time-code"
            pattern="[0-9]{6}"
            maxLength={6}
            placeholder="000000"
            value={codigo}
            onChange={(e) => setCodigo(e.target.value.replace(/\D/g, ''))}
          />
        )}

        <div className="acceso-acciones">
          <Button type="submit" variante="primary" className="acceso-avanzar" cargando={enviando}>
            {enviando ? (paso === 'codigo' ? 'Verificando…' : 'Entrando…') : actual.accion}
            {!enviando && <ArrowRight size={16} aria-hidden="true" />}
          </Button>
          <span className="acceso-tecla" aria-hidden="true">
            o pulsa Enter
            <KeyReturn size={14} />
          </span>
          {paso !== 'correo' && (
            <button type="button" className="acceso-atras" onClick={volver} disabled={enviando}>
              <ArrowLeft size={14} aria-hidden="true" />
              {paso === 'codigo' ? 'Usar otra cuenta' : 'Cambiar de correo'}
            </button>
          )}
        </div>
      </form>
    </PantallaAcceso>
  )
}
