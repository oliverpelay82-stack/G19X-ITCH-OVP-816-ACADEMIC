import { Building2, FolderKanban, ShieldCheck, Vault } from 'lucide-react'

/**
 * 4 KPIs ejecutivos en tiempo real: Empresas, Expedientes, Documentos en
 * Bóveda y % de Cumplimiento General (promedio de porcentaje_completitud).
 */
export default function MetricsCards({ titulares, expedientes, documentos, loading }) {
  const totalTitulares = titulares.length
  const totalExpedientes = expedientes.length
  const totalDocumentos = documentos.length

  const cumplimientoGeneral = totalExpedientes
    ? expedientes.reduce((acc, e) => acc + Number(e.porcentaje_completitud || 0), 0) / totalExpedientes
    : 0

  const cards = [
    {
      icon: Building2,
      label: 'Empresas Registradas',
      value: totalTitulares,
      accent: 'var(--accent)',
      accentBg: 'var(--accent-bg)',
    },
    {
      icon: FolderKanban,
      label: 'Expedientes Activos',
      value: totalExpedientes,
      accent: 'var(--revision-fg)',
      accentBg: 'var(--revision-bg)',
    },
    {
      icon: Vault,
      label: 'Documentos en Bóveda',
      value: totalDocumentos,
      accent: 'var(--boveda-fg)',
      accentBg: 'var(--boveda-bg)',
    },
    {
      icon: ShieldCheck,
      label: '% Cumplimiento General',
      value: `${cumplimientoGeneral.toFixed(1)}%`,
      accent: 'var(--conforme-fg)',
      accentBg: 'var(--conforme-bg)',
      isProgress: true,
      progress: cumplimientoGeneral,
    },
  ]

  return (
    <section className="metrics-grid">
      {cards.map((card) => (
        <div className="metric-card" key={card.label}>
          <div className="metric-card-top">
            <span className="metric-icon" style={{ color: card.accent, background: card.accentBg }}>
              <card.icon size={18} strokeWidth={2.25} />
            </span>
            <span className="metric-label">{card.label}</span>
          </div>
          <div className="metric-value">{loading ? '—' : card.value}</div>
          {card.isProgress && (
            <div className="metric-progress-track">
              <div
                className="metric-progress-fill"
                style={{ width: `${Math.min(100, card.progress)}%`, background: card.accent }}
              />
            </div>
          )}
        </div>
      ))}
    </section>
  )
}
