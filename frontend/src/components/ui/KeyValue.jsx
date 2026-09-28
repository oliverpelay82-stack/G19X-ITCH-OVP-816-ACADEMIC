/**
 * Metadatos como lista de definiciones: `KeyValueList` es el <dl> (su clase
 * de rejilla la da el contexto: `detail-grid`, `registro-grid`,
 * `profile-grid`, `inspect-grid`) y cada `KeyValue` un par <dt>/<dd>
 * agrupado en un <div>, que es lo que la rejilla distribuye.
 *
 * Para RFC y hashes, el valor puede ser un CopyChip.
 */
export function KeyValueList({ className, children, ...props }) {
  return (
    <dl className={className} {...props}>
      {children}
    </dl>
  )
}

/** `valorClassName` (mono, tabular) y `valorTitulo` (valor completo de un hash abreviado) van al <dd>. */
export function KeyValue({ etiqueta, className, valorClassName, valorTitulo, children }) {
  return (
    <div className={className || undefined}>
      <dt>{etiqueta}</dt>
      <dd className={valorClassName} title={valorTitulo}>
        {children}
      </dd>
    </div>
  )
}
