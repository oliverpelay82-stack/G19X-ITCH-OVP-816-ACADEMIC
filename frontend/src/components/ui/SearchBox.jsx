import { Search, X } from 'lucide-react'

/** Buscador con icono y botón para limpiar. */
export default function SearchBox({ value, onChange, placeholder, label, compacto = false }) {
  return (
    <label className={`search-box ${compacto ? 'search-box--sm' : ''}`}>
      <Search size={14} aria-hidden="true" />
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        aria-label={label || placeholder}
      />
      {value && (
        <button type="button" className="search-clear" onClick={() => onChange('')} aria-label="Limpiar búsqueda">
          <X size={12} strokeWidth={1.75} />
        </button>
      )}
    </label>
  )
}
