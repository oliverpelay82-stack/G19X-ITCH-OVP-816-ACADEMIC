import { createContext, useContext } from 'react'

/**
 * Conecta las citas del dictamen y del chat con el visor del documento. El
 * modal del documento provee `mostrar({ cita, tono })`, que ubica y resalta
 * una cita; `irAPagina(n)`, que abre el visor en la página de un fragmento
 * consultado, y `mostrarZonas(pagina, recuadros)`, que resalta zonas ya
 * ubicadas (los sellos que detectó el Nivel 3). Fuera del modal (sin visor)
 * el contexto es null y las citas se muestran como texto.
 */
export const EvidenciaContext = createContext(null)

export const useEvidencia = () => useContext(EvidenciaContext)
