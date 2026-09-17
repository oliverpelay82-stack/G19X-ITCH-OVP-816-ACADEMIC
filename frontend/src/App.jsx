import { useCallback, useEffect, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import MetricsCards from './components/MetricsCards.jsx'
import TitularesTab from './components/TitularesTab.jsx'
import ExpedientesTab from './components/ExpedientesTab.jsx'
import BovedaTab from './components/BovedaTab.jsx'
import ReglasTab from './components/ReglasTab.jsx'
import { getStatus, getTitulares, getExpedientes, getDocumentos, getReglas } from './services/api.js'
import './App.css'

export default function App() {
  const [tabActiva, setTabActiva] = useState('titulares')
  const [backendOnline, setBackendOnline] = useState(false)
  const [loading, setLoading] = useState(true)

  const [titulares, setTitulares] = useState([])
  const [expedientes, setExpedientes] = useState([])
  const [documentos, setDocumentos] = useState([])
  const [reglas, setReglas] = useState([])

  const cargarTodo = useCallback(async () => {
    try {
      const [status, t, e, d, r] = await Promise.all([
        getStatus(),
        getTitulares(),
        getExpedientes(),
        getDocumentos(),
        getReglas(),
      ])
      setBackendOnline(Boolean(status))
      setTitulares(t || [])
      setExpedientes(e || [])
      setDocumentos(d || [])
      setReglas(r || [])
    } catch {
      setBackendOnline(false)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    cargarTodo()
    const interval = setInterval(cargarTodo, 15000)
    return () => clearInterval(interval)
  }, [cargarTodo])

  return (
    <div className="app-shell">
      <Sidebar tabActiva={tabActiva} onTabChange={setTabActiva} backendOnline={backendOnline} />

      <main className="app-main">
        <MetricsCards titulares={titulares} expedientes={expedientes} documentos={documentos} loading={loading} />

        <div className="tabs-content">
          {tabActiva === 'titulares' && (
            <TitularesTab titulares={titulares} loading={loading} onRefresh={cargarTodo} />
          )}
          {tabActiva === 'expedientes' && (
            <ExpedientesTab expedientes={expedientes} titulares={titulares} loading={loading} onRefresh={cargarTodo} />
          )}
          {tabActiva === 'boveda' && (
            <BovedaTab documentos={documentos} expedientes={expedientes} loading={loading} onRefresh={cargarTodo} />
          )}
          {tabActiva === 'reglas' && <ReglasTab reglas={reglas} loading={loading} onRefresh={cargarTodo} />}
        </div>
      </main>
    </div>
  )
}
