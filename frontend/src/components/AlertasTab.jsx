import { useEffect, useMemo, useState } from 'react'
import { ArrowUpRight, BellOff, ChevronDown, SearchX } from 'lucide-react'
import { SkeletonCards } from './Skeleton.jsx'
import Desplegable from './expedientes/Desplegable.jsx'
import { AlertaItem } from './Alertas.jsx'
import FolioExpediente from './FolioExpediente.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { alertasDeExpedientes } from '../utils/alertas.js'
import { coincideEn, normalizar } from '../utils/busqueda.js'
import useDesplazamiento from '../hooks/useDesplazamiento.js'
import { Button, Card, EmptyState, SearchBox, Segmented, Select } from './ui/index.js'
import {
  ALERTA_META,
  getSeveridadMeta,
  SEVERIDADES,
  TIPO_EXPEDIENTE_LABEL,
  TIPOS_EXPEDIENTE,
} from '../constants.js'

/**
 * Bandeja de alertas y recomendaciones de todos los expedientes (Módulo 5:
 * RF-18, RF-21, HU-15, HU-16). Las alertas vienen en la evaluación de cada
 * expediente, así que la bandeja se actualiza con el mismo sondeo que el
 * resto del panel y una alerta desaparece en cuanto se corrige su hallazgo.
 */
export default function AlertasTab({ expedientes, loading, onAbrirExpediente, busquedaInicial = null, onFiltroAtendido }) {
  // Desde el detalle de una empresa llega su RFC: la bandeja se monta ya filtrada.
  const [busqueda, setBusqueda] = useState(busquedaInicial || '')
  const [filtroSeveridad, setFiltroSeveridad] = useState('TODAS')
  const [filtroCodigo, setFiltroCodigo] = useState('TODAS')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  // Grupos de severidad abiertos: las críticas, por defecto.
  const [abiertos, setAbiertos] = useState(() => new Set(['CRITICA']))
  const alternar = (clave) =>
    setAbiertos((previos) => {
      const siguientes = new Set(previos)
      if (siguientes.has(clave)) siguientes.delete(clave)
      else siguientes.add(clave)
      return siguientes
    })
  const consulta = useDebounce(busqueda, 220)

  // Filtro pedido desde otra vista: aplicado al montar, se da por atendido.
  useEffect(() => {
    if (busquedaInicial) onFiltroAtendido?.()
  }, [busquedaInicial, onFiltroAtendido])
  const bandeja = useDesplazamiento()

  const alertas = useMemo(() => alertasDeExpedientes(expedientes), [expedientes])

  const opcionesSeveridad = useMemo(
    () => [
      { id: 'TODAS', label: 'Todas', conteo: alertas.length },
      ...SEVERIDADES.map((s) => ({
        id: s,
        label: getSeveridadMeta(s).label,
        tono: getSeveridadMeta(s).tono === 'brand' ? undefined : getSeveridadMeta(s).tono,
        conteo: alertas.filter((a) => a.severidad === s).length,
      })),
    ],
    [alertas]
  )

  const codigos = useMemo(() => [...new Set(alertas.map((a) => a.codigo))], [alertas])

  const filtradas = useMemo(() => {
    const q = normalizar(consulta)
    return alertas.filter((a) => {
      const sevOk = filtroSeveridad === 'TODAS' || a.severidad === filtroSeveridad
      const codOk = filtroCodigo === 'TODAS' || a.codigo === filtroCodigo
      const tipoOk = filtroTipo === 'TODOS' || a.expediente.tipo === filtroTipo
      const textoOk = coincideEn(
        [a.titulo, a.detalle, a.recomendacion, a.expediente.codigo, a.expediente.razon_social, a.expediente.rfc],
        q
      )
      return sevOk && codOk && tipoOk && textoOk
    })
  }, [alertas, consulta, filtroSeveridad, filtroCodigo, filtroTipo])
  const nExpedientes = new Set(filtradas.map((a) => a.expediente.id)).size
  const unico = nExpedientes === 1 ? filtradas[0].expediente : null
  // Grupos de la más grave a la menos grave; una severidad fuera del catálogo va al final.
  const grupos = SEVERIDADES.map((s) => ({ sev: s, items: filtradas.filter((a) => a.severidad === s) }))
    .concat([{ sev: null, items: filtradas.filter((a) => !SEVERIDADES.includes(a.severidad)) }])
    .filter((g) => g.items.length)

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar hallazgo, folio o empresa…"
          label="Buscar alertas"
        />
        <Segmented label="Filtrar por severidad" valor={filtroSeveridad} onChange={setFiltroSeveridad} opciones={opcionesSeveridad} />
        <Select etiqueta="Filtrar por categoría" value={filtroCodigo} onChange={(e) => setFiltroCodigo(e.target.value)}>
          <option value="TODAS">Toda categoría</option>
          {codigos.map((c) => (
            <option key={c} value={c}>
              {ALERTA_META[c]?.label || c}
            </option>
          ))}
        </Select>
        <Select etiqueta="Filtrar por tipo de expediente" value={filtroTipo} onChange={(e) => setFiltroTipo(e.target.value)}>
          <option value="TODOS">Todo tipo de expediente</option>
          {TIPOS_EXPEDIENTE.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
      </div>

      {loading && <SkeletonCards count={3} height={96} />}

      {!loading && filtradas.length === 0 && (
        <Card>
          <EmptyState
            icon={alertas.length === 0 ? BellOff : SearchX}
            titulo={alertas.length === 0 ? 'Sin alertas vigentes' : 'Sin coincidencias'}
            descripcion={
              alertas.length === 0
                ? 'Todos los expedientes cumplen: no hay documentos faltantes, vencidos ni anexos ausentes.'
                : 'Ajusta la búsqueda o los filtros de severidad, categoría y tipo.'
            }
          >
            {alertas.length > 0 && (
              <Button
                compacto
                onClick={() => {
                  setBusqueda('')
                  setFiltroSeveridad('TODAS')
                  setFiltroCodigo('TODAS')
                  setFiltroTipo('TODOS')
                }}
              >
                Limpiar filtros
              </Button>
            )}
          </EmptyState>
        </Card>
      )}

      {!loading && filtradas.length > 0 && (
        <>
          <div className="bandeja-resumen">
            <p className="field-hint">
              {filtradas.length} {filtradas.length === 1 ? 'alerta' : 'alertas'} en {nExpedientes}{' '}
              {nExpedientes === 1 ? 'expediente' : 'expedientes'}, de la más grave a la menos grave.
              {filtroTipo !== 'TODOS' && ` Tipo: ${TIPO_EXPEDIENTE_LABEL[filtroTipo]}.`}
            </p>
            {/* Todas del mismo expediente: se nombra una vez aquí en lugar de en cada alerta. */}
            {unico && (
              <>
                <FolioExpediente expediente={unico.completo} className="mono cell-muted" />
                <span className="field-hint">{unico.razon_social}</span>
                <Button compacto icono={ArrowUpRight} onClick={() => onAbrirExpediente?.(unico.id)}>
                  Abrir expediente
                </Button>
              </>
            )}
          </div>
          <div className="bandeja-grupos" ref={bandeja}>
            {grupos.map(({ sev, items }) => {
              const meta = getSeveridadMeta(sev)
              const titulo = sev ? meta.label : 'Otras'
              const clave = sev || 'OTRAS'
              // Las críticas entran abiertas; las demás, plegadas. Filtrar por una severidad la abre.
              const abierto = abiertos.has(clave) || filtroSeveridad === sev
              const idLista = `alertas-${clave.toLowerCase()}`
              return (
                <section key={clave} className="bandeja-grupo" aria-label={`Severidad ${titulo.toLowerCase()}`}>
                  <h2 className="section-title">
                    <button
                      type="button"
                      className="bandeja-grupo-cabecera"
                      aria-expanded={abierto}
                      aria-controls={idLista}
                      onClick={() => alternar(clave)}
                    >
                      <ChevronDown size={14} strokeWidth={1.5} className="bandeja-grupo-flecha" aria-hidden="true" />
                      <span className={`status-dot status-dot--${meta.tono}`} aria-hidden="true" />
                      {titulo} <span className="tabular cell-muted">· {items.length}</span>
                    </button>
                  </h2>
                  <Desplegable abierto={abierto}>
                    <ul id={idLista} className="alerta-lista alerta-lista--bandeja">
                      {items.map((a, i) => (
                        <AlertaItem
                          key={`${a.expediente.id}-${a.codigo}-${a.tipo_documento}-${i}`}
                          alerta={a}
                          claveFlip={`${a.expediente.id}-${a.codigo}-${a.tipo_documento}`}
                          indice={i}
                          expediente={unico ? undefined : a.expediente}
                          onAbrirExpediente={onAbrirExpediente}
                        />
                      ))}
                    </ul>
                  </Desplegable>
                </section>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
