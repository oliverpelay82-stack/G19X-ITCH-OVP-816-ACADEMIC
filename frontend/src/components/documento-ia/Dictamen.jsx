// Dictamen de la auditoría en tres vistas: resultado (veredicto y resumen), evidencia
// (cotejo, contenido, vigencia, sellos y observaciones) y datos técnicos de la lectura.
import { useEvidencia } from '../evidencia-context.js'
import { Badge, Card, KeyValue, KeyValueList } from '../ui/index.js'
import { TIPO_DOCUMENTO_LABEL } from '../../constants.js'
import { EstadoLectura, MetaInferencia } from './Lectura.jsx'
import {
  ESTATUS_IA,
  RESULTADO_CONTENIDO,
  RESULTADO_COTEJO,
  RESULTADO_VIGENCIA,
  TIPO_IA_LABEL,
  TITULARIDAD,
  diasRestantes,
  fechaIso,
  nombreModelo,
  numero,
  resultadoTipo,
  separarMotivo,
  vigenciaSegunReglas,
} from './formato.js'

/** Barra de confianza de 3 px con el porcentaje y la banda a la que pertenece. */
function Confianza({ dictamen }) {
  const valor = dictamen.nivel_confianza || 0
  const conforme = dictamen.umbral_confianza_conforme ?? 0.85
  const hitl = dictamen.umbral_confianza_hitl ?? 0.7
  const tono = valor >= conforme ? 'ok' : valor >= hitl ? 'warn' : 'bad'
  return (
    <div className="confidence">
      <div className="confidence-head">
        <span className="eyebrow">Confianza</span>
        <span className={`confidence-value confidence-value--${tono} tabular`}>{Math.round(valor * 100)}%</span>
      </div>
      <span className="confidence-bar" aria-hidden="true">
        <span className={`confidence-fill confidence-fill--${tono}`} style={{ width: `${valor * 100}%` }} />
        <span className="confidence-mark" style={{ left: `${conforme * 100}%` }} />
      </span>
      <span className="confidence-foot">Conforme desde {Math.round(conforme * 100)}%</span>
    </div>
  )
}

/**
 * Tabla de cotejo documental: lo que registra el expediente frente a lo que
 * extrajo el modelo, con el resultado que calculó el dictamen determinista.
 * La titularidad se acredita con el RFC o, si el documento no lo incluye,
 * con la razón social; un documento sin ninguno de los dos pasa a revisión.
 */
function Cotejo({ dictamen, expediente, tipoRegistrado }) {
  const rfcTitular = expediente?.titular?.rfc || null
  const titularidad = dictamen.titularidad
  const filas = [
    {
      campo: 'RFC',
      esperado: rfcTitular,
      detectado: dictamen.rfc_detectado,
      mono: true,
      // Sin RFC en el documento no hay rechazo: la titularidad se busca por razón social.
      resultado: !rfcTitular ? 'na' : !dictamen.rfc_detectado ? 'ausente' : dictamen.match_titular ? 'ok' : 'bad',
      nota: dictamen.rfc_detectado && !dictamen.rfc_estructura_valida ? 'Estructura SAT inválida' : null,
    },
    {
      campo: 'Razón social',
      esperado: expediente?.titular?.razon_social,
      detectado: dictamen.razon_social_detectada,
      resultado: titularidad === 'RAZON_SOCIAL' ? 'ok' : titularidad === 'NO_LOCALIZADA' ? 'bad' : 'info',
      nota: titularidad === 'RAZON_SOCIAL' ? 'Acredita la titularidad' : null,
    },
    {
      campo: 'Tipo documental',
      esperado: TIPO_DOCUMENTO_LABEL[tipoRegistrado] || tipoRegistrado,
      detectado: TIPO_IA_LABEL[dictamen.tipo_documento_detectado] || TIPO_IA_LABEL.OTRO,
      resultado: resultadoTipo(dictamen, tipoRegistrado),
    },
  ]
  return (
    <Card className="table-card table-card--flat">
      <table className="data-table data-table--inner cotejo">
        <colgroup>
          <col style={{ width: '18%' }} />
          <col />
          <col />
          {/* Ancho fijo: la etiqueta del resultado nunca se recorta, ni con el visor abierto. */}
          <col style={{ width: '132px' }} />
        </colgroup>
        <thead>
          <tr>
            <th>Campo</th>
            <th>Esperado · expediente</th>
            <th>Detectado · documento</th>
            <th className="col-right">Resultado</th>
          </tr>
        </thead>
        <tbody>
          {filas.map((f) => {
            const r = RESULTADO_COTEJO[f.resultado]
            return (
              <tr key={f.campo}>
                <td className="cell-muted">{f.campo}</td>
                <td className={f.mono ? 'mono cell-mono' : ''}>{f.esperado || <span className="cell-muted">—</span>}</td>
                <td className={f.mono ? 'mono cell-mono' : ''}>
                  {f.detectado || <span className="cell-muted">No localizado</span>}
                  {f.nota && <span className={`cell-sub ${f.resultado === 'ok' ? '' : 'cell-bad'}`}>{f.nota}</span>}
                </td>
                <td className="col-right">
                  <Badge tono={r.tono}>{r.label}</Badge>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}

/**
 * Elementos que el catálogo exige al tipo de documento (reglas RSC/RDS) con su
 * resultado: la cita literal que lo sustenta si se localizó, o la
 * recomendación del catálogo si falta. Una omisión no rechaza el documento:
 * lo deja en revisión para el analista (RSC-01).
 */
function VerificacionContenido({ verificaciones }) {
  const evidencia = useEvidencia()
  if (!verificaciones?.length) return null
  const pendientes = verificaciones.filter((v) => v.resultado !== 'CUMPLE').length
  return (
    <div className="contenido">
      <div className="contenido-head">
        <p className="eyebrow">Verificación de contenido</p>
        <span className="cell-muted tabular">
          {verificaciones.length - pendientes} de {verificaciones.length} localizados
        </span>
      </div>
      <Card className="table-card table-card--flat">
        <table className="data-table data-table--inner contenido-tabla">
          <colgroup>
            <col style={{ width: '30%' }} />
            <col />
            <col style={{ width: '132px' }} />
          </colgroup>
          <thead>
            <tr>
              <th>Elemento · regla</th>
              <th>Evidencia o recomendación</th>
              <th className="col-right">Resultado</th>
            </tr>
          </thead>
          <tbody>
            {verificaciones.map((v) => {
              const r = RESULTADO_CONTENIDO[v.resultado] || RESULTADO_CONTENIDO.NO_VERIFICABLE
              return (
                <tr key={v.codigo_regla}>
                  <td>
                    {v.nombre_regla || v.codigo_regla}
                    <span className="cell-sub mono">{v.codigo_regla}</span>
                  </td>
                  <td>
                    {v.resultado === 'CUMPLE' && v.cita ? (
                      evidencia ? (
                        <button
                          type="button"
                          className="cita-enlace contenido-cita"
                          onClick={() => evidencia.mostrar({ cita: v.cita, tono: 'ok' })}
                          title="Ver la cita resaltada en el documento"
                        >
                          <q>{v.cita}</q>
                        </button>
                      ) : (
                        <q className="contenido-cita">{v.cita}</q>
                      )
                    ) : (
                      <>
                        {v.observacion && <span className="cell-muted">{v.observacion} </span>}
                        {v.recomendacion && <span className="contenido-recomendacion">{v.recomendacion}</span>}
                      </>
                    )}
                  </td>
                  <td className="col-right">
                    <Badge tono={r.tono}>{r.label}</Badge>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </Card>
    </div>
  )
}

/** Sello Digital SAT detectado en el texto (DOC-08): evidencia informativa. */
function SelloDigitalSat() {
  return (
    <div className="sellos">
      <p className="eyebrow">Sellos</p>
      <div className="sellos-fila">
        <Badge>Sello Digital SAT</Badge>
      </div>
    </div>
  )
}

/**
 * Franja de resumen del dictamen: cada aspecto con su resultado y un clic que
 * lleva a su sección. Solo resume datos que el dictamen ya trae.
 */
function ResumenDictamen({ dictamen, vigencia, ids, onIr }) {
  const verificaciones = dictamen.verificaciones || []
  const localizados = verificaciones.filter((v) => v.resultado === 'CUMPLE').length
  const titularidad = TITULARIDAD[dictamen.titularidad]
  const puntos = [
    titularidad && { etiqueta: 'Titularidad', ...titularidad, destino: ids.cotejo },
    {
      etiqueta: 'Tipo',
      tono: dictamen.tipo_coincide === true ? 'ok' : dictamen.tipo_coincide === false ? 'bad' : 'neutral',
      texto: dictamen.tipo_coincide === true ? 'Coincide' : dictamen.tipo_coincide === false ? 'Distinto' : 'Sin contraste',
      destino: ids.cotejo,
    },
    { etiqueta: 'Vigencia', tono: vigencia.tono, texto: vigencia.texto, destino: ids.fechas },
    verificaciones.length > 0 && {
      etiqueta: 'Contenido',
      tono: localizados === verificaciones.length ? 'ok' : 'warn',
      texto: `${localizados} de ${verificaciones.length}`,
      destino: ids.contenido,
    },
  ].filter(Boolean)
  return (
    <nav className="resumen-dictamen" aria-label="Resumen del dictamen">
      {puntos.map((p) => (
        <button key={p.etiqueta} type="button" className="resumen-punto" onClick={() => onIr?.(p.destino)}>
          <span className="resumen-etiqueta">{p.etiqueta}</span>
          <span className={`resumen-valor resumen-valor--${p.tono}`}>
            <span className={`status-dot status-dot--${p.tono}`} aria-hidden="true" />
            {p.texto}
          </span>
        </button>
      ))}
    </nav>
  )
}

/** Recomendaciones del motor como pasos a seguir (las mismas que acompañan a cada elemento pendiente). */
function AccionesRecomendadas({ recomendaciones = [] }) {
  const unicas = [...new Set(recomendaciones.filter(Boolean))]
  if (!unicas.length) return null
  return (
    <div className="acciones">
      <p className="eyebrow">Acciones recomendadas</p>
      <ol>
        {unicas.map((r) => (
          <li key={r}>{r}</li>
        ))}
      </ol>
    </div>
  )
}

/* ── Dictamen ───────────────────────────────────────────────────── */

/** Vigencia del dictamen en texto y tono; la comparten el resultado y la evidencia. */
function vigenciaDe(dictamen) {
  const dias = diasRestantes(dictamen)
  const textoVencimiento =
    dias === null
      ? 'Sin fecha de vencimiento'
      : dias < 0
        ? `Vencido hace ${numero(Math.abs(dias))} ${Math.abs(dias) === 1 ? 'día' : 'días'}`
        : dias === 0
          ? 'Vence hoy'
          : `${numero(dias)} ${dias === 1 ? 'día restante' : 'días restantes'}`
  const segunReglas = vigenciaSegunReglas(dictamen.vigencia_nivel_2, textoVencimiento)
  const tono = segunReglas?.tono ?? (dias === null ? 'neutral' : dias < 0 ? 'bad' : dias <= 30 ? 'warn' : 'ok')
  const corta =
    RESULTADO_VIGENCIA[dictamen.vigencia_nivel_2?.resultado]?.label ?? (dias === null ? 'sin vencimiento' : textoVencimiento)
  return { dias, tono, texto: segunReglas?.texto ?? textoVencimiento, corta: corta.charAt(0).toUpperCase() + corta.slice(1) }
}

/** Bloque delimitado de la evidencia; sin `titulo` cuando el contenido trae el suyo. */
function Bloque({ id, titulo, etiqueta, children }) {
  return (
    <section id={id} className="ia-bloque ancla" aria-label={titulo || etiqueta}>
      {titulo && <p className="eyebrow">{titulo}</p>}
      {children}
    </section>
  )
}

/**
 * Resultado de la auditoría recién hecha: la franja de resumen (cada punto
 * lleva a su evidencia), el veredicto con la confianza y las acciones
 * recomendadas. `onIrEvidencia(id)` cambia a la sección de evidencia.
 */
export function DictamenResultado({ dictamen, ids, onIrEvidencia }) {
  const estatus = ESTATUS_IA[dictamen.estatus_preliminar] || {
    tono: 'neutral',
    label: dictamen.estatus_preliminar || 'Sin dictamen',
  }
  const { motivo } = separarMotivo(dictamen.observaciones)
  const vigencia = vigenciaDe(dictamen)
  return (
    <div className="dictamen">
      <div className={`verdict verdict--${estatus.tono}`}>
        <div className="verdict-main">
          <p className="eyebrow">Resultado de la auditoría</p>
          <p className="verdict-word">{estatus.label}</p>
          {motivo && <p className="verdict-reason">{motivo}</p>}
          <p className={`vigencia-line vigencia-line--${vigencia.tono}`}>
            <span className={`status-dot status-dot--${vigencia.tono}`} aria-hidden="true" />
            <span className="tabular">{vigencia.texto}</span>
          </p>
          {dictamen.requiere_revision_humana && (
            <div className="badge-row">
              <Badge tono="warn">Requiere revisión de un analista</Badge>
            </div>
          )}
        </div>
        <Confianza dictamen={dictamen} />
      </div>

      <ResumenDictamen dictamen={dictamen} vigencia={{ tono: vigencia.tono, texto: vigencia.corta }} ids={ids} onIr={onIrEvidencia} />

      <AccionesRecomendadas recomendaciones={dictamen.recomendaciones} />
    </div>
  )
}

/**
 * Evidencia de la auditoría en bloques delimitados: titularidad y tipo,
 * contenido exigido, vigencia, sellos y observaciones.
 */
export function DictamenEvidencia({ dictamen, expediente, tipoRegistrado, ids }) {
  const { resto } = separarMotivo(dictamen.observaciones)
  const vigencia = vigenciaDe(dictamen)
  return (
    <div className="dictamen dictamen--evidencia">
      <Bloque id={ids.cotejo} titulo="Titularidad y tipo documental">
        <Cotejo dictamen={dictamen} expediente={expediente} tipoRegistrado={tipoRegistrado} />
      </Bloque>

      {(dictamen.verificaciones || []).length > 0 && (
        <Bloque id={ids.contenido} etiqueta="Contenido que exige el catálogo">
          <VerificacionContenido verificaciones={dictamen.verificaciones} />
        </Bloque>
      )}

      <Bloque id={ids.fechas} titulo="Vigencia">
        <KeyValueList className="detail-grid detail-grid--3">
          <KeyValue etiqueta="Emisión" className="detail-item" valorClassName="mono">
            {fechaIso(dictamen.fecha_emision)}
          </KeyValue>
          <KeyValue etiqueta="Vencimiento" className="detail-item" valorClassName="mono">
            {fechaIso(dictamen.fecha_vencimiento)}
          </KeyValue>
          <KeyValue etiqueta="Días para el vencimiento" className="detail-item" valorClassName="mono">
            {vigencia.dias === null ? '—' : numero(vigencia.dias)}
          </KeyValue>
        </KeyValueList>
      </Bloque>

      {dictamen.sello_digital_sat && (
        <Bloque id={ids.sellos} etiqueta="Sellos">
          <SelloDigitalSat />
        </Bloque>
      )}

      {resto.length > 0 && (
        <Bloque titulo="Observaciones">
          <ul className="observaciones-lista">
            {resto.map((obs, i) => (
              <li key={i} className="observacion">
                {obs}
              </li>
            ))}
          </ul>
        </Bloque>
      )}
    </div>
  )
}

/** Datos técnicos de la auditoría: cómo se leyó el documento y qué modelo respondió. */
export function DictamenTecnico({ dictamen, duracion }) {
  return (
    <div className="ia-bloque">
      <p className="eyebrow">Lectura y análisis</p>
      <EstadoLectura lectura={dictamen.extraccion_nivel_3} contexto={dictamen.contexto_llm} />
      <p className="verdict-foot">
        <MetaInferencia modelo={dictamen.modelo_utilizado} duracion={duracion} />
        <span>{nombreModelo(dictamen.modelo_utilizado)} · temperatura 0.0</span>
      </p>
      {/* Con qué lectura e instrucciones se emitió el dictamen, para reproducirlo (protocolo del DOC-05). */}
      {dictamen.versiones && (
        <p className="verdict-foot">
          <span>
            Lectura <span className="mono">{dictamen.versiones.version_lectura}</span>
          </span>
          <span>
            Instrucciones <span className="mono">{dictamen.versiones.version_instrucciones}</span>
          </span>
          {dictamen.versiones.version_catalogo && (
            <span>
              Catálogo <span className="mono">{dictamen.versiones.version_catalogo}</span>
            </span>
          )}
        </p>
      )}
    </div>
  )
}
