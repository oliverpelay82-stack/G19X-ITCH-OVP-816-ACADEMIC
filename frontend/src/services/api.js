/**
 * Cliente HTTP centralizado del Motor de Validación de Cumplimiento Documental.
 * Arquitectura de microservicios desacoplados (DOC-08): cada dominio apunta a
 * su propio servicio FastAPI independiente.
 *   - Core Service  (:8001) → Titulares, Expedientes, Documentos.
 *   - Rules Service (:8002) → Reglas de Validación.
 *   - AI Service    (:8003) → Extracción de texto/OCR (Nivel 3) y análisis
 *                            semántico con LLM vía Groq Cloud (Nivel 4).
 */
// Configurables en el build (VITE_CORE_URL, VITE_RULES_URL, VITE_AI_URL) para
// desplegar o probar contra otros puertos sin tocar el código; por defecto,
// los puertos oficiales del DOC-08.
export const CORE_BASE_URL = import.meta.env.VITE_CORE_URL || 'http://127.0.0.1:8001/api/v1'
export const RULES_BASE_URL = import.meta.env.VITE_RULES_URL || 'http://127.0.0.1:8002/api/v1'
export const AI_BASE_URL = import.meta.env.VITE_AI_URL || 'http://127.0.0.1:8003/api/v1'

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request(baseUrl, path, { method = 'GET', body, isFormData = false, params } = {}) {
  let url = `${baseUrl}${path}`

  if (params) {
    const query = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== '')
    ).toString()
    if (query) url += `?${query}`
  }

  const options = { method, headers: {} }

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
  } catch {
    throw new ApiError(`No fue posible conectar con ${baseUrl} (¿el microservicio está corriendo?).`, 0, null)
  }

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const detail = payload?.detail || `Error HTTP ${response.status}`
    throw new ApiError(detail, response.status, payload?.detail)
  }

  return payload
}

/* ── Salud de los microservicios ────────────────────────────────── */
export const getHealthCore = () => request(CORE_BASE_URL, '/health')
export const getHealthRules = () => request(RULES_BASE_URL, '/health')
export const getHealthAi = () => request(AI_BASE_URL, '/health')

/* ── M1: Titulares (Core Service :8001) ─────────────────────────── */
export const getTitulares = () => request(CORE_BASE_URL, '/titulares')
export const createTitular = (data) => request(CORE_BASE_URL, '/titulares', { method: 'POST', body: data })

/* ── M1: Expedientes (Core Service :8001) ───────────────────────── */
/** Filtros opcionales (RF-05): { q, tipo_expediente, estado, desde, hasta }. */
export const getExpedientes = (params) => request(CORE_BASE_URL, '/expedientes', { params })
export const getExpedienteById = (id) => request(CORE_BASE_URL, `/expedientes/${id}`)
export const createExpediente = (data) => request(CORE_BASE_URL, '/expedientes', { method: 'POST', body: data })

/* ── M1: Documentos / Bóveda (Core Service :8001) ───────────────── */
export const getDocumentos = () => request(CORE_BASE_URL, '/documentos')
export const getDocumentosPorExpediente = (expedienteId) =>
  request(CORE_BASE_URL, `/documentos/expediente/${expedienteId}`)
export const uploadDocumento = (formData) =>
  request(CORE_BASE_URL, '/documentos/upload', { method: 'POST', body: formData, isFormData: true })

/* ── Dictámenes y bitácora (Core Service :8001) ─────────────────── */
/** Historial de dictámenes de un documento, del más reciente al más antiguo. */
export const getDictamenes = (params) => request(CORE_BASE_URL, '/dictamenes', { params })

/** Ratificación humana (Nivel 5): { nuevo_estatus, justificacion, usuario }. */
export const ratificarDictamen = (dictamenId, data) =>
  request(CORE_BASE_URL, `/dictamenes/${dictamenId}/ratificar`, { method: 'POST', body: data })

export const getBitacora = (params) => request(CORE_BASE_URL, '/bitacora', { params })

/* ── M5: Alertas y recomendaciones (Core Service :8001) ─────────── */
export const getAlertas = (params) => request(CORE_BASE_URL, '/alertas', { params })

/* ── M6: Reportes exportables (Core Service :8001) ──────────────── */
/**
 * Descarga un reporte (PDF o Excel) y lo entrega al navegador como archivo.
 * `ruta`: '/reportes/expedientes/{id}' o '/reportes/cumplimiento'.
 */
export async function descargarReporte(ruta, params) {
  const query = new URLSearchParams(
    Object.entries(params || {}).filter(([, v]) => v !== undefined && v !== null && v !== '')
  ).toString()
  let response
  try {
    response = await fetch(`${CORE_BASE_URL}${ruta}${query ? `?${query}` : ''}`)
  } catch {
    throw new ApiError(`No fue posible conectar con ${CORE_BASE_URL} (¿el microservicio está corriendo?).`, 0, null)
  }
  if (!response.ok) {
    const payload = await response.json().catch(() => null)
    throw new ApiError(payload?.detail || `Error HTTP ${response.status}`, response.status, payload?.detail)
  }
  const disposicion = response.headers.get('content-disposition') || ''
  const nombre = /filename="([^"]+)"/.exec(disposicion)?.[1] || `reporte.${params?.formato || 'pdf'}`
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

/* ── M2: Reglas de Validación (Rules Service :8002) ─────────────── */
export const getReglas = (params) => request(RULES_BASE_URL, '/reglas', { params })
export const createRegla = (data) => request(RULES_BASE_URL, '/reglas', { method: 'POST', body: data })
export const toggleRegla = (id, activo) =>
  request(RULES_BASE_URL, `/reglas/${id}/activo`, { method: 'PATCH', params: { activo } })

export { ApiError }


/* ── Nivel 3 y 4: Análisis con IA (AI Service :8003) ────────────── */
export const extraerTextoDocumento = (formData) =>
  request(AI_BASE_URL, '/ai/extraer-texto', { method: 'POST', body: formData, isFormData: true })

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

export const localizarCita = (documentoId, cita) =>
  request(AI_BASE_URL, `/ai/documentos/${documentoId}/localizar`, { method: 'POST', body: { cita } })
