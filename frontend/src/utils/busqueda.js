/**
 * Búsqueda tolerante de todo el sistema: la paleta de comandos (D1) y el
 * buscador de cada vista. Sin distinguir mayúsculas ni acentos, y cada palabra
 * buscada debe aparecer en el texto (en cualquier orden): «aceros norte»
 * encuentra «Aceros del Norte, S.A.» y «situacion» encuentra «Situación».
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

/** Como `coincide`, sobre varios campos de un registro (los vacíos se ignoran). */
export function coincideEn(campos, consulta) {
  return coincide(campos.filter(Boolean).join(' '), consulta)
}
