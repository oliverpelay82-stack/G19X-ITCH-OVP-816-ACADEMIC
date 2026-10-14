import { useCallback, useEffect, useMemo, useState } from 'react'
import { getPerfil } from '../../services/api.js'
import { MOTIVO, actualizarPerfil, iniciarSesion, sesionActual, suscribir, terminarSesion } from '../../services/sesion.js'
import { SesionContext } from './sesion-context.js'

/**
 * Sesión del usuario para toda la interfaz (Módulo 7, PRD §5.2): quién está
 * dentro, con qué rol y por qué se cerró la última sesión (para decirlo en la
 * pantalla de acceso). La fuente de verdad es services/sesion.js; este
 * proveedor solo la refleja en React.
 *
 * Al cargar la página con una sesión guardada, pide el perfil al core: el rol o
 * el estado de la cuenta pudieron cambiar desde que se guardó, y un token que ya
 * no vale cierra la sesión ahí mismo.
 */
export function SesionProvider({ children }) {
  const [sesion, setSesion] = useState(sesionActual)
  const [motivoCierre, setMotivoCierre] = useState(null)

  useEffect(
    () =>
      suscribir((nueva, motivo) => {
        setSesion(nueva)
        if (motivo === MOTIVO.EXPIRADA || motivo === MOTIVO.CIERRE) setMotivoCierre(motivo)
        if (motivo === MOTIVO.INICIO) setMotivoCierre(null)
      }),
    []
  )

  useEffect(() => {
    if (!sesionActual()) return
    getPerfil().then(actualizarPerfil).catch(() => {}) // un 401 ya cerró la sesión en api.js
  }, [])

  const entrar = useCallback((respuesta) => iniciarSesion(respuesta), [])
  const salir = useCallback(() => terminarSesion(MOTIVO.CIERRE), [])
  const refrescarPerfil = useCallback((usuario) => actualizarPerfil(usuario), [])

  const valor = useMemo(
    () => ({ usuario: sesion?.usuario ?? null, motivoCierre, entrar, salir, refrescarPerfil }),
    [sesion, motivoCierre, entrar, salir, refrescarPerfil]
  )
  return <SesionContext.Provider value={valor}>{children}</SesionContext.Provider>
}
