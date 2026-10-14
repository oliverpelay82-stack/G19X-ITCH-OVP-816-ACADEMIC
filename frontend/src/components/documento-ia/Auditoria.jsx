// Flujo de la auditoría repartido en secciones: resultado (auditar, veredicto, dictamen vigente
// con su ratificación y cotejo de representación), evidencia y registro técnico.
import { useEffect, useId, useState } from 'react'
import { createPortal } from 'react-dom'
import { FileMagnifyingGlass, Sparkle } from '../iconos.js'
import { Skeleton } from '../Skeleton.jsx'
import DictamenesGuardados, { AvisoIntegridad } from '../DictamenesGuardados.jsx'
import CotejoRepresentacion from '../CotejoRepresentacion.jsx'
import { Button, EmptyState } from '../ui/index.js'
import useToast from '../../hooks/useToast.js'
import { analizarDocumento, getVisorDocumento, prepararDocumento } from '../../services/api.js'
import { DictamenEvidencia, DictamenResultado, DictamenTecnico } from './Dictamen.jsx'
import { Stepper } from './Etapas.jsx'
import { ETAPAS_INICIALES, fallarEnCascada } from './etapas.js'
import { FUENTE_TEXTO, avisarFallo, cronometrar, detalleReglas, formatDuracion, nombreModelo } from './formato.js'

/**
 * `seccion` decide qué parte se ve ('resultado', 'evidencia' o 'registro');
 * las tres quedan montadas para no perder el dictamen ni la ratificación al
 * alternar. `solicitudRatificar` (un contador) abre la ratificación desde el
 * encabezado del modal; `onIrSeccion` cambia de sección (del resumen a la
 * evidencia) y `registroTecnico` son los datos del archivo que pone el modal.
 */
export function AuditoriaIa({
  doc,
  expediente,
  iaOnline,
  onCambio,
  onOcupado,
  seccion = 'resultado',
  solicitudRatificar = 0,
  ratificacionEnEncabezado = false,
  ranuraAccion = null,
  onIrSeccion,
  registroTecnico = null,
}) {
  const toast = useToast()
  const base = useId()
  const ids = { cotejo: `${base}-cotejo`, contenido: `${base}-contenido`, sellos: `${base}-sellos`, fechas: `${base}-fechas` }
  // Del resumen a su evidencia: se cambia de sección y, ya visible, se desplaza al bloque.
  const irEvidencia = (id) => {
    onIrSeccion?.('evidencia')
    requestAnimationFrame(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' }))
  }
  const [etapas, setEtapas] = useState(null)
  const [recarga, setRecarga] = useState(0)
  // La ratificación cambia el cotejo de representación (RN-05): se vuelve a consultar.
  const [ratificaciones, setRatificaciones] = useState(0)
  const [alterado, setAlterado] = useState(doc.estado_integridad === 'ALTERADO')
  const [dictamen, setDictamen] = useState(null)
  const [duracion, setDuracion] = useState(null)
  const rfcTitular = expediente?.titular?.rfc || null
  const analizando = Boolean(etapas) && Object.values(etapas).some((e) => e.estado === 'activo')
  // La explicación de qué hace la auditoría solo se lee antes de la primera: con un
  // dictamen (de esta sesión o ya guardado) el botón queda solo.
  const estadoEnExpediente = expediente?.evaluacion?.documentos?.find((d) => d.documento_id === doc.id)?.estado
  const auditado = Boolean(dictamen) || Boolean(estadoEnExpediente && estadoEnExpediente !== 'SIN_DICTAMEN')

  // El modal bloquea el cambio de documento mientras la auditoría está en curso.
  useEffect(() => {
    onOcupado?.(analizando)
  }, [analizando, onOcupado])

  const marcar = (cambios) => setEtapas((prev) => ({ ...prev, ...cambios }))

  const auditar = async () => {
    const inicio = performance.now()
    let actual = 'lectura'
    setEtapas({ ...ETAPAS_INICIALES, lectura: { estado: 'activo', detalle: 'Resolviendo el texto del documento…' } })
    // La auditoría lee todas las páginas: se anuncia cuántas y cuántas van por
    // OCR, para que una lectura larga no parezca detenida. Es solo informativo.
    getVisorDocumento(doc.id)
      .then((info) => {
        const escaneadas = (info?.paginas || []).filter((p) => p.metodo === 'OCR').length
        const detalle = escaneadas
          ? `Leyendo ${info.total_paginas} págs. · ${escaneadas} por OCR (la primera vez tarda)…`
          : `Leyendo ${info.total_paginas} págs. de capa de texto…`
        setEtapas((prev) => (prev?.lectura?.estado === 'activo' ? { ...prev, lectura: { estado: 'activo', detalle } } : prev))
      })
      .catch(() => {})
    try {
      // Etapa 1: el texto queda resuelto (memoria, disco u OCR) antes de llamar al modelo.
      const { resultado: prep, duracion: msLectura } = await cronometrar(() => prepararDocumento(doc.id))
      const n3 = prep?.extraccion_nivel_3 || {}
      actual = 'analisis'
      marcar({
        lectura: {
          estado: 'hecho',
          detalle: [
            n3.metodo_extraccion,
            n3.total_paginas && `${n3.total_paginas - (n3.paginas_omitidas_ocr || 0)} de ${n3.total_paginas} págs.`,
            FUENTE_TEXTO[prep?.fuente_texto],
            formatDuracion(msLectura),
          ]
            .filter(Boolean)
            .join(' · '),
        },
        analisis: { estado: 'activo', detalle: 'Extrayendo datos con IA…' },
        reglas: { estado: 'espera', detalle: 'Espera las fechas extraídas' },
      })

      // Etapas 2 y 3: el análisis reutiliza ese texto y el servicio consulta las reglas RCV.
      const resultado = await analizarDocumento({
        documento_id: doc.id,
        rfc_titular: rfcTitular || undefined,
        razon_social_titular: expediente?.titular?.razon_social || undefined,
      })
      marcar({
        analisis: {
          estado: 'hecho',
          detalle: `${nombreModelo(resultado?.modelo_utilizado)} · ${formatDuracion(resultado?.tiempos_ms?.inferencia)}`,
        },
        reglas: detalleReglas(resultado?.vigencia_nivel_2),
      })
      setDictamen(resultado)
      setDuracion(performance.now() - inicio)
      // El éxito ya se ve en el stepper y en el veredicto; un aviso flotante lo
      // repetía y tapaba el visor. Solo se avisa lo que no se ve en pantalla.
      if (resultado?.persistencia?.guardado === false) {
        toast.alerta('Dictamen no guardado', `El sistema no lo registró: ${resultado.persistencia.detalle}`)
      }
      setRecarga((n) => n + 1)
      onCambio?.()
    } catch (err) {
      marcar(fallarEnCascada(actual, err?.message || 'Error del servicio de análisis con IA'))
      if (err?.status === 409) {
        // RIE-03: el core-service bloqueó el documento y emitió su dictamen.
        setAlterado(true)
        setRecarga((n) => n + 1)
        onCambio?.()
        toast.error('Integridad comprometida', err.message)
      } else {
        // P5: con la IA sin responder, la auditoría queda diferida y el expediente
        // muestra su alerta; se refresca para verla de inmediato.
        if (err?.status === 503) onCambio?.()
        avisarFallo(toast, err, 'No se pudo auditar el documento')
      }
    }
  }

  const botonAuditar = (
    <Button
      variante={auditado ? 'secondary' : 'primary'}
      compacto={auditado}
      icono={Sparkle}
      cargando={analizando}
      onClick={auditar}
      disabled={!iaOnline || alterado}
      title={alterado ? 'Documento bloqueado: el archivo cambió después de custodiarse' : iaOnline ? undefined : 'El servicio de análisis con IA no responde'}
    >
      {analizando ? 'Auditando…' : auditado ? 'Volver a auditar' : 'Auditar documento'}
    </Button>
  )

  return (
    <div className="ai-view">
      {/* ── Resultado ── */}
      <div className="ai-seccion" hidden={seccion !== 'resultado'}>
        {/* Sin dictamen, la auditoría se explica y su botón es la acción principal.
            Con dictamen, auditar de nuevo es secundario y va junto a las pestañas
            (ranura de la cabecera del panel): no ocupa un renglón ni compite con
            «Ratificar dictamen». Solo en la sección Resultado, donde se ve el avance. */}
        {auditado ? (
          ranuraAccion && seccion === 'resultado' && createPortal(botonAuditar, ranuraAccion)
        ) : (
          <div className="ai-cta">
            <p className="ai-cta-desc">
              Clasifica el documento, coteja su titularidad, verifica su vigencia y localiza lo que el catálogo exige a
              su tipo. Al proveedor de IA solo viaja el texto extraído, nunca el archivo.
            </p>
            {botonAuditar}
          </div>
        )}

        {!iaOnline && !dictamen && (
          <p className="field-hint">El servicio de análisis con IA no responde; la auditoría no está disponible.</p>
        )}

        {etapas && <Stepper etapas={etapas} compacto={!analizando} />}

        {analizando && (
          <div className="ia-bloque" aria-hidden="true">
            <Skeleton w="30%" h={24} />
            <Skeleton w="72%" />
            <Skeleton w="100%" h={3} r="var(--r-full)" />
            <Skeleton w="54%" />
          </div>
        )}

        {alterado && <AvisoIntegridad />}

        {!analizando && dictamen && <DictamenResultado dictamen={dictamen} ids={ids} onIrEvidencia={irEvidencia} />}

        <section className="ia-apartado" aria-label="Dictamen vigente">
          <p className="eyebrow">Dictamen vigente</p>
          <DictamenesGuardados
            doc={doc}
            recarga={recarga}
            dictamenSesionId={dictamen?.persistencia?.dictamen?.id}
            ratificacionEnEncabezado={ratificacionEnEncabezado}
            solicitudRatificar={solicitudRatificar}
            onCambio={() => {
              setRatificaciones((n) => n + 1)
              onCambio?.()
            }}
          />
        </section>

        <CotejoRepresentacion doc={doc} recarga={recarga + ratificaciones} />
      </div>

      {/* ── Evidencia ── */}
      <div className="ai-seccion" hidden={seccion !== 'evidencia'}>
        {dictamen ? (
          <DictamenEvidencia dictamen={dictamen} expediente={expediente} tipoRegistrado={doc.tipo_documento} ids={ids} />
        ) : (
          <EmptyState
            icon={FileMagnifyingGlass}
            titulo="Sin evidencia de esta sesión"
            descripcion="La evidencia detallada (cotejo, contenido con sus citas, vigencia, sellos y observaciones) se muestra al auditar el documento. El dictamen vigente conserva el resultado de cada regla."
          />
        )}
      </div>

      {/* ── Registro técnico ── */}
      <div className="ai-seccion" hidden={seccion !== 'registro'}>
        {dictamen && <DictamenTecnico dictamen={dictamen} duracion={duracion} />}
        {registroTecnico}
      </div>
    </div>
  )
}
