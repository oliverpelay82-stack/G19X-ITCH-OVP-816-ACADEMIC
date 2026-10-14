/**
 * Cliente HTTP centralizado del Motor de Validación de Cumplimiento Documental.
 * Arquitectura de microservicios desacoplados (DOC-08): cada dominio apunta a
 * su propio servicio FastAPI independiente.
 *   - Core Service  (:8001) → Titulares, Expedientes, Documentos.
 *   - Rules Service (:8002) → Reglas de Validación.
 *   - AI Service    (:8003) → Extracción de texto/OCR (Nivel 3) y análisis
 *                            semántico con LLM vía Groq Cloud (Nivel 4).
 */
import { idAleatorio } from '../utils/id.js'
import { MOTIVO, actualizarPerfil, sesionActual, terminarSesion, tokenActual } from './sesion.js'

// Configurables en el build (VITE_CORE_URL, VITE_RULES_URL, VITE_AI_URL) para
// desplegar o probar contra otros puertos sin tocar el código; por defecto,
// los puertos oficiales del DOC-08.
export const CORE_BASE_URL = import.meta.env.VITE_CORE_URL || 'http://127.0.0.1:8001/api/v1'
export const RULES_BASE_URL = import.meta.env.VITE_RULES_URL || 'http://127.0.0.1:8002/api/v1'
export const AI_BASE_URL = import.meta.env.VITE_AI_URL || 'http://127.0.0.1:8003/api/v1'

/**
 * Texto legible del `detail` de una respuesta de error. FastAPI lo envía como
 * cadena en los errores propios (HTTPException) y como lista de objetos
 * { loc, msg } en los de validación (422); sin esto, la lista llegaba al aviso
 * como «[object Object]».
 */
function mensajeDeError(detail, status) {
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    return detail
      .map((e) => {
        const campo = Array.isArray(e?.loc) ? e.loc.filter((p) => p !== 'body').join('.') : ''
        const msg = (e?.msg || String(e)).replace(/^Value error, /, '')
        return campo ? `${campo}: ${msg}` : msg
      })
      .join('; ')
  }
  return `Error HTTP ${status}`
}

class ApiError extends Error {
  constructor(message, status, detail, folio = null) {
    // PLUS-21: un error del servidor lleva su folio de seguimiento para el soporte.
    super(folio && status >= 500 ? `${message} (Folio de seguimiento: ${folio})` : message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
    this.folio = folio
  }
}

/** PLUS-21: folio de seguimiento de cada llamada (X-Request-ID). */
const nuevoFolio = idAleatorio

/**
 * Tiempo máximo de las lecturas que el panel repite cada 15 s (salud y listas).
 * Sin límite, un servicio que acepta la conexión pero no responde dejaba cada
 * ciclo pendiente sobre el anterior. La auditoría y el chat no lo llevan: un
 * documento escaneado largo puede tardar más de 25 s (RNF-02).
 */
const LIMITE_SONDEO_MS = 10000

/**
 * Módulo 7: cada petición lleva el token de la sesión. Un 401 significa que la
 * sesión ya no vale (venció, la cuenta se desactivó): se cierra y la interfaz
 * vuelve al inicio de sesión. Un 403 por contraseña temporal (el administrador la
 * restableció) lleva a la pantalla de cambio. Las peticiones `publicas` (el inicio
 * de sesión) reciben su 401 como un error más: ahí significa credenciales malas.
 */
function conSesion(headers) {
  const token = tokenActual()
  return token ? { ...headers, Authorization: `Bearer ${token}` } : headers
}

const CONTRASENA_TEMPORAL = /contraseña temporal/i

function atenderRechazo(status, detail, publica) {
  if (publica) return
  if (status === 401) terminarSesion(MOTIVO.EXPIRADA)
  else if (status === 403 && typeof detail === 'string' && CONTRASENA_TEMPORAL.test(detail)) {
    const usuario = sesionActual()?.usuario
    if (usuario) actualizarPerfil({ ...usuario, debe_cambiar_contrasena: true })
  }
}

async function request(baseUrl, path, { method = 'GET', body, isFormData = false, params, tiempoLimite, publica = false } = {}) {
  let url = `${baseUrl}${path}`

  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (query) url += `?${query}`
  }

  const folio = nuevoFolio()
  const options = { method, headers: conSesion({ 'X-Request-ID': folio }) }
  if (tiempoLimite) options.signal = AbortSignal.timeout(tiempoLimite)

  if (body !== undefined) {
    if (isFormData) {
      options.body = body
    } else {
      options.headers['Content-Type'] = 'application/json'
      options.body = JSON.stringify(body)
    }
  }

  let response
  try {
    response = await fetch(url, options)
  } catch (err) {
    if (err?.name === 'TimeoutError') {
      throw new ApiError(`${baseUrl} no respondió en ${tiempoLimite / 1000} s.`, 0, null)
    }
    throw new ApiError(`No fue posible conectar con ${baseUrl} (¿el microservicio está corriendo?).`, 0, null)
  }

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json().catch(() => null) : null

  if (!response.ok) {
    atenderRechazo(response.status, payload?.detail, publica)
    const recibido = response.headers.get('X-Request-ID') || payload?.id_peticion || folio
    throw new ApiError(mensajeDeError(payload?.detail, response.status), response.status, payload?.detail, recibido)
  }

  return payload
}

/* ── Módulo 7: sesión, segundo factor y cuentas (Core Service :8001) ── */
/**
 * Inicio de sesión. Con la verificación en dos pasos y sin `codigo`, responde
 * { requiere_codigo: true } sin token; con él (o sin MFA), { access_token, usuario… }.
 */
export const iniciarSesionApi = (email, contrasena, codigo) =>
  request(CORE_BASE_URL, '/auth/login', { method: 'POST', body: { email, contrasena, codigo: codigo || undefined }, publica: true })
export const getPerfil = () => request(CORE_BASE_URL, '/auth/me')
export const cambiarContrasena = (contrasena_actual, contrasena_nueva) =>
  request(CORE_BASE_URL, '/auth/cambiar-contrasena', { method: 'POST', body: { contrasena_actual, contrasena_nueva } })
/** Fase F3: { secreto, uri } para la app autenticadora; aún no habilita nada. */
export const generarMfa = (contrasena) => request(CORE_BASE_URL, '/auth/mfa/generar', { method: 'POST', body: { contrasena } })
export const activarMfa = (codigo) => request(CORE_BASE_URL, '/auth/mfa/activar', { method: 'POST', body: { codigo } })
export const desactivarMfa = (contrasena, codigo) =>
  request(CORE_BASE_URL, '/auth/mfa/desactivar', { method: 'POST', body: { contrasena, codigo } })

/** Cuentas (solo ADMIN, HU-05). */
export const getUsuarios = () => request(CORE_BASE_URL, '/usuarios', { tiempoLimite: LIMITE_SONDEO_MS })
export const crearUsuario = (datos) => request(CORE_BASE_URL, '/usuarios', { method: 'POST', body: datos })
/** { nombre_completo?, rol?, activo?, contrasena_temporal?, restablecer_mfa? }: lo omitido no cambia. */
export const actualizarUsuario = (id, cambios) => request(CORE_BASE_URL, `/usuarios/${id}`, { method: 'PATCH', body: cambios })
export const getExpedientesDeUsuario = (id) => request(CORE_BASE_URL, `/usuarios/${id}/expedientes`)
export const asignarExpedientes = (id, expedienteIds) =>
  request(CORE_BASE_URL, `/usuarios/${id}/expedientes`, { method: 'PUT', body: { expediente_ids: expedienteIds } })

/** HU-31: semáforo de los expedientes asignados a quien consulta. */
export const getExpedientesAsignados = () =>
  request(CORE_BASE_URL, '/expedientes/asignados', { tiempoLimite: LIMITE_SONDEO_MS })

/* ── Salud de los microservicios ────────────────────────────────── */
export const getHealthCore = () => request(CORE_BASE_URL, '/health', { tiempoLimite: LIMITE_SONDEO_MS })
export const getHealthRules = () => request(RULES_BASE_URL, '/health', { tiempoLimite: LIMITE_SONDEO_MS })
export const getHealthAi = () => request(AI_BASE_URL, '/health', { tiempoLimite: LIMITE_SONDEO_MS })

/* ── M1: Titulares (Core Service :8001) ─────────────────────────── */
export const getTitulares = () => request(CORE_BASE_URL, '/titulares', { tiempoLimite: LIMITE_SONDEO_MS })
export const createTitular = (data) => request(CORE_BASE_URL, '/titulares', { method: 'POST', body: data })
/** Corrección de datos de captura: razón social y categoría (el RFC no se edita). */
export const corregirTitular = (id, cambios) =>
  request(CORE_BASE_URL, `/titulares/${id}`, { method: 'PATCH', body: cambios })

/* ── M1: Expedientes (Core Service :8001) ───────────────────────── */
/** Filtros opcionales (RF-05): { q, tipo_expediente, estado, desde, hasta }. */
export const getExpedientes = (params) => request(CORE_BASE_URL, '/expedientes', { params, tiempoLimite: LIMITE_SONDEO_MS })
export const getExpedienteById = (id) => request(CORE_BASE_URL, `/expedientes/${id}`)
export const createExpediente = (data) => request(CORE_BASE_URL, '/expedientes', { method: 'POST', body: data })
/** Renombra un expediente (nulo quita el nombre); el tipo no se edita. */
export const renombrarExpediente = (id, nombre) =>
  request(CORE_BASE_URL, `/expedientes/${id}`, { method: 'PATCH', body: { nombre } })

/* ── M1: Documentos / Bóveda (Core Service :8001) ───────────────── */
export const getDocumentos = () => request(CORE_BASE_URL, '/documentos', { tiempoLimite: LIMITE_SONDEO_MS })
const uploadDocumento = (formData) =>
  request(CORE_BASE_URL, '/documentos/upload', { method: 'POST', body: formData, isFormData: true })
/**
 * RNF-02: pide al ai-service leer de fondo el documento recién custodiado (todas
 * sus páginas, sin el modelo ni tokens), para que la auditoría encuentre el texto
 * listo. No se espera ni se avisa: si la IA no responde, la auditoría lee como antes.
 */
const anticiparLectura = (documentoId) =>
  request(AI_BASE_URL, `/ai/documentos/${documentoId}/anticipar`, { method: 'POST', tiempoLimite: LIMITE_SONDEO_MS }).catch(
    () => {}
  )

/** Custodia un archivo con su tipo en un expediente (una carga individual o un elemento de un lote, RF-02). */
export const custodiarArchivo = async (expedienteId, archivo, tipoDocumento) => {
  const formData = new FormData()
  formData.append('expediente_id', expedienteId)
  formData.append('tipo_documento', tipoDocumento)
  formData.append('file', archivo)
  const documento = await uploadDocumento(formData)
  if (documento?.id) anticiparLectura(documento.id)
  return documento
}

/* ── Dictámenes y bitácora (Core Service :8001) ─────────────────── */
/** Historial de dictámenes de un documento, del más reciente al más antiguo. */
export const getDictamenes = (params) => request(CORE_BASE_URL, '/dictamenes', { params })

/** Ratificación humana (Nivel 5): { nuevo_estatus, justificacion }; ratifica el usuario en sesión. */
export const ratificarDictamen = (dictamenId, data) =>
  request(CORE_BASE_URL, `/dictamenes/${dictamenId}/ratificar`, { method: 'POST', body: data })

export const getBitacora = (params) => request(CORE_BASE_URL, '/bitacora', { params })
/** P3: recalcula la cadena sellada de la bitácora (hashes, enlaces y génesis). */
export const verificarCadena = () => request(CORE_BASE_URL, '/bitacora/verificar-cadena')

/* ── M6: Reportes exportables (Core Service :8001) ──────────────── */
/**
 * Descarga un archivo del core (un reporte en PDF o Excel, o el original de
 * un documento) y lo entrega al navegador. `ruta`: '/reportes/expedientes/{id}',
 * '/reportes/cumplimiento' o '/documentos/{id}/contenido'.
 */
export async function descargarReporte(ruta, params) {
  const query = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  ).toString()
  let response
  const folio = nuevoFolio()
  try {
    response = await fetch(`${CORE_BASE_URL}${ruta}${query ? `?${query}` : ''}`, {
      headers: conSesion({ 'X-Request-ID': folio }),
    })
  } catch {
    throw new ApiError(`No fue posible conectar con ${CORE_BASE_URL} (¿el microservicio está corriendo?).`, 0, null)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    atenderRechazo(response.status, payload?.detail, false)
    throw new ApiError(mensajeDeError(payload?.detail, response.status), response.status, payload?.detail,
      response.headers.get('X-Request-ID') || folio)
  }
  const disposicion = response.headers.get('content-disposition') || ''
  // filename* (RFC 6266) conserva acentos y eñes; filename es el respaldo ASCII.
  const extendido = /filename\*=UTF-8''([^;]+)/i.exec(disposicion)?.[1]
  const nombre =
    (extendido && decodeURIComponent(extendido)) ||
    /filename="([^"]+)"/.exec(disposicion)?.[1] ||
    `reporte.${params?.formato || 'pdf'}`
  const url = URL.createObjectURL(await response.blob())
  const enlace = document.createElement('a')
  enlace.href = url
  enlace.download = nombre
  document.body.appendChild(enlace)
  enlace.click()
  enlace.remove()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
  return nombre
}

/** El archivo original de un documento, verificado por RIE-03; la descarga queda en la bitácora. */
export const descargarOriginal = (documentoId) =>
  descargarReporte(`/documentos/${documentoId}/contenido`, { descarga: true })

/* ── M2: Reglas de Validación (Rules Service :8002) ─────────────── */
export const getReglas = (params) => request(RULES_BASE_URL, '/reglas', { params, tiempoLimite: LIMITE_SONDEO_MS })
export const createRegla = (data) => request(RULES_BASE_URL, '/reglas', { method: 'POST', body: data })
export const toggleRegla = (id, activo) =>
  request(RULES_BASE_URL, `/reglas/${id}/activo`, { method: 'PATCH', params: { activo } })


/* ── Nivel 3 y 4: Análisis con IA (AI Service :8003) ────────────── */
/** Resuelve el texto del documento (Nivel 3) sin llamar al modelo: primera etapa de la auditoría. */
export const prepararDocumento = (documentoId) =>
  request(AI_BASE_URL, `/ai/documentos/${documentoId}/preparar`, { method: 'POST' })

export const analizarDocumento = (data) =>
  request(AI_BASE_URL, '/ai/analisis-semantico', { method: 'POST', body: data })

export const preguntarSobreDocumento = (data) =>
  request(AI_BASE_URL, '/ai/chat-documento', { method: 'POST', body: data })

/* ── Visor de evidencia (HU-20, RF-13) ──────────────────────────── */
export const getVisorDocumento = (documentoId) => request(AI_BASE_URL, `/ai/documentos/${documentoId}/visor`)

/** URL de la página renderizada; el ai-service la sirve desde el binario verificado (RIE-03). */
export const urlPaginaDocumento = (documentoId, pagina, ancho) =>
  `${AI_BASE_URL}/ai/documentos/${documentoId}/paginas/${pagina}?ancho=${ancho}`

/**
 * Imagen de una página del visor como blob. Un <img src> no puede enviar el token
 * (Módulo 7), así que la página se pide con fetch y se muestra desde una URL de
 * objeto (hooks/useImagenAutenticada.js).
 */
export async function getPaginaDocumento(url, signal) {
  let response
  try {
    response = await fetch(url, { headers: conSesion({ 'X-Request-ID': nuevoFolio() }), signal })
  } catch (err) {
    if (err?.name === 'AbortError') throw err
    throw new ApiError(`No fue posible conectar con ${AI_BASE_URL} (¿el microservicio está corriendo?).`, 0, null)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    atenderRechazo(response.status, payload?.detail, false)
    throw new ApiError(mensajeDeError(payload?.detail, response.status), response.status, payload?.detail)
  }
  return response.blob()
}

export const localizarCita = (documentoId, cita) =>
  request(AI_BASE_URL, `/ai/documentos/${documentoId}/localizar`, { method: 'POST', body: { cita } })
