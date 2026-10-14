/**
 * Identificador aleatorio de 16 caracteres hexadecimales: el folio de
 * seguimiento de cada llamada (PLUS-21) y las claves de los mensajes del chat
 * y de las búsquedas de citas. getRandomValues existe también fuera de un
 * contexto seguro (la intranet por IP, sin HTTPS), donde crypto.randomUUID no
 * existe y lanzaría un TypeError.
 */
export function idAleatorio() {
  return Array.from(crypto.getRandomValues(new Uint8Array(8)), (b) => b.toString(16).padStart(2, '0')).join('')
}
