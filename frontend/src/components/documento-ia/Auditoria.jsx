// Flujo de la auditoría: etapas, dictamen, registro de auditoría y cotejo de representación.
import { useEffect, useState } from 'react'
import { Sparkles } from 'lucide-react'
import { Skeleton } from '../Skeleton.jsx'
import DictamenesGuardados, { AvisoIntegridad } from '../DictamenesGuardados.jsx'
import CotejoRepresentacion from '../CotejoRepresentacion.jsx'
import { Button } from '../ui/index.js'
import useToast from '../../hooks/useToast.js'
import { analizarDocumento, getVisorDocumento, prepararDocumento } from '../../services/api.js'
import { DictamenIa } from './Dictamen.jsx'
import { Stepper } from './Etapas.jsx'
import { ETAPAS_INICIALES, fallarEnCascada } from './etapas.js'
import { FUENTE_TEXTO, avisarFallo, cronometrar, detalleReglas, formatDuracion, nombreModelo } from './formato.js'

export function AuditoriaIa({ doc, expediente, iaOnline, onCambio, onOcupado }) {
  const toast = useToast()
  const [etapas, setEtapas] = useState(null)
  const [recarga, setRecarga] = useState(0)
  // La ratificación cambia el cotejo de representación (RN-05): se vuelve a consultar.
  const [ratificaciones, setRatificaciones] = useState(0)
  const [alterado, setAlterado] = useState(doc.estado_integridad === 'ALTERADO')
  const [dictamen, setDictamen] = useState(null)
  const [duracion, setDuracion] = useState(null)
  const rfcTitular = expediente?.titular?.rfc || null
  const analizando = Boolean(etapas) && Object.values(etapas).some((e) => e.estado === 'activo')

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
        toast.alerta('Dictamen no guardado', `El core-service no lo registró: ${resultado.persistencia.detalle}`)
      }
      setRecarga((n) => n + 1)
      onCambio?.()
    } catch (err) {
      marcar(fallarEnCascada(actual, err?.message || 'Error del ai-service'))
      if (err?.status === 409) {
        // RIE-03: el core-service bloqueó el documento y emitió su dictamen.
        setAlterado(true)
        setRecarga((n) => n + 1)
        onCambio?.()
        toast.error('Integridad comprometida', err.message)
      } else {
        avisarFallo(toast, err, 'No se pudo auditar el documento')
      }
    }
  }

  return (
    <div className="ai-view">
      <div className="ai-cta">
        <p className="ai-cta-desc">
          Clasifica el documento, coteja su titularidad, verifica la vigencia con las reglas del catálogo y localiza
          los elementos que el catálogo exige a su tipo. Al proveedor de IA solo viaja el texto extraído, nunca el
          archivo.
        </p>
        <Button
          variante={dictamen ? 'secondary' : 'primary'}
          icono={Sparkles}
          cargando={analizando}
          onClick={auditar}
          disabled={!iaOnline || alterado}
          title={alterado ? 'Documento bloqueado: el archivo cambió después de custodiarse' : iaOnline ? undefined : 'El servicio de análisis con IA no responde'}
        >
          {analizando ? 'Auditando…' : dictamen ? 'Volver a auditar' : 'Auditar documento'}
        </Button>
      </div>

      {!iaOnline && !dictamen && (
        <p className="field-hint">El ai-service (:8003) no responde; la auditoría no está disponible.</p>
      )}

      {etapas && <Stepper etapas={etapas} compacto={!analizando} />}

      {analizando && (
        <div className="ai-loading" aria-hidden="true">
          <Skeleton w="30%" h={24} />
          <Skeleton w="72%" />
          <Skeleton w="100%" h={3} r="var(--r-full)" />
          <Skeleton w="54%" />
        </div>
      )}

      {alterado && <AvisoIntegridad />}

      {!analizando && dictamen && (
        <DictamenIa dictamen={dictamen} expediente={expediente} tipoRegistrado={doc.tipo_documento} duracion={duracion} />
      )}

      <div className="registro-auditoria">
        <h5 className="section-title section-title--sm">Registro de auditoría</h5>
        <DictamenesGuardados
          doc={doc}
          recarga={recarga}
          onCambio={() => {
            setRatificaciones((n) => n + 1)
            onCambio?.()
          }}
        />
      </div>

      <CotejoRepresentacion doc={doc} recarga={recarga + ratificaciones} />
    </div>
  )
}

/* ── Chat ───────────────────────────────────────────────────────── */
