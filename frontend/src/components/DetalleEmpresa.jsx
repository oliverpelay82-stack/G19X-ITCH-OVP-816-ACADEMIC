import { useMemo } from 'react'
import { ArrowLeft, ArrowUpRight, FolderPlus, SearchX } from 'lucide-react'
import { CorregirEmpresa } from './CorreccionDatos.jsx'
import FolioExpediente from './FolioExpediente.jsx'
import EstadoBadge from './EstadoBadge.jsx'
import { IconoExpediente } from './IconosMotor.jsx'
import { Avatar, Badge, Button, Card, CopyChip, EmptyState, KeyValue, KeyValueList, Tag } from './ui/index.js'
import { RANGO_ESTADO } from '../hooks/useOrden.js'
import {
  categoriaTitular,
  getEstadoBadge,
  getSeveridadMeta,
  rangoSeveridad,
  TIPO_EXPEDIENTE_LABEL,
} from '../constants.js'
import { alertasDeExpedientes } from '../utils/alertas.js'
import { formatIndice, indiceDe } from '../utils/indice.js'
import { formatFechaCorta, plural } from '../utils/format.js'

/** Cuántas alertas se resumen: las más graves; todas están en la bandeja de Alertas. */
const MAX_ALERTAS = 5

/**
 * Detalle de la empresa (#/empresas/<RFC>, PRD §13.1): sus datos, un resumen
 * en una línea, todos sus expedientes de lo más grave a lo conforme y un
 * resumen de sus alertas más graves, una por línea, con el enlace a la bandeja
 * de Alertas filtrada por la empresa, donde está cada recomendación (RF-18,
 * RF-21): las tarjetas completas no se repiten aquí. Todo sale del
 * listado de expedientes ya cargado, que trae la evaluación de cada uno; no
 * hay tarjetas de métricas, que van solo en Expedientes. Para volver a la
 * lista basta la miga «Empresas» del encabezado (o «Atrás»): un botón propio
 * la repetiría.
 */
export default function DetalleEmpresa({
  titular,
  expedientes,
  aviso,
  onAbrir,
  onAperturar,
  onVerAlertas,
  onRefresh,
  isOnline,
}) {
  const ordenados = useMemo(
    () =>
      [...expedientes].sort(
        (a, b) =>
          (RANGO_ESTADO[a.estado_cumplimiento] ?? 9) - (RANGO_ESTADO[b.estado_cumplimiento] ?? 9) ||
          (indiceDe(a)?.porcentaje ?? 101) - (indiceDe(b)?.porcentaje ?? 101)
      ),
    [expedientes]
  )

  const resumen = useMemo(() => {
    const porEstado = { CONFORME: 0, EN_REVISION: 0, NO_CONFORME: 0 }
    let documentos = 0
    for (const e of expedientes) {
      porEstado[e.estado_cumplimiento] = (porEstado[e.estado_cumplimiento] || 0) + 1
      documentos += e.evaluacion?.documentos?.length || 0
    }
    const alertas = alertasDeExpedientes(expedientes)
    const graves = alertas.filter((a) => ['CRITICA', 'ALTA'].includes(a.severidad)).length
    return { porEstado, documentos, alertas, graves }
  }, [expedientes])

  const lineaResumen = [
    plural(expedientes.length, 'expediente', 'expedientes'),
    ...Object.entries(resumen.porEstado)
      .filter(([, n]) => n > 0)
      .map(([estado, n]) => `${n} ${getEstadoBadge(estado).label.toLowerCase()}`),
    plural(resumen.documentos, 'documento vigente', 'documentos vigentes'),
    resumen.alertas.length
      ? `${plural(resumen.alertas.length, 'alerta', 'alertas')}${
          resumen.graves ? ` (${plural(resumen.graves, 'crítica o alta', 'críticas o altas')})` : ''
        }`
      : 'sin alertas',
  ].join(' · ')

  return (
    <div className="tab-panel empresa-detalle">
      <Card as="section" className="empresa-ficha" aria-labelledby="empresa-nombre">
        <header className="profile-head">
          <Avatar nombre={titular.razon_social} grande />
          <div className="profile-identity">
            <h2 id="empresa-nombre" className="empresa-nombre">
              {titular.razon_social}
            </h2>
            <p className="profile-sub">{lineaResumen}</p>
          </div>
          <div className="empresa-acciones">
            <CorregirEmpresa titular={titular} onCorregido={onRefresh} disabled={!isOnline} />
            <Button variante="primary" compacto icono={FolderPlus} onClick={() => onAperturar(titular)} disabled={!isOnline}>
              Aperturar expediente
            </Button>
          </div>
        </header>
        <KeyValueList className="profile-grid empresa-datos">
          <KeyValue etiqueta="RFC">
            <CopyChip valor={titular.rfc} etiqueta="RFC" />
            {aviso}
          </KeyValue>
          <KeyValue etiqueta="Tipo de persona">{titular.tipo_persona === 'FISICA' ? 'Física' : 'Moral'}</KeyValue>
          <KeyValue etiqueta="Categoría">
            <Tag>{categoriaTitular(titular.categoria)}</Tag>
          </KeyValue>
          <KeyValue etiqueta="Alta">{formatFechaCorta(titular.creado_en)}</KeyValue>
        </KeyValueList>
      </Card>

      <section className="empresa-seccion" aria-labelledby="empresa-expedientes">
        <h3 id="empresa-expedientes" className="section-title">
          Expedientes
        </h3>
        {ordenados.length === 0 ? (
          <Card>
            <EmptyState
              icon={IconoExpediente}
              titulo="Esta empresa aún no tiene expedientes"
              descripcion="Apertura el primero para empezar a custodiar y validar sus documentos."
            />
          </Card>
        ) : (
          <Card className="table-card">
            <div className="table-scroll">
              <table className="data-table">
                <colgroup>
                  <col style={{ width: '27%' }} />
                  <col style={{ width: '13%' }} />
                  <col style={{ width: '16%' }} />
                  <col style={{ width: '10%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: 104 }} />
                </colgroup>
                <thead>
                  <tr>
                    <th>Expediente</th>
                    <th>Tipo</th>
                    <th>Semáforo</th>
                    <th className="col-right">Índice</th>
                    <th className="col-right">Obligatorios</th>
                    <th className="col-right">Alertas</th>
                    <th aria-label="Acciones" />
                  </tr>
                </thead>
                <tbody>
                  {ordenados.map((e) => {
                    const alertas = e.evaluacion?.alertas || []
                    const peor = alertas.reduce(
                      (p, a) => (p == null || rangoSeveridad(a.severidad) < rangoSeveridad(p) ? a.severidad : p),
                      null
                    )
                    return (
                      <tr key={e.id}>
                        <td>
                          <div className="exp-identity">
                            <FolioExpediente expediente={e} className="mono empresa-folio" />
                            {e.nombre && <span className="cell-sub">{e.nombre}</span>}
                          </div>
                        </td>
                        <td>{TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente}</td>
                        <td>
                          <EstadoBadge estado={e.estado_cumplimiento} />
                        </td>
                        <td className="col-right cell-num tabular">{formatIndice(indiceDe(e)?.porcentaje)}</td>
                        <td className="col-right cell-num tabular">{`${Math.round(e.porcentaje_completitud ?? 0)}%`}</td>
                        <td className="col-right cell-num tabular">
                          {alertas.length ? (
                            <span title={`La más grave: ${getSeveridadMeta(peor).label.toLowerCase()}`}>
                              {alertas.length}
                            </span>
                          ) : (
                            <span className="cell-muted">—</span>
                          )}
                        </td>
                        <td className="col-action">
                          <Button compacto icono={ArrowUpRight} onClick={() => onAbrir(e.id)}>
                            Abrir
                          </Button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        )}
      </section>

      {resumen.alertas.length > 0 && (
        <section className="empresa-seccion" aria-labelledby="empresa-alertas">
          <div className="empresa-seccion-cabecera">
            <h3 id="empresa-alertas" className="section-title">
              Alertas más graves
            </h3>
            <Button compacto icono={ArrowUpRight} onClick={() => onVerAlertas?.(titular.rfc)}>
              {resumen.alertas.length === 1 ? 'Ver en Alertas' : `Ver las ${resumen.alertas.length} en Alertas`}
            </Button>
          </div>
          <Card as="ul" className="empresa-alertas">
            {resumen.alertas.slice(0, MAX_ALERTAS).map((a, i) => {
              const sev = getSeveridadMeta(a.severidad)
              return (
                <li key={`${a.expediente.id}-${a.codigo}-${a.tipo_documento}-${i}`} className="empresa-alerta">
                  <Badge tono={sev.tono === 'brand' ? undefined : sev.tono} punto>
                    {sev.label}
                  </Badge>
                  <span className="empresa-alerta-titulo">{a.titulo}</span>
                  {/* Con un solo expediente, el folio repetiría lo que ya dice la tabla. */}
                  {expedientes.length > 1 && <FolioExpediente expediente={a.expediente.completo} className="mono cell-muted" />}
                </li>
              )
            })}
          </Card>
        </section>
      )}
    </div>
  )
}

/** La URL apunta a un RFC que no está registrado (enlace viejo o mal escrito). */
export function EmpresaNoEncontrada({ rfc, onVolver }) {
  return (
    <div className="tab-panel">
      <Card>
        <EmptyState
          icon={SearchX}
          titulo="Empresa no encontrada"
          descripcion={`No hay una empresa registrada con el RFC ${rfc}.`}
        >
          <Button compacto icono={ArrowLeft} onClick={onVolver}>
            Volver a Empresas
          </Button>
        </EmptyState>
      </Card>
    </div>
  )
}
