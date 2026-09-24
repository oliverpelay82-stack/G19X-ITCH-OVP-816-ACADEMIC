import { useState } from 'react'
import { Check, Copy, Search, X } from 'lucide-react'
import useToast from '../hooks/useToast.js'
import { copiarAlPortapapeles } from '../utils/format.js'

/**
 * Primitivas compartidas por las pestañas: buscador, control segmentado,
 * estado vacío y chip de copiado. Mantienen idéntica la barra de
 * herramientas de cada vista y evitan duplicar la lógica en cada pestaña.
 */

/** Buscador con icono y botón para limpiar. */
export function SearchBox({ value, onChange, placeholder, label, compacto = false }) {
  return (
    <label className={`search-box ${compacto ? 'search-box--sm' : ''}`}>
      <Search size={14} strokeWidth={2} aria-hidden="true" />
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label || placeholder}
      />
      {value && (
        <button type="button" className="search-clear" onClick={() => onChange('')} aria-label="Limpiar búsqueda">
          <X size={12} strokeWidth={2} />
        </button>
      )}
    </label>
  )
}

/**
 * Control segmentado para los filtros rápidos. Cada opción admite un conteo
 * y un tono de estado, que se pinta como punto junto a la etiqueta.
 */
export function Segmented({ opciones, valor, onChange, label, role = 'group' }) {
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

/** Estado vacío con icono, título y una línea de ayuda. */
export function EmptyState({ icon: Icono, titulo, descripcion, children }) {
  return (
    <div className="empty-state">
      {Icono && (
        <span className="empty-icon" aria-hidden="true">
          <Icono size={18} strokeWidth={1.75} />
        </span>
      )}
      <p className="empty-title">{titulo}</p>
      {descripcion && <p className="empty-desc">{descripcion}</p>}
      {children}
    </div>
  )
}

/** Fila de tabla que aloja el estado vacío a todo lo ancho. */
export function EmptyRow({ columnas, ...props }) {
  return (
    <tr className="empty-row">
      <td colSpan={columnas}>
        <EmptyState {...props} />
      </td>
    </tr>
  )
}

/** Valor monoespaciado (RFC, hash) con copiado de un clic y confirmación. */
export function CopyChip({ valor, visible, etiqueta, completo = false }) {
  const [copiado, setCopiado] = useState(false)
  const toast = useToast()

  const copiar = async (e) => {
    e.stopPropagation()
    if (await copiarAlPortapapeles(valor)) {
      setCopiado(true)
      toast.exito(`${etiqueta} copiado`, visible ?? valor)
      setTimeout(() => setCopiado(false), 1400)
    } else {
      toast.error('No se pudo copiar', 'El navegador bloqueó el portapapeles.')
    }
  }

  return (
    <button
      type="button"
      className={`copy-chip ${completo ? 'copy-chip--full' : ''}`}
      onClick={copiar}
      data-tooltip={copiado ? 'Copiado' : `Copiar ${etiqueta}`}
    >
      <span className="mono">{visible ?? valor}</span>
      {copiado ? <Check size={12} strokeWidth={2.4} className="copy-ok" /> : <Copy size={12} strokeWidth={2} />}
    </button>
  )
}
