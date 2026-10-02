import { lazy, Suspense, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import Sidebar from './components/Sidebar.jsx'
import Header from './components/Header.jsx'
import MetricsCards from './components/MetricsCards.jsx'
import ExpedientesTab from './components/ExpedientesTab.jsx'
import { SkeletonRows } from './components/Skeleton.jsx'
import PaletaComandos from './components/PaletaComandos.jsx'
import ErrorVista from './components/ErrorVista.jsx'
import useToast from './hooks/useToast.js'
import useTheme from './hooks/useTheme.js'
import useRuta from './hooks/useRuta.js'
import { registrarTiposDeclarados } from './constants.js'
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

// Carga por vista: Expedientes es la de inicio y va en el paquete principal; las
// demás se descargan al abrirlas. Reportes trae las gráficas (Recharts), que así
// no pesan en el resto del sistema.
const TitularesTab = lazy(() => import('./components/TitularesTab.jsx'))
const BovedaTab = lazy(() => import('./components/BovedaTab.jsx'))
const ReglasTab = lazy(() => import('./components/ReglasTab.jsx'))
const AlertasTab = lazy(() => import('./components/AlertasTab.jsx'))
const ReportesTab = lazy(() => import('./components/ReportesTab.jsx'))

/** Mientras llega el código de una vista: el mismo esqueleto de las tablas, sin aviso. */
function CargandoVista() {
  return (
    <table className="data-table" aria-busy="true" aria-label="Cargando la vista">
      <tbody>
        <SkeletonRows rows={5} cols={4} />
      </tbody>
    </table>
  )
}

/**
 * Título de cada sección y su grupo de navegación. Las migas tienen dos
 * niveles (Grupo › Sección), igual que la barra lateral.
 */
const SECCIONES = {
  titulares: { titulo: 'Empresas', grupo: 'Cumplimiento', miga: 'Empresas' },
  expedientes: { titulo: 'Expedientes', grupo: 'Cumplimiento', miga: 'Expedientes' },
  boveda: { titulo: 'Bóveda', grupo: 'Cumplimiento', miga: 'Bóveda' },
  alertas: { titulo: 'Alertas', grupo: 'Auditoría', miga: 'Alertas' },
  reportes: { titulo: 'Reportes', grupo: 'Auditoría', miga: 'Reportes' },
  reglas: { titulo: 'Reglas', grupo: 'Configuración', miga: 'Reglas' },
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

/** Nombre de cada servicio en lenguaje llano, para los avisos de caída (RNF-08). */
const SERVICIO_LLANO = {
  core: 'El sistema de expedientes',
  rules: 'El catálogo de reglas',
  ai: 'El servicio de análisis con IA',
}

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

  // Momento de la última carga con datos: la cabecera dice «Actualizado hace…».
  const [actualizado, setActualizado] = useState(null)

  const cargarTodo = useCallback(async () => {
    const [t, e, d, r] = await Promise.allSettled([
      getTitulares(),
      getExpedientes(),
      getDocumentos(),
      getReglas(),
    ])
    if ([t, e, d].some((x) => x.status === 'fulfilled')) setActualizado(Date.now())
    if (t.status === 'fulfilled') setTitulares(t.value || [])
    if (e.status === 'fulfilled') setExpedientes(e.value || [])
    if (d.status === 'fulfilled') setDocumentos(d.value || [])
    if (r.status === 'fulfilled') registrarTiposDeclarados(r.value || []) // RF-09: antes de pintar
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
            `${SERVICIO_LLANO[clave] || 'Un servicio'} no responde`,
            'El resto del sistema sigue operando con normalidad.'
          )
        }
        if (estado.online && caidasAvisadas.current.has(clave)) {
          caidasAvisadas.current.delete(clave)
          toast.exito(`${SERVICIO_LLANO[clave] || 'Un servicio'} vuelve a responder`, `Latencia ${estado.latencia} ms`)
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
    // Con la pestaña oculta no se sondea; al volver se refresca de inmediato,
    // así nunca se muestra información vieja.
    const id = setInterval(() => {
      if (montado && !document.hidden) ciclo()
    }, INTERVALO_REFRESCO)
    const alVolver = () => {
      if (montado && !document.hidden) ciclo()
    }
    document.addEventListener('visibilitychange', alVolver)

    return () => {
      montado = false
      clearInterval(id)
      document.removeEventListener('visibilitychange', alVolver)
    }
  }, [cargarTodo, chequearSalud])

  // Atajo «/»: lleva el foco al buscador de la vista, salvo mientras se escribe o con un modal abierto.
  useEffect(() => {
    const alPulsar = (e) => {
      if (e.key !== '/' || e.ctrlKey || e.metaKey || e.altKey) return
      if (e.target.closest?.('input, textarea, select, [contenteditable="true"]') || document.querySelector('.modal')) return
      const buscador = document.querySelector('.app-content input[type="search"]')
      if (!buscador) return
      e.preventDefault()
      buscador.focus()
    }
    document.addEventListener('keydown', alPulsar)
    return () => document.removeEventListener('keydown', alPulsar)
  }, [])

  // En el menú solo cuenta lo que pide acción: las alertas, en tono de
  // advertencia si alguna es crítica o alta.
  const contadores = useMemo(() => {
    const alertas = expedientes.flatMap((e) => e.evaluacion?.alertas || [])
    return {
      alertas: {
        total: alertas.length,
        tono: alertas.some((a) => a.severidad === 'CRITICA' || a.severidad === 'ALTA') ? 'warn' : undefined,
      },
    }
  }, [expedientes])

  const seccion = SECCIONES[tabActiva]
  // Detalle de una empresa (#/empresas/<RFC>): una tercera miga con su razón social.
  const empresaAbierta =
    tabActiva === 'titulares' && ruta.folio ? titulares.find((t) => t.rfc === ruta.folio) ?? null : null
  const migas = [
    { id: INICIO_GRUPO[seccion.grupo] === tabActiva ? null : INICIO_GRUPO[seccion.grupo], label: seccion.grupo },
    { id: empresaAbierta ? tabActiva : null, label: seccion.miga },
    ...(empresaAbierta ? [{ id: null, label: empresaAbierta.razon_social }] : []),
  ]

  // Expediente desplegado según la URL (#/expedientes/<folio>), una vez cargada la lista.
  const focoExpediente = useMemo(
    () =>
      ruta.seccion === 'expedientes' && ruta.folio
        ? expedientes.find((e) => e.codigo_expediente === ruta.folio)?.id ?? null
        : null,
    [ruta.seccion, ruta.folio, expedientes]
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

  const verEmpresa = useCallback((rfc) => ir('titulares', rfc), [ir])

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

  // D1: Ctrl+K (⌘K en Mac) abre o cierra la paleta de comandos desde cualquier vista.
  const [paletaAbierta, setPaletaAbierta] = useState(false)
  useEffect(() => {
    const alPulsar = (e) => {
      if ((e.ctrlKey || e.metaKey) && !e.altKey && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setPaletaAbierta((abierta) => !abierta)
      }
    }
    window.addEventListener('keydown', alPulsar)
    return () => window.removeEventListener('keydown', alPulsar)
  }, [])

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
          actualizado={actualizado}
          isDark={isDark}
          onToggleTheme={toggleTheme}
          onAbrirPaleta={() => setPaletaAbierta(true)}
        />

        <main className="app-content">
          {CON_METRICAS.has(tabActiva) && (
            <MetricsCards titulares={titulares} expedientes={expedientes} documentos={documentos} loading={loading} />
          )}

          <div className="tab-region" key={tabActiva}>
            <ErrorVista key={tabActiva}>
            <Suspense fallback={<CargandoVista />}>
            {tabActiva === 'titulares' && (
              <TitularesTab
                titulares={titulares}
                expedientes={expedientes}
                onAbrirExpediente={abrirExpediente}
                onAperturarExpediente={aperturarExpediente}
                rfcAbierto={tabActiva === 'titulares' ? ruta.folio : null}
                onVerEmpresa={verEmpresa}
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
            </Suspense>
            </ErrorVista>
          </div>
        </main>
        {paletaAbierta && (
          <PaletaComandos
            onCerrar={() => setPaletaAbierta(false)}
            secciones={SECCIONES}
            titulares={titulares}
            expedientes={expedientes}
            documentos={documentos}
            onIr={setTabActiva}
            onVerEmpresa={verEmpresa}
            onAbrirExpediente={abrirExpediente}
            isDark={isDark}
            onToggleTheme={toggleTheme}
            onRefresh={refrescar}
          />
        )}
      </div>
    </div>
  )
}
