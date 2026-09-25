import { useEffect, useState } from 'react'
import { History, Loader2, ShieldAlert, UserCheck } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import { Segmented } from './ui.jsx'
import useToast from '../hooks/useToast.js'
import { getDictamenes, ratificarDictamen } from '../services/api.js'
import { formatFecha, formatRelativo, hashCorto } from '../utils/format.js'

const ESTATUS = {
  CONFORME: { tono: 'ok', label: 'Conforme' },
  EN_REVISION: { tono: 'warn', label: 'En revisión' },
  NO_CONFORME: { tono: 'bad', label: 'No conforme' },
}

const RESULTADO_REGLA = {
  CUMPLE: 'ok',
  VIGENTE: 'ok',
  PROXIMO_A_VENCER: 'warn',
  INDETERMINADO: 'warn',
  NO_APLICA: 'neutral',
  VENCIDO: 'bad',
  NO_CUMPLE: 'bad',
}

const VIGENCIA = {
  VIGENTE: 'Vigente',
  PROXIMO_A_VENCER: 'Próximo a vencer',
  VENCIDO: 'Vencido',
  INDETERMINADO: 'No verificable',
  SIN_REGLAS: 'Sin reglas aplicables',
  NO_VERIFICADA: 'No verificada',
}

const DECISIONES = [
  { id: 'CONFORME', label: 'Conforme', tono: 'ok' },
  { id: 'NO_CONFORME', label: 'No conforme', tono: 'bad' },
]

const MIN_JUSTIFICACION = 10

const meta = (estatus) => ESTATUS[estatus] || { tono: 'neutral', label: estatus || 'Sin estatus' }
const pct = (n) => (n === null || n === undefined ? '—' : `${Math.round(n * 100)}%`)

/** Marca de tiempo relativa, con la fecha absoluta en el tooltip. */
function Momento({ valor }) {
  return (
    <time className="tabular" dateTime={valor} title={formatFecha(valor)}>
      {formatRelativo(valor)}
    </time>
  )
}

function EstatusBadge({ estatus }) {
  const m = meta(estatus)
  return (
    <span className={`badge badge--${m.tono}`}>
      <span className={`status-dot status-dot--${m.tono}`} aria-hidden="true" />
      {m.label}
    </span>
  )
}

/** Panel del Nivel 5: la decisión del analista y su justificación (RN-05). */
function FormularioRatificacion({ dictamen, onRatificado, onCancelar }) {
  const toast = useToast()
  const [decision, setDecision] = useState('CONFORME')
  const [justificacion, setJustificacion] = useState('')
  const [usuario, setUsuario] = useState('OPERADOR')
  const [tocado, setTocado] = useState(false)
  const [enviando, setEnviando] = useState(false)
  const [error, setError] = useState('')

  const largo = justificacion.trim().length
  const faltan = Math.max(0, MIN_JUSTIFICACION - largo)
  const justificacionValida = faltan === 0
  const valida = justificacionValida && usuario.trim().length > 0
  const estadoCampo = justificacionValida ? 'valido' : tocado ? 'invalido' : 'neutro'

  const enviar = async (e) => {
    e.preventDefault()
    setTocado(true)
    if (!valida) return
    setEnviando(true)
    setError('')
    try {
      const r = await ratificarDictamen(dictamen.id, {
        nuevo_estatus: decision,
        justificacion: justificacion.trim(),
        usuario: usuario.trim(),
      })
      toast.exito(
        'Revisión humana registrada',
        `Dictamen ${meta(r.estatus).label.toLowerCase()} · expediente ${meta(r.estado_expediente).label.toLowerCase()}`
      )
      onRatificado(r)
    } catch (err) {
      const detalle = Array.isArray(err.detail) ? err.detail.map((d) => d.msg).join(' ') : err.message
      setError(detalle)
      toast.error('No se pudo ratificar', detalle)
    } finally {
      setEnviando(false)
    }
  }

  return (
    <form className="ratificacion" onSubmit={enviar} noValidate>
      <header className="ratificacion-head">
        <span className="squircle" aria-hidden="true">
          <UserCheck size={15} />
        </span>
        <div>
          <p className="ratificacion-title">Resolver revisión humana</p>
          <p className="ratificacion-sub">
            Nivel 5 · la decisión prevalece sobre la del motor (RN-05) y queda en la bitácora inmutable.
          </p>
        </div>
      </header>

      <div className="ratificacion-grid">
        <div className="field">
          <span className="field-label">Decisión</span>
          <Segmented label="Decisión del analista" valor={decision} onChange={setDecision} opciones={DECISIONES} />
        </div>
        <label className="field">
          <span className="field-label">Analista</span>
          <input value={usuario} onChange={(e) => setUsuario(e.target.value)} maxLength={100} required />
        </label>
      </div>

      <label className="field">
        <span className="field-label">
          Justificación
          <span className={`field-counter tabular field-counter--${estadoCampo}`}>
            {largo} / {MIN_JUSTIFICACION} mín.
          </span>
        </span>
        <textarea
          rows={3}
          className={`input--${estadoCampo}`}
          value={justificacion}
          onChange={(e) => setJustificacion(e.target.value)}
          onBlur={() => setTocado(true)}
          placeholder="Qué se cotejó y por qué se confirma o corrige el dictamen automático…"
          maxLength={2000}
          aria-invalid={estadoCampo === 'invalido'}
          aria-describedby={`ayuda-${dictamen.id}`}
          required
        />
        <span id={`ayuda-${dictamen.id}`} className={`field-feedback field-feedback--${estadoCampo}`}>
          {justificacionValida
            ? 'Justificación suficiente.'
            : `Faltan ${faltan} ${faltan === 1 ? 'carácter' : 'caracteres'} para registrar la decisión.`}
        </span>
      </label>

      {error && <p className="form-error">{error}</p>}

      <div className="ratificacion-actions">
        <button type="button" className="btn btn-secondary btn-sm" onClick={onCancelar} disabled={enviando}>
          Cancelar
        </button>
        <button type="submit" className="btn btn-primary btn-sm" disabled={!valida || enviando}>
          {enviando && <Loader2 className="spin" size={13} />}
          Ratificar dictamen
        </button>
      </div>
    </form>
  )
}

/** Dictamen vigente del documento: estatus, datos clave, reglas aplicadas y ratificación. */
function DictamenVigente({ dictamen, puedeRatificar, onRatificar }) {
  const ratificado = dictamen.revisado_por_humano
  const esIntegridad = dictamen.origen === 'RIE-03'
  return (
    <article className="registro-card">
      <header className="registro-head">
        <EstatusBadge estatus={dictamen.estatus} />
        {ratificado && (
          <span className="badge badge--neutral" title={`Ratificado por ${dictamen.revisado_por}`}>
            <UserCheck size={12} strokeWidth={1.75} aria-hidden="true" />
            Ratificado
          </span>
        )}
        <span className="registro-origen">{esIntegridad ? 'Integridad RIE-03' : 'Nivel 4 + reglas del Nivel 2'}</span>
        <span className="registro-fecha">
          <Momento valor={dictamen.creado_en} />
        </span>
      </header>

      <dl className="registro-grid">
        <div>
          <dt>Confianza</dt>
          <dd className="tabular">{pct(dictamen.nivel_confianza)}</dd>
        </div>
        <div>
          <dt>Vigencia</dt>
          <dd>{VIGENCIA[dictamen.vigencia_resultado] || '—'}</dd>
        </div>
        <div>
          <dt>Dictamen automático</dt>
          <dd>{meta(dictamen.estatus_preliminar).label}</dd>
        </div>
        <div>
          <dt>Huella evaluada</dt>
          <dd className="mono" title={dictamen.hash_sha256}>
            {hashCorto(dictamen.hash_sha256, 8, 6)}
          </dd>
        </div>
      </dl>

      {dictamen.reglas_aplicadas?.length > 0 && (
        <ul className="registro-reglas" aria-label="Reglas aplicadas">
          {dictamen.reglas_aplicadas.map((r) => (
            <li key={`${r.codigo_regla}-${r.resultado}`} title={r.detalle || undefined}>
              <span className={`status-dot status-dot--${RESULTADO_REGLA[r.resultado] || 'off'}`} aria-hidden="true" />
              <span className="mono">{r.codigo_regla}</span>
              <span className="cell-muted">{String(r.resultado).toLowerCase().replace(/_/g, ' ')}</span>
            </li>
          ))}
        </ul>
      )}

      {ratificado && (
        <blockquote className="registro-cita">
          <p>«{dictamen.justificacion_humana}»</p>
          <footer>
            {dictamen.revisado_por} · <Momento valor={dictamen.revisado_en} />
          </footer>
        </blockquote>
      )}

      {puedeRatificar && (
        <div className="registro-accion">
          <p>
            <span className="status-dot status-dot--warn" aria-hidden="true" />
            Pendiente de ratificación humana: confianza por debajo del umbral o vigencia no verificable.
          </p>
          <button type="button" className="btn btn-secondary btn-sm" onClick={onRatificar}>
            <UserCheck size={14} />
            Resolver revisión humana
          </button>
        </div>
      )}
    </article>
  )
}

/**
 * Dictámenes persistidos del documento (core-service): el vigente, el acceso a
 * la ratificación humana cuando está EN_REVISION y el historial completo.
 * `recarga` es un contador: el padre lo incrementa tras cada auditoría.
 */
export default function DictamenesGuardados({ doc, recarga = 0, onCambio }) {
  const [dictamenes, setDictamenes] = useState(null)
  const [error, setError] = useState('')
  const [ratificando, setRatificando] = useState(false)
  // Tras una ratificación se vuelve a consultar sin depender del padre.
  const [recargaLocal, setRecargaLocal] = useState(0)

  useEffect(() => {
    let vigente = true
    getDictamenes({ documento_id: doc.id })
      .then((lista) => {
        if (!vigente) return
        setDictamenes(lista || [])
        setError('')
      })
      .catch((err) => {
        if (!vigente) return
        setError(err.message)
        setDictamenes([])
      })
    return () => {
      vigente = false
    }
  }, [doc.id, recarga, recargaLocal])

  if (dictamenes === null) {
    return (
      <div className="ai-loading" aria-hidden="true">
        <Skeleton w="40%" />
        <Skeleton w="100%" h={56} />
      </div>
    )
  }
  if (error) return <p className="field-hint">No se pudo consultar el historial de dictámenes: {error}</p>
  if (dictamenes.length === 0) {
    return <p className="field-hint">Este documento aún no tiene dictámenes guardados: audítalo para emitir el primero.</p>
  }

  const [vigente, ...anteriores] = dictamenes
  const puedeRatificar =
    vigente.estatus === 'EN_REVISION' &&
    !vigente.revisado_por_humano &&
    vigente.origen !== 'RIE-03' &&
    doc.estado_integridad !== 'ALTERADO'

  const alRatificar = () => {
    setRatificando(false)
    setRecargaLocal((n) => n + 1)
    onCambio?.()
  }

  return (
    <section className="dictamenes-guardados" aria-label="Dictámenes guardados">
      <DictamenVigente dictamen={vigente} puedeRatificar={puedeRatificar && !ratificando} onRatificar={() => setRatificando(true)} />

      {ratificando && (
        <FormularioRatificacion dictamen={vigente} onRatificado={alRatificar} onCancelar={() => setRatificando(false)} />
      )}

      {anteriores.length > 0 && (
        <details className="historial">
          <summary>
            <History size={12} strokeWidth={1.75} aria-hidden="true" />
            Historial · {anteriores.length} {anteriores.length === 1 ? 'dictamen anterior' : 'dictámenes anteriores'}
          </summary>
          <ul>
            {anteriores.map((d) => (
              <li key={d.id} className="historial-item">
                <EstatusBadge estatus={d.estatus} />
                <span className="cell-muted">
                  {d.origen === 'RIE-03' ? 'Integridad RIE-03' : `Confianza ${pct(d.nivel_confianza)}`}
                  {d.revisado_por_humano && ` · ratificado por ${d.revisado_por}`}
                </span>
                <span className="cell-muted historial-fecha">
                  <Momento valor={d.creado_en} />
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </section>
  )
}

/** Aviso de bloqueo por alteración criptográfica (RIE-03). */
export function AvisoIntegridad() {
  return (
    <div className="verdict verdict--bad verdict--compact" role="alert">
      <div className="verdict-main">
        <p className="eyebrow eyebrow--icon">
          <ShieldAlert size={12} strokeWidth={1.75} aria-hidden="true" /> Integridad RIE-03
        </p>
        <p className="verdict-word verdict-word--sm">Documento bloqueado</p>
        <p className="verdict-reason">
          La huella SHA-256 del archivo en la bóveda ya no coincide con la registrada en la carga. El documento no se analiza
          ni se entrega; recarga el archivo original para sustituirlo.
        </p>
      </div>
    </div>
  )
}
