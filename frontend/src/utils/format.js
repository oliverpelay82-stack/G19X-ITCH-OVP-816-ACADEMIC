/**
 * Utilidades de presentación compartidas por el panel.
 * Ninguna toca la red: solo dan formato a lo que ya devolvieron las APIs.
 */

/** Tamaño de archivo legible a partir de bytes. */
export function formatBytes(bytes) {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  const unidades = ['B', 'KB', 'MB', 'GB']
  let i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), unidades.length - 1)
  // «1006.9 KB» se lee peor que «1.0 MB»: desde 1000 se usa la unidad siguiente.
  if (n / 1024 ** i >= 1000 && i < unidades.length - 1) i += 1
  const valor = n / 1024 ** i
  return `${valor.toFixed(i === 0 ? 0 : 1)} ${unidades[i]}`
}

/** Fecha corta local, tolerante a valores ausentes o inválidos. */
export function formatFecha(valor, opciones) {
  if (!valor) return '—'
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return '—'
  return d.toLocaleString('es-MX', opciones || { dateStyle: 'medium', timeStyle: 'short' })
}

/** Solo el día, sin la hora. */
/**
 * Día y mes («27 sep»), con el año solo si no es el actual («14 may 2002»).
 * Se arma por partes: con día y mes solos, es-MX escribiría «27-sep».
 */
function diaMes(fecha) {
  const conAnio = fecha.getFullYear() !== new Date().getFullYear()
  return new Intl.DateTimeFormat('es-MX', { day: '2-digit', month: 'short', ...(conAnio && { year: 'numeric' }) })
    .formatToParts(fecha)
    .filter((p) => p.type !== 'literal')
    .map((p) => p.value.replace(/\.$/, ''))
    .join(' ')
}

export function formatFechaCorta(valor) {
  if (!valor) return '—'
  const d = new Date(valor)
  return Number.isNaN(d.getTime()) ? '—' : diaMes(d)
}

/**
 * Fecha de calendario sin hora (AAAA-MM-DD, p. ej. una fecha de vencimiento).
 * `new Date('2026-10-01')` la interpretaría como medianoche UTC y en México se
 * mostraría el día anterior; aquí se construye en hora local.
 */
export function formatDia(valor) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor || '')
  if (!m) return formatFechaCorta(valor)
  return diaMes(new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])))
}

/** "hace 4 min", "hace 2 h"… para marcas de tiempo recientes. */
export function formatRelativo(valor) {
  if (!valor) return '—'
  const d = new Date(valor)
  if (Number.isNaN(d.getTime())) return '—'
  const segundos = Math.round((Date.now() - d.getTime()) / 1000)
  if (segundos < 60) return 'hace instantes'
  const minutos = Math.round(segundos / 60)
  if (minutos < 60) return `hace ${minutos} min`
  const horas = Math.round(minutos / 60)
  if (horas < 24) return `hace ${horas} h`
  const dias = Math.round(horas / 24)
  if (dias < 30) return `hace ${dias} d`
  return formatFechaCorta(valor)
}

/** «1 expediente», «3 expedientes»: la cifra con la palabra en singular o plural. */
export const plural = (n, uno, varios) => `${n} ${n === 1 ? uno : varios}`

/** Iniciales para el avatar de un titular (máximo dos letras). */
export function iniciales(nombre) {
  if (!nombre) return '??'
  // Se descartan las formas societarias y los conectores, y después
  // cualquier resto sin letras (los puntos sueltos de "S.A. de C.V.").
  const palabras = nombre
    .replace(/\b(S\.?A\.?|C\.?V\.?|R\.?L\.?|S\.?C\.?|de|del|la|el|y)\b/gi, ' ')
    .split(/\s+/)
    .map((p) => p.replace(/[^\p{L}\p{N}]/gu, ''))
    .filter(Boolean)
  if (palabras.length === 0) return nombre.replace(/[^\p{L}\p{N}]/gu, '').slice(0, 2).toUpperCase()
  if (palabras.length === 1) return palabras[0].slice(0, 2).toUpperCase()
  return (palabras[0][0] + palabras[1][0]).toUpperCase()
}

/* ── RFC (SAT) ─────────────────────────────────────────────────────
   Persona moral: 3 letras + 6 dígitos de fecha + 3 de homoclave = 12.
   Persona física: 4 letras + 6 dígitos de fecha + 3 de homoclave = 13. */
const RFC_MORAL = /^[A-ZÑ&]{3}\d{6}[A-Z\d]{3}$/
const RFC_FISICA = /^[A-ZÑ&]{4}\d{6}[A-Z\d]{3}$/

/** Valida el RFC y explica por qué falla, para el aviso en vivo del formulario. */
export function validarRfc(rfc, tipoPersona) {
  const valor = (rfc || '').trim().toUpperCase()
  if (!valor) return { estado: 'vacio', mensaje: '' }
  if (RFC_GENERICOS.has(valor)) return { estado: 'valido', mensaje: 'RFC genérico del SAT.' }

  const esperado = tipoPersona === 'FISICA' ? 13 : 12
  if (valor.length < esperado) {
    return {
      estado: 'incompleto',
      mensaje: `Faltan ${esperado - valor.length} caracteres (${tipoPersona === 'FISICA' ? 'persona física' : 'persona moral'}: ${esperado}).`,
    }
  }
  if (valor.length > esperado) {
    return { estado: 'invalido', mensaje: `Un RFC de ${tipoPersona === 'FISICA' ? 'persona física' : 'persona moral'} tiene ${esperado} caracteres.` }
  }

  const patron = tipoPersona === 'FISICA' ? RFC_FISICA : RFC_MORAL
  if (!patron.test(valor)) {
    return { estado: 'invalido', mensaje: 'Formato incorrecto: letras iniciales, fecha AAMMDD y homoclave.' }
  }

  const fecha = valor.slice(tipoPersona === 'FISICA' ? 4 : 3, tipoPersona === 'FISICA' ? 10 : 9)
  if (!fechaRfcPosible(fecha)) {
    return { estado: 'invalido', mensaje: 'La fecha embebida (AAMMDD) no existe.' }
  }

  // M1: el dígito verificador del SAT. Uno que no coincide se acepta con
  // advertencia (RFC de prueba), igual que en el servidor.
  if (digitoRfc(valor) !== valor.at(-1)) {
    return {
      estado: 'advertencia',
      mensaje: 'Formato válido, pero el dígito verificador no coincide: revisa que esté bien escrito.',
    }
  }
  return { estado: 'valido', mensaje: 'RFC válido: el dígito verificador coincide.' }
}

/** El RFC se puede registrar (válido, o con la advertencia del dígito verificador). */
export const rfcRegistrable = (check) => check.estado === 'valido' || check.estado === 'advertencia'

const RFC_GENERICOS = new Set(['XAXX010101000', 'XEXX010101000'])
const DICCIONARIO_RFC = '0123456789ABCDEFGHIJKLMN&OPQRSTUVWXYZ Ñ'

/** Dígito verificador del SAT (módulo 11); la persona moral se completa con un espacio inicial. */
function digitoRfc(rfc) {
  const base = rfc.slice(0, -1).padStart(12, ' ')
  const suma = [...base].reduce((total, c, i) => total + DICCIONARIO_RFC.indexOf(c) * (13 - i), 0)
  const resto = suma % 11
  if (resto === 0) return '0'
  return 11 - resto === 10 ? 'A' : String(11 - resto)
}

/** La fecha AAMMDD existe en 1900 o en 2000 (así el 29/02/00 es válido). */
function fechaRfcPosible(aammdd) {
  const [aa, mm, dd] = [aammdd.slice(0, 2), aammdd.slice(2, 4), aammdd.slice(4, 6)].map(Number)
  return [1900, 2000].some((siglo) => {
    const f = new Date(Date.UTC(siglo + aa, mm - 1, dd))
    return f.getUTCMonth() === mm - 1 && f.getUTCDate() === dd
  })
}

/** Copia al portapapeles con respaldo para navegadores sin permiso. */
export async function copiarAlPortapapeles(texto) {
  try {
    await navigator.clipboard.writeText(texto)
    return true
  } catch {
    try {
      const area = document.createElement('textarea')
      area.value = texto
      area.setAttribute('readonly', '')
      area.style.position = 'fixed'
      area.style.opacity = '0'
      document.body.appendChild(area)
      area.select()
      const ok = document.execCommand('copy')
      document.body.removeChild(area)
      return ok
    } catch {
      return false
    }
  }
}

/** Recorta un hash largo dejando visibles el principio y el final. */
export function hashCorto(hash, inicio = 10, fin = 8) {
  if (!hash) return '—'
  if (hash.length <= inicio + fin + 1) return hash
  return `${hash.slice(0, inicio)}…${hash.slice(-fin)}`
}
