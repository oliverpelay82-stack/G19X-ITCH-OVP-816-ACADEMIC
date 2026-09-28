import { Children, cloneElement, isValidElement, useId } from 'react'
import { cx } from './clases.js'

/**
 * Campo de formulario con etiqueta estática (`.field`), ayuda y validación.
 *
 * Por defecto es un <label> que envuelve al control, así la etiqueta queda
 * asociada sin ids. Con `as="div"` sirve para grupos que no son etiquetables
 * (radios con role="radiogroup"). La `ayuda` y la `retro` de validación
 * ({ estado: 'valido' | 'invalido' | 'incompleto' | 'neutro', mensaje }) se
 * enlazan al control con aria-describedby para que el lector de pantalla
 * las anuncie.
 */
export function Field({ etiqueta, ayuda, retro, as: Elemento = 'label', className, children }) {
  const id = useId()
  const idAyuda = ayuda ? `${id}-ayuda` : null
  const idRetro = retro?.mensaje ? `${id}-retro` : null
  const describe = [idAyuda, idRetro].filter(Boolean).join(' ') || undefined

  const hijos =
    describe && Children.count(children) === 1 && isValidElement(children)
      ? cloneElement(children, { 'aria-describedby': cx(children.props['aria-describedby'], describe) })
      : children

  return (
    <Elemento className={cx('field', className)}>
      <span className="field-label">{etiqueta}</span>
      {hijos}
      {ayuda && (
        <span id={idAyuda} className="field-hint">
          {ayuda}
        </span>
      )}
      {retro?.mensaje && (
        <span id={idRetro} className={`field-feedback field-feedback--${retro.estado}`}>
          {retro.mensaje}
        </span>
      )}
    </Elemento>
  )
}

/**
 * Campo de texto. Hereda altura (--control-md), borde y anillo de foco de la
 * regla global de App.css; `estado` añade el borde de validación y marca
 * aria-invalid cuando es inválido.
 */
export function Input({ estado, className, ...props }) {
  return (
    <input
      className={cx(estado && `input--${estado}`, className) || undefined}
      aria-invalid={estado === 'invalido' || undefined}
      {...props}
    />
  )
}

/**
 * Lista desplegable. Dentro de un Field no lleva `etiqueta`. Con `etiqueta`
 * es un filtro de barra de herramientas (`.select-inline`): la etiqueta queda
 * solo para lectores de pantalla, porque la primera opción ya dice qué filtra
 * («Todo tipo de expediente»); `claseContenedor` añade una clase de
 * maquetación a ese contenedor (p. ej. `report-select`).
 */
export function Select({ etiqueta, className, claseContenedor, children, ...props }) {
  const select = (
    <select className={className} {...props}>
      {children}
    </select>
  )
  if (!etiqueta) return select
  return (
    <label className={cx('select-inline', claseContenedor)}>
      <span className="sr-only">{etiqueta}</span>
      {select}
    </label>
  )
}
