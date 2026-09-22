/**
 * Placeholders de carga. Sustituyen a los textos planos de "Cargando…"
 * para que la interfaz conserve su silueta mientras llegan los datos.
 */

export function Skeleton({ w = '100%', h = 14, r = 'var(--r-xs)', className = '', style }) {
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
          <Skeleton w={j === 0 ? '72%' : `${42 + ((i + j) % 4) * 11}%`} />
        </td>
      ))}
    </tr>
  ))
}

/** Rejilla de tarjetas fantasma para las vistas que no son tabla. */
export function SkeletonCards({ count = 6, height = 168 }) {
  return (
    <div className="skeleton-card-grid">
      {Array.from({ length: count }, (_, i) => (
        <div className="skeleton-card" key={i} style={{ minHeight: height }}>
          <div className="skeleton-card-top">
            <Skeleton w={104} h={22} r="var(--r-full)" />
            <Skeleton w={40} h={22} r="var(--r-full)" />
          </div>
          <Skeleton w="76%" h={17} />
          <Skeleton w="94%" h={12} />
          <Skeleton w="58%" h={12} />
          <Skeleton w="100%" h={8} r="var(--r-full)" style={{ marginTop: 'auto' }} />
        </div>
      ))}
    </div>
  )
}

export default Skeleton
