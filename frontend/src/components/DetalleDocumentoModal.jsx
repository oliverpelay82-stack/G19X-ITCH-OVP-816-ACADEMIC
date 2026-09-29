import { useCallback, useEffect, useMemo, useState } from 'react'
import { ChevronDown, ChevronUp, PanelRightClose, PanelRightOpen } from 'lucide-react'
import { Badge, Button, CopyChip, IconButton, KeyValue, KeyValueList, Modal } from './ui/index.js'
import DocumentoIaPanel from './DocumentoIaPanel.jsx'
import ExportarReporte from './ExportarReporte.jsx'
import VisorDocumento from './VisorDocumento.jsx'
import { EvidenciaContext } from './evidencia-context.js'
import { localizarCita } from '../services/api.js'
import { TIPO_DOCUMENTO_LABEL } from '../constants.js'
import { firmaDeMime, tipoCorto } from '../utils/documentos.js'
import { formatBytes, formatFecha } from '../utils/format.js'

function Dato({ label, children, ancho = false }) {
  return (
    <KeyValue etiqueta={label} className={ancho ? 'detail-item detail-item--full' : 'detail-item'}>
      {children}
    </KeyValue>
  )
}

/**
 * Metadatos, auditoría con IA y, a la derecha, el visor del documento
 * original. Un clic en una cita del dictamen o del chat abre el visor en la
 * página donde está y la resalta (HU-20). Se monta con `key={doc.id}` para
 * reiniciar el visor al cambiar de documento.
 */
function InspectorDocumento({ doc, expediente, iaOnline, onRefresh, onVisor, onOcupado, visorInicial, children }) {
  // Al pasar al documento siguiente el visor sigue abierto si lo estaba.
  const [visorAbierto, setVisorAbierto] = useState(Boolean(visorInicial) && iaOnline)
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
  // Zonas ya ubicadas por el Nivel 3 (sellos): no hay nada que buscar, solo resaltar.
  const mostrarZonas = useCallback(
    (pagina, recuadros) => {
      setVisorAbierto(true)
      onVisor(true)
      setBusqueda({
        clave: crypto.randomUUID(),
        tono: 'neutral',
        zonas: true,
        resultado: { encontrada: true, completa: true, aproximada: false, pagina, recuadros },
      })
    },
    [onVisor]
  )
  const contexto = useMemo(
    () => (iaOnline ? { mostrar, irAPagina, mostrarZonas } : null),
    [iaOnline, mostrar, irAPagina, mostrarZonas]
  )

  return (
    <EvidenciaContext.Provider value={contexto}>
      <div className={`inspector ${visorAbierto ? 'inspector--visor' : ''}`}>
        <div className="inspector-principal">
          {children}
          <div className="inspector-acciones">
            <Button
              compacto
              icono={visorAbierto ? PanelRightClose : PanelRightOpen}
              onClick={() => alternarVisor(!visorAbierto)}
              disabled={!iaOnline}
              title={iaOnline ? undefined : 'El visor lo sirve el ai-service (:8003), que no responde'}
            >
              {visorAbierto ? 'Ocultar documento' : 'Ver documento'}
            </Button>
            <span className="field-hint">Un clic en una cita del dictamen o del chat la resalta en el documento.</span>
          </div>
          <div className="inspector-acciones">
            <span className="field-hint">Ficha de custodia (huellas, versiones, dictámenes y sellos de la bitácora):</span>
            <ExportarReporte ruta={`/reportes/documentos/${doc.id}/custodia`} compacto />
          </div>
          <DocumentoIaPanel doc={doc} expediente={expediente} iaOnline={iaOnline} onCambio={onRefresh} onOcupado={onOcupado} />
        </div>
        {visorAbierto && <VisorDocumento doc={doc} busqueda={busqueda} onCerrar={() => alternarVisor(false)} />}
      </div>
    </EvidenciaContext.Provider>
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
  const posicion = lista.findIndex((d) => d.id === documento.id)

  const irA = useCallback(
    (paso) => {
      const siguiente = lista[posicion + paso]
      if (!siguiente || auditando) return
      onCambiar(siguiente)
    },
    [lista, posicion, auditando, onCambiar]
  )

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
  const navegacion = posicion >= 0 && lista.length > 1 && (
    <div className="modal-nav" role="group" aria-label="Navegar entre documentos">
      <IconButton
        etiqueta="Documento anterior"
        compacto
        onClick={() => irA(-1)}
        disabled={posicion <= 0 || auditando}
        title={auditando ? 'Espera a que termine la auditoría' : 'Documento anterior (Alt+↑)'}
      >
        <ChevronUp size={15} />
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
        <ChevronDown size={15} />
      </IconButton>
    </div>
  )

  return (
    <Modal
      size={visorAbierto ? 'xl' : 'lg'}
      title={documento.nombre_archivo_original}
      subtitle={`${expediente?.codigo_expediente || 'Sin expediente'} · ${expediente?.titular?.razon_social || 'Sin titular'}`}
      onClose={onCerrar}
      acciones={navegacion}
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
      >
        <KeyValueList className="inspect-grid">
          <Dato label="Huella SHA-256 · inmutable (RIE-03)" ancho>
            <CopyChip valor={documento.hash_sha256} etiqueta="hash SHA-256" completo />
          </Dato>
          <Dato label="Titular asociado">
            <span className="cell-stack">
              <span>{expediente?.titular?.razon_social || 'Sin titular'}</span>
              <span className="cell-sub mono">{expediente?.titular?.rfc || '—'}</span>
            </span>
          </Dato>
          <Dato label="Tipo documental">{TIPO_DOCUMENTO_LABEL[documento.tipo_documento] || tipoCorto(documento.tipo_documento)}</Dato>
          <Dato label="Firma binaria">
            <span className="mono">
              {firma.label} · {firma.firma}
            </span>
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
        </KeyValueList>
      </InspectorDocumento>
    </Modal>
  )
}
