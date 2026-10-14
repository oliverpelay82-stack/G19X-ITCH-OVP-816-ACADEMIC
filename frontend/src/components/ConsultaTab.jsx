import { useMemo, useState } from 'react'
import { FolderOpen } from './iconos.js'
import EstadoBadge from './EstadoBadge.jsx'
import { SkeletonRows } from './Skeleton.jsx'
import { CORE_FUERA_DE_LINEA, sinRespuesta } from './sinRespuesta.js'
import { Card, EmptyRow, SearchBox } from './ui/index.js'
import { TIPO_EXPEDIENTE_LABEL } from '../constants.js'
import { coincideEn, normalizar } from '../utils/busqueda.js'
import { formatRelativo } from '../utils/format.js'

/**
 * Vista del usuario de consulta (HU-31): el semáforo de los expedientes que el
 * administrador le asignó, sin documentos, dictámenes, alertas ni configuración.
 * El core solo le entrega estos datos (GET /expedientes/asignados), así que la
 * vista no oculta nada: no lo recibe.
 */
export default function ConsultaTab({ asignados, loading, isOnline }) {
  const [busqueda, setBusqueda] = useState('')
  const filtrados = useMemo(
    () => asignados.filter((e) => coincideEn([e.codigo_expediente, e.nombre, e.razon_social, e.rfc], normalizar(busqueda))),
    [asignados, busqueda]
  )

  const vacio =
    !isOnline && asignados.length === 0
      ? sinRespuesta(CORE_FUERA_DE_LINEA, 'La lista se actualizará en cuanto vuelva a responder.')
      : asignados.length === 0
        ? {
            icon: FolderOpen,
            titulo: 'Aún no tienes expedientes asignados',
            descripcion: 'Pide al administrador del sistema que te asigne los expedientes que debes seguir.',
          }
        : { icon: FolderOpen, titulo: 'Ningún expediente coincide', descripcion: 'Prueba con otro término.' }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por folio, nombre, empresa o RFC…"
          label="Buscar en mis expedientes"
        />
      </div>
      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                <th scope="col">Expediente</th>
                <th scope="col">Empresa</th>
                <th scope="col">Tipo</th>
                <th scope="col">Semáforo</th>
                <th scope="col">Actualizado</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <SkeletonRows rows={4} cols={5} />
              ) : filtrados.length === 0 ? (
                <EmptyRow columnas={5} {...vacio} />
              ) : (
                filtrados.map((e) => (
                  <tr key={e.id}>
                    <td>
                      <div className="cell-stack">
                        <span className="identity-name">{e.nombre || 'Expediente sin nombre'}</span>
                        <span className="cell-sub mono tabular">{e.codigo_expediente}</span>
                      </div>
                    </td>
                    <td>
                      <div className="cell-stack">
                        <span>{e.razon_social}</span>
                        <span className="cell-sub mono">{e.rfc}</span>
                      </div>
                    </td>
                    <td>{TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente}</td>
                    <td>
                      <EstadoBadge estado={e.estado_cumplimiento} />
                    </td>
                    <td className="tabular">{e.actualizado_en ? formatRelativo(e.actualizado_en) : '—'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  )
}
