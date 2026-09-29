/**
 * Utilidades de presentación compartidas por el panel.
 * Ninguna toca la red: solo dan formato a lo que ya devolvieron las APIs.
 */

/** Tamaño de archivo legible a partir de bytes. */
export function formatBytes(bytes) {
  const n = Number(bytes)
  if (!Number.isFinite(n) || n <= 0) return '0 B'
  const unidades = ['B', 'KB', 'MB', 'GB']
  const i = Math.min(Math.floor(Math.log(n) / Math.log(1024)), unidades.length - 1)
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
export function formatFechaCorta(valor) {
  return formatFecha(valor, { day: '2-digit', month: 'short', year: 'numeric' })
}

/**
 * Fecha de calendario sin hora (AAAA-MM-DD, p. ej. una fecha de vencimiento).
 * `new Date('2026-10-01')` la interpretaría como medianoche UTC y en México se
 * mostraría el día anterior; aquí se construye en hora local.
 */
export function formatDia(valor) {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(valor || '')
  if (!m) return formatFechaCorta(valor)
  return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3])).toLocaleDateString('es-MX', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  })
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
  const mes = Number(fecha.slice(2, 4))
  const dia = Number(fecha.slice(4, 6))
  if (mes < 1 || mes > 12 || dia < 1 || dia > 31) {
    return { estado: 'invalido', mensaje: 'La fecha embebida (AAMMDD) no es válida.' }
  }

  return { estado: 'valido', mensaje: 'Formato de RFC válido.' }
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
