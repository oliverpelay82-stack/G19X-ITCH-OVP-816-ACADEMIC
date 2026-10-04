import { useEffect, useState } from 'react'
import { History, Save, ShieldAlert, UserCheck } from 'lucide-react'
import { Skeleton } from './Skeleton.jsx'
import EstadoBadge from './EstadoBadge.jsx'
import { getEstadoBadge } from '../constants.js'
import { Badge, Button, Field, Input, KeyValue, KeyValueList, Segmented } from './ui/index.js'
import useToast from '../hooks/useToast.js'
import { getDictamenes, ratificarDictamen } from '../services/api.js'
import { formatFecha, formatRelativo, hashCorto } from '../utils/format.js'

const RESULTADO_REGLA = {
  CUMPLE: 'ok',
  VIGENTE: 'ok',
  PROXIMO_A_VENCER: 'warn',
  INDETERMINADO: 'warn',
  NO_APLICA: 'neutral',
  VENCIDO: 'bad',
  NO_CUMPLE: 'bad',
  NO_LOCALIZADO: 'bad',
  NO_VERIFICABLE: 'warn',
}

/** Qué emitió el dictamen, cuando no fue el análisis con IA (integridad y validación de la carga). */
const ORIGEN = {
  'RIE-03': 'Verificación de integridad',
  NIVEL_3_ILEGIBLE: 'Lectura del documento · ilegible, se requiere recarga',
  NIVEL_1: 'Validación de la carga · PDF protegido',
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

/** Orígenes cuyo dictamen no se ratifica: una alteración (RIE-03) y un documento ilegible (se recarga). */
const SIN_RATIFICACION = new Set(['RIE-03', 'NIVEL_3_ILEGIBLE'])

const meta = getEstadoBadge
const pct = (n) => (n === null || n === undefined ? '—' : `${Math.round(n * 100)}%`)

/** Marca de tiempo relativa, con la fecha absoluta en el tooltip. */
function Momento({ valor }) {
  return (
    <time className="tabular" dateTime={valor} title={formatFecha(valor)}>
      {formatRelativo(valor)}
    </time>
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
      const detalle = err.message // api.js ya compone el texto de los errores de validación (422)
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
          <UserCheck size={16} />
        </span>
        <div>
          <p className="ratificacion-title">Resolver revisión humana</p>
          <p className="ratificacion-sub">
            La decisión del analista prevalece sobre la del motor y queda en la bitácora inmutable.
          </p>
        </div>
      </header>

      <div className="ratificacion-grid">
        <Field as="div" etiqueta="Decisión">
          <Segmented label="Decisión del analista" valor={decision} onChange={setDecision} opciones={DECISIONES} />
        </Field>
        <Field etiqueta="Analista">
          <Input value={usuario} onChange={(e) => setUsuario(e.target.value)} maxLength={100} required />
        </Field>
      </div>

      <Field
        etiqueta={
          <>
            Justificación
            <span className={`field-counter tabular field-counter--${estadoCampo}`}>
              {largo} / {MIN_JUSTIFICACION} mín.
            </span>
          </>
        }
        retro={{
          estado: estadoCampo,
          mensaje: justificacionValida
            ? 'Justificación suficiente.'
            : `Faltan ${faltan} ${faltan === 1 ? 'carácter' : 'caracteres'} para registrar la decisión.`,
        }}
      >
        <textarea
          rows={3}
          className={`input--${estadoCampo}`}
          value={justificacion}
          onChange={(e) => setJustificacion(e.target.value)}
          onBlur={() => setTocado(true)}
          placeholder="Qué se cotejó y por qué se confirma o corrige el dictamen automático…"
          maxLength={2000}
          aria-invalid={estadoCampo === 'invalido'}
          required
        />
      </Field>

      {error && <p className="form-error">{error}</p>}

      <div className="ratificacion-actions">
        <Button compacto onClick={onCancelar} disabled={enviando}>
          Cancelar
        </Button>
        <Button type="submit" variante="primary" compacto cargando={enviando} disabled={!valida}>
          Ratificar dictamen
        </Button>
      </div>
    </form>
  )
}

/**
 * Dictamen vigente del documento: estatus, datos clave, reglas aplicadas y
 * ratificación. Sin `onRatificar` (el encabezado del modal ya ofrece
 * «Ratificar dictamen») el aviso de pendiente queda como texto.
 */
function DictamenVigente({ dictamen, puedeRatificar, onRatificar }) {
  const ratificado = dictamen.revisado_por_humano
  // El automático solo informa algo cuando la ratificación lo cambió; si coincide, repetiría el estatus del encabezado.
  const cambioAutomatico = Boolean(dictamen.estatus_preliminar) && dictamen.estatus_preliminar !== dictamen.estatus
  return (
    <article className="registro-card">
      <header className="registro-head">
        <EstadoBadge estado={dictamen.estatus} />
        {ratificado && (
          <Badge title={`Ratificado por ${dictamen.revisado_por}`}>
            <UserCheck size={12} strokeWidth={1.75} aria-hidden="true" />
            Ratificado
          </Badge>
        )}
        <span className="registro-origen">{ORIGEN[dictamen.origen] || 'Análisis con IA y reglas de vigencia'}</span>
        <span className="registro-fecha">
          <Momento valor={dictamen.creado_en} />
        </span>
      </header>

      <KeyValueList className={`registro-grid${cambioAutomatico ? '' : ' registro-grid--tres'}`}>
        <KeyValue etiqueta="Confianza" valorClassName="tabular">
          {pct(dictamen.nivel_confianza)}
        </KeyValue>
        <KeyValue etiqueta="Vigencia">{VIGENCIA[dictamen.vigencia_resultado] || '—'}</KeyValue>
        {cambioAutomatico && (
          <KeyValue etiqueta="Dictamen automático">{meta(dictamen.estatus_preliminar).label}</KeyValue>
        )}
        <KeyValue etiqueta="Huella evaluada" valorClassName="mono" valorTitulo={dictamen.hash_sha256}>
          {hashCorto(dictamen.hash_sha256, 8, 6)}
        </KeyValue>
      </KeyValueList>

      {dictamen.reglas_aplicadas?.length > 0 && (
        <ul className="registro-reglas" aria-label="Reglas aplicadas">
          {dictamen.reglas_aplicadas.map((r) => (
            <li key={`${r.codigo_regla}-${r.resultado}`} title={[r.nombre_regla, r.detalle, r.recomendacion].filter(Boolean).join(' · ') || undefined}>
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
            Pendiente de ratificación: el motor no puede cerrar este dictamen sin un analista.
          </p>
          {onRatificar && (
            <Button compacto icono={UserCheck} onClick={onRatificar}>
              Resolver revisión humana
            </Button>
          )}
        </div>
      )}
    </article>
  )
}

/**
 * Dictámenes persistidos del documento (core-service): el vigente, la
 * ratificación humana cuando está EN_REVISION y el historial completo.
 * `recarga` es un contador que el padre incrementa tras cada auditoría;
 * `solicitudRatificar`, otro que incrementa el botón «Ratificar dictamen» del
 * encabezado del modal y abre el formulario si el dictamen lo admite.
 *
 * `dictamenSesionId` es el dictamen que guardó la auditoría recién hecha: si es
 * el vigente y no se ha ratificado, el resultado de la auditoría ya lo muestra
 * completo y aquí queda en una línea (fecha e historial). Un dictamen anterior
 * distinto, o uno ya ratificado, se muestra completo.
 */
export default function DictamenesGuardados({
  doc,
  recarga = 0,
  onCambio,
  solicitudRatificar = 0,
  dictamenSesionId = null,
  ratificacionEnEncabezado = false,
}) {
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

  // Solicitud del encabezado del modal: se atiende al renderizar, en cuanto
  // los dictámenes están cargados (mismo patrón que la apertura en Expedientes).
  const [solicitudAtendida, setSolicitudAtendida] = useState(solicitudRatificar)
  if (dictamenes?.length && solicitudRatificar !== solicitudAtendida) {
    setSolicitudAtendida(solicitudRatificar)
    const [primero] = dictamenes
    if (primero.estatus === 'EN_REVISION' && !primero.revisado_por_humano && !SIN_RATIFICACION.has(primero.origen)) {
      setRatificando(true)
    }
  }

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
    !SIN_RATIFICACION.has(vigente.origen) &&
    doc.estado_integridad !== 'ALTERADO'

  const alRatificar = () => {
    setRatificando(false)
    setRecargaLocal((n) => n + 1)
    onCambio?.()
  }

  // Resumido solo si nada se pierde: la ratificación sigue a mano en el encabezado.
  const resumido =
    dictamenSesionId != null &&
    vigente.id === dictamenSesionId &&
    !vigente.revisado_por_humano &&
    (!puedeRatificar || ratificacionEnEncabezado)

  const historial = anteriores.length > 0 && (
    <details className="historial">
      <summary>
        <History size={12} strokeWidth={1.75} aria-hidden="true" />
        Historial · {anteriores.length} {anteriores.length === 1 ? 'dictamen anterior' : 'dictámenes anteriores'}
      </summary>
      <ul>
        {anteriores.map((d) => (
          <li key={d.id} className="historial-item">
            <EstadoBadge estado={d.estatus} />
            <span className="cell-muted">
              {ORIGEN[d.origen] || `Confianza ${pct(d.nivel_confianza)}`}
              {d.revisado_por_humano && ` · ratificado por ${d.revisado_por}`}
            </span>
            <span className="cell-muted historial-fecha">
              <Momento valor={d.creado_en} />
            </span>
          </li>
        ))}
      </ul>
    </details>
  )

  if (resumido) {
    return (
      <section className="dictamenes-guardados" aria-label="Dictámenes guardados">
        <div className="dictamen-linea">
          <p className="dictamen-linea-texto">
            <Save size={14} strokeWidth={1.75} aria-hidden="true" />
            Es el resultado de esta auditoría, guardado <Momento valor={vigente.creado_en} />
          </p>
          {historial}
        </div>
        {ratificando && (
          <FormularioRatificacion dictamen={vigente} onRatificado={alRatificar} onCancelar={() => setRatificando(false)} />
        )}
      </section>
    )
  }

  return (
    <section className="dictamenes-guardados" aria-label="Dictámenes guardados">
      <DictamenVigente
        dictamen={vigente}
        puedeRatificar={puedeRatificar && !ratificando}
        onRatificar={ratificacionEnEncabezado ? null : () => setRatificando(true)}
      />

      {ratificando && (
        <FormularioRatificacion dictamen={vigente} onRatificado={alRatificar} onCancelar={() => setRatificando(false)} />
      )}

      {historial}
    </section>
  )
}

/** Aviso de bloqueo por alteración criptográfica (RIE-03). */
export function AvisoIntegridad() {
  return (
    <div className="verdict verdict--bad verdict--compact" role="alert">
      <div className="verdict-main">
        <p className="eyebrow eyebrow--icon">
          <ShieldAlert size={12} strokeWidth={1.75} aria-hidden="true" /> Integridad comprometida
        </p>
        <p className="verdict-word verdict-word--sm">Documento bloqueado</p>
        <p className="verdict-reason">
          La huella digital del archivo en la bóveda ya no coincide con la registrada en la carga. El documento no se analiza
          ni se entrega; recarga el archivo original para sustituirlo.
        </p>
      </div>
    </div>
  )
}
