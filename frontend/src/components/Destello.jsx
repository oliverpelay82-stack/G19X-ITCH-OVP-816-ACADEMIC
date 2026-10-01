import { useState } from 'react'

/**
 * Envuelve un estado (semáforo, estado del documento) y lo resalta con un
 * destello de un segundo, en su `tono` (ok, warn, bad, neutral), cuando su
 * `valor` cambia mientras está a la vista, por ejemplo tras «Auditar
 * pendientes» o una ratificación. Al montarse no
 * destella: solo un cambio real lo hace. El destello es una capa que sube y
 * baja de opacidad (index.css, `destello`); con «reducir movimiento» no se ve.
 */
export default function Destello({ valor, tono = 'neutral', children }) {
  const [previo, setPrevio] = useState(valor)
  const [cambios, setCambios] = useState(0)
  // Ajuste de estado durante el render: el cambio se detecta sin un efecto.
  if (valor !== previo) {
    setPrevio(valor)
    setCambios((n) => n + 1)
  }
  // La clave nueva vuelve a montar la envoltura, y con ella la animación.
  return (
    <span key={cambios} className={`destello destello--${tono}${cambios ? ' is-activo' : ''}`}>
      {children}
    </span>
  )
}
