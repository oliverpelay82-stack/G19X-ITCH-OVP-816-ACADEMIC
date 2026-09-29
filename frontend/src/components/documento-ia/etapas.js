// Etapas de la auditoría (lectura, análisis y reglas de vigencia) y su cancelación en cascada.


/**
 * Etapas de la auditoría en el orden real del pipeline: la lectura es una
 * petición propia (preparar) y el análisis semántico y las reglas de vigencia
 * viajan en la misma petición, porque las reglas necesitan las fechas que
 * extrae el modelo.
 */
export const ETAPAS = [
  { id: 'lectura', label: 'Lectura', nivel: 'Texto del archivo' },
  { id: 'analisis', label: 'Análisis semántico', nivel: 'Con IA' },
  { id: 'reglas', label: 'Reglas de vigencia', nivel: 'Sin IA' },
]

export const ETAPAS_INICIALES = Object.fromEntries(ETAPAS.map((e) => [e.id, { estado: 'pendiente', detalle: '' }]))

/**
 * Cancelación en cascada: si una etapa falla, las posteriores no pueden
 * ejecutarse (el Nivel 4 necesita el texto del Nivel 3, y las reglas RCV las
 * fechas que extrae el Nivel 4). Pasan a "omitido" en lugar de quedar en cola.
 */
export function fallarEnCascada(idEtapa, detalle) {
  const i = ETAPAS.findIndex((e) => e.id === idEtapa)
  const cambios = { [idEtapa]: { estado: 'error', detalle } }
  for (const posterior of ETAPAS.slice(i + 1)) {
    cambios[posterior.id] = {
      estado: 'omitido',
      detalle: `Cancelado: falló ${ETAPAS[i].label.toLowerCase()}`,
    }
  }
  return cambios
}
