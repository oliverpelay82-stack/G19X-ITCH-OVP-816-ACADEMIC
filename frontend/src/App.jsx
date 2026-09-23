import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Header from './components/Header.jsx'
import MetricsCards from './components/MetricsCards.jsx'
import MotorIaPanel from './components/MotorIaPanel.jsx'
import TitularesTab from './components/TitularesTab.jsx'
import ExpedientesTab from './components/ExpedientesTab.jsx'
import BovedaTab from './components/BovedaTab.jsx'
import ReglasTab from './components/ReglasTab.jsx'
import useToast from './hooks/useToast.js'
import useTheme from './hooks/useTheme.js'
import {
  getDocumentos,
  getExpedientes,
  getHealthAi,
  getHealthCore,
  getHealthRules,
  getReglas,
  getTitulares,
} from './services/api.js'
import './App.css'

const SECCIONES = {
  titulares: { titulo: 'Empresas' },
  expedientes: { titulo: 'Expedientes' },
  boveda: { titulo: 'Bóveda criptográfica' },
  reglas: { titulo: 'Catálogo de reglas' },
}

const INTERVALO_REFRESCO = 15000

/** Mide la latencia de un health check sin alterar el cliente HTTP. */
async function sondear(fn) {
  const inicio = performance.now()
  try {
    const payload = await fn()
    return { online: true, latencia: Math.round(performance.now() - inicio), payload }
  } catch {
    return { online: false, latencia: null, payload: null }
  }
}

const HEALTH_INICIAL = {
  core: { online: false, latencia: null, payload: null },
  rules: { online: false, latencia: null, payload: null },
  ai: { online: false, latencia: null, payload: null },
}

export default function App() {
  const toast = useToast()
  const { isDark, toggleTheme } = useTheme()

  const [tabActiva, setTabActiva] = useState('titulares')
  const [health, setHealth] = useState(HEALTH_INICIAL)
  const [loading, setLoading] = useState(true)
  const [refrescando, setRefrescando] = useState(false)

  const [titulares, setTitulares] = useState([])
  const [expedientes, setExpedientes] = useState([])
  const [documentos, setDocumentos] = useState([])
  const [reglas, setReglas] = useState([])

  // Evita avisar de la misma caída en cada ciclo de sondeo.
  const caidasAvisadas = useRef(new Set())
  const primeraCarga = useRef(true)

  const cargarTodo = useCallback(async () => {
    const [t, e, d, r] = await Promise.allSettled([
      getTitulares(),
      getExpedientes(),
      getDocumentos(),
      getReglas(),
    ])
    if (t.status === 'fulfilled') setTitulares(t.value || [])
    if (e.status === 'fulfilled') setExpedientes(e.value || [])
    if (d.status === 'fulfilled') setDocumentos(d.value || [])
    setReglas(r.status === 'fulfilled' ? r.value || [] : [])
    setLoading(false)
  }, [])

  const chequearSalud = useCallback(async () => {
    const [core, rules, ai] = await Promise.all([
      sondear(getHealthCore),
      sondear(getHealthRules),
      sondear(getHealthAi),
    ])
    const siguiente = { core, rules, ai }
    setHealth(siguiente)

    if (!primeraCarga.current) {
      for (const [clave, estado] of Object.entries(siguiente)) {
        if (!estado.online && !caidasAvisadas.current.has(clave)) {
          caidasAvisadas.current.add(clave)
          toast.alerta(
            `Microservicio ${clave} sin respuesta`,
            'El resto del sistema sigue operando con normalidad.'
          )
        }
        if (estado.online && caidasAvisadas.current.has(clave)) {
          caidasAvisadas.current.delete(clave)
          toast.exito(`Microservicio ${clave} restablecido`, `Latencia ${estado.latencia} ms`)
        }
      }
    }
    primeraCarga.current = false
  }, [toast])

  const refrescar = useCallback(async () => {
    setRefrescando(true)
    try {
      await Promise.all([cargarTodo(), chequearSalud()])
    } finally {
      setRefrescando(false)
    }
  }, [cargarTodo, chequearSalud])

  useEffect(() => {
    let montado = true

    // Un solo ciclo de sondeo, reutilizado por la carga inicial y el intervalo.
    // Al ser asíncrono, ningún setState ocurre durante el propio efecto.
    const ciclo = async () => {
      await Promise.all([cargarTodo(), chequearSalud()])
    }

    ciclo()
    const id = setInterval(() => {
      if (montado) ciclo()
    }, INTERVALO_REFRESCO)

    return () => {
      montado = false
      clearInterval(id)
    }
  }, [cargarTodo, chequearSalud])

  const contadores = useMemo(
    () => ({
      titulares: titulares.length,
      expedientes: expedientes.length,
      boveda: documentos.length,
      reglas: reglas.length,
    }),
    [titulares, expedientes, documentos, reglas]
  )

  const seccion = SECCIONES[tabActiva]

  return (
    <div className="app-shell">
      <Sidebar tabActiva={tabActiva} onTabChange={setTabActiva} health={health} contadores={contadores} />

      <div className="app-main">
        <Header
          titulo={seccion.titulo}
          onRefresh={refrescar}
          refrescando={refrescando}
          isDark={isDark}
          onToggleTheme={toggleTheme}
        />

        <main className="app-content">
          <MetricsCards
            titulares={titulares}
            expedientes={expedientes}
            documentos={documentos}
            loading={loading}
          />

          <MotorIaPanel estado={health.ai} loading={loading} />

          <div className="tab-region" key={tabActiva}>
            {tabActiva === 'titulares' && (
              <TitularesTab
                titulares={titulares}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.core.online}
              />
            )}
            {tabActiva === 'expedientes' && (
              <ExpedientesTab
                expedientes={expedientes}
                titulares={titulares}
                documentos={documentos}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.core.online}
              />
            )}
            {tabActiva === 'boveda' && (
              <BovedaTab
                documentos={documentos}
                expedientes={expedientes}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.core.online}
                iaOnline={health.ai.online}
              />
            )}
            {tabActiva === 'reglas' && (
              <ReglasTab
                reglas={reglas}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.rules.online}
              />
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
