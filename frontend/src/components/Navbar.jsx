import { ShieldCheck, Database } from 'lucide-react'

/**
 * Cabecera corporativa: branding oficial, status dot de conectividad MySQL
 * y badge de alcance del producto (B2B Compliance).
 */
export default function Navbar({ backendOnline }) {
  return (
    <header className="navbar">
      <div className="navbar-brand">
        <div className="navbar-logo">
          <ShieldCheck size={20} strokeWidth={2.25} />
        </div>
        <div className="navbar-titles">
          <span className="navbar-title">Motor de Validación de Cumplimiento Documental</span>
          <span className="navbar-subtitle">PluriOne S.A. de C.V. · Develop Talent &amp; Technology</span>
        </div>
      </div>

      <div className="navbar-actions">
        <span className="navbar-badge">
          <Database size={13} strokeWidth={2.25} />
          B2B Compliance
        </span>

        <span className={`status-pill ${backendOnline ? 'status-pill--ok' : 'status-pill--off'}`}>
          <span className={`status-dot ${backendOnline ? 'status-dot--ok' : 'status-dot--off'}`} />
          {backendOnline ? 'MySQL Conectado' : 'Backend Desconectado'}
        </span>
      </div>
    </header>
  )
}
