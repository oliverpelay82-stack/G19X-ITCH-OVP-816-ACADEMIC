import { useState } from 'react'
import { PencilSimple } from './iconos.js'
import { Button, Field, Input } from './ui/index.js'
import useToast from '../hooks/useToast.js'
import usePermiso from '../hooks/usePermiso.js'
import useUmbralesVencimiento from '../hooks/useUmbralesVencimiento.js'
import { cambiarUmbralesVencimiento } from '../services/api.js'
import { formatFecha } from '../utils/format.js'

const SEVERIDADES = ['Media', 'Media-alta', 'Alta']

const enumerar = (dias) => `${dias.slice(0, -1).join(', ')} y ${dias.at(-1)}`

/**
 * HU-14 (RF-17): días de anticipación de las alertas de vencimiento, en el detalle
 * de la regla RCV-01 (vigencia). Todos los ven; solo el administrador los cambia.
 * Uno por severidad de la alerta «Próximo a vencer», de mayor a menor; el core
 * valida y registra el cambio en la bitácora.
 */
export default function AvisosVencimiento() {
  const administrar = usePermiso('administrarReglas')
  const toast = useToast()
  const { umbrales, configurado, actualizado_en: actualizadoEn, recargar } = useUmbralesVencimiento()
  const [valores, setValores] = useState(null)
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  const editar = () => {
    setValores(umbrales.map(String))
    setError('')
  }

  const guardar = async (e) => {
    e.preventDefault()
    setGuardando(true)
    setError('')
    try {
      const nuevos = valores.map((v) => Number.parseInt(v, 10))
      await cambiarUmbralesVencimiento(nuevos)
      await recargar()
      setValores(null)
      toast.exito('Avisos de vencimiento actualizados', `Se avisará a ${enumerar(nuevos)} días del vencimiento.`)
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  if (valores) {
    return (
      <form className="avisos-vencimiento" onSubmit={guardar} noValidate>
        <div className="avisos-vencimiento-campos">
          {SEVERIDADES.map((severidad, i) => (
            <Field key={severidad} etiqueta={`Alerta ${severidad.toLowerCase()} (días)`}>
              <Input
                type="number"
                min={1}
                max={365}
                inputMode="numeric"
                value={valores[i]}
                estado={error ? 'invalido' : undefined}
                onChange={(ev) => setValores(valores.map((v, j) => (j === i ? ev.target.value : v)))}
              />
            </Field>
          ))}
        </div>
        {error && (
          <p className="avisos-vencimiento-error" role="alert">
            {error}
          </p>
        )}
        <div className="avisos-vencimiento-acciones">
          <Button type="submit" variante="primary" compacto cargando={guardando}>
            Guardar
          </Button>
          <Button compacto onClick={() => setValores(null)} disabled={guardando}>
            Cancelar
          </Button>
        </div>
      </form>
    )
  }

  return (
    <div className="avisos-vencimiento">
      <span>
        A {enumerar(umbrales)} días del vencimiento (alerta {SEVERIDADES.map((s) => s.toLowerCase()).join(', ')})
        {configurado && actualizadoEn ? ` · ajustado el ${formatFecha(actualizadoEn)}` : ''}
      </span>
      {administrar && (
        <Button compacto icono={PencilSimple} onClick={editar}>
          Cambiar
        </Button>
      )}
    </div>
  )
}

