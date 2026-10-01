import { useMemo, useState } from 'react'

/** Orden de los estados de cumplimiento: lo más grave primero. */
export const RANGO_ESTADO = { NO_CONFORME: 0, FALTANTE: 0, EN_REVISION: 1, SIN_DICTAMEN: 2, CONFORME: 3 }

const comparar = (a, b) =>
  typeof a === 'number' && typeof b === 'number'
    ? a - b
    : String(a).localeCompare(String(b), 'es', { numeric: true, sensitivity: 'base' })

/**
 * Orden por columna de una tabla. `claves` (memorizado por el llamador) da,
 * por columna, el valor con el que se ordena cada fila. Sin orden elegido se
 * respeta el de la lista. Los valores vacíos van siempre al final.
 */
export default function useOrden(lista, claves) {
  const [orden, setOrden] = useState(null)
  const ordenada = useMemo(() => {
    if (!orden || !claves[orden.columna]) return lista
    const valor = claves[orden.columna]
    const factor = orden.sentido === 'asc' ? 1 : -1
    return [...lista].sort((x, y) => {
      const a = valor(x)
      const b = valor(y)
      if (a == null || b == null) return a == null ? (b == null ? 0 : 1) : -1
      return factor * comparar(a, b)
    })
  }, [lista, orden, claves])

  // Primer clic: el sentido inicial de la columna; segundo: el contrario; tercero: sin orden.
  const ordenar = (columna, inicial = 'asc') =>
    setOrden((previo) => {
      if (previo?.columna !== columna) return { columna, sentido: inicial }
      if (previo.sentido === inicial) return { columna, sentido: inicial === 'asc' ? 'desc' : 'asc' }
      return null
    })

  return { ordenada, orden, ordenar }
}
