/**
 * Cliente HTTP centralizado del Motor de Validación de Cumplimiento Documental.
 * Arquitectura de microservicios desacoplados (DOC-08): cada dominio apunta a
 * su propio servicio FastAPI independiente.
 *   - Core Service  (:8001) → Titulares, Expedientes, Documentos.
 *   - Rules Service (:8002) → Reglas de Validación.
 *   - AI Service    (:8003) → Extracción de texto/OCR (Nivel 3) y análisis
 *                            semántico con LLM vía Groq Cloud (Nivel 4).
 */
export const CORE_BASE_URL = 'http://127.0.0.1:8001/api/v1'
export const RULES_BASE_URL = 'http://127.0.0.1:8002/api/v1'
export const AI_BASE_URL = 'http://127.0.0.1:8003/api/v1'

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
export const getExpedientes = () => request(CORE_BASE_URL, '/expedientes')
export const getExpedienteById = (id) => request(CORE_BASE_URL, `/expedientes/${id}`)
export const createExpediente = (data) => request(CORE_BASE_URL, '/expedientes', { method: 'POST', body: data })

/* ── M1: Documentos / Bóveda (Core Service :8001) ───────────────── */
export const getDocumentos = () => request(CORE_BASE_URL, '/documentos')
export const getDocumentosPorExpediente = (expedienteId) =>
  request(CORE_BASE_URL, `/documentos/expediente/${expedienteId}`)
export const uploadDocumento = (formData) =>
  request(CORE_BASE_URL, '/documentos/upload', { method: 'POST', body: formData, isFormData: true })

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
