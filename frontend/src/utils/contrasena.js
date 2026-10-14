/**
 * Contraseñas temporales del alta de cuentas (Módulo 7, HU-05), sin React.
 *
 * El core exige al menos 10 caracteres (config/seguridad.py). Para una contraseña
 * que el administrador entrega, la interfaz pide además una mayúscula y un número o
 * símbolo, y ofrece generar una que lo cumple. La persona la cambia en su primer
 * acceso.
 */
export const LONGITUD_MINIMA = 10

const MAYUSCULAS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'
const MINUSCULAS = 'abcdefghijkmnpqrstuvwxyz'
const NUMEROS = '23456789'
const SIMBOLOS = '-_.!@#$%*+='
// Sin caracteres que se confunden al dictarlos o copiarlos a mano: 0/O, 1/l/I.
const TODOS = MAYUSCULAS + MINUSCULAS + NUMEROS + SIMBOLOS

/** Requisitos de una contraseña temporal, en el orden en que se muestran. */
export function requisitosDe(texto = '') {
  return [
    { id: 'longitud', etiqueta: `${LONGITUD_MINIMA} caracteres o más`, cumple: texto.length >= LONGITUD_MINIMA },
    { id: 'mayuscula', etiqueta: 'Una mayúscula', cumple: /\p{Lu}/u.test(texto) },
    { id: 'numero', etiqueta: 'Un número o símbolo', cumple: /[\d\p{P}\p{S}]/u.test(texto) },
  ]
}

export const cumpleRequisitos = (texto) => requisitosDe(texto).every((r) => r.cumple)

/** Índice aleatorio uniforme en [0, n) con el generador criptográfico del navegador. */
function azar(n) {
  const limite = Math.floor(0x100000000 / n) * n
  const valor = new Uint32Array(1)
  do crypto.getRandomValues(valor)
  while (valor[0] >= limite)
  return valor[0] % n
}

const uno = (alfabeto) => alfabeto[azar(alfabeto.length)]

/** Contraseña aleatoria que cumple los requisitos: una de cada clase y el resto de todas, mezclada. */
export function contrasenaSegura(longitud = 14) {
  const caracteres = [uno(MAYUSCULAS), uno(MINUSCULAS), uno(NUMEROS), uno(SIMBOLOS)]
  while (caracteres.length < Math.max(longitud, LONGITUD_MINIMA)) caracteres.push(uno(TODOS))
  for (let i = caracteres.length - 1; i > 0; i -= 1) {
    const j = azar(i + 1)
    ;[caracteres[i], caracteres[j]] = [caracteres[j], caracteres[i]]
  }
  return caracteres.join('')
}
