/**
 * Valor de una lista tras un ciclo de carga del panel (App.jsx): lo recibido o,
 * si la petición falló, lo que ya había. Una caída no vacía la vista: el estado
 * del servicio lo comunica la salud (isOnline) y, sin datos, `sinRespuesta`.
 */
export const valorTrasCarga = (resultado, previo) =>
  resultado.status === 'fulfilled' ? resultado.value || [] : previo
