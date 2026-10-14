import { useState } from 'react'
import {
  ArrowsClockwise,
  Check,
  Circle,
  Copy,
  EnvelopeSimple,
  Eye,
  LockKey,
  MagnifyingGlass,
  ShieldCheck,
  User,
  UserGear,
} from '../iconos.js'
import { Button, Field, Modal } from '../ui/index.js'
import { CampoIcono } from '../sesion/Campos.jsx'
import { crearUsuario } from '../../services/api.js'
import useToast from '../../hooks/useToast.js'
import { contrasenaSegura, cumpleRequisitos, requisitosDe } from '../../utils/contrasena.js'
import { copiarAlPortapapeles } from '../../utils/format.js'
import { ALCANCE_ROL, NOMBRE_ROL, ROL } from '../../utils/permisos.js'

const VACIO = { email: '', nombre_completo: '', rol: ROL.VALIDADOR, contrasena_temporal: '' }
const CORREO = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

/** Icono de cada rol en el selector. */
const ICONO_ROL = { ADMIN: UserGear, VALIDADOR: ShieldCheck, AUDITOR: MagnifyingGlass, CONSULTA: Eye }

/** Bloque del formulario con su título y una línea de ayuda. */
function Seccion({ titulo, ayuda, children }) {
  return (
    <section className="alta-seccion">
      <header className="alta-seccion-head">
        <p className="eyebrow">{titulo}</p>
        {ayuda && <p className="alta-seccion-ayuda">{ayuda}</p>}
      </header>
      {children}
    </section>
  )
}

/** Rol como tarjetas de opción (radios nativos) y el alcance del elegido en una línea. */
function SelectorRol({ valor, onChange }) {
  return (
    <>
      <div className="rol-opciones" role="radiogroup" aria-label="Rol de la cuenta">
        {Object.values(ROL).map((rol) => {
          const Icono = ICONO_ROL[rol]
          return (
            <label key={rol} className="rol-opcion">
              <input type="radio" name="rol" value={rol} checked={valor === rol} onChange={() => onChange(rol)} />
              <Icono size={16} aria-hidden="true" />
              <span>{NOMBRE_ROL[rol]}</span>
            </label>
          )
        })}
      </div>
      <p className="rol-alcance" aria-live="polite">
        <strong>{NOMBRE_ROL[valor]}:</strong> {ALCANCE_ROL[valor]}
      </p>
    </>
  )
}

/** Requisitos de la contraseña temporal, cada uno con su marca de cumplido. */
function Requisitos({ contrasena }) {
  return (
    <ul className="requisitos" aria-label="Requisitos de la contraseña">
      {requisitosDe(contrasena).map((r) => (
        <li key={r.id} className={r.cumple ? 'requisito is-ok' : 'requisito'}>
          {r.cumple ? <Check size={12} weight="bold" aria-hidden="true" /> : <Circle size={12} aria-hidden="true" />}
          {r.etiqueta}
          <span className="sr-only">{r.cumple ? ': cumple' : ': falta'}</span>
        </li>
      ))}
    </ul>
  )
}

/**
 * Alta de una cuenta (HU-05), en tres bloques: la persona, su rol con el alcance
 * en una línea y la contraseña temporal, que se puede generar segura con un clic
 * y copiar para entregarla por un medio aparte. La persona la cambia en su primer
 * acceso. El core exige 10 caracteres; aquí se pide además una mayúscula y un
 * número o símbolo (utils/contrasena.js).
 */
export default function AltaUsuario({ onCerrar, onCreado }) {
  const toast = useToast()
  const [form, setForm] = useState(VACIO)
  const [enviando, setEnviando] = useState(false)
  const [copiada, setCopiada] = useState(false)
  const [error, setError] = useState('')
  const cambiar = (campo) => (e) => setForm({ ...form, [campo]: e.target.value })
  const correoValido = CORREO.test(form.email.trim())
  const listo = form.nombre_completo.trim() && correoValido && cumpleRequisitos(form.contrasena_temporal)

  const generar = () => {
    setForm({ ...form, contrasena_temporal: contrasenaSegura() })
    setCopiada(false)
  }

  const copiar = async () => {
    if (await copiarAlPortapapeles(form.contrasena_temporal)) {
      setCopiada(true)
      setTimeout(() => setCopiada(false), 1600)
    } else {
      toast.error('No se pudo copiar', 'El navegador bloqueó el portapapeles.')
    }
  }

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
      <form className="alta-cuenta" onSubmit={enviar} noValidate>
        <Seccion titulo="Persona">
          <div className="field-row">
            <Field etiqueta="Nombre completo">
              <CampoIcono
                icono={User}
                value={form.nombre_completo}
                onChange={cambiar('nombre_completo')}
                maxLength={150}
                placeholder="Nombre y apellidos"
                required
                autoFocus
              />
            </Field>
            <Field
              etiqueta="Correo institucional"
              retro={form.email && !correoValido ? { estado: 'invalido', mensaje: 'Escribe un correo válido.' } : null}
            >
              <CampoIcono
                icono={EnvelopeSimple}
                type="email"
                value={form.email}
                estado={form.email && !correoValido ? 'invalido' : undefined}
                onChange={cambiar('email')}
                maxLength={150}
                placeholder="nombre@empresa.com"
                autoComplete="off"
                required
              />
            </Field>
          </div>
        </Seccion>

        <Seccion titulo="Rol y alcance" ayuda="Define lo que la persona podrá ver y hacer.">
          <SelectorRol valor={form.rol} onChange={(rol) => setForm({ ...form, rol })} />
        </Seccion>

        <Seccion titulo="Contraseña temporal" ayuda="Entrégala por un medio aparte; se cambia en el primer acceso.">
          <Field etiqueta="Contraseña">
            <CampoIcono
              icono={LockKey}
              className="mono"
              value={form.contrasena_temporal}
              onChange={(e) => {
                setForm({ ...form, contrasena_temporal: e.target.value })
                setCopiada(false)
              }}
              maxLength={72}
              placeholder="Escríbela o genera una segura"
              autoComplete="off"
              spellCheck="false"
              required
              accion={
                <>
                  <button
                    type="button"
                    className="campo-icono-boton"
                    onClick={generar}
                    aria-label="Generar contraseña segura"
                    data-tooltip="Generar segura"
                  >
                    <ArrowsClockwise size={16} />
                  </button>
                  <button
                    type="button"
                    className={copiada ? 'campo-icono-boton is-ok' : 'campo-icono-boton'}
                    onClick={copiar}
                    disabled={!form.contrasena_temporal}
                    aria-label={copiada ? 'Contraseña copiada' : 'Copiar contraseña'}
                    data-tooltip={copiada ? 'Copiada' : 'Copiar'}
                  >
                    {copiada ? <Check size={16} /> : <Copy size={16} />}
                  </button>
                </>
              }
            />
          </Field>
          <Requisitos contrasena={form.contrasena_temporal} />
        </Seccion>

        {error && <p className="form-error">{error}</p>}

        <div className="modal-footer">
          <Button onClick={onCerrar} disabled={enviando}>
            Cancelar
          </Button>
          <Button type="submit" variante="primary" cargando={enviando} disabled={!listo}>
            {enviando ? 'Creando…' : 'Crear cuenta'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}
