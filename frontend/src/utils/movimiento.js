/**
 * Preferencia del sistema «reducir movimiento». Las animaciones CSS ya la
 * respetan (index.css); las que se hacen desde JavaScript (conteo de cifras,
 * indicador deslizante, fundido del tema) la consultan aquí y no corren.
 */
export function reducirMovimiento() {
  return typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches === true
}
