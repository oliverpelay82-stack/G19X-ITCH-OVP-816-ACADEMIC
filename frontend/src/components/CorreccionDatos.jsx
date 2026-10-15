import { useState } from 'react'
import { PencilSimple } from './iconos.js'
import { Button, Field, Input, Modal, Select } from './ui/index.js'
import useToast from '../hooks/useToast.js'
import { corregirTitular, renombrarExpediente } from '../services/api.js'
import { categoriaTitular } from '../constants.js'

const CATEGORIAS = ['PROVEEDOR', 'CLIENTE']

/**
 * Corrección de datos de captura (ESTADO_DEL_DESARROLLO §3, ui-actividad-correccion-datos.puml).
 * Cada cambio queda en la bitácora con su valor anterior y el nuevo; el RFC, el
 * tipo de persona y el tipo de expediente no se editan.
 */
function FormularioCorreccion({ titulo, subtitulo, onCerrar, onGuardar, puedeGuardar, children }) {
  const toast = useToast()
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    try {
      const aviso = await onGuardar()
      toast.exito(aviso.titulo, aviso.detalle)
      onCerrar()
    } catch (err) {
      setError(err.message)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <Modal title={titulo} subtitle={subtitulo} onClose={onCerrar}>
      <form className="form-grid" onSubmit={enviar}>
        {children}
        {error && <p className="form-error">{error}</p>}
        <div className="modal-footer">
          <Button onClick={onCerrar}>Cancelar</Button>
          <Button type="submit" variante="primary" cargando={enviando} disabled={!puedeGuardar}>
            Guardar corrección
          </Button>
        </div>
      </form>
    </Modal>
  )
}

/** «Corregir datos» de una empresa: razón social y categoría. */
export function CorregirEmpresa({ titular, onCorregido, disabled }) {
  const [abierto, setAbierto] = useState(false)
  const [form, setForm] = useState({ razon_social: '', categoria: '' })
  const abrir = () => {
    setForm({ razon_social: titular.razon_social, categoria: titular.categoria })
    setAbierto(true)
  }
  const cambios = Object.fromEntries(
    Object.entries({ razon_social: form.razon_social.trim().replace(/\s+/g, ' '), categoria: form.categoria }).filter(
      ([campo, valor]) => valor !== titular[campo]
    )
  )
  const valido = form.razon_social.trim().length >= 3 && Object.keys(cambios).length > 0
  // Una categoría heredada (p. ej. «Proveedor crítico») se conserva como opción.
  const categorias = CATEGORIAS.includes(titular.categoria) ? CATEGORIAS : [...CATEGORIAS, titular.categoria]

  return (
    <>
      <Button compacto icono={PencilSimple} onClick={abrir} disabled={disabled}>
        Corregir datos
      </Button>
      {abierto && (
        <FormularioCorreccion
          titulo="Corregir datos de la empresa"
          subtitulo={`RFC ${titular.rfc} · el RFC y el tipo de persona no se editan`}
          onCerrar={() => setAbierto(false)}
          puedeGuardar={valido}
          onGuardar={async () => {
            await corregirTitular(titular.id, cambios)
            onCorregido?.()
            return { titulo: 'Datos corregidos', detalle: 'El cambio quedó en la bitácora con su valor anterior.' }
          }}
        >
          <Field etiqueta="Razón social / Nombre completo">
            <Input
              required
              minLength={3}
              maxLength={200}
              value={form.razon_social}
              onChange={(e) => setForm({ ...form, razon_social: e.target.value })}
            />
          </Field>
          <Field etiqueta="Categoría">
            <Select value={form.categoria} onChange={(e) => setForm({ ...form, categoria: e.target.value })}>
              {categorias.map((c) => (
                <option key={c} value={c}>
                  {categoriaTitular(c)}
                </option>
              ))}
            </Select>
          </Field>
        </FormularioCorreccion>
      )}
    </>
  )
}

/** «Renombrar» un expediente: solo su nombre descriptivo (el tipo decide qué se exige). */
export function RenombrarExpediente({ exp, onRenombrado, disabled }) {
  const [abierto, setAbierto] = useState(false)
  const [nombre, setNombre] = useState('')
  const limpio = nombre.trim().replace(/\s+/g, ' ')

  return (
    <>
      <Button
        compacto
        icono={PencilSimple}
        onClick={() => {
          setNombre(exp.nombre || '')
          setAbierto(true)
        }}
        disabled={disabled}
      >
        Renombrar
      </Button>
      {abierto && (
        <FormularioCorreccion
          titulo="Renombrar expediente"
          subtitulo={`${exp.codigo_expediente} · el tipo de expediente no se edita`}
          onCerrar={() => setAbierto(false)}
          puedeGuardar={limpio !== (exp.nombre || '')}
          onGuardar={async () => {
            await renombrarExpediente(exp.id, limpio || null)
            onRenombrado?.()
            return {
              titulo: limpio ? 'Expediente renombrado' : 'Nombre quitado',
              detalle: 'El cambio quedó en el historial del expediente.',
            }
          }}
        >
          <Field etiqueta="Nombre del expediente" ayuda="Vacío para quitarlo.">
            <Input maxLength={150} value={nombre} onChange={(e) => setNombre(e.target.value)} />
          </Field>
        </FormularioCorreccion>
      )}
    </>
  )
}
