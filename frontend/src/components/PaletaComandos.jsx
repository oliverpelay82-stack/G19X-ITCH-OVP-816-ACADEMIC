import { useEffect, useId, useMemo, useRef, useState } from 'react'
import { createPortal } from 'react-dom'
import { CornerDownLeft, FileText, FolderOpen, Moon, Navigation, RefreshCw, Search, Sun } from 'lucide-react'
import { getEstadoBadge, TIPO_DOCUMENTO_LABEL, TIPO_EXPEDIENTE_LABEL } from '../constants.js'
import { coincide, normalizar } from '../utils/busqueda.js'

const POR_GRUPO = 6

/**
 * D1 · Paleta de comandos (Ctrl+K o ⌘K): saltar a un expediente por folio,
 * nombre, empresa o RFC; a un documento por su archivo; a una sección; o
 * cambiar el tema y actualizar los datos, sin el ratón. ↑/↓ recorren, Intro
 * ejecuta y Escape cierra; el foco vuelve a donde estaba.
 */
export default function PaletaComandos({ onCerrar, secciones, expedientes, documentos, onIr, onAbrirExpediente, isDark, onToggleTheme, onRefresh }) {
  const [texto, setTexto] = useState('')
  const [activo, setActivo] = useState(0)
  const campo = useRef(null)
  const lista = useRef(null)
  const id = useId()

  const grupos = useMemo(() => {
    const q = normalizar(texto)
    const porId = new Map(expedientes.map((e) => [e.id, e]))
    const filtrar = (items) => items.filter((i) => coincide(i.busqueda, q)).slice(0, POR_GRUPO)
    const acciones = [
      {
        clave: 'tema',
        icono: isDark ? Sun : Moon,
        titulo: isDark ? 'Cambiar a tema claro' : 'Cambiar a tema oscuro',
        busqueda: 'tema claro oscuro noche dia apariencia',
        ejecutar: onToggleTheme,
      },
      { clave: 'refrescar', icono: RefreshCw, titulo: 'Actualizar los datos', busqueda: 'actualizar refrescar recargar datos', ejecutar: onRefresh },
    ]
    const irA = Object.entries(secciones).map(([clave, s]) => ({
      clave: `ir-${clave}`,
      icono: Navigation,
      titulo: `Ir a ${s.titulo}`,
      sub: s.grupo,
      busqueda: `ir a ${s.titulo} ${s.grupo}`,
      ejecutar: () => onIr(clave),
    }))
    const deExpedientes = expedientes.map((e) => ({
      clave: `exp-${e.id}`,
      icono: FolderOpen,
      titulo: e.titular?.razon_social || e.codigo_expediente,
      sub: `${e.codigo_expediente} · ${TIPO_EXPEDIENTE_LABEL[e.tipo_expediente] || e.tipo_expediente} · ${getEstadoBadge(e.estado_cumplimiento).label}`,
      busqueda: [e.codigo_expediente, e.nombre, e.titular?.razon_social, e.titular?.rfc].filter(Boolean).join(' '),
      ejecutar: () => onAbrirExpediente(e.id),
    }))
    const deDocumentos = documentos.map((d) => {
      const exp = porId.get(d.expediente_id)
      return {
        clave: `doc-${d.id}`,
        icono: FileText,
        titulo: d.nombre_archivo_original,
        sub: [TIPO_DOCUMENTO_LABEL[d.tipo_documento] || d.tipo_documento, exp?.codigo_expediente].filter(Boolean).join(' · '),
        busqueda: [d.nombre_archivo_original, TIPO_DOCUMENTO_LABEL[d.tipo_documento], exp?.codigo_expediente].filter(Boolean).join(' '),
        ejecutar: () => onAbrirExpediente(d.expediente_id),
      }
    })
    // Sin texto: lo que se usa para moverse. Con texto: primero lo buscado.
    return (q
      ? [
          { titulo: 'Expedientes', items: filtrar(deExpedientes) },
          { titulo: 'Documentos', items: filtrar(deDocumentos) },
          { titulo: 'Ir a', items: filtrar(irA) },
          { titulo: 'Acciones', items: filtrar(acciones) },
        ]
      : [
          { titulo: 'Ir a', items: irA },
          { titulo: 'Acciones', items: acciones },
        ]
    ).filter((g) => g.items.length)
  }, [texto, expedientes, documentos, secciones, isDark, onAbrirExpediente, onIr, onRefresh, onToggleTheme])

  const planos = grupos.flatMap((g) => g.items)
  const actual = Math.min(activo, Math.max(planos.length - 1, 0))

  const ejecutar = (item) => {
    if (!item) return
    onCerrar()
    item.ejecutar()
  }

  useEffect(() => {
    const origen = document.activeElement
    campo.current?.focus()
    document.body.style.overflow = 'hidden'
    return () => {
      document.body.style.overflow = ''
      origen?.focus?.()
    }
  }, [])

  useEffect(() => {
    lista.current?.querySelector('[aria-selected="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [actual, texto])

  const alPulsar = (e) => {
    if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
      e.preventDefault()
      if (planos.length) setActivo((actual + (e.key === 'ArrowDown' ? 1 : -1) + planos.length) % planos.length)
    } else if (e.key === 'Enter') {
      e.preventDefault()
      ejecutar(planos[actual])
    } else if (e.key === 'Escape') {
      e.preventDefault()
      onCerrar()
    } else if (e.key === 'Tab') {
      e.preventDefault() // el campo es el único control: el foco no sale de la paleta
    }
  }

  let indice = -1
  return createPortal(
    <div className="paleta-velo" onMouseDown={(e) => e.target === e.currentTarget && onCerrar()}>
      <div className="paleta" role="dialog" aria-modal="true" aria-label="Paleta de comandos">
        <div className="paleta-campo">
          <Search size={16} aria-hidden="true" />
          <input
            ref={campo}
            type="search"
            value={texto}
            onChange={(e) => {
              setTexto(e.target.value)
              setActivo(0)
            }}
            onKeyDown={alPulsar}
            placeholder="Buscar expediente, empresa, RFC, documento o sección…"
            role="combobox"
            aria-expanded="true"
            aria-controls={`${id}-lista`}
            aria-activedescendant={planos.length ? `${id}-${actual}` : undefined}
            aria-autocomplete="list"
            spellCheck={false}
          />
          <kbd className="paleta-tecla">Esc</kbd>
        </div>
        <div ref={lista} id={`${id}-lista`} role="listbox" aria-label="Resultados" className="paleta-lista">
          {planos.length === 0 && <p className="paleta-vacia">Sin resultados para «{texto}».</p>}
          {grupos.map((g) => (
            <div key={g.titulo} role="group" aria-label={g.titulo}>
              <p className="paleta-grupo">{g.titulo}</p>
              {g.items.map((item) => {
                indice += 1
                const propio = indice
                const Icono = item.icono
                return (
                  <div
                    key={item.clave}
                    id={`${id}-${propio}`}
                    role="option"
                    aria-selected={propio === actual}
                    className="paleta-opcion"
                    onMouseMove={() => propio !== actual && setActivo(propio)}
                    onClick={() => ejecutar(item)}
                  >
                    <Icono size={14} aria-hidden="true" />
                    <span className="paleta-opcion-texto">
                      <span className="paleta-opcion-titulo">{item.titulo}</span>
                      {item.sub && <span className="paleta-opcion-sub">{item.sub}</span>}
                    </span>
                    {propio === actual && <CornerDownLeft size={12} className="paleta-intro" aria-hidden="true" />}
                  </div>
                )
              })}
            </div>
          ))}
        </div>
        <p className="paleta-pie">
          <kbd className="paleta-tecla">↑</kbd>
          <kbd className="paleta-tecla">↓</kbd> recorrer · <kbd className="paleta-tecla">Intro</kbd> abrir ·{' '}
          <kbd className="paleta-tecla">Ctrl</kbd> <kbd className="paleta-tecla">K</kbd> abrir o cerrar
        </p>
      </div>
    </div>,
    document.body
  )
}
