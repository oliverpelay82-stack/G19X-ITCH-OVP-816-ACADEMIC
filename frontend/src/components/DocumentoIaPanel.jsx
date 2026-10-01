import { useState } from 'react'
import { Segmented } from './ui/index.js'
import { AuditoriaIa } from './documento-ia/Auditoria.jsx'
import { ChatDocumento } from './documento-ia/Chat.jsx'

const VISTAS = [
  { id: 'resultado', label: 'Resultado' },
  { id: 'evidencia', label: 'Evidencia' },
  { id: 'registro', label: 'Registro técnico' },
  { id: 'chat', label: 'Chat' },
]

/**
 * Panel de inteligencia documental dentro del detalle de un documento, en
 * secciones: resultado (auditar, veredicto, dictamen vigente y ratificación),
 * evidencia (cotejo, contenido, vigencia, sellos y observaciones), registro
 * técnico (lectura, modelo y los datos del archivo que pasa el modal en
 * `registroTecnico`) y chat.
 *
 * La sección puede controlarla el modal (`vista` y `onVista`: el encabezado
 * lleva a Resultado al pedir la ratificación); si no, el panel la guarda.
 * `ratificacionEnEncabezado` indica que el encabezado del modal ya ofrece
 * «Ratificar dictamen»: el dictamen vigente no repite el botón.
 * El padre debe montarlo con `key={doc.id}` para que el dictamen y el hilo
 * se reinicien al cambiar de documento.
 */
export default function DocumentoIaPanel({
  doc,
  expediente,
  iaOnline = true,
  onCambio,
  onOcupado,
  vista: vistaControlada,
  onVista,
  solicitudRatificar = 0,
  ratificacionEnEncabezado = false,
  registroTecnico = null,
}) {
  const [vistaPropia, setVistaPropia] = useState('resultado')
  // Ranura de la cabecera donde la auditoría pone «Volver a auditar» (portal).
  const [ranuraAccion, setRanuraAccion] = useState(null)
  const vista = vistaControlada ?? vistaPropia
  const setVista = onVista ?? setVistaPropia

  return (
    <section className="ai-panel" aria-label="Análisis con inteligencia artificial">
      <header className="ai-panel-head">
        <div>
          <h4 className="section-title">Inteligencia documental</h4>
          <p className="section-desc">Clasificación y verificación del contenido con IA</p>
        </div>
        <div className="ai-panel-acciones">
          <span ref={setRanuraAccion} className="ai-panel-ranura" />
          <Segmented role="tablist" label="Sección del panel de IA" valor={vista} onChange={setVista} opciones={VISTAS} />
        </div>
      </header>

      {/* Todas las secciones permanecen montadas para no perder el dictamen ni el hilo al alternar. */}
      <div hidden={vista === 'chat'}>
        <AuditoriaIa
          doc={doc}
          expediente={expediente}
          iaOnline={iaOnline}
          onCambio={onCambio}
          onOcupado={onOcupado}
          seccion={vista}
          solicitudRatificar={solicitudRatificar}
          ratificacionEnEncabezado={ratificacionEnEncabezado}
          ranuraAccion={ranuraAccion}
          onIrSeccion={setVista}
          registroTecnico={registroTecnico}
        />
      </div>
      <div hidden={vista !== 'chat'}>
        <ChatDocumento doc={doc} iaOnline={iaOnline} />
      </div>
    </section>
  )
}
