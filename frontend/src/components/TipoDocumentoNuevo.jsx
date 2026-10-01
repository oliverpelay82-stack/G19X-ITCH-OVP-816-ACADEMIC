import { useState } from 'react'
import { FilePlus2 } from 'lucide-react'
import { Button, Field, Input, Modal, Select } from './ui/index.js'
import useToast from '../hooks/useToast.js'
import { createRegla } from '../services/api.js'
import {
  codigoDeTipo,
  getSeveridadMeta,
  SEVERIDADES,
  TIPO_DOCUMENTO_LABEL,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_EXPEDIENTE,
} from '../constants.js'

const FORM_INICIAL = { nombre: '', criterio: '', recomendacion: '', tipoExpediente: '', severidad: 'CRITICA' }

/**
 * RF-09 · Alta de un tipo de documento nuevo (RDS-01) con el criterio que la IA
 * debe verificar (RDS-02). Crea una regla RDS que declara el tipo y, si se indica
 * en qué tipo de expediente es obligatorio, su regla RIE-01 (RF-06). Todo
 * documento de este tipo pasa a revisión humana (RDS-03).
 * Diagrama: docs/uml/rf09-actividad-tipo-documento-nuevo.puml.
 */
export default function TipoDocumentoNuevo({ onCreado, disabled }) {
  const toast = useToast()
  const [abierto, setAbierto] = useState(false)
  const [form, setForm] = useState(FORM_INICIAL)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const nombre = form.nombre.trim().replace(/\s+/g, ' ')
  const codigo = codigoDeTipo(nombre)
  const repetido = Boolean(codigo && TIPO_DOCUMENTO_LABEL[codigo])
  const valido =
    nombre.length >= 3 && codigo.length >= 2 && !repetido && form.criterio.trim().length >= 10 && form.recomendacion.trim()

  const cerrar = () => {
    setAbierto(false)
    setForm(FORM_INICIAL)
    setError('')
  }

  const enviar = async (e) => {
    e.preventDefault()
    setEnviando(true)
    setError('')
    const recomendacion = form.recomendacion.trim()
    try {
      await createRegla({
        codigo_regla: `RDS-${codigo}`,
        nombre_regla: nombre,
        familia_regla: 'RDS',
        descripcion: form.criterio.trim(),
        severidad: form.tipoExpediente ? form.severidad : 'MEDIA',
        accion: recomendacion,
        tipo_documento: codigo,
        documento_obligatorio: false,
        tipo_expediente: form.tipoExpediente || null,
      })
    } catch (err) {
      setError(err.message)
      setEnviando(false)
      return
    }
    if (form.tipoExpediente) {
      const expediente = TIPO_EXPEDIENTE_LABEL[form.tipoExpediente].toLowerCase()
      try {
        // Misma forma que las reglas RIE-01 del catálogo base (seed_reglas_validacion.py).
        await createRegla({
          codigo_regla: `RIE-01-${codigo}`,
          nombre_regla: `Completitud: ${nombre}`,
          familia_regla: 'RIE',
          descripcion: `El expediente ${expediente} debe contener: ${nombre}. Mientras falte, el expediente no puede obtener estatus de aprobado (RIE-01).`,
          severidad: form.severidad,
          accion: `Semáforo Rojo: falta ${nombre}.`,
          tipo_documento: codigo,
          documento_obligatorio: true,
          tipo_expediente: form.tipoExpediente,
        })
      } catch (err) {
        // El tipo ya existe: solo faltó volverlo obligatorio. Se dice cuál y cómo completarlo.
        toast.alerta('Tipo creado, pero no quedó como obligatorio', `${err.message} Créalo como regla RIE desde «Nueva regla».`)
        onCreado?.()
        cerrar()
        setEnviando(false)
        return
      }
    }
    toast.exito('Tipo de documento creado', `${nombre} · ya se puede custodiar en los expedientes`)
    onCreado?.()
    cerrar()
    setEnviando(false)
  }

  return (
    <>
      <Button icono={FilePlus2} onClick={() => setAbierto(true)} disabled={disabled}>
        Nuevo tipo de documento
      </Button>
      {abierto && (
        <Modal
          title="Nuevo tipo de documento"
          subtitle="Un documento que el catálogo no contempla, con lo que la IA debe verificar en él"
          onClose={cerrar}
        >
          <form className="form-grid" onSubmit={enviar}>
            <Field
              etiqueta="Nombre del tipo"
              ayuda={codigo ? `Código: ${codigo}` : 'Ej. Permiso de Impacto Ambiental'}
              retro={repetido ? { estado: 'invalido', mensaje: 'Ya existe un tipo de documento con ese nombre.' } : null}
            >
              <Input
                required
                minLength={3}
                maxLength={150}
                estado={repetido ? 'invalido' : undefined}
                value={form.nombre}
                onChange={(e) => setForm({ ...form, nombre: e.target.value })}
              />
            </Field>

            <Field
              etiqueta="Qué debe verificar la IA"
              ayuda="En lenguaje natural. Cada documento de este tipo pasará a revisión de un analista."
            >
              <textarea
                required
                minLength={10}
                rows={3}
                placeholder="Ej. Verificar que el documento indique expresamente que el inmueble cuenta con visto bueno vigente de Protección Civil."
                value={form.criterio}
                onChange={(e) => setForm({ ...form, criterio: e.target.value })}
              />
            </Field>

            <Field etiqueta="Qué hacer si no se cumple">
              <Input
                required
                maxLength={255}
                placeholder="Ej. Solicitar al titular el visto bueno vigente de Protección Civil."
                value={form.recomendacion}
                onChange={(e) => setForm({ ...form, recomendacion: e.target.value })}
              />
            </Field>

            <div className="field-row">
              <Field etiqueta="Obligatorio en">
                <Select value={form.tipoExpediente} onChange={(e) => setForm({ ...form, tipoExpediente: e.target.value })}>
                  <option value="">Ningún expediente (opcional)</option>
                  {TIPOS_EXPEDIENTE.map((t) => (
                    <option key={t.value} value={t.value}>
                      Expediente {t.label.toLowerCase()}
                    </option>
                  ))}
                </Select>
              </Field>
              <Field etiqueta="Severidad si falta">
                <Select
                  value={form.severidad}
                  onChange={(e) => setForm({ ...form, severidad: e.target.value })}
                  disabled={!form.tipoExpediente}
                >
                  {SEVERIDADES.map((s) => (
                    <option key={s} value={s}>
                      {getSeveridadMeta(s).label}
                    </option>
                  ))}
                </Select>
              </Field>
            </div>

            {error && <p className="form-error">{error}</p>}

            <div className="modal-footer">
              <Button onClick={cerrar}>Cancelar</Button>
              <Button type="submit" variante="primary" cargando={enviando} disabled={!valido}>
                Crear tipo de documento
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </>
  )
}
