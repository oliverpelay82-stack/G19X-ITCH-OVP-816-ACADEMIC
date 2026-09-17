import { Building2, FolderKanban, ShieldCheck, Vault, BadgeCheck, Activity, TrendingUp } from 'lucide-react'

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
      iconClass: 'metric-icon--blue',
      label: 'Empresas Registradas',
      value: totalTitulares,
      accent: '#2563EB',
      accentBg: '#EFF6FF',
      badgeIcon: BadgeCheck,
      badgeText: 'Registro Verificado',
    },
    {
      icon: FolderKanban,
      iconClass: 'metric-icon--amber',
      label: 'Expedientes Activos',
      value: totalExpedientes,
      accent: '#D97706',
      accentBg: '#FFFBEB',
      badgeIcon: Activity,
      badgeText: 'Seguimiento en Vivo',
    },
    {
      icon: Vault,
      iconClass: 'metric-icon--purple',
      label: 'Documentos en Bóveda',
      value: totalDocumentos,
      accent: '#7C3AED',
      accentBg: '#FAF5FF',
      badgeIcon: ShieldCheck,
      badgeText: 'Auditado NOM-151',
    },
    {
      icon: ShieldCheck,
      iconClass: 'metric-icon--emerald',
      label: '% Cumplimiento General',
      value: `${cumplimientoGeneral.toFixed(1)}%`,
      accent: '#059669',
      accentBg: '#ECFDF5',
      badgeIcon: TrendingUp,
      badgeText: cumplimientoGeneral >= 100 ? '100% Verificado' : `${cumplimientoGeneral.toFixed(0)}% en Progreso`,
      isProgress: true,
      progress: cumplimientoGeneral,
    },
  ]

  return (
    <section className="metrics-grid">
      {cards.map((card) => (
        <div className="metric-card" key={card.label}>
          <div className="metric-card-top">
            <span className={`metric-icon ${card.iconClass}`}>
              <card.icon size={20} strokeWidth={2.25} />
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
          {!loading && (
            <span className="metric-badge" style={{ color: card.accent, background: card.accentBg }}>
              <card.badgeIcon size={12} strokeWidth={2.5} />
              {card.badgeText}
            </span>
          )}
        </div>
      ))}
    </section>
  )
}
