// Constantes y funciones puras del panel de inteligencia documental (sin JSX).
import { formatFechaCorta } from '../../utils/format.js'

const MODELO_POR_DEFECTO = 'Modelo de lenguaje'

/** Catálogo del Nivel 4 (espejo de TIPOS_DOCUMENTALES en analisis_semantico.py). */
export const TIPO_IA_LABEL = {
  CONSTANCIA_SITUACION_FISCAL: 'Constancia de Situación Fiscal',
  OPINION_CUMPLIMIENTO: 'Opinión de Cumplimiento (32-D)',
  COMPROBANTE_DOMICILIO: 'Comprobante de Domicilio',
  ACTA_CONSTITUTIVA: 'Acta Constitutiva',
  PODER_NOTARIAL: 'Poder Notarial',
  ESTADO_CUENTA: 'Estado de Cuenta Bancario',
  CONTRATO: 'Contrato',
  POLIZA: 'Póliza de Seguro',
  LICENCIA: 'Licencia',
  CERTIFICACION: 'Certificación',
  IDENTIFICACION_OFICIAL: 'Identificación Oficial',
  OTRO: 'No clasificado',
}

/** Equivalencia entre el catálogo del Nivel 4 y el del core-service (espejo de TIPO_A_CATALOGO_CORE). */
const TIPO_IA_A_CORE = {
  CONSTANCIA_SITUACION_FISCAL: 'CSF_SAT',
  COMPROBANTE_DOMICILIO: 'COMP_DOMICILIO',
  ACTA_CONSTITUTIVA: 'ACTA_CONSTITUTIVA',
  PODER_NOTARIAL: 'PODER_NOTARIAL',
  OPINION_CUMPLIMIENTO: 'OPINION_CUMPLIMIENTO',
  ESTADO_CUENTA: 'ESTADO_CUENTA',
}

/** Resultado de cada elemento exigido por las reglas RSC/RDS (verificacion_contenido.py). */
export const RESULTADO_CONTENIDO = {
  CUMPLE: { tono: 'ok', label: 'Localizado' },
  NO_LOCALIZADO: { tono: 'bad', label: 'No localizado' },
  NO_VERIFICABLE: { tono: 'warn', label: 'No verificado' },
  // Regla determinista (RSC-OPIN-SENT): el documento contradice el requisito, con su cita.
  NO_CUMPLE: { tono: 'bad', label: 'Incumple' },
}

export const ESTATUS_IA = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  EN_REVISION: { tono: 'warn', label: 'En revisión' },
  NO_CONFORME: { tono: 'bad', label: 'No conforme' },
}

export const FUENTE_TEXTO = { memoria: 'desde memoria', persistencia: 'desde disco', extraccion: 'extraído ahora' }

export const RESULTADO_VIGENCIA = {
  VIGENTE: { tono: 'ok', label: 'vigente' },
  PROXIMO_A_VENCER: { tono: 'warn', label: 'próximo a vencer' },
  VENCIDO: { tono: 'bad', label: 'vencido' },
  INDETERMINADO: { tono: 'warn', label: 'no verificable' },
}

/** Nombre legible del modelo: "qwen/qwen3.8-27b" → "Qwen 3.8 (27B)". */
export function nombreModelo(modelo) {
  if (!modelo) return MODELO_POR_DEFECTO
  // Groq antepone el proveedor del modelo ("qwen/"); para mostrarlo sobra.
  const id = modelo.split('/').pop()
  const partes = /^([a-z]+)-?([\d.]+)-(\d+b)$/i.exec(id)
  if (!partes) return id
  const [, familia, version, tamanio] = partes
  return `${familia.charAt(0).toUpperCase()}${familia.slice(1)} ${version} (${tamanio.toUpperCase()})`
}

/** Traduce los fallos del ai-service a un toast accionable para el operador. */
export function avisarFallo(toast, err, contexto) {
  if (err?.status === 0) {
    toast.error('El análisis con IA no responde', 'El servicio de análisis no está disponible. Verifica que esté en marcha.')
  } else if (err?.status === 503) {
    toast.alerta('El proveedor de IA no está disponible', err.message)
  } else if (err?.status === 502) {
    toast.alerta('Respuesta inválida del modelo', `${err.message} Intenta de nuevo en unos segundos.`)
  } else {
    toast.error(contexto, err?.message || 'Error inesperado del ai-service.')
  }
}

/** Días restantes: se prefiere el cálculo del backend y se recalcula solo si falta. */
export function diasRestantes(dictamen) {
  if (Number.isInteger(dictamen.dias_para_vencimiento)) return dictamen.dias_para_vencimiento
  if (!dictamen.fecha_vencimiento) return null
  const vence = new Date(`${dictamen.fecha_vencimiento}T00:00:00`)
  if (Number.isNaN(vence.getTime())) return null
  const hoy = new Date()
  hoy.setHours(0, 0, 0, 0)
  return Math.round((vence - hoy) / 86_400_000)
}

/** Ejecuta la petición y devuelve su resultado junto con el tiempo de respuesta. */
export async function cronometrar(peticion) {
  const inicio = performance.now()
  const resultado = await peticion()
  return { resultado, duracion: performance.now() - inicio }
}

export function formatDuracion(ms) {
  if (ms === null || ms === undefined) return '—'
  return ms < 1000 ? `${Math.round(ms)} ms` : `${(ms / 1000).toFixed(1)} s`
}

export const numero = (n) => Number(n).toLocaleString('es-MX')

export const fechaIso = (iso) => formatFechaCorta(iso && `${iso}T00:00:00`)

/** La regla RCV que decidió el resultado de vigencia (la de antigüedad, si aplicó). */
function reglaDecisiva(vigencia) {
  const evaluaciones = vigencia?.evaluaciones || []
  return (
    evaluaciones.find((e) => e.resultado === vigencia.resultado && e.criterio === 'ANTIGUEDAD_DESDE_EMISION') ||
    evaluaciones.find((e) => e.resultado === vigencia.resultado) ||
    null
  )
}

/**
 * Vigencia según las reglas RCV del rules-service (Nivel 2), con la regla que
 * decidió el resultado. Devuelve null si ninguna regla de vigencia aplicó, para
 * mostrar entonces solo los días hasta el vencimiento.
 */
export function vigenciaSegunReglas(vigencia, textoVencimiento) {
  if (vigencia?.disponible === false) return { tono: 'warn', texto: 'Reglas de vigencia no disponibles' }
  const meta = RESULTADO_VIGENCIA[vigencia?.resultado]
  const decisiva = meta && reglaDecisiva(vigencia)
  if (!decisiva) return null
  let texto = textoVencimiento
  if (vigencia.resultado === 'INDETERMINADO') texto = 'No verificable'
  else if (decisiva.criterio === 'ANTIGUEDAD_DESDE_EMISION') {
    texto = `${numero(decisiva.dias_calculados)} días desde emisión (máx. ${decisiva.limite_dias})`
  }
  return { tono: meta.tono, texto: `${texto} · ${decisiva.codigo_regla}` }
}

/** Traza compacta de la etapa 3 a partir de la respuesta del análisis. */
export function detalleReglas(vigencia) {
  if (vigencia?.disponible === false) return { estado: 'error', detalle: 'rules-service sin respuesta' }
  const decisiva = vigencia?.resultado && reglaDecisiva(vigencia)
  if (!decisiva) return { estado: 'hecho', detalle: 'Sin reglas aplicables al tipo' }
  const meta = RESULTADO_VIGENCIA[vigencia.resultado]
  const dias =
    Number.isInteger(decisiva.dias_calculados) && decisiva.criterio === 'ANTIGUEDAD_DESDE_EMISION'
      ? ` · ${numero(decisiva.dias_calculados)} días (máx. ${decisiva.limite_dias})`
      : ''
  return { estado: 'hecho', detalle: `${decisiva.codigo_regla} · ${meta?.label || vigencia.resultado.toLowerCase()}${dias}` }
}

/**
 * Separa la observación que motiva el dictamen ("Dictamen X: motivo.") del
 * resto, para mostrarla junto al veredicto.
 */
export function separarMotivo(observaciones = []) {
  const i = observaciones.findIndex((o) => /^Dictamen [A-Z_]+:/.test(o))
  if (i === -1) return { motivo: null, resto: observaciones }
  const texto = observaciones[i].replace(/^Dictamen [A-Z_]+:\s*/, '')
  return {
    motivo: texto.charAt(0).toUpperCase() + texto.slice(1),
    resto: observaciones.filter((_, j) => j !== i),
  }
}

/* ── Piezas visuales ────────────────────────────────────────────── */

/** Resultado de una fila del cotejo: coincide, discrepa o no se puede comparar. */
export const RESULTADO_COTEJO = {
  ok: { tono: 'ok', label: 'Coincide' },
  bad: { tono: 'bad', label: 'Discrepa' },
  na: { tono: 'neutral', label: 'Sin referencia' },
  ausente: { tono: 'warn', label: 'No localizado' },
  info: { tono: 'neutral', label: 'Informativo' },
}

/** Resultado del tipo documental: el contraste lo decide el servicio (TIPOS_COMPATIBLES). */
export function resultadoTipo(dictamen, tipoRegistrado) {
  if (!tipoRegistrado) return 'na'
  if (dictamen.tipo_coincide === true) return 'ok'
  if (dictamen.tipo_coincide === false) return 'bad'
  // Tipo sin equivalente en el catálogo del Nivel 4 (o dictamen previo): se compara solo si hay espejo.
  const detectadoCore = TIPO_IA_A_CORE[dictamen.tipo_documento_detectado]
  if (dictamen.tipo_coincide === null && !detectadoCore) return 'na'
  return detectadoCore === tipoRegistrado ? 'ok' : 'bad'
}

/** Titularidad según el dictamen: cómo se acreditó o por qué falta. */
export const TITULARIDAD = {
  RFC: { tono: 'ok', texto: 'RFC coincide' },
  RAZON_SOCIAL: { tono: 'ok', texto: 'Por razón social' },
  AJENA: { tono: 'bad', texto: 'RFC ajeno' },
  NO_LOCALIZADA: { tono: 'warn', texto: 'Por confirmar' },
  SIN_REFERENCIA: { tono: 'neutral', texto: 'Sin referencia' },
}
