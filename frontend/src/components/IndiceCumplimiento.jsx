import { ListChecks, Lock } from './iconos.js'
import { Badge } from './ui/index.js'
import { TIPO_DOCUMENTO_LABEL } from '../constants.js'
import { formatIndice } from '../utils/indice.js'

const RESULTADO = {
  CUMPLIDA: { tono: 'ok', label: 'Cumplida', plural: ['cumplida', 'cumplidas'] },
  INCUMPLIDA: { tono: 'bad', label: 'Incumplida', plural: ['incumplida', 'incumplidas'] },
  PENDIENTE: { tono: 'warn', label: 'Pendiente', plural: ['pendiente', 'pendientes'] },
}

// Unidades del índice que no son una regla del catálogo: no muestran código.
const SIN_CODIGO = new Set(['AUDITORIA', 'TITULARIDAD', 'NIVEL_1'])

/** Agrupa las reglas evaluadas por documento; las del expediente (RIE-01, RIE-02) van primero. */
function porDocumento(reglas) {
  const grupos = new Map()
  for (const r of reglas) {
    const clave = r.documento_id || 'expediente'
    if (!grupos.has(clave)) {
      const nombre = r.documento_id ? TIPO_DOCUMENTO_LABEL[r.tipo_documento] || r.tipo_documento : 'Expediente'
      grupos.set(clave, { nombre, reglas: [] })
    }
    grupos.get(clave).reglas.push(r)
  }
  return [...grupos.values()]
}

/**
 * Índice de cumplimiento del DOC-05 (C6, PRD §10.5) en el detalle del
 * expediente: reglas cumplidas entre reglas aplicables, con lo pendiente en
 * el denominador. La completitud (documentos obligatorios presentes) se
 * muestra al lado, con su nombre. El estado lo sigue comunicando el semáforo:
 * los segmentos de la barra llevan su conteo y su etiqueta.
 */
export default function IndiceCumplimiento({ indice, presentes, obligatorios }) {
  // Resumen para la columna lateral del detalle; la tabla de reglas evaluadas
  // vive en la columna principal (ReglasEvaluadas), donde cabe.
  if (!indice) return null
  const conteos = [
    ['CUMPLIDA', indice.cumplidas],
    ['INCUMPLIDA', indice.incumplidas],
    ['PENDIENTE', indice.pendientes],
  ]
  return (
    <section className="indice" aria-label="Índice de cumplimiento">
      <p className="eyebrow">Índice de cumplimiento</p>
      <div className="indice-cifra">
        <span className="indice-valor tabular">{formatIndice(indice.porcentaje)}</span>
        <span className="field-hint">
          {indice.aplicables === 0
            ? 'Sin reglas aplicables todavía.'
            : `${indice.cumplidas} de ${indice.aplicables} reglas cumplidas`}
        </span>
      </div>
      {indice.aplicables > 0 && (
        <>
          <span className="indice-barra" aria-hidden="true">
            {conteos.map(([resultado, n]) =>
              n > 0 ? (
                <span
                  key={resultado}
                  className={`indice-segmento indice-segmento--${RESULTADO[resultado].tono}`}
                  style={{ width: `${(n / indice.aplicables) * 100}%` }}
                />
              ) : null
            )}
          </span>
          <p className="indice-leyenda tabular">
            {conteos.map(([resultado, n]) => (
              <span key={resultado} className="indice-leyenda-item">
                <span className={`status-dot status-dot--${RESULTADO[resultado].tono}`} aria-hidden="true" />
                {n} {RESULTADO[resultado].plural[n === 1 ? 0 : 1]}
              </span>
            ))}
          </p>
        </>
      )}
      <p className="indice-obligatorios field-hint tabular">
        Documentos obligatorios presentes: {presentes} de {obligatorios}
      </p>
      {indice.bloqueado && (
        <div className="notice notice--bad indice-bloqueo">
          {/* Qué bloquea y qué hacer ya está en los motivos del semáforo: aquí solo se dice que bloquea. */}
          <p className="indice-bloqueo-titulo" title={indice.bloqueos.join(' ')}>
            <Lock size={12} aria-hidden="true" />
            <span>
              {indice.bloqueos.length === 1
                ? 'Bloqueado por una regla crítica'
                : `Bloqueado por ${indice.bloqueos.length} reglas críticas`}
              : el semáforo es No conforme sin importar el porcentaje. El detalle está en los motivos.
            </span>
          </p>
        </div>
      )}
    </section>
  )
}

/** Tabla de las reglas evaluadas por documento, plegada: la evidencia del índice. */
export function ReglasEvaluadas({ indice }) {
  if (!indice?.reglas?.length) return null
  return (
    <details className="indice-detalle">
          <summary className="desplegable-titulo">
            <ListChecks size={12} aria-hidden="true" />
            Reglas evaluadas para el índice
            <span className="tabular cell-muted"> · {indice.reglas.length}</span>
          </summary>
          <p className="field-hint">
            Cada regla vale lo mismo. Lo pendiente cuenta hasta que se audita o se ratifica; al auditar un documento
            pendiente se suman sus reglas de contenido, así que el índice puede bajar.
          </p>
          <table className="data-table data-table--inner indice-tabla">
            <colgroup>
              <col style={{ width: '58%' }} />
              <col style={{ width: '24%' }} />
              <col style={{ width: '18%' }} />
            </colgroup>
            <thead>
              <tr>
                <th>Evaluación</th>
                <th>Regla</th>
                <th className="col-right">Resultado</th>
              </tr>
            </thead>
            {porDocumento(indice.reglas).map((g) => (
              <tbody key={g.nombre}>
                <tr className="indice-grupo">
                  <th colSpan={3} scope="colgroup">
                    {g.nombre}
                  </th>
                </tr>
                {g.reglas.map((r, i) => (
                  <tr key={`${r.regla}-${i}`}>
                    <td>
                      {r.nombre}
                      {r.bloqueante && <span className="cell-sub cell-bad"> · bloquea</span>}
                    </td>
                    <td className="mono cell-mono cell-code">{SIN_CODIGO.has(r.regla) ? '—' : r.regla}</td>
                    <td className="col-right">
                      <Badge tono={RESULTADO[r.resultado]?.tono}>{RESULTADO[r.resultado]?.label || r.resultado}</Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            ))}
          </table>
    </details>
  )
}
