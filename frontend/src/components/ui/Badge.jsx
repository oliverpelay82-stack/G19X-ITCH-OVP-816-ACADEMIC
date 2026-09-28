import { cx } from './clases.js'

/**
 * Píldora de estado (`.badge`). El `tono` sale de los mapas de constants.js
 * (ESTADO_BADGE, SEVERIDAD_META, VIGENCIA…): `ok` conforme, `warn` en
 * revisión, `bad` no conforme o vencido, `neutral`/`skip` informativo u
 * omitido. El color nunca va solo: el texto del estado siempre acompaña.
 * `punto` antepone el punto semafórico; `grande` es la variante del
 * semáforo del expediente.
 */
export function Badge({ tono = 'neutral', punto = false, grande = false, className, children, ...props }) {
  return (
    <span className={cx('badge', grande && 'badge--lg', `badge--${tono}`, className)} {...props}>
      {punto && <span className={`status-dot status-dot--${tono}`} aria-hidden="true" />}
      {children}
    </span>
  )
}

/**
 * Etiqueta neutra de categoría (`.tag`), sin significado de estado: tipo
 * documental o de expediente (`tipo`), categoría regulatoria, código de
 * regla. `mono` y `tabular` para folios, códigos y cifras.
 */
export function Tag({ tipo = false, mono = false, tabular = false, className, children, ...props }) {
  return (
    <span className={cx('tag', tipo && 'tag--type', mono && 'mono', tabular && 'tabular', className)} {...props}>
      {children}
    </span>
  )
}
