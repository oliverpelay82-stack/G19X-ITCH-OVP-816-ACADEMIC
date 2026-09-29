import { useState } from 'react'
import { Segmented } from './ui/index.js'
import { AuditoriaIa } from './documento-ia/Auditoria.jsx'
import { ChatDocumento } from './documento-ia/Chat.jsx'

const VISTAS = [
  { id: 'auditoria', label: 'Auditoría' },
  { id: 'chat', label: 'Chat' },
]

/**
 * Panel de inteligencia documental dentro del detalle de un documento:
 * dictamen (Niveles 2 a 4) y conversación en lenguaje natural contra el
 * ai-service (:8003), que a su vez consulta Groq Cloud.
 *
 * El padre debe montarlo con `key={doc.id}` para que el dictamen y el hilo
 * se reinicien al cambiar de documento.
 */
export default function DocumentoIaPanel({ doc, expediente, iaOnline = true, onCambio, onOcupado }) {
  const [vista, setVista] = useState('auditoria')

  return (
    <section className="ai-panel" aria-label="Análisis con inteligencia artificial">
      <header className="ai-panel-head">
        <div>
          <h4 className="section-title">Inteligencia documental</h4>
          <p className="section-desc">Clasificación y verificación del contenido con IA</p>
        </div>
        <Segmented role="tablist" label="Vista del panel de IA" valor={vista} onChange={setVista} opciones={VISTAS} />
      </header>

      {/* Ambas vistas permanecen montadas para no perder el dictamen ni el hilo al alternar. */}
      <div hidden={vista !== 'auditoria'}>
        <AuditoriaIa doc={doc} expediente={expediente} iaOnline={iaOnline} onCambio={onCambio} onOcupado={onOcupado} />
      </div>
      <div hidden={vista !== 'chat'}>
        <ChatDocumento doc={doc} iaOnline={iaOnline} />
      </div>
    </section>
  )
}
