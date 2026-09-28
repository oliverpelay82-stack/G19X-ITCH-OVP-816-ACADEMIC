/** Estado vacío con icono, título y una línea de ayuda. */
export function EmptyState({ icon: Icono, titulo, descripcion, children }) {
  return (
    <div className="empty-state">
      {Icono && (
        <span className="squircle squircle--lg empty-icon" aria-hidden="true">
          <Icono size={16} />
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
