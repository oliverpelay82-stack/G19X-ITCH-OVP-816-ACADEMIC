import { MagnifyingGlass, X } from '../iconos.js'

/**
 * Buscador con icono y botón para limpiar. Escape borra la búsqueda; la
 * tecla «/» (App.jsx) lleva el foco al buscador de la vista.
 */
export default function SearchBox({ value, onChange, placeholder, label, compacto = false }) {
  return (
    <label className={`search-box ${compacto ? 'search-box--sm' : ''}`}>
      <MagnifyingGlass size={14} aria-hidden="true" />
      <input
        type="search"
        placeholder={placeholder}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Escape' && value) {
            e.stopPropagation()
            onChange('')
          }
        }}
        aria-label={label || placeholder}
        aria-keyshortcuts="/"
      />
      {value && (
        <button type="button" className="search-clear" onClick={() => onChange('')} aria-label="Limpiar búsqueda">
          <X size={12} aria-hidden="true" />
        </button>
      )}
    </label>
  )
}
