/**
 * Búsqueda tolerante para la paleta de comandos (D1): sin distinguir
 * mayúsculas ni acentos, y cada palabra buscada debe aparecer en el texto
 * (en cualquier orden). «aceros norte» encuentra «Aceros del Norte, S.A.».
 */
export function normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim()
}

/** `consulta` ya normalizada; vacía coincide con todo. */
export function coincide(texto, consulta) {
  if (!consulta) return true
  const donde = normalizar(texto)
  return consulta.split(/\s+/).every((palabra) => donde.includes(palabra))
}
