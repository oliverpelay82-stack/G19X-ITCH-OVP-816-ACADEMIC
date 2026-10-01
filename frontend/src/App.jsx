import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Header from './components/Header.jsx'
import MetricsCards from './components/MetricsCards.jsx'
import TitularesTab from './components/TitularesTab.jsx'
import ExpedientesTab from './components/ExpedientesTab.jsx'
import BovedaTab from './components/BovedaTab.jsx'
import ReglasTab from './components/ReglasTab.jsx'
import AlertasTab from './components/AlertasTab.jsx'
import ReportesTab from './components/ReportesTab.jsx'
import useToast from './hooks/useToast.js'
import useTheme from './hooks/useTheme.js'
import useRuta from './hooks/useRuta.js'
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

/**
 * Título de cada sección y su grupo de navegación. Las migas tienen dos
 * niveles (Grupo › Sección), igual que la barra lateral.
 */
const SECCIONES = {
  titulares: { titulo: 'Empresas', grupo: 'Cumplimiento', miga: 'Empresas' },
  expedientes: { titulo: 'Expedientes', grupo: 'Cumplimiento', miga: 'Expedientes' },
  boveda: { titulo: 'Bóveda criptográfica', grupo: 'Cumplimiento', miga: 'Bóveda' },
  alertas: { titulo: 'Alertas y recomendaciones', grupo: 'Auditoría', miga: 'Alertas' },
  reportes: { titulo: 'Reportes de cumplimiento', grupo: 'Auditoría', miga: 'Reportes' },
  reglas: { titulo: 'Catálogo de reglas', grupo: 'Configuración', miga: 'Reglas' },
}

/** Sección a la que lleva el clic en el grupo de las migas. */
const INICIO_GRUPO = { Cumplimiento: 'expedientes', Auditoría: 'alertas', Configuración: 'reglas' }

/**
 * Las tarjetas de métricas solo acompañan a las vistas de seguimiento. En
 * Empresas, Bóveda, Alertas y Reglas ocupaban la primera sexta parte de la
 * pantalla a 1366 × 768 sin aportar a la tarea (revisión del frontend, Lote 3).
 * Reportes las monta él mismo, bajo la barra del reporte global.
 */
const CON_METRICAS = new Set(['expedientes'])

const INTERVALO_REFRESCO = 15000

/** Duración mínima del giro del botón de refresco, para que el clic se perciba. */
const REFRESCO_MINIMO_MS = 600

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

/** `online: null` significa "aún sin sondear" (la cabecera lo muestra en gris). */
const HEALTH_INICIAL = {
  core: { online: null, latencia: null, payload: null },
  rules: { online: null, latencia: null, payload: null },
  ai: { online: null, latencia: null, payload: null },
}

export default function App() {
  const toast = useToast()
  const { isDark, toggleTheme } = useTheme()

  // La URL es la fuente de verdad de la sección y del expediente desplegado.
  const [ruta, ir] = useRuta()
  const tabActiva = ruta.seccion
  const setTabActiva = useCallback((seccion) => ir(seccion), [ir])
  const [health, setHealth] = useState(HEALTH_INICIAL)
  const [loading, setLoading] = useState(true)
  const [refrescando, setRefrescando] = useState(false)

  const [titulares, setTitulares] = useState([])
  const [expedientes, setExpedientes] = useState([])
  const [documentos, setDocumentos] = useState([])
  const [reglas, setReglas] = useState([])
  // Titular para el que se pidió aperturar un expediente desde Empresas.
  const [aperturaTitular, setAperturaTitular] = useState(null)

  // Evita avisar de la misma caída en cada ciclo de sondeo.
  const caidasAvisadas = useRef(new Set())
  const primeraCarga = useRef(true)
  const cicloEnCurso = useRef(false)

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
      await Promise.all([cargarTodo(), chequearSalud(), new Promise((r) => setTimeout(r, REFRESCO_MINIMO_MS))])
    } finally {
      setRefrescando(false)
    }
  }, [cargarTodo, chequearSalud])

  useEffect(() => {
    let montado = true

    // Un solo ciclo de sondeo, reutilizado por la carga inicial y el intervalo.
    // Al ser asíncrono, ningún setState ocurre durante el propio efecto. Si el
    // ciclo anterior sigue esperando a un servicio lento, el siguiente no se
    // apila sobre él (las lecturas del sondeo además caducan a los 10 s). La
    // marca vive en una ref para valer también entre montajes del efecto.
    const ciclo = async () => {
      if (cicloEnCurso.current) return
      cicloEnCurso.current = true
      try {
        await Promise.all([cargarTodo(), chequearSalud()])
      } finally {
        cicloEnCurso.current = false
      }
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
      alertas: expedientes.reduce((n, e) => n + (e.evaluacion?.alertas?.length || 0), 0),
      reglas: reglas.length,
    }),
    [titulares, expedientes, documentos, reglas]
  )

  const seccion = SECCIONES[tabActiva]
  const migas = [
    { id: INICIO_GRUPO[seccion.grupo] === tabActiva ? null : INICIO_GRUPO[seccion.grupo], label: seccion.grupo },
    { id: tabActiva, label: seccion.miga },
  ]

  // Expediente desplegado según la URL (#/expedientes/<folio>), una vez cargada la lista.
  const focoExpediente = useMemo(
    () => (ruta.folio ? expedientes.find((e) => e.codigo_expediente === ruta.folio)?.id ?? null : null),
    [ruta.folio, expedientes]
  )
  const folioDe = useCallback(
    (expedienteId) => expedientes.find((e) => e.id === expedienteId)?.codigo_expediente ?? null,
    [expedientes]
  )

  // Desde Empresas o Alertas: una entrada nueva del historial («Atrás» regresa).
  const abrirExpediente = useCallback((expedienteId) => ir('expedientes', folioDe(expedienteId)), [ir, folioDe])
  // Desplegar o plegar en la lista: sustituye la entrada, no la acumula. Un
  // expediente recién aperturado llega con su folio (aún no está en la lista).
  const alternarExpediente = useCallback(
    (expedienteId, folio = null) =>
      ir('expedientes', expedienteId ? folio || folioDe(expedienteId) : null, { reemplazar: true }),
    [ir, folioDe]
  )

  const aperturarExpediente = useCallback(
    (titularId) => {
      setAperturaTitular(titularId)
      ir('expedientes')
    },
    [ir]
  )

  useEffect(() => {
    document.title = `${seccion.titulo} · PluriOne`
  }, [seccion.titulo])

  return (
    <div className="app-shell">
      <Sidebar tabActiva={tabActiva} onTabChange={setTabActiva} contadores={contadores} />

      <div className="app-main">
        <Header
          titulo={seccion.titulo}
          migas={migas}
          onNavigate={setTabActiva}
          health={health}
          reglas={reglas}
          onRefresh={refrescar}
          refrescando={refrescando}
          isDark={isDark}
          onToggleTheme={toggleTheme}
        />

        <main className="app-content">
          {CON_METRICAS.has(tabActiva) && (
            <MetricsCards titulares={titulares} expedientes={expedientes} documentos={documentos} loading={loading} />
          )}

          <div className="tab-region" key={tabActiva}>
            {tabActiva === 'titulares' && (
              <TitularesTab
                titulares={titulares}
                expedientes={expedientes}
                onAbrirExpediente={abrirExpediente}
                onAperturarExpediente={aperturarExpediente}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.core.online}
              />
            )}
            {tabActiva === 'expedientes' && (
              <ExpedientesTab
                expedientes={expedientes}
                titulares={titulares}
                loading={loading}
                onRefresh={refrescar}
                isOnline={health.core.online}
                iaOnline={health.ai.online}
                documentos={documentos}
                foco={focoExpediente}
                onAlternar={alternarExpediente}
                apertura={aperturaTitular}
                onAperturaAtendida={() => setAperturaTitular(null)}
              />
            )}
            {tabActiva === 'alertas' && (
              <AlertasTab expedientes={expedientes} loading={loading} onAbrirExpediente={abrirExpediente} />
            )}
            {tabActiva === 'reportes' && (
              <ReportesTab
                expedientes={expedientes}
                titulares={titulares}
                documentos={documentos}
                loading={loading}
                isOnline={health.core.online}
                onAbrirExpediente={abrirExpediente}
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
