/**
 * Control segmentado para los filtros rápidos. Cada opción admite un conteo
 * y un tono de estado, que se pinta como punto junto a la etiqueta.
 */
export default function Segmented({ opciones, valor, onChange, label, role = 'group' }) {
  const esTabs = role === 'tablist'
  return (
    <div className="segmented" role={role} aria-label={label}>
      {opciones.map((o) => {
        const activo = valor === o.id
        return (
          <button
            key={o.id}
            type="button"
            role={esTabs ? 'tab' : undefined}
            aria-selected={esTabs ? activo : undefined}
            aria-pressed={esTabs ? undefined : activo}
            className={`segmented-item ${activo ? 'is-active' : ''}`}
            onClick={() => onChange(o.id)}
            data-tooltip={o.tooltip}
          >
            {o.tono && <span className={`status-dot status-dot--${o.tono}`} aria-hidden="true" />}
            {o.label}
            {o.conteo !== undefined && <span className="segmented-count tabular">{o.conteo}</span>}
          </button>
        )
      })}
    </div>
  )
}
