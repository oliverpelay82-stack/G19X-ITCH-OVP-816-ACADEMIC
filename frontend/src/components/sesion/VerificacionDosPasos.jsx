import { useEffect, useState } from 'react'
import { activarMfa, desactivarMfa, generarMfa } from '../../services/api.js'
import useSesion from '../../hooks/useSesion.js'
import useToast from '../../hooks/useToast.js'
import { Button, CopyChip, Field, Input, Modal } from '../ui/index.js'

/** Código QR de la URI otpauth://, generado en el navegador: el secreto no sale a ningún servicio. */
function CodigoQr({ uri }) {
  const [imagen, setImagen] = useState(null)
  useEffect(() => {
    let vigente = true
    // qrcode se carga solo al abrir esta ventana: no pesa en el paquete principal.
    import('qrcode')
      .then(({ toDataURL }) => toDataURL(uri, { margin: 1, width: 368, errorCorrectionLevel: 'M' }))
      .then((url) => vigente && setImagen(url))
      .catch(() => vigente && setImagen(''))
    return () => {
      vigente = false
    }
  }, [uri])
  if (imagen === '') return <p className="mfa-texto">No se pudo dibujar el código QR: escribe la clave a mano.</p>
  return <div className="mfa-qr">{imagen && <img src={imagen} alt="Código QR para la app autenticadora" />}</div>
}

const soloDigitos = (valor) => valor.replace(/\D/g, '').slice(0, 6)

function CampoCodigo({ valor, onChange }) {
  return (
    <Field etiqueta="Código de 6 dígitos">
      <Input
        className="acceso-codigo tabular"
        inputMode="numeric"
        autoComplete="one-time-code"
        maxLength={6}
        value={valor}
        onChange={(e) => onChange(soloDigitos(e.target.value))}
        required
      />
    </Field>
  )
}

/**
 * Verificación en dos pasos de la cuenta propia (RF-25, fase F3;
 * docs/uml/m7-actividad-mfa.puml).
 *
 * Alta: la contraseña genera el secreto (aún sin habilitar); la persona lo
 * registra en su app (código QR o clave) y lo confirma con el primer código.
 * Baja: contraseña y un código vigente. Si pierde el teléfono, el administrador
 * puede quitarla desde Usuarios.
 */
export default function VerificacionDosPasos({ onCerrar }) {
  const { usuario, refrescarPerfil } = useSesion()
  const toast = useToast()
  const [contrasena, setContrasena] = useState('')
  const [codigo, setCodigo] = useState('')
  const [secreto, setSecreto] = useState(null)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const ejecutar = async (accion) => {
    setEnviando(true)
    setError('')
    try {
      await accion()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  const generar = (e) => {
    e.preventDefault()
    ejecutar(async () => setSecreto(await generarMfa(contrasena)))
  }

  const activar = (e) => {
    e.preventDefault()
    ejecutar(async () => {
      refrescarPerfil(await activarMfa(codigo))
      toast.exito('Verificación en dos pasos activa', 'Tu próximo inicio de sesión pedirá el código de tu app.')
      onCerrar()
    })
  }

  const desactivar = (e) => {
    e.preventDefault()
    ejecutar(async () => {
      refrescarPerfil(await desactivarMfa(contrasena, codigo))
      toast.exito('Verificación en dos pasos desactivada', 'Entrarás solo con tu correo y tu contraseña.')
      onCerrar()
    })
  }

  const errorVisible = error && <p className="form-error">{error}</p>

  if (usuario.mfa_habilitado) {
    return (
      <Modal title="Verificación en dos pasos" subtitle="Activa en tu cuenta" onClose={onCerrar}>
        <form className="form-grid" onSubmit={desactivar}>
          <p className="mfa-texto">Para desactivarla confirma tu contraseña y escribe el código que muestra ahora tu app.</p>
          <Field etiqueta="Contraseña">
            <Input type="password" autoComplete="current-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} required autoFocus />
          </Field>
          <CampoCodigo valor={codigo} onChange={setCodigo} />
          {errorVisible}
          <div className="modal-footer">
            <Button onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" variante="primary" cargando={enviando} disabled={!contrasena || codigo.length !== 6}>
              Desactivar
            </Button>
          </div>
        </form>
      </Modal>
    )
  }

  return (
    <Modal title="Verificación en dos pasos" subtitle="Un código de tu teléfono, además de tu contraseña" onClose={onCerrar}>
      {!secreto ? (
        <form className="form-grid" onSubmit={generar}>
          <p className="mfa-texto">
            Necesitas una app autenticadora en tu teléfono, como Google Authenticator o Microsoft Authenticator. Para empezar,
            confirma tu contraseña.
          </p>
          <Field etiqueta="Contraseña">
            <Input type="password" autoComplete="current-password" value={contrasena} onChange={(e) => setContrasena(e.target.value)} required autoFocus />
          </Field>
          {errorVisible}
          <div className="modal-footer">
            <Button onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" variante="primary" cargando={enviando} disabled={!contrasena}>
              Continuar
            </Button>
          </div>
        </form>
      ) : (
        <form className="form-grid mfa-pasos" onSubmit={activar}>
          <p className="mfa-texto">1. En tu app, agrega una cuenta y escanea este código.</p>
          <CodigoQr uri={secreto.uri} />
          <p className="mfa-texto">Si no puedes escanearlo, escribe esta clave:</p>
          <CopyChip valor={secreto.secreto} etiqueta="Código secreto" completo />
          <p className="mfa-texto">2. Escribe el código de 6 dígitos que muestra la app para confirmar.</p>
          <CampoCodigo valor={codigo} onChange={setCodigo} />
          {errorVisible}
          <div className="modal-footer">
            <Button onClick={onCerrar}>Cancelar</Button>
            <Button type="submit" variante="primary" cargando={enviando} disabled={codigo.length !== 6}>
              Activar
            </Button>
          </div>
        </form>
      )}
    </Modal>
  )
}
