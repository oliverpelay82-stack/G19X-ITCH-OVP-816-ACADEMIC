/** Une las clases verdaderas en un solo `className` (descarta false, null, undefined y ''). */
export const cx = (...clases) => clases.filter(Boolean).join(' ')
