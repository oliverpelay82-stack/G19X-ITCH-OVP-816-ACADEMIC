import { FileText, Fingerprint, ListChecks, SealCheck, Sparkle, TrafficSignal } from '../iconos.js'

/** Las tres capacidades del motor, con lo que de verdad hace (PRD §10 y §21.3). */
const CAPACIDADES = [
  {
    icono: Fingerprint,
    titulo: 'Criptografía y trazabilidad',
    texto: 'Huella SHA-256 de cada archivo y bitácora sellada en cadena: cualquier alteración se detecta.',
  },
  {
    icono: Sparkle,
    titulo: 'Auditoría con IA',
    texto: 'OCR y extracción semántica con la cita exacta del documento; la decisión final es de una persona.',
    viva: true,
  },
  {
    icono: TrafficSignal,
    titulo: 'Semáforo determinista',
    texto: 'Vigencia, completitud y reglas del catálogo evaluadas en cada consulta, sin depender de la IA.',
  },
]

/** Etapas del dictamen. Las dos últimas, donde el motor decide, van destacadas. */
const ETAPAS = [
  { icono: FileText, etiqueta: 'Documento' },
  { icono: Fingerprint, etiqueta: 'Huella' },
  { icono: ListChecks, etiqueta: 'Reglas' },
  { icono: Sparkle, etiqueta: 'IA', activa: true },
  { icono: SealCheck, etiqueta: 'Dictamen', activa: true },
]

/**
 * Vitrina de la pantalla de acceso (pantallas anchas): qué es el motor, el
 * recorrido de un documento hasta su dictamen con un pulso que avanza por la
 * pista, y sus tres capacidades en tarjetas que entran escalonadas. La de IA
 * lleva un pulso en el borde que denota actividad. Los iconos van en squircles
 * tonales; los pasos destacados, en peso duotone, como el estado activo del
 * menú. Solo CSS sobre transform y opacity; «reducir movimiento» lo detiene.
 */
export default function Vitrina() {
  return (
    <aside className="acceso-vitrina" aria-label="Motor de Validación de Cumplimiento Documental">
      <p className="vitrina-eyebrow">PluriOne · Motor de Cumplimiento</p>
      <h2 className="vitrina-titulo">Validación documental inteligente y auditable</h2>
      <p className="vitrina-sub">
        Reglas deterministas, una IA que solo extrae y cita su evidencia, y la decisión de una persona: cada paso queda
        en una bitácora que no se puede alterar.
      </p>

      <div className="vitrina-flujo" aria-hidden="true">
        <span className="flujo-pista">
          <span className="flujo-pulso" />
        </span>
        {ETAPAS.map(({ icono: Icono, etiqueta, activa }, i) => (
          <span key={etiqueta} className={activa ? 'flujo-etapa is-activa' : 'flujo-etapa'} style={{ '--i': i }}>
            <span className="flujo-nodo">
              <Icono size={16} weight={activa ? 'duotone' : 'regular'} />
            </span>
            <span className="flujo-etiqueta">{etiqueta}</span>
          </span>
        ))}
      </div>

      <ul className="vitrina-capacidades">
        {CAPACIDADES.map(({ icono: Icono, titulo, texto, viva }, i) => (
          <li key={titulo} className={viva ? 'capacidad capacidad--viva' : 'capacidad'} style={{ '--i': i }}>
            <span className="capacidad-icono" aria-hidden="true">
              <Icono size={16} weight={viva ? 'duotone' : 'regular'} />
            </span>
            <div className="capacidad-cuerpo">
              <p className="capacidad-titulo">
                {titulo}
                {viva && (
                  <span className="capacidad-vivo">
                    <span className="capacidad-vivo-punto" aria-hidden="true" />
                    Activa
                  </span>
                )}
              </p>
              <p className="capacidad-texto">{texto}</p>
            </div>
          </li>
        ))}
      </ul>
    </aside>
  )
}
