import { useState } from 'react'

/**
 * Envuelve un estado (semáforo, estado del documento) y lo resalta con un
 * destello de un segundo, en su `tono` (ok, warn, bad, neutral), cuando su
 * `valor` cambia mientras está a la vista, por ejemplo tras «Auditar
 * pendientes» o una ratificación. Al montarse no
 * destella: solo un cambio real lo hace. El destello es una capa que sube y
 * baja de opacidad (index.css, `destello`); con «reducir movimiento» no se ve.
 *
 * Fase B (D4): si el cambio es a un estado conforme (`tono` ok), además se
 * dibuja un check de un solo trazo junto al estado, que luego se desvanece.
 * Va en posición absoluta: no mueve nada a su alrededor. `ladoCheck` elige el
 * lado libre (en la lista de expedientes, la derecha la ocupa el índice).
 */
export default function Destello({ valor, tono = 'neutral', ladoCheck = 'derecha', children }) {
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
      {cambios > 0 && tono === 'ok' && (
        <svg className={`check-dibujado check-dibujado--${ladoCheck}`} viewBox="0 0 16 16" aria-hidden="true">
          <path d="M3.5 8.5l3 3 6-7" pathLength="1" />
        </svg>
      )}
    </span>
  )
}
