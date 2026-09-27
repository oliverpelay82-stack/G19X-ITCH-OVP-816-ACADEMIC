/**
 * Clasificación temática del expediente (RF-01, DOC-02 Tabla 5). Espejo de
 * core-service → config/catalogo.py.
 */
export const TIPOS_EXPEDIENTE = [
  { value: 'CORPORATIVO', label: 'Corporativo', descripcion: 'Operación legal y administrativa de la empresa' },
  { value: 'JURIDICO', label: 'Jurídico', descripcion: 'Documentación contractual y sus anexos legales' },
  { value: 'REGULATORIO', label: 'Regulatorio', descripcion: 'Licencias, permisos y certificaciones del sector' },
]

export const TIPO_EXPEDIENTE_LABEL = Object.fromEntries(TIPOS_EXPEDIENTE.map((t) => [t.value, t.label]))

/**
 * Catálogo oficial de tipos documentales (espejo de schemas/documento_schema.py
 * → TipoDocumentoEnum; DOC-02, Tablas 2 a 4). `grupo` es el tipo de
 * expediente en cuyo inventario aparece, para ordenar y agrupar los selectores.
 */
export const TIPOS_DOCUMENTO = [
  // Expediente corporativo
  { value: 'CSF_SAT', label: 'Constancia de Situación Fiscal (SAT)', corto: 'CSF SAT', grupo: 'CORPORATIVO' },
  { value: 'COMP_DOMICILIO', label: 'Comprobante de Domicilio Fiscal', corto: 'Domicilio', grupo: 'CORPORATIVO' },
  { value: 'ACTA_CONSTITUTIVA', label: 'Acta Constitutiva', corto: 'Acta', grupo: 'CORPORATIVO' },
  { value: 'PODER_NOTARIAL', label: 'Poder Notarial', corto: 'Poder', grupo: 'CORPORATIVO' },
  { value: 'ESTATUTOS_SOCIALES', label: 'Estatutos Sociales', corto: 'Estatutos', grupo: 'CORPORATIVO' },
  { value: 'ACTA_ASAMBLEA', label: 'Acta de Asamblea', corto: 'Asamblea', grupo: 'CORPORATIVO' },
  { value: 'CEDULA_RFC', label: 'Registro Federal de Contribuyentes (empresa)', corto: 'RFC', grupo: 'CORPORATIVO' },
  { value: 'AVISO_PRIVACIDAD', label: 'Aviso de Privacidad', corto: 'Privacidad', grupo: 'CORPORATIVO' },
  { value: 'OPINION_CUMPLIMIENTO', label: 'Opinión de Cumplimiento SAT (Art. 32-D)', corto: 'Opinión 32-D', grupo: 'CORPORATIVO' },
  { value: 'ESTADO_CUENTA', label: 'Carátula de Estado de Cuenta Bancario', corto: 'Edo. Cuenta', grupo: 'CORPORATIVO' },
  // Expediente jurídico
  { value: 'CONTRATO_SERVICIOS', label: 'Contrato de Prestación de Servicios', corto: 'Contrato', grupo: 'JURIDICO' },
  { value: 'ACUERDO_CONFIDENCIALIDAD', label: 'Acuerdo de Confidencialidad (NDA)', corto: 'NDA', grupo: 'JURIDICO' },
  { value: 'ANEXO_CONTRATO', label: 'Anexo Legal del Contrato', corto: 'Anexo', grupo: 'JURIDICO' },
  { value: 'DICTAMEN_PERICIAL', label: 'Dictamen o Peritaje', corto: 'Peritaje', grupo: 'JURIDICO' },
  { value: 'CONVENIO_MODIFICATORIO', label: 'Convenio Modificatorio', corto: 'Convenio', grupo: 'JURIDICO' },
  // Expediente regulatorio
  { value: 'LICENCIA_OPERACION', label: 'Licencia de Operación', corto: 'Licencia', grupo: 'REGULATORIO' },
  { value: 'PERMISO_SECTORIAL', label: 'Permiso Municipal o Sectorial', corto: 'Permiso', grupo: 'REGULATORIO' },
  { value: 'CERTIFICACION', label: 'Certificación (ISO, calidad, ambiental)', corto: 'Certificación', grupo: 'REGULATORIO' },
  { value: 'POLIZA_SEGURO', label: 'Póliza de Seguro', corto: 'Póliza', grupo: 'REGULATORIO' },
  { value: 'POLIZA_RC', label: 'Póliza de Responsabilidad Civil', corto: 'Póliza RC', grupo: 'REGULATORIO' },
  { value: 'FIANZA', label: 'Fianza', corto: 'Fianza', grupo: 'REGULATORIO' },
  { value: 'CONSTANCIA_CAPACITACION', label: 'Constancia de Capacitación', corto: 'Capacitación', grupo: 'REGULATORIO' },
  { value: 'REGISTRO_SECTORIAL', label: 'Registro ante Autoridad Sectorial', corto: 'Registro', grupo: 'REGULATORIO' },
]

export const TIPO_DOCUMENTO_LABEL = Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.label]))
export const TIPO_DOCUMENTO_CORTO = Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.corto]))

/**
 * Tipos documentales ordenados para cargar en un expediente: primero los que
 * faltan (obligatorios y anexos), luego el inventario de su tipo y al final el
 * resto del catálogo. Cada opción lleva `seccion` para agruparla en el selector.
 */
export function tiposParaCarga(tipoExpediente, faltantes = []) {
  const pendientes = new Set(faltantes)
  const seccion = (t) =>
    pendientes.has(t.value)
      ? 'Faltantes en el expediente'
      : t.grupo === tipoExpediente
        ? `Inventario ${TIPO_EXPEDIENTE_LABEL[t.grupo]?.toLowerCase() || ''}`
        : 'Otros documentos del catálogo'
  const rango = (t) => (pendientes.has(t.value) ? 0 : t.grupo === tipoExpediente ? 1 : 2)
  return TIPOS_DOCUMENTO.map((t) => ({ ...t, seccion: seccion(t) })).sort((a, b) => rango(a) - rango(b))
}

/** Vigencia del documento recalculada a la fecha de consulta (RN-02). */
export const VIGENCIA_META = {
  VIGENTE: { tono: 'ok', label: 'Vigente' },
  PROXIMO_A_VENCER: { tono: 'warn', label: 'Próximo a vencer' },
  VENCIDO: { tono: 'bad', label: 'Vencido' },
}

/** Categorías de alerta del core-service (RF-18). */
export const ALERTA_META = {
  INTEGRIDAD_COMPROMETIDA: { label: 'Integridad' },
  DOCUMENTO_FALTANTE: { label: 'Faltante' },
  ANEXO_FALTANTE: { label: 'Anexo ausente' },
  DOCUMENTO_VENCIDO: { label: 'Vencido' },
  DICTAMEN_NO_CONFORME: { label: 'Dictamen' },
  PROXIMO_A_VENCER: { label: 'Por vencer' },
  PENDIENTE_RATIFICACION: { label: 'Ratificación' },
  PENDIENTE_AUDITORIA: { label: 'Sin auditar' },
}

export const FAMILIAS_REGLA = ['RIE', 'RCV', 'RSC', 'RDS']

/** Metadatos de cada familia normativa del DOC-05. */
export const FAMILIA_META = {
  RIE: { nombre: 'Integridad y Estructura', nivel: 'Niveles 1 y 2', clase: 'rie' },
  RCV: { nombre: 'Cronológicas y de Vigencia', nivel: 'Nivel 2', clase: 'rcv' },
  RSC: { nombre: 'Semánticas y Contractuales', nivel: 'Nivel 4 — IA', clase: 'rsc' },
  RDS: { nombre: 'Dinámicas y Sectoriales', nivel: 'Configurables', clase: 'rds' },
}

export const SEVERIDADES = ['CRITICA', 'ALTA', 'MEDIA_ALTA', 'MEDIA']

/** Severidades con su etiqueta legible y el tono de estado que les toca. */
export const SEVERIDAD_META = {
  CRITICA: { label: 'Crítica', tono: 'bad' },
  ALTA: { label: 'Alta', tono: 'warn' },
  MEDIA_ALTA: { label: 'Media-Alta', tono: 'warn' },
  MEDIA: { label: 'Media', tono: 'brand' },
}

/** Orden de gravedad para listar alertas de la más grave a la menos grave. */
export const rangoSeveridad = (s) => {
  const i = SEVERIDADES.indexOf(s)
  return i === -1 ? SEVERIDADES.length : i
}

export const getSeveridadMeta = (severidad) =>
  SEVERIDAD_META[severidad] || { label: severidad || 'Sin severidad', tono: 'neutral' }

/** Los tres microservicios del DOC-08, tal como los expone docker-compose. */
export const SERVICIOS = [
  { key: 'core', nombre: 'Core Service', etiqueta: 'Core', puerto: 8001, alcance: 'Titulares · Expedientes · Bóveda' },
  { key: 'rules', nombre: 'Rules Service', etiqueta: 'Rules', puerto: 8002, alcance: 'Catálogo de reglas (Nivel 2)' },
  { key: 'ai', nombre: 'AI Service', etiqueta: 'AI Groq', puerto: 8003, alcance: 'Extracción y análisis semántico' },
]

/**
 * Mapa de estados de auditoría. `tono` apunta a los tokens de estado del
 * sistema de diseño; ningún estado se comunica solo con color, siempre
 * viaja acompañado de su etiqueta.
 */
export const ESTADO_BADGE = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  APROBADO: { tono: 'ok', label: 'Aprobado' },
  EN_REVISION: { tono: 'warn', label: 'En Revisión' },
  REQUIERE_REVISION_HUMANA: { tono: 'warn', label: 'Revisión Humana' },
  PENDIENTE: { tono: 'warn', label: 'Pendiente' },
  NO_CONFORME: { tono: 'bad', label: 'No Conforme' },
  RECHAZADO: { tono: 'bad', label: 'Rechazado' },
  BLOQUEADO: { tono: 'bad', label: 'Bloqueado' },
}

/** Estado de un documento dentro del semáforo del expediente (core-service). */
export const ESTADO_DOCUMENTO = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  EN_REVISION: { tono: 'warn', label: 'En revisión' },
  NO_CONFORME: { tono: 'bad', label: 'No conforme' },
  SIN_DICTAMEN: { tono: 'neutral', label: 'Sin auditar' },
  FALTANTE: { tono: 'bad', label: 'Faltante' },
}

export const getEstadoBadge = (estado) =>
  ESTADO_BADGE[estado] || { tono: 'neutral', label: estado || 'Sin estado' }

/** Umbrales del semáforo de completitud documental (DOC-05). */
export function tonoPorPorcentaje(pct) {
  if (pct >= 100) return 'ok'
  if (pct >= 60) return 'warn'
  return 'bad'
}

/** Firmas binarias (Magic Bytes) para el lector client-side del Nivel 1. */
export const MAGIC_BYTES = [
  { mime: 'application/pdf', label: 'PDF', signature: [0x25, 0x50, 0x44, 0x46, 0x2d] }, // %PDF-
  { mime: 'image/jpeg', label: 'JPEG', signature: [0xff, 0xd8, 0xff] },
  { mime: 'image/png', label: 'PNG', signature: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
]

export const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
