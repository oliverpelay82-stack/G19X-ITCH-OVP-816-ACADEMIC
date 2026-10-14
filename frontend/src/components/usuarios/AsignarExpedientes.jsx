import { useEffect, useMemo, useState } from 'react'
import { Button, Modal, SearchBox } from '../ui/index.js'
import { asignarExpedientes, getExpedientesDeUsuario } from '../../services/api.js'
import useToast from '../../hooks/useToast.js'
import { coincideEn, normalizar } from '../../utils/busqueda.js'
import { NOMBRE_ROL, ROL } from '../../utils/permisos.js'
import { plural } from '../../utils/format.js'

/** Para qué sirve asignar, según el rol de la cuenta (HU-31 y RF-20). */
const PROPOSITO = {
  [ROL.CONSULTA]: 'Verá el semáforo de estos expedientes y nada más.',
  [ROL.VALIDADOR]: 'Queda como responsable de estos expedientes.',
}

/**
 * Expedientes asignados a una cuenta (PUT /usuarios/{id}/expedientes): la lista
 * marcada reemplaza la anterior. A los demás asignados de cada expediente no los
 * toca, y cada expediente que cambia deja su evento en la bitácora.
 */
export default function AsignarExpedientes({ usuario, expedientes, onCerrar, onGuardado }) {
  const toast = useToast()
  const [marcados, setMarcados] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [guardando, setGuardando] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    let vigente = true
    getExpedientesDeUsuario(usuario.id)
      .then((ids) => vigente && setMarcados(new Set(ids)))
      .catch((err) => vigente && (setMarcados(new Set()), setError(err.message)))
    return () => {
      vigente = false
    }
  }, [usuario.id])

  const visibles = useMemo(
    () =>
      expedientes.filter((e) =>
        coincideEn([e.codigo_expediente, e.nombre, e.titular?.razon_social, e.titular?.rfc], normalizar(busqueda))
      ),
    [expedientes, busqueda]
  )

  const alternar = (id) =>
    setMarcados((actual) => {
      const nuevo = new Set(actual)
      if (nuevo.has(id)) nuevo.delete(id)
      else nuevo.add(id)
      return nuevo
    })

  const guardar = async () => {
    setGuardando(true)
    setError('')
    try {
      const ids = await asignarExpedientes(usuario.id, [...marcados])
      toast.exito('Asignación guardada', `${usuario.nombre_completo} · ${plural(ids.length, 'expediente', 'expedientes')}`)
      onGuardado()
    } catch (err) {
      setError(err.message)
    } finally {
      setGuardando(false)
    }
  }

  return (
    <Modal
      title={`Expedientes de ${usuario.nombre_completo}`}
      subtitle={`${NOMBRE_ROL[usuario.rol]}. ${PROPOSITO[usuario.rol] || 'La asignación no cambia lo que su rol puede ver.'}`}
      onClose={onCerrar}
    >
      <div className="form-grid asignacion">
        <SearchBox value={busqueda} onChange={setBusqueda} placeholder="Buscar por folio, nombre o empresa…" label="Buscar expedientes" />
        <div className="asignacion-lista" role="group" aria-label="Expedientes">
          {marcados === null ? (
            <p className="mfa-texto">Cargando…</p>
          ) : visibles.length === 0 ? (
            <p className="mfa-texto">Ningún expediente coincide.</p>
          ) : (
            visibles.map((e) => (
              <label key={e.id} className="asignacion-opcion">
                <input type="checkbox" checked={marcados.has(e.id)} onChange={() => alternar(e.id)} />
                <span className="asignacion-detalle">
                  <span>{e.nombre || e.titular?.razon_social || e.codigo_expediente}</span>
                  <span className="mono">
                    {e.codigo_expediente}
                    {e.titular?.razon_social ? ` · ${e.titular.razon_social}` : ''}
                  </span>
                </span>
              </label>
            ))
          )}
        </div>
        {error && <p className="form-error">{error}</p>}
        <div className="modal-footer">
          <Button onClick={onCerrar}>Cancelar</Button>
          <Button variante="primary" cargando={guardando} disabled={marcados === null} onClick={guardar}>
            Guardar asignación
            {marcados && ` (${marcados.size})`}
          </Button>
        </div>
      </div>
    </Modal>
  )
}
