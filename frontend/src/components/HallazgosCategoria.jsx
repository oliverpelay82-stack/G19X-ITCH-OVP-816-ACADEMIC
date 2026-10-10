import { useMemo } from 'react'
import { Card, Tag } from './ui/index.js'
import { ALERTA_META } from '../constants.js'
import { plural } from '../utils/format.js'

const diasTexto = (n) => (n === 0 ? 'desde hoy' : plural(n, 'día', 'días'))
const documentosTexto = (n) => plural(n, 'documento', 'documentos')

/**
 * Hallazgos por categoría (RF-22, HU-26) con lo que espera al analista: cada
 * categoría como etiqueta, con su conteo y su barra, y la antigüedad de lo que
 * espera ratificación (PLUS-20). Los folios no se repiten aquí: cada hallazgo,
 * con su expediente, está en Alertas y en la tabla de esta misma vista.
 * Reúne la lista «Por categoría» y la tarjeta «Pendientes del analista», que
 * desglosaban las mismas alertas (PRD §13.1, depuración de redundancias).
 */
export default function HallazgosCategoria({ expedientes }) {
  const { categorias, total } = useMemo(() => {
    const porCodigo = new Map()
    for (const e of expedientes) {
      for (const a of e.evaluacion?.alertas || []) {
        porCodigo.set(a.codigo, (porCodigo.get(a.codigo) || 0) + 1)
      }
    }
    const lista = [...porCodigo.entries()].map(([codigo, n]) => ({ codigo, total: n })).sort((a, b) => b.total - a.total)
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
            <li key={g.codigo} className="dist-row">
              <span className="dist-label">
                <Tag>{ALERTA_META[g.codigo]?.label || g.codigo}</Tag>
              </span>
              <span className="dist-track" aria-hidden="true">
                <span className="dist-fill" style={{ width: `${Math.round((g.total / total) * 100)}%` }} />
              </span>
              <span className="dist-value tabular">{documentosTexto(g.total)}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  )
}
