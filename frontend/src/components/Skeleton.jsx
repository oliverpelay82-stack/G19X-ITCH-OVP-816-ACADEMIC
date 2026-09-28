import { Card } from './ui/index.js'

/**
 * Placeholders de carga. Sustituyen a los textos planos de "Cargando…"
 * para que la interfaz conserve su silueta mientras llegan los datos.
 */

export function Skeleton({ w = '100%', h = 12, r = 'var(--r-xs)', className = '', style }) {
  return (
    <span
      className={`skeleton ${className}`}
      style={{ width: w, height: h, borderRadius: r, ...style }}
      aria-hidden="true"
    />
  )
}

/** Filas fantasma con el mismo número de columnas que la tabla real. */
export function SkeletonRows({ rows = 5, cols = 5 }) {
  return Array.from({ length: rows }, (_, i) => (
    <tr key={i} className="skeleton-row">
      {Array.from({ length: cols }, (_, j) => (
        <td key={j}>
          <Skeleton w={j === 0 ? '64%' : `${40 + ((i + j) % 4) * 10}%`} />
        </td>
      ))}
    </tr>
  ))
}

/** Rejilla de tarjetas fantasma para las vistas que no son tabla. */
export function SkeletonCards({ count = 6, height = 160 }) {
  return (
    <div className="card-grid">
      {Array.from({ length: count }, (_, i) => (
        <Card className="skeleton-card" key={i} style={{ minHeight: height }}>
          <Skeleton w="40%" h={12} />
          <Skeleton w="72%" h={16} />
          <Skeleton w="92%" h={12} />
          <Skeleton w="100%" h={4} r="var(--r-full)" style={{ marginTop: 'auto' }} />
        </Card>
      ))}
    </div>
  )
}

export default Skeleton
