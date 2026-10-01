import { useMemo } from 'react'
import { Card } from './ui/index.js'
import { ALERTA_META } from '../constants.js'
import FolioExpediente from './FolioExpediente.jsx'

/** Folios que se muestran por categoría; el resto está en Alertas. */
const MAX_FOLIOS = 3

const diasTexto = (n) => (n === 0 ? 'desde hoy' : `${n} ${n === 1 ? 'día' : 'días'}`)

/**
 * Hallazgos por categoría (RF-22, HU-26) con lo que espera al analista: cada
 * categoría con su conteo, su barra y los expedientes donde aparece (cada folio
 * abre su expediente), y la antigüedad de lo que espera ratificación (PLUS-20).
 * Reúne la lista «Por categoría» y la tarjeta «Pendientes del analista», que
 * desglosaban las mismas alertas (PRD §13.1, depuración de redundancias).
 */
export default function HallazgosCategoria({ expedientes, onAbrirExpediente }) {
  const { categorias, total } = useMemo(() => {
    const porCodigo = new Map()
    for (const e of expedientes) {
      for (const a of e.evaluacion?.alertas || []) {
        const grupo = porCodigo.get(a.codigo) || { codigo: a.codigo, total: 0, porExpediente: new Map() }
        grupo.total += 1
        grupo.porExpediente.set(e.id, { expediente: e, n: (grupo.porExpediente.get(e.id)?.n || 0) + 1 })
        porCodigo.set(a.codigo, grupo)
      }
    }
    const lista = [...porCodigo.values()]
      .map((g) => ({ ...g, porExpediente: [...g.porExpediente.values()].sort((a, b) => b.n - a.n) }))
      .sort((a, b) => b.total - a.total)
    return { categorias: lista, total: lista.reduce((s, g) => s + g.total, 0) }
  }, [expedientes])

  const esperas = useMemo(
    () =>
      expedientes
        .flatMap((e) => e.evaluacion?.documentos || [])
        .map((d) => d.dias_en_espera)
        .filter((n) => n !== null && n !== undefined),
    [expedientes]
  )

  return (
    <Card as="article" className="report-card">
      <p className="eyebrow">Por categoría · {total}</p>
      {esperas.length > 0 && (
        <p className="tablero-antiguedad">
          {esperas.length === 1 ? 'Un dictamen espera' : `${esperas.length} dictámenes esperan`} ratificación · el más
          antiguo, <span className="tabular">{diasTexto(Math.max(...esperas))}</span>
          {esperas.length > 1 && (
            <>
              ; promedio,{' '}
              <span className="tabular">{diasTexto(Math.round(esperas.reduce((s, n) => s + n, 0) / esperas.length))}</span>
            </>
          )}
          .
        </p>
      )}
      {total === 0 ? (
        <p className="field-hint">Sin hallazgos vigentes.</p>
      ) : (
        <ul className="tablero-lista">
          {categorias.map((g) => (
            <li key={g.codigo} className="tablero-grupo">
              <div className="dist-row">
                <span className="dist-label">{ALERTA_META[g.codigo]?.label || g.codigo}</span>
                <span className="dist-track" aria-hidden="true">
                  <span className="dist-fill" style={{ width: `${Math.round((g.total / total) * 100)}%` }} />
                </span>
                <span className="dist-value tabular">{g.total}</span>
              </div>
              <div className="tablero-chips">
                {g.porExpediente.slice(0, MAX_FOLIOS).map(({ expediente, n }) => (
                  <button
                    key={expediente.id}
                    type="button"
                    className="chip chip--xs"
                    onClick={() => onAbrirExpediente?.(expediente.id)}
                    title={expediente.titular?.razon_social || undefined}
                  >
                    <FolioExpediente expediente={expediente} enfocable={false} className="mono" />
                    {/* Espacio de no separación: el chip es inline-flex y recorta el espacio inicial del texto. */}
                    {n > 1 ? `\u00a0· ${n}` : ''}
                  </button>
                ))}
                {g.porExpediente.length > MAX_FOLIOS && (
                  <span className="field-hint">y {g.porExpediente.length - MAX_FOLIOS} más</span>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
