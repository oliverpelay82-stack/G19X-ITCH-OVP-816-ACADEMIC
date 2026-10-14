import { useCallback, useEffect, useMemo, useState } from 'react'
import { CaretDown, CaretUp, DownloadSimple, SidebarSimple, UserCheck } from './iconos.js'
import { Badge, Button, CopyChip, IconButton, KeyValue, KeyValueList, Modal } from './ui/index.js'
import { cx } from './ui/clases.js'
import Destello from './Destello.jsx'
import DocumentoIaPanel from './DocumentoIaPanel.jsx'
import ExportarReporte from './ExportarReporte.jsx'
import VisorDocumento from './VisorDocumento.jsx'
import { EvidenciaContext } from './evidencia-context.js'
import useToast from '../hooks/useToast.js'
import { descargarOriginal, localizarCita } from '../services/api.js'
import { ESTADO_DOCUMENTO, TIPO_DOCUMENTO_LABEL } from '../constants.js'
import { firmaDeMime, tipoCorto } from '../utils/documentos.js'
import { formatBytes, formatDia, formatFecha } from '../utils/format.js'

function Dato({ label, children, ancho = false }) {
  return (
    <KeyValue etiqueta={label} className={ancho ? 'detail-item detail-item--full' : 'detail-item'}>
      {children}
    </KeyValue>
  )
}

/** P6 (PLUS-18): contenido activo del PDF (JavaScript, acciones automáticas, adjuntos…), que lleva a revisión. */
function SenalesArchivo({ documento }) {
  const senales = documento.senales_pdf
  if (!senales) return <span className="cell-sub">Se calculará en la próxima verificación programada.</span>
  if (senales.no_analizable) return <span className="cell-sub">No se pudo analizar la estructura del PDF.</span>
  const revision = documento.senales_revision || []
  if (!revision.length) return <span>Sin contenido activo.</span>
  return (
    <span className="cell-stack">
      {revision.map((motivo) => (
        <span key={motivo} className="senal-archivo senal-archivo--warn">
          {motivo}
        </span>
      ))}
    </span>
  )
}

/**
 * Estado del documento para el encabezado del modal, a partir de la evaluación
 * de su expediente: el del dictamen si es la versión vigente de su tipo,
 * «Sustituido» si hay una posterior y «Alterado» si su huella ya no coincide.
 */
function estadoEnExpediente(doc, expediente) {
  if (doc.estado_integridad === 'ALTERADO') {
    return { tono: 'bad', label: 'Alterado', nota: 'La huella ya no coincide con la de la carga: el documento está bloqueado.' }
  }
  const evaluacion = expediente?.evaluacion
  const estado = evaluacion?.documentos?.find((d) => d.documento_id === doc.id)
  if (!estado) {
    return evaluacion
      ? { tono: 'neutral', label: 'Sustituido', nota: 'Una versión más reciente del mismo tipo es la vigente.' }
      : null
  }
  const meta = ESTADO_DOCUMENTO[estado.estado] || ESTADO_DOCUMENTO.SIN_DICTAMEN
  const fecha = estado.fecha_caducidad ? formatDia(estado.fecha_caducidad) : null
  const vigencia =
    estado.vigencia === 'VENCIDO'
      ? `Vencido desde el ${fecha}`
      : estado.vigencia === 'PROXIMO_A_VENCER'
        ? `Vence el ${fecha}`
        : estado.vigencia === 'VIGENTE'
          ? `Vigente hasta el ${fecha}`
          : estado.estado === 'SIN_DICTAMEN'
            ? 'Aún no tiene dictamen'
            : 'Sin fecha de vencimiento'
  // P5 (DOC-05, Tabla 1): un documento ilegible se recarga, no se ratifica; uno
  // diferido espera a que la IA responda.
  const excepcion = estado.ilegible
    ? 'ilegible: se requiere recargarlo con mejor resolución'
    : estado.procesamiento_diferido
      ? estado.procesamiento_diferido.agotado
        ? 'la IA no respondió y se agotaron los reintentos automáticos'
        : 'la IA no respondió; la auditoría se reintentará sola'
      : null
  return {
    tono: estado.vigencia === 'VENCIDO' ? 'bad' : meta.tono,
    label: estado.vigencia === 'VENCIDO' ? 'Vencido' : meta.label,
    nota: [vigencia, excepcion, estado.revisado_por_humano && 'ratificado por un analista'].filter(Boolean).join(' · '),
    ratificable: estado.estado === 'EN_REVISION' && !estado.revisado_por_humano && !estado.ilegible,
  }
}

/**
 * Encabezado de veredicto, auditoría con IA por secciones y, a la derecha, el visor del documento
 * original. Un clic en una cita del dictamen o del chat abre el visor en la
 * página donde está y la resalta (HU-20). Se monta con `key={doc.id}` para
 * reiniciar el visor al cambiar de documento.
 */
function InspectorDocumento({ doc, expediente, iaOnline, onRefresh, onVisor, onOcupado, visorInicial, entrada, children }) {
  // Al pasar al documento siguiente el visor sigue abierto si lo estaba.
  const [visorAbierto, setVisorAbierto] = useState(Boolean(visorInicial) && iaOnline)
  // Sección del panel de IA y solicitudes de ratificación desde el encabezado.
  const [vista, setVista] = useState('resultado')
  const [solicitudRatificar, setSolicitudRatificar] = useState(0)
  const estado = estadoEnExpediente(doc, expediente)
  const ratificar = () => {
    setVista('resultado')
    setSolicitudRatificar((n) => n + 1)
  }
  const [busqueda, setBusqueda] = useState(null)
  const alternarVisor = (abierto) => {
    setVisorAbierto(abierto)
    onVisor(abierto)
  }
  // Ubica la cita en el documento; si llega otra antes de terminar, gana la última.
  const mostrar = useCallback(
    async ({ cita, tono = 'ok' }) => {
      const clave = crypto.randomUUID()
      setVisorAbierto(true)
      onVisor(true)
      setBusqueda({ clave, tono, buscando: true })
      const vigente = (previa) => previa?.clave === clave
      try {
        const resultado = await localizarCita(doc.id, cita)
        setBusqueda((previa) => (vigente(previa) ? { clave, tono, resultado } : previa))
      } catch (err) {
        const error = err?.message || 'No se pudo ubicar la cita.'
        setBusqueda((previa) => (vigente(previa) ? { clave, tono, error } : previa))
      }
    },
    [doc.id, onVisor]
  )
  const irAPagina = useCallback(
    (pagina) => {
      setVisorAbierto(true)
      onVisor(true)
      setBusqueda({ clave: crypto.randomUUID(), pagina })
    },
    [onVisor]
  )
  const contexto = useMemo(
    () => (iaOnline ? { mostrar, irAPagina } : null),
    [iaOnline, mostrar, irAPagina]
  )

  return (
    <EvidenciaContext.Provider value={contexto}>
      <div className={cx('inspector', visorAbierto && 'inspector--visor', entrada && `inspector--desde-${entrada}`)}>
        <div className="inspector-principal">
          {/* Encabezado de veredicto: el estado del documento y las acciones
              principales, antes que cualquier detalle. */}
          <div className={`doc-veredicto doc-veredicto--${estado?.tono || 'neutral'}`}>
            <div className="doc-veredicto-estado">
              <p className="eyebrow">Estado del documento</p>
              {estado ? (
                <>
                  <Destello valor={estado.label} tono={estado.tono}>
                    <Badge tono={estado.tono} punto grande>
                      {estado.label}
                    </Badge>
                  </Destello>
                  <p className="doc-veredicto-nota">{estado.nota}</p>
                </>
              ) : (
                <p className="doc-veredicto-nota">Sin evaluación del expediente.</p>
              )}
            </div>
            <div className="doc-veredicto-acciones">
              {estado?.ratificable && (
                <Button variante="primary" compacto icono={UserCheck} onClick={ratificar}>
                  Ratificar dictamen
                </Button>
              )}
              <Button
                compacto
                icono={visorAbierto ? SidebarSimple : SidebarSimple}
                onClick={() => alternarVisor(!visorAbierto)}
                disabled={!iaOnline}
                title={
                  iaOnline
                    ? 'Un clic en una cita del dictamen o del chat la resalta en el documento'
                    : 'El visor no está disponible: el servicio de análisis no responde'
                }
              >
                {visorAbierto ? 'Ocultar documento' : 'Ver documento'}
              </Button>
            </div>
          </div>
          <DocumentoIaPanel
            doc={doc}
            expediente={expediente}
            iaOnline={iaOnline}
            onCambio={onRefresh}
            onOcupado={onOcupado}
            vista={vista}
            onVista={setVista}
            solicitudRatificar={solicitudRatificar}
            ratificacionEnEncabezado={Boolean(estado?.ratificable)}
            registroTecnico={
              <>
                <section className="ia-bloque" aria-label="Archivo original">
                  <p className="eyebrow">Archivo original</p>
                  <div className="inspector-custodia">
                    <p className="field-hint">El archivo tal como se custodió, verificado contra su huella.</p>
                    <DescargarOriginal doc={doc} />
                  </div>
                </section>
                <section className="ia-bloque" aria-label="Ficha de custodia">
                  <p className="eyebrow">Ficha de custodia</p>
                  <div className="inspector-custodia">
                    <p className="field-hint">Huellas, versiones, dictámenes y sellos de la bitácora del documento.</p>
                    <ExportarReporte ruta={`/reportes/documentos/${doc.id}/custodia`} compacto />
                  </div>
                </section>
                <section className="ia-apartado" aria-label="Datos del archivo">
                  <p className="eyebrow">Datos del archivo</p>
                  {children}
                </section>
              </>
            }
          />
        </div>
        {visorAbierto && <VisorDocumento doc={doc} busqueda={busqueda} onCerrar={() => alternarVisor(false)} />}
      </div>
    </EvidenciaContext.Provider>
  )
}

/** Descarga del original (RIE-03); si la huella no coincide, el core lo rechaza y el aviso lo explica. */
function DescargarOriginal({ doc }) {
  const toast = useToast()
  const [descargando, setDescargando] = useState(false)
  const descargar = async () => {
    setDescargando(true)
    try {
      toast.exito('Original descargado', await descargarOriginal(doc.id))
    } catch (err) {
      toast.error('No se pudo descargar el original', err.message)
    } finally {
      setDescargando(false)
    }
  }
  return (
    <Button compacto icono={DownloadSimple} cargando={descargando} onClick={descargar}>
      Descargar original
    </Button>
  )
}

/**
 * Detalle de un documento en un modal: metadatos de custodia, auditoría con IA,
 * visor de evidencia y navegación al documento anterior o siguiente de `lista`
 * (Alt+↑ / Alt+↓), bloqueada mientras una auditoría está en curso. Lo usan la
 * Bóveda y el detalle del expediente.
 */
export default function DetalleDocumentoModal({ documento, lista, expediente, iaOnline, onRefresh, onCambiar, onCerrar }) {
  const [visorAbierto, setVisorAbierto] = useState(false)
  const [auditando, setAuditando] = useState(false)
  // Último paso de la navegación (↑/↓): el documento nuevo entra desde ese lado.
  const [navegacion, setNavegacion] = useState(null)
  const posicion = lista.findIndex((d) => d.id === documento.id)

  const irA = useCallback(
    (paso) => {
      const siguiente = lista[posicion + paso]
      if (!siguiente || auditando) return
      setNavegacion({ id: siguiente.id, desde: paso > 0 ? 'abajo' : 'arriba' })
      onCambiar(siguiente)
    },
    [lista, posicion, auditando, onCambiar]
  )
  // Solo si el documento a la vista es el de esa navegación (no uno abierto desde la lista).
  const entrada = navegacion?.id === documento.id ? navegacion.desde : null

  useEffect(() => {
    const alPulsar = (e) => {
      if (!e.altKey || (e.key !== 'ArrowUp' && e.key !== 'ArrowDown')) return
      if (e.target.closest?.('input, textarea, select, [contenteditable="true"]')) return
      e.preventDefault()
      irA(e.key === 'ArrowUp' ? -1 : 1)
    }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [irA])

  const firma = firmaDeMime(documento.mime_type)
  const controlesNavegacion = posicion >= 0 && lista.length > 1 && (
    <div className="modal-nav" role="group" aria-label="Navegar entre documentos">
      <IconButton
        etiqueta="Documento anterior"
        compacto
        onClick={() => irA(-1)}
        disabled={posicion <= 0 || auditando}
        title={auditando ? 'Espera a que termine la auditoría' : 'Documento anterior (Alt+↑)'}
      >
        <CaretUp size={16} />
      </IconButton>
      <span className="tabular modal-nav-pos">
        {posicion + 1} / {lista.length}
      </span>
      <IconButton
        etiqueta="Documento siguiente"
        compacto
        onClick={() => irA(1)}
        disabled={posicion >= lista.length - 1 || auditando}
        title={auditando ? 'Espera a que termine la auditoría' : 'Documento siguiente (Alt+↓)'}
      >
        <CaretDown size={16} />
      </IconButton>
    </div>
  )

  return (
    <Modal
      size={visorAbierto ? 'xl' : 'lg'}
      title={documento.nombre_archivo_original}
      subtitle={`${expediente?.codigo_expediente || 'Sin expediente'} · ${expediente?.titular?.razon_social || 'Sin titular'}`}
      onClose={onCerrar}
      acciones={controlesNavegacion}
    >
      <InspectorDocumento
        key={documento.id}
        doc={documento}
        expediente={expediente}
        iaOnline={iaOnline}
        onRefresh={onRefresh}
        onVisor={setVisorAbierto}
        onOcupado={setAuditando}
        visorInicial={visorAbierto}
        entrada={entrada}
      >
        <KeyValueList className="inspect-grid">
          <Dato label="Huella SHA-256 · inmutable" ancho>
            <CopyChip valor={documento.hash_sha256} etiqueta="hash SHA-256" completo />
          </Dato>
          <Dato label="Titular asociado">
            <span className="cell-stack">
              <span>{expediente?.titular?.razon_social || 'Sin titular'}</span>
              <span className="cell-sub mono">{expediente?.titular?.rfc || '—'}</span>
            </span>
          </Dato>
          <Dato label="Tipo documental">{TIPO_DOCUMENTO_LABEL[documento.tipo_documento] || tipoCorto(documento.tipo_documento)}</Dato>
          <Dato label="Formato verificado">
            <span title={`Firma binaria del archivo: ${firma.firma}`}>{firma.label}</span>
          </Dato>
          <Dato label="Tamaño · Ingesta">
            <span className="mono">
              {formatBytes(documento.tamanio_bytes)} · {formatFecha(documento.creado_en)}
            </span>
          </Dato>
          <Dato label="Expediente">
            <span className="mono">{expediente?.codigo_expediente || '—'}</span>
          </Dato>
          <Dato label="Integridad">
            {documento.estado_integridad === 'ALTERADO' ? (
              <Badge tono="bad">Alterado · bloqueado</Badge>
            ) : (
              <Badge tono="ok">Íntegro al ingresar</Badge>
            )}
          </Dato>
          {documento.mime_type === 'application/pdf' && (
            <Dato label="Contenido activo" ancho>
              <SenalesArchivo documento={documento} />
            </Dato>
          )}
        </KeyValueList>
      </InspectorDocumento>
    </Modal>
  )
}
