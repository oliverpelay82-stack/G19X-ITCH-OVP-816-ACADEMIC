/**
 * Carga en lote (RF-02): revisión previa del lote en el navegador, sin React.
 *
 * Cada archivo se envía después, uno a la vez, a POST /documentos/upload, así
 * que el core aplica a cada uno su Nivel 1, la unicidad de la huella
 * (PLUS-01) y su evento de bitácora. Esta revisión solo evita envíos que el
 * core rechazaría o que el analista no quiso:
 *  - una huella repetida dentro del lote (el core respondería 409);
 *  - dos archivos con el mismo tipo: el último sustituye al primero como
 *    versión vigente (RF-04), así que se avisa, pero se admite.
 *
 * Un elemento del lote es { id, archivo, analisis, tipo }, donde `analisis`
 * es el veredicto de analizarNivel1 (null mientras se calcula) y `tipo` es
 * '' hasta que el analista lo elige: el lote no tiene tipo por omisión.
 */
import { plural } from './format.js'

/**
 * Observaciones de cada elemento, por id: `duplicadoDe` (nombre del primer
 * archivo con la misma huella) y `sustituyeA` (nombre del archivo anterior
 * con el mismo tipo). `custodiadas` (huella → nombre) son las que este lote
 * ya custodió: salieron de la lista, pero una copia suya seguiría siendo un 409.
 */
export function revisarLote(elementos, custodiadas = new Map()) {
  const porHuella = new Map(custodiadas)
  const porTipo = new Map()
  const revision = new Map()
  for (const e of elementos) {
    const hash = e.analisis?.hash
    const duplicadoDe = hash && porHuella.has(hash) ? porHuella.get(hash) : null
    if (hash && !duplicadoDe) porHuella.set(hash, e.archivo.name)
    const sustituyeA = !duplicadoDe && e.tipo && porTipo.has(e.tipo) ? porTipo.get(e.tipo) : null
    if (e.tipo && !duplicadoDe) porTipo.set(e.tipo, e.archivo.name)
    revision.set(e.id, { duplicadoDe, sustituyeA })
  }
  return revision
}

/** El archivo pasó el Nivel 1 del navegador y no repite una huella del lote. */
function admisible(elemento, revision) {
  return Boolean(elemento.analisis?.conforme) && !revision.get(elemento.id)?.duplicadoDe
}

/**
 * Estado del lote para el botón de envío: cuántos son admisibles, los
 * elementos que se enviarán, los admisibles que aún no tienen tipo y los que no se enviarán (formato o
 * tamaño no admitido, o huella repetida). Se puede enviar cuando todos los
 * análisis terminaron, hay al menos uno por enviar y ningún admisible quedó
 * sin tipo (enviar parte del lote en silencio confundiría al analista).
 */
export function estadoLote(elementos, revision) {
  const analizando = elementos.some((e) => !e.analisis)
  const admisibles = elementos.filter((e) => admisible(e, revision))
  const sinTipo = admisibles.filter((e) => !e.tipo).length
  return {
    admisibles: admisibles.length,
    porEnviar: admisibles.filter((e) => e.tipo),
    sinTipo,
    omitidos: elementos.length - admisibles.length,
    listo: !analizando && admisibles.length > 0 && sinTipo === 0,
  }
}

/** Texto del aviso final del lote: cuántos se custodiaron y cuántos se rechazaron. */
export function resumenLote(custodiados, rechazados) {
  const partes = [plural(custodiados, 'documento custodiado', 'documentos custodiados')]
  if (rechazados) partes.push(plural(rechazados, 'rechazado, sigue en la lista con su motivo', 'rechazados, siguen en la lista con su motivo'))
  return partes.join(' · ')
}
