import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import { ChevronLeft, ChevronRight, Loader2, ScanText, X } from 'lucide-react'
import { Badge, IconButton, Segmented } from './ui/index.js'
import { getVisorDocumento, urlPaginaDocumento } from '../services/api.js'

const ZOOMS = [
  { id: 1, label: 'Ajustar' },
  { id: 1.5, label: '150%' },
  { id: 2, label: '200%' },
]

/** Ancho de la imagen que se pide: el del visor por el zoom y la densidad de la pantalla, en pasos de 200 px. */
function anchoSolicitado(contenedor, zoom) {
  const base = (contenedor || 600) * zoom * Math.min(window.devicePixelRatio || 1, 2)
  return Math.min(2000, Math.max(400, Math.ceil(base / 200) * 200))
}

/** Estado de la búsqueda de una cita, en palabras del analista. */
function AvisoEvidencia({ estado, onIrA, paginaActual }) {
  if (!estado) return null
  if (estado.pagina) {
    return (
      <p className="visor-aviso visor-aviso--neutral">
        Página {estado.pagina}: fragmento que el modelo consultó para responder.
      </p>
    )
  }
  if (estado.buscando) {
    return (
      <p className="visor-aviso" role="status">
        <Loader2 className="spin" size={13} aria-hidden="true" />
        Ubicando la cita en el documento… en un escaneo, la primera búsqueda reconoce las páginas.
      </p>
    )
  }
  if (estado.error) return <p className="visor-aviso visor-aviso--warn">{estado.error}</p>
  if (estado.zonas) {
    const n = estado.resultado?.recuadros?.length || 0
    return (
      <p className="visor-aviso visor-aviso--neutral">
        {n === 1 ? 'Sello en tinta de color' : `${n} sellos en tinta de color`} detectado{n === 1 ? '' : 's'} en la
        página {estado.resultado?.pagina}. El sello forma parte del documento original; su texto no se transcribe.
      </p>
    )
  }
  const r = estado.resultado
  if (!r?.encontrada) {
    return (
      <p className="visor-aviso visor-aviso--neutral">
        La cita no se localizó en las páginas del documento ({r?.paginas_revisadas ?? 0} revisadas). Consúltala en el
        texto extraído: el visor no resalta nada que no pueda ubicar.
      </p>
    )
  }
  const paginas = [...new Set(r.recuadros.map((x) => x.pagina))]
  const tono = r.aproximada || !r.completa ? 'warn' : 'ok'
  return (
    <div className={`visor-aviso visor-aviso--${tono}`} role="status">
      <span>
        {!r.completa
          ? 'Solo se ubicó una parte de la cita.'
          : r.aproximada
            ? 'Ubicación aproximada: el reconocimiento de la imagen difiere un poco del texto analizado.'
            : 'Evidencia localizada en el documento.'}
      </span>
      {paginas.length > 1 && (
        <span className="visor-aviso-paginas">
          Páginas:
          {paginas.map((n) => (
            <button
              key={n}
              type="button"
              className={`chip chip--xs ${n === paginaActual ? 'is-active' : ''}`}
              onClick={() => onIrA(n)}
            >
              {n}
            </button>
          ))}
        </span>
      )}
    </div>
  )
}

/**
 * Visor del documento con la evidencia resaltada (HU-20, RF-13). Muestra el
 * archivo página por página, renderizado por el ai-service desde el binario
 * verificado (RIE-03), y al recibir una cita la ubica —en la capa de texto o
 * con las coordenadas del OCR— y la resalta con un recuadro por renglón. Un
 * recuadro punteado indica una ubicación aproximada.
 *
 * `busqueda`: la última petición, { clave } más `pagina` (ir a una página) o
 * una cita: `tono` con `buscando`, `resultado` (respuesta de /localizar) o
 * `error`. La búsqueda la hace quien recibe el clic; el visor solo salta a la
 * página y dibuja los recuadros.
 */
export default function VisorDocumento({ doc, busqueda, onCerrar }) {
  const [info, setInfo] = useState(null)
  const [errorInfo, setErrorInfo] = useState('')
  const [pagina, setPagina] = useState(1)
  const [zoom, setZoom] = useState(1)
  const [cargando, setCargando] = useState(true)
  const [errorImagen, setErrorImagen] = useState(false)
  const [anchoVisor, setAnchoVisor] = useState(600)
  const [claveVista, setClaveVista] = useState(null)
  const lienzo = useRef(null)
  const primerRecuadro = useRef(null)

  useEffect(() => {
    let vigente = true
    getVisorDocumento(doc.id)
      .then((r) => vigente && setInfo(r))
      .catch((err) => vigente && setErrorInfo(err?.message || 'No se pudo abrir el documento.'))
    return () => {
      vigente = false
    }
  }, [doc.id])

  useLayoutEffect(() => {
    const el = lienzo.current
    if (!el) return undefined
    const observador = new ResizeObserver(([entrada]) => setAnchoVisor(entrada.contentRect.width))
    observador.observe(el)
    return () => observador.disconnect()
  }, [])

  // Cada resultado nuevo lleva el visor a la página de la cita. Se ajusta el
  // estado durante el render (y no en un efecto) para no pintar la página vieja.
  const resultado = busqueda?.resultado
  const destino = resultado?.encontrada ? resultado.pagina : busqueda?.pagina
  if ((resultado || busqueda?.pagina) && busqueda.clave !== claveVista) {
    setClaveVista(busqueda.clave)
    // Solo una página distinta vuelve a cargar imagen; la misma no dispara onLoad.
    if (destino && destino !== pagina) {
      setCargando(true)
      setErrorImagen(false)
      setPagina(destino)
    }
  }

  const recuadros = (resultado?.recuadros || []).filter((r) => r.pagina === pagina)
  const hayRecuadros = recuadros.length > 0

  // Con la página cargada, el primer recuadro se desplaza a la vista.
  useEffect(() => {
    if (!cargando && hayRecuadros) primerRecuadro.current?.scrollIntoView({ block: 'center', behavior: 'smooth' })
  }, [cargando, hayRecuadros, claveVista, pagina])

  const total = info?.total_paginas || 0
  const datosPagina = info?.paginas?.[pagina - 1]
  const irA = (n) => {
    if (n < 1 || n > total || n === pagina) return
    setCargando(true)
    setErrorImagen(false)
    setPagina(n)
  }
  const alTeclear = (e) => {
    if (e.key === 'ArrowRight') irA(pagina + 1)
    if (e.key === 'ArrowLeft') irA(pagina - 1)
  }
  const ancho = anchoSolicitado(anchoVisor, zoom)
  const tono = busqueda?.tono || 'ok'

  return (
    <section className="visor" aria-label="Visor del documento" onKeyDown={alTeclear}>
      <header className="visor-head">
        <div className="visor-titulo">
          <span className="squircle" aria-hidden="true">
            <ScanText size={14} />
          </span>
          <div>
            <p className="eyebrow">Documento original</p>
            <p className="visor-meta">
              {total ? `Página ${pagina} de ${total}` : 'Cargando…'}
              {datosPagina && (
                <Badge>{datosPagina.metodo === 'VECTORIAL' ? 'Capa de texto' : 'Escaneo · OCR'}</Badge>
              )}
            </p>
          </div>
        </div>
        <IconButton etiqueta="Cerrar el visor" compacto onClick={onCerrar}>
          <X size={15} />
        </IconButton>
      </header>

      <div className="visor-controles">
        <div className="visor-paginacion">
          <IconButton etiqueta="Página anterior" compacto onClick={() => irA(pagina - 1)} disabled={pagina <= 1}>
            <ChevronLeft size={15} />
          </IconButton>
          <span className="tabular visor-contador">
            {total ? `${pagina} / ${total}` : '— / —'}
          </span>
          <IconButton etiqueta="Página siguiente" compacto onClick={() => irA(pagina + 1)} disabled={!total || pagina >= total}>
            <ChevronRight size={15} />
          </IconButton>
        </div>
        <Segmented label="Zoom del visor" valor={zoom} onChange={setZoom} opciones={ZOOMS} />
      </div>

      <AvisoEvidencia estado={busqueda} onIrA={irA} paginaActual={pagina} />

      <div className="visor-lienzo" ref={lienzo} tabIndex={0} aria-label={`Página ${pagina} del documento`}>
        {errorInfo ? (
          <p className="visor-aviso visor-aviso--warn">{errorInfo}</p>
        ) : (
          info && (
            <div
              className="visor-pagina"
              style={{
                width: `${zoom * 100}%`,
                aspectRatio: datosPagina ? `${datosPagina.ancho} / ${datosPagina.alto}` : undefined,
              }}
            >
              {cargando && <div className="visor-cargando skeleton" aria-hidden="true" />}
              {errorImagen ? (
                <p className="visor-aviso visor-aviso--warn">No se pudo mostrar la página {pagina}.</p>
              ) : (
                <img
                  key={`${pagina}-${ancho}`}
                  src={urlPaginaDocumento(doc.id, pagina, ancho)}
                  alt={`Página ${pagina} de ${doc.nombre_archivo_original}`}
                  onLoad={() => setCargando(false)}
                  onError={() => {
                    setCargando(false)
                    setErrorImagen(true)
                  }}
                  draggable={false}
                />
              )}
              {!cargando &&
                recuadros.map((r, i) => (
                  <span
                    key={`${r.pagina}-${r.x0}-${r.y0}`}
                    ref={i === 0 ? primerRecuadro : undefined}
                    className={`visor-recuadro visor-recuadro--${r.aproximada ? 'warn' : tono} ${
                      r.aproximada ? 'visor-recuadro--aprox' : ''
                    }`}
                    style={{
                      left: `${r.x0 * 100}%`,
                      top: `${r.y0 * 100}%`,
                      width: `${(r.x1 - r.x0) * 100}%`,
                      height: `${(r.y1 - r.y0) * 100}%`,
                    }}
                    aria-hidden="true"
                  />
                ))}
            </div>
          )
        )}
      </div>
    </section>
  )
}
