/**
 * Índice de cumplimiento del DOC-05 (C6, PRD §10.5): lo calcula el core-service
 * en cada evaluación (evaluacion.indice_cumplimiento); aquí solo se lee y se
 * presenta. Sin reglas aplicables, el porcentaje es nulo y se muestra «—».
 */
export const indiceDe = (expediente) => expediente?.evaluacion?.indice_cumplimiento ?? null

export const formatIndice = (porcentaje) => (porcentaje == null ? '—' : `${Math.round(porcentaje)}%`)

/** Promedio de los índices de los expedientes: cada expediente pesa igual (decisión 5 de C6). */
export function promedioIndice(expedientes) {
  const valores = expedientes.map((e) => indiceDe(e)?.porcentaje).filter((p) => p != null)
  return valores.length ? valores.reduce((a, b) => a + b, 0) / valores.length : null
}
