/**
 * Espejo en el navegador del Nivel 1 del pipeline (DOC-05): firma binaria,
 * límite de tamaño y huella SHA-256. Sirve para dar retroalimentación
 * inmediata antes de enviar el archivo; la validación que manda sigue siendo
 * la del core-service (:8001).
 */
import { MAGIC_BYTES, MAX_FILE_SIZE_BYTES } from '../constants.js'

function bytesAHex(buffer) {
  return Array.from(new Uint8Array(buffer))
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('')
}

/** Huella SHA-256 del archivo completo (NOM-151-SCFI-2016). */
export async function calcularSha256(file) {
  const buffer = await file.arrayBuffer()
  const digest = await crypto.subtle.digest('SHA-256', buffer)
  return bytesAHex(digest)
}

/** Lee la cabecera y la coteja contra el catálogo de firmas admitidas. */
export async function detectarMagicBytes(file) {
  const cabecera = new Uint8Array(await file.slice(0, 8).arrayBuffer())
  return MAGIC_BYTES.find((firma) => firma.signature.every((byte, i) => cabecera[i] === byte)) || null
}

/** Analiza un archivo y devuelve el veredicto de Nivel 1. */
export async function analizarNivel1(file) {
  const [hash, magic] = await Promise.all([calcularSha256(file), detectarMagicBytes(file)])
  const tamanioOk = file.size > 0 && file.size <= MAX_FILE_SIZE_BYTES
  return {
    hash,
    magic,
    tamanioOk,
    conforme: Boolean(magic) && tamanioOk,
  }
}
