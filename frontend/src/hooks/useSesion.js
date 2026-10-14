import { useContext } from 'react'
import { SesionContext } from '../components/sesion/sesion-context.js'

/** Sesión del usuario: { usuario, motivoCierre, entrar, salir, refrescarPerfil }. */
export default function useSesion() {
  const ctx = useContext(SesionContext)
  if (!ctx) throw new Error('useSesion debe usarse dentro de <SesionProvider>')
  return ctx
}
