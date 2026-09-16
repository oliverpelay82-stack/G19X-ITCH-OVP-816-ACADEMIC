/**
 * Cliente HTTP centralizado del Motor de Validación de Cumplimiento Documental.
 * Apunta al backend FastAPI (/api/v1) según DOC-08 (versionado semántico de API).
 */
export const API_BASE_URL = 'http://127.0.0.1:8000/api/v1'

class ApiError extends Error {
  constructor(message, status, detail) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

async function request(path, { method = 'GET', body, isFormData = false, params } = {}) {
  let url = `${API_BASE_URL}${path}`

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
    throw new ApiError('No fue posible conectar con el backend (¿está corriendo en :8000?).', 0, null)
  }

  const contentType = response.headers.get('content-type') || ''
  const payload = contentType.includes('application/json') ? await response.json().catch(() => null) : null

  if (!response.ok) {
    const detail = payload?.detail || `Error HTTP ${response.status}`
    throw new ApiError(detail, response.status, payload?.detail)
  }

  return payload
}

/* ── Estado del sistema ─────────────────────────────────────────── */
export const getStatus = () => request('/status')

/* ── M1: Titulares ──────────────────────────────────────────────── */
export const getTitulares = () => request('/titulares')
export const createTitular = (data) => request('/titulares', { method: 'POST', body: data })

/* ── M1: Expedientes ────────────────────────────────────────────── */
export const getExpedientes = () => request('/expedientes')
export const getExpedienteById = (id) => request(`/expedientes/${id}`)
export const createExpediente = (data) => request('/expedientes', { method: 'POST', body: data })

/* ── M1: Documentos (Bóveda) ────────────────────────────────────── */
export const getDocumentos = () => request('/documentos')
export const getDocumentosPorExpediente = (expedienteId) => request(`/documentos/expediente/${expedienteId}`)
export const uploadDocumento = (formData) =>
  request('/documentos/upload', { method: 'POST', body: formData, isFormData: true })

/* ── M2: Reglas de Validación ───────────────────────────────────── */
export const getReglas = (params) => request('/reglas', { params })
export const createRegla = (data) => request('/reglas', { method: 'POST', body: data })
export const toggleRegla = (id, activo) =>
  request(`/reglas/${id}/activo`, { method: 'PATCH', params: { activo } })

export { ApiError }
