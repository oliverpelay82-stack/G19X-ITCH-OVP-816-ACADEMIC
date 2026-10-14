/**
 * Sesión del usuario (Módulo 7, PRD §5.2), sin React.
 *
 * Guarda el token Bearer y el perfil en sessionStorage: sobrevive a una recarga y
 * se pierde al cerrar la pestaña. El cliente HTTP (api.js) lee el token de aquí y
 * avisa cuando el servidor lo rechaza; SesionProvider escucha los cambios y
 * vuelve a pintar la interfaz.
 *
 * El almacenamiento puede no estar disponible (navegación privada estricta): la
 * sesión sigue en memoria mientras dure la página.
 */
const CLAVE = 'plurione.sesion'

/** Motivos de un cambio de sesión que la interfaz explica al usuario. */
export const MOTIVO = Object.freeze({ INICIO: 'inicio', CIERRE: 'cierre', EXPIRADA: 'expirada', PERFIL: 'perfil' })

function leer() {
  try {
    const guardada = JSON.parse(window.sessionStorage.getItem(CLAVE) || 'null')
    return guardada?.token && guardada.expira > Date.now() ? guardada : null
  } catch {
    return null
  }
}

function escribir(valor) {
  try {
    if (valor) window.sessionStorage.setItem(CLAVE, JSON.stringify(valor))
    else window.sessionStorage.removeItem(CLAVE)
  } catch {
    // Sin almacenamiento: la sesión vive solo en memoria.
  }
}

let actual = typeof window === 'undefined' ? null : leer()
const oyentes = new Set()

function avisar(motivo) {
  for (const oyente of oyentes) oyente(actual, motivo)
}

/** { token, usuario, expira } vigente, o null. */
export function sesionActual() {
  if (actual && actual.expira <= Date.now()) {
    actual = null
    escribir(null)
  }
  return actual
}

export function tokenActual() {
  return sesionActual()?.token ?? null
}

/** Guarda la respuesta de POST /auth/login con token. */
export function iniciarSesion({ access_token: token, expira_en: segundos, usuario }) {
  actual = { token, usuario, expira: Date.now() + segundos * 1000 }
  escribir(actual)
  avisar(MOTIVO.INICIO)
}

/** El perfil cambió (GET /auth/me, contraseña cambiada, MFA): mismo token, datos nuevos. */
export function actualizarPerfil(usuario) {
  if (!actual) return
  actual = { ...actual, usuario }
  escribir(actual)
  avisar(MOTIVO.PERFIL)
}

/** Cierra la sesión: `EXPIRADA` cuando el servidor rechazó el token, `CIERRE` cuando el usuario sale. */
export function terminarSesion(motivo = MOTIVO.CIERRE) {
  if (!actual) return
  actual = null
  escribir(null)
  avisar(motivo)
}

/** Escucha los cambios de sesión; devuelve la función para dejar de escuchar. */
export function suscribir(oyente) {
  oyentes.add(oyente)
  return () => oyentes.delete(oyente)
}
