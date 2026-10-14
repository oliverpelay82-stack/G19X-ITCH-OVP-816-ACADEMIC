/**
 * Permisos de la interfaz por rol (Módulo 7, matriz del PRD §5.1).
 *
 * La interfaz solo oculta lo que el rol no puede hacer; quien aplica la regla es
 * cada servicio (un intento igual recibiría 403). Por eso estos nombres siguen la
 * matriz del PRD y no las pantallas.
 */
export const ROL = Object.freeze({ ADMIN: 'ADMIN', VALIDADOR: 'VALIDADOR', AUDITOR: 'AUDITOR', CONSULTA: 'CONSULTA' })

/** Nombre del rol para mostrar (DOC-04, Tabla 1). */
export const NOMBRE_ROL = {
  ADMIN: 'Administrador',
  VALIDADOR: 'Responsable de cumplimiento',
  AUDITOR: 'Auditor',
  CONSULTA: 'Consulta',
}

const { ADMIN, VALIDADOR, AUDITOR, CONSULTA } = ROL

export const PERMISOS = Object.freeze({
  // Empresas, expedientes, carga, corrección de datos, auditoría, chat y ratificación.
  operar: [ADMIN, VALIDADOR],
  // Alta de un tipo de documento nuevo con su criterio para la IA (RDS-01).
  tipoDocumentoNuevo: [ADMIN, VALIDADOR],
  // Pausar o reactivar reglas y darlas de alta de cualquier familia.
  administrarReglas: [ADMIN],
  gestionarUsuarios: [ADMIN],
  // Expedientes, documentos, visor, dictámenes, alertas, reglas, bitácora, reportes y descargas.
  leer: [ADMIN, VALIDADOR, AUDITOR],
})

/** Secciones del menú de cada rol, en el orden de la barra lateral. */
const SECCIONES = {
  ADMIN: ['titulares', 'expedientes', 'boveda', 'alertas', 'reportes', 'reglas', 'usuarios'],
  VALIDADOR: ['titulares', 'expedientes', 'boveda', 'alertas', 'reportes', 'reglas'],
  AUDITOR: ['titulares', 'expedientes', 'boveda', 'alertas', 'reportes', 'reglas'],
  CONSULTA: ['consulta'],
}

export function puede(rol, permiso) {
  return Boolean(PERMISOS[permiso]?.includes(rol))
}

export function seccionesDe(rol) {
  return SECCIONES[rol] ?? []
}

/** Pantalla de inicio del rol: Expedientes, salvo la consulta, que solo tiene la suya. */
export function seccionInicial(rol) {
  return rol === CONSULTA ? 'consulta' : 'expedientes'
}

/** Sección que se muestra para una ruta pedida: la misma si el rol la tiene, o su inicio. */
export function seccionPermitida(rol, seccion) {
  return seccionesDe(rol).includes(seccion) ? seccion : seccionInicial(rol)
}
