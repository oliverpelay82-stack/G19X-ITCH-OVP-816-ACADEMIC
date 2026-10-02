import usePresencia from '../../hooks/usePresencia.js'

/**
 * Detalle desplegable del expediente: entra con altura animada y, al
 * plegarse, sigue montado lo que dura la salida (`is-plegando`, vistas.css)
 * para cerrarse con el mismo movimiento con que se abrió. Mientras se pliega
 * queda inerte: no recibe foco ni clics.
 */
export default function Desplegable({ abierto, children }) {
  const { montado, saliendo } = usePresencia(abierto)
  if (!montado) return null
  return (
    <div className={`exp-desplegable${saliendo ? ' is-plegando' : ''}`} inert={saliendo || undefined}>
      {children}
    </div>
  )
}
