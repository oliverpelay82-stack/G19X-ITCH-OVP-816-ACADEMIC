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
 * Categoría del titular (DOC-08, Tabla 5: CLIENTE o PROVEEDOR). PROVEEDOR_CRITICO
 * viene de los datos de demostración (core-service/seed_demo.py); cualquier otro
 * valor se muestra en minúsculas y sin guiones bajos.
 */
const CATEGORIA_TITULAR_LABEL = { PROVEEDOR: 'Proveedor', CLIENTE: 'Cliente', PROVEEDOR_CRITICO: 'Proveedor crítico' }

export function categoriaTitular(categoria) {
  if (!categoria) return '—'
  const texto = CATEGORIA_TITULAR_LABEL[categoria] || categoria.replaceAll('_', ' ').toLowerCase()
  return texto.charAt(0).toUpperCase() + texto.slice(1)
}

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

// OTRO no se ofrece al cargar: es el tipo heredado de documentos custodiados
// antes del catálogo actual (CHECK de la base). Se nombra para no mostrar el
// código tal cual en tablas, historial y detalle.
export const TIPO_DOCUMENTO_LABEL = {
  ...Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.label])),
  OTRO: 'Otro documento',
}
export const TIPO_DOCUMENTO_CORTO = Object.fromEntries(TIPOS_DOCUMENTO.map((t) => [t.value, t.corto]))

const TIPOS_BASE = new Set(TIPOS_DOCUMENTO.map((t) => t.value))
// RIE-01-<código> cabe en los 50 caracteres de codigo_regla.
const LARGO_MAXIMO_CODIGO = 43

/** Código de un tipo nuevo a partir de su nombre: sin acentos, en mayúsculas y con guiones bajos. */
export function codigoDeTipo(nombre) {
  return (nombre || '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, '_')
    .replace(/^[_0-9]+|_+$/g, '')
    .slice(0, LARGO_MAXIMO_CODIGO)
    .replace(/_+$/, '')
}

/**
 * RF-09: incorpora al catálogo los tipos declarados por reglas RDS (RDS-01),
 * con el mismo criterio que el rules-service (GET /reglas/tipos-documento): el
 * nombre de la regla más antigua de cada código y activo si alguna lo está.
 * Modifica los objetos exportados para que todas las vistas los nombren sin
 * cambiar sus importaciones; la carga solo ofrece los activos. Se llama cada vez
 * que llegan las reglas.
 */
export function registrarTiposDeclarados(reglas) {
  const declarados = new Map()
  const ordenadas = [...(reglas || [])].sort((a, b) =>
    String(a.creado_en).localeCompare(String(b.creado_en)) || a.codigo_regla.localeCompare(b.codigo_regla)
  )
  for (const r of ordenadas) {
    const codigo = r.familia_regla === 'RDS' && r.tipo_documento?.trim().toUpperCase()
    if (!codigo || TIPOS_BASE.has(codigo)) continue
    const previo = declarados.get(codigo)
    if (!previo) declarados.set(codigo, { value: codigo, label: r.nombre_regla, corto: r.nombre_regla,
      grupo: r.tipo_expediente || null, activo: r.activo, declarado: true })
    else if (r.activo) previo.activo = true
  }
  for (let i = TIPOS_DOCUMENTO.length - 1; i >= 0; i--) if (TIPOS_DOCUMENTO[i].declarado) TIPOS_DOCUMENTO.splice(i, 1)
  for (const tipo of declarados.values()) {
    TIPO_DOCUMENTO_LABEL[tipo.value] = tipo.label
    TIPO_DOCUMENTO_CORTO[tipo.value] = tipo.corto
    if (tipo.activo) TIPOS_DOCUMENTO.push(tipo)
  }
}

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
  CONTENIDO_NO_LOCALIZADO: { label: 'Contenido' },
  PENDIENTE_AUDITORIA: { label: 'Sin auditar' },
  REPRESENTACION_NO_ACREDITADA: { label: 'Representación' },
  // P5 (DOC-05, Tabla 1): excepciones del procesamiento.
  DOCUMENTO_ILEGIBLE: { label: 'Ilegible' },
  PROCESAMIENTO_DIFERIDO: { label: 'Diferido' },
  // P6: señales del archivo.
  POSIBLE_EDICION: { label: 'Posible edición' },
  CONTENIDO_ACTIVO: { label: 'Contenido activo' },
  ARCHIVO_DE_OTRO_TITULAR: { label: 'Otro titular' },
  REQUIERE_NUEVA_AUDITORIA: { label: 'Nueva auditoría' },
}

export const FAMILIAS_REGLA = ['RIE', 'RCV', 'RSC', 'RDS']

/** Metadatos de cada familia normativa del DOC-05. */
export const FAMILIA_META = {
  RIE: { nombre: 'Integridad y Estructura', nivel: 'Carga y completitud', clase: 'rie' },
  RCV: { nombre: 'Cronológicas y de Vigencia', nivel: 'Fechas, sin IA', clase: 'rcv' },
  RSC: { nombre: 'Semánticas y Contractuales', nivel: 'Contenido, con IA', clase: 'rsc' },
  RDS: { nombre: 'Dinámicas y Sectoriales', nivel: 'Definidas por el usuario', clase: 'rds' },
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
  { key: 'rules', nombre: 'Rules Service', etiqueta: 'Rules', puerto: 8002, alcance: 'Catálogo de reglas y vigencias' },
  { key: 'ai', nombre: 'AI Service', etiqueta: 'IA', puerto: 8003, alcance: 'Extracción y análisis semántico' },
]

/**
 * Mapa de estados de auditoría. `tono` apunta a los tokens de estado del
 * sistema de diseño; ningún estado se comunica solo con color, siempre
 * viaja acompañado de su etiqueta.
 */
export const ESTADO_BADGE = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  APROBADO: { tono: 'ok', label: 'Aprobado' },
  EN_REVISION: { tono: 'warn', label: 'En revisión' },
  REQUIERE_REVISION_HUMANA: { tono: 'warn', label: 'Revisión humana' },
  PENDIENTE: { tono: 'warn', label: 'Pendiente' },
  NO_CONFORME: { tono: 'bad', label: 'No conforme' },
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

/** Firmas binarias (Magic Bytes) para el lector client-side del Nivel 1. */
export const MAGIC_BYTES = [
  { mime: 'application/pdf', label: 'PDF', signature: [0x25, 0x50, 0x44, 0x46, 0x2d] }, // %PDF-
  { mime: 'image/jpeg', label: 'JPEG', signature: [0xff, 0xd8, 0xff] },
  { mime: 'image/png', label: 'PNG', signature: [0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a] },
]

export const MAX_FILE_SIZE_BYTES = 15 * 1024 * 1024
