import { useMemo, useState } from 'react'
import { BellOff, SearchX } from 'lucide-react'
import { SkeletonCards } from './Skeleton.jsx'
import { AlertaItem } from './Alertas.jsx'
import useDebounce from '../hooks/useDebounce.js'
import { Card, EmptyState, SearchBox, Segmented, Select } from './ui/index.js'
import {
  ALERTA_META,
  getSeveridadMeta,
  rangoSeveridad,
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
export default function AlertasTab({ expedientes, loading, onAbrirExpediente }) {
  const [busqueda, setBusqueda] = useState('')
  const [filtroSeveridad, setFiltroSeveridad] = useState('TODAS')
  const [filtroCodigo, setFiltroCodigo] = useState('TODAS')
  const [filtroTipo, setFiltroTipo] = useState('TODOS')
  const consulta = useDebounce(busqueda, 220)

  const alertas = useMemo(
    () =>
      expedientes
        .flatMap((exp) =>
          (exp.evaluacion?.alertas || []).map((a) => ({
            ...a,
            expediente: {
              id: exp.id,
              codigo: exp.codigo_expediente,
              nombre: exp.nombre || exp.titular?.razon_social || '',
              razon_social: exp.titular?.razon_social || '',
              rfc: exp.titular?.rfc || '',
              tipo: exp.tipo_expediente,
            },
          }))
        )
        .sort((a, b) => rangoSeveridad(a.severidad) - rangoSeveridad(b.severidad)),
    [expedientes]
  )

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
    const q = consulta.trim().toLowerCase()
    return alertas.filter((a) => {
      const sevOk = filtroSeveridad === 'TODAS' || a.severidad === filtroSeveridad
      const codOk = filtroCodigo === 'TODAS' || a.codigo === filtroCodigo
      const tipoOk = filtroTipo === 'TODOS' || a.expediente.tipo === filtroTipo
      const textoOk =
        !q ||
        [a.titulo, a.detalle, a.recomendacion, a.expediente.codigo, a.expediente.razon_social, a.expediente.rfc]
          .filter(Boolean)
          .some((t) => t.toLowerCase().includes(q))
      return sevOk && codOk && tipoOk && textoOk
    })
  }, [alertas, consulta, filtroSeveridad, filtroCodigo, filtroTipo])

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Hallazgo, recomendación, folio o empresa…"
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
          />
        </Card>
      )}

      {!loading && filtradas.length > 0 && (
        <>
          <p className="field-hint">
            {filtradas.length} {filtradas.length === 1 ? 'alerta' : 'alertas'} en{' '}
            {new Set(filtradas.map((a) => a.expediente.id)).size} expedientes, de la más grave a la menos grave.
            {filtroTipo !== 'TODOS' && ` Tipo: ${TIPO_EXPEDIENTE_LABEL[filtroTipo]}.`}
          </p>
          <ul className="alerta-lista alerta-lista--bandeja">
            {filtradas.map((a, i) => (
              <AlertaItem
                key={`${a.expediente.id}-${a.codigo}-${a.tipo_documento}-${i}`}
                alerta={a}
                expediente={a.expediente}
                onAbrirExpediente={onAbrirExpediente}
              />
            ))}
          </ul>
        </>
      )}
    </div>
  )
}
