import { rangoSeveridad } from '../constants.js'

/**
 * Las alertas de varios expedientes en una sola lista, de la más grave a la
 * menos grave, cada una con el expediente al que pertenece: su folio, titular
 * y tipo para filtrar y mostrarla, y el expediente completo para la vista
 * previa del folio (D2). La usan la bandeja de Alertas y el detalle de la empresa.
 */
export function alertasDeExpedientes(expedientes) {
  return expedientes
    .flatMap((exp) =>
      (exp.evaluacion?.alertas || []).map((a) => ({
        ...a,
        expediente: {
          id: exp.id,
          codigo: exp.codigo_expediente,
          nombre: exp.nombre || exp.titular?.razon_social || '',
          razon_social: exp.titular?.razon_social || '',
          rfc: exp.titular?.rfc || '',
          tipo: exp.tipo_expediente,
          completo: exp,
        },
      }))
    )
    .sort((a, b) => rangoSeveridad(a.severidad) - rangoSeveridad(b.severidad))
}
