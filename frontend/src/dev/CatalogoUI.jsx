import { useEffect, useState } from 'react'
import { ArrowLeft, Download, FolderPlus, Moon, Plus, RefreshCw, Sparkles, Sun, X } from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  CopyChip,
  EmptyState,
  Field,
  IconButton,
  Input,
  KeyValue,
  KeyValueList,
  Modal,
  SearchBox,
  Segmented,
  Select,
  Tag,
  Tooltip,
} from '../components/ui/index.js'
import useTheme from '../hooks/useTheme.js'
import './catalogo.css'

/**
 * Catálogo del sistema de diseño "White & Warm Minimalist" (solo en
 * desarrollo). Se abre en `#/ui` con `npm run dev`; main.jsx lo carga de forma
 * diferida detrás de `import.meta.env.DEV`, así que no existe en el build de
 * producción. Muestra los tokens de index.css con su valor real en el tema
 * activo y el contraste WCAG calculado en vivo, y cada primitiva de
 * src/components/ui/ en sus variantes.
 */

const SUPERFICIES = ['--bg-canvas', '--bg-surface', '--bg-subtle', '--bg-muted', '--bg-inverse']
const LINEAS = ['--line-subtle', '--line', '--line-strong']
const TEXTOS = [
  { token: '--text-primary', uso: 'Títulos y datos' },
  { token: '--text-secondary', uso: 'Texto de apoyo' },
  { token: '--text-muted', uso: 'Versales, metadatos y conteos' },
  { token: '--text-tertiary', uso: 'Solo placeholders y decoración' },
]
const ESTADOS = [
  { tono: 'ok', nombre: 'Conforme' },
  { tono: 'warn', nombre: 'En revisión' },
  { tono: 'bad', nombre: 'No conforme / vencido' },
  { tono: 'neutral', nombre: 'Informativo / omitido' },
]
const TIPOGRAFIA = [
  { token: '--fs-display', muestra: '85%' },
  { token: '--fs-metric', muestra: '12 documentos' },
  { token: '--fs-h1', muestra: 'Catálogo de reglas' },
  { token: '--fs-title', muestra: 'Inteligencia documental' },
  { token: '--fs-body', muestra: 'Cuerpo de texto y celdas de tabla' },
  { token: '--fs-small', muestra: 'Celdas secundarias y ayudas' },
  { token: '--fs-micro', muestra: 'VERSALES Y METADATOS' },
]
const ESPACIOS = ['--s-1', '--s-2', '--s-3', '--s-4', '--s-5', '--s-6', '--s-8', '--s-10']
const RADIOS = ['--r-xs', '--r-sm', '--r-squircle', '--r-md', '--r-lg', '--r-full']

const leer = (token) => getComputedStyle(document.documentElement).getPropertyValue(token).trim()

/** Luminancia relativa de un color #rrggbb (WCAG 2.1); null si el token no es opaco. */
function luminancia(color) {
  const m = /^#([0-9a-f]{6})$/i.exec(color)
  if (!m) return null
  const canales = [0, 2, 4].map((i) => parseInt(m[1].slice(i, i + 2), 16) / 255)
  const [r, g, b] = canales.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4))
  return 0.2126 * r + 0.7152 * g + 0.0722 * b
}

function contraste(a, b) {
  const la = luminancia(a)
  const lb = luminancia(b)
  if (la === null || lb === null) return null
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05)
}

/** Relee los tokens cuando cambia el tema (index.css redefine los mismos nombres). */
function useTokens(tema) {
  const [valores, setValores] = useState({})
  useEffect(() => {
    const todos = [...SUPERFICIES, ...LINEAS, ...TEXTOS.map((t) => t.token)]
    for (const e of ESTADOS) todos.push(`--${e.tono}`, `--${e.tono}-bg`, `--${e.tono}-border`)
    // El atributo data-theme se escribe en un efecto del hook de tema: se lee en el cuadro siguiente.
    const id = requestAnimationFrame(() => setValores(Object.fromEntries(todos.map((t) => [t, leer(t)]))))
    return () => cancelAnimationFrame(id)
  }, [tema])
  return valores
}

function Ratio({ texto, fondo }) {
  const r = contraste(texto, fondo)
  if (r === null) return <Badge>n/d</Badge>
  return (
    <Badge tono={r >= 4.5 ? 'ok' : 'bad'} title={r >= 4.5 ? 'Cumple AA para texto normal' : 'No cumple AA para texto normal'}>
      {r.toFixed(2)}:1
    </Badge>
  )
}

function Seccion({ id, titulo, descripcion, children }) {
  return (
    <section className="catalogo-seccion" aria-labelledby={id}>
      <header className="catalogo-seccion-head">
        <h2 id={id} className="section-title">
          {titulo}
        </h2>
        {descripcion && <p className="field-hint">{descripcion}</p>}
      </header>
      {children}
    </section>
  )
}

function Muestra({ etiqueta, children }) {
  return (
    <div className="catalogo-muestra">
      <span className="catalogo-muestra-etiqueta mono">{etiqueta}</span>
      <div className="catalogo-muestra-cuerpo">{children}</div>
    </div>
  )
}

export default function CatalogoUI() {
  const { theme, isDark, toggleTheme } = useTheme()
  const t = useTokens(theme)
  const [segmento, setSegmento] = useState('todos')
  const [busqueda, setBusqueda] = useState('')
  const [rfc, setRfc] = useState('PLU20')
  const [modal, setModal] = useState(false)
  const [cargando, setCargando] = useState(false)

  const simularCarga = () => {
    setCargando(true)
    setTimeout(() => setCargando(false), 1500)
  }

  return (
    <div className="catalogo">
      <header className="catalogo-cabecera">
        <div>
          <p className="eyebrow">Solo en desarrollo · #/ui</p>
          <h1 className="catalogo-titulo">Sistema de diseño · White &amp; Warm Minimalist</h1>
          <p className="field-hint">
            Tokens de <code>src/index.css</code> con su valor en el tema activo y primitivas de{' '}
            <code>src/components/ui/</code>. La equivalencia de marcado la prueba <code>npm run test:ui</code>.
          </p>
        </div>
        <div className="toolbar-grupo">
          <IconButton etiqueta={isDark ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro'} tooltip onClick={toggleTheme}>
            {isDark ? <Sun size={16} /> : <Moon size={16} />}
          </IconButton>
          <Button icono={ArrowLeft} onClick={() => (window.location.hash = '')}>
            Volver al panel
          </Button>
        </div>
      </header>

      <Seccion id="cat-color" titulo="Color" descripcion="El color solo comunica estado; todo lo demás es grafito cálido (escala stone).">
        <div className="catalogo-rejilla">
          {SUPERFICIES.map((token) => (
            <div key={token} className="catalogo-color">
              <span className="catalogo-color-muestra" style={{ background: `var(${token})` }} />
              <span className="mono">{token}</span>
              <span className="cell-sub mono">{t[token]}</span>
            </div>
          ))}
          {LINEAS.map((token) => (
            <div key={token} className="catalogo-color">
              <span className="catalogo-color-muestra catalogo-color-muestra--linea" style={{ borderColor: `var(${token})` }} />
              <span className="mono">{token}</span>
              <span className="cell-sub mono">{t[token]}</span>
            </div>
          ))}
        </div>

        <Card className="table-card table-card--flat">
          <table className="data-table data-table--inner">
            <thead>
              <tr>
                <th>Token de texto</th>
                <th>Uso</th>
                <th className="col-right">Sobre --bg-surface</th>
                <th className="col-right">Sobre --bg-subtle</th>
              </tr>
            </thead>
            <tbody>
              {TEXTOS.map(({ token, uso }) => (
                <tr key={token}>
                  <td>
                    <span className="mono" style={{ color: `var(${token})` }}>
                      {token}
                    </span>
                    <span className="cell-sub mono">{t[token]}</span>
                  </td>
                  <td className="cell-muted">{uso}</td>
                  <td className="col-right">
                    <Ratio texto={t[token]} fondo={t['--bg-surface']} />
                  </td>
                  <td className="col-right">
                    <Ratio texto={t[token]} fondo={t['--bg-subtle']} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </Card>

        <div className="catalogo-rejilla">
          {ESTADOS.map(({ tono, nombre }) => (
            <div key={tono} className="catalogo-estado" style={{ background: `var(--${tono}-bg)`, borderColor: `var(--${tono}-border)` }}>
              <span style={{ color: `var(--${tono})` }}>
                <span className={`status-dot status-dot--${tono}`} aria-hidden="true" /> {nombre}
              </span>
              <span className="cell-sub mono">
                --{tono} {t[`--${tono}`]}
              </span>
              <Ratio texto={t[`--${tono}`]} fondo={t[`--${tono}-bg`]} />
            </div>
          ))}
        </div>
      </Seccion>

      <Seccion id="cat-tipo" titulo="Tipografía" descripcion="Inter 400/500/600; JetBrains Mono con cifras tabulares para hashes, folios, RFC y fechas.">
        <Card className="catalogo-lista">
          {TIPOGRAFIA.map(({ token, muestra }) => (
            <Muestra key={token} etiqueta={token}>
              <span style={{ fontSize: `var(${token})`, fontWeight: token === '--fs-micro' ? 500 : 600 }}>{muestra}</span>
            </Muestra>
          ))}
          <Muestra etiqueta="mono / tabular">
            <span className="mono">EXP-BIM980101XYZ-001 · b9ea8ab3…a86ae9 · 27 sep 2026 · 1,006.9 KB</span>
          </Muestra>
        </Card>
      </Seccion>

      <Seccion id="cat-medidas" titulo="Espaciado, radios y controles" descripcion="Rejilla de 4 px; controles de 28 y 32 px.">
        <Card className="catalogo-lista">
          {ESPACIOS.map((token) => (
            <Muestra key={token} etiqueta={token}>
              <span className="catalogo-barra" style={{ width: `var(${token})` }} />
            </Muestra>
          ))}
          <Muestra etiqueta="radios">
            {RADIOS.map((token) => (
              <span key={token} className="catalogo-radio" style={{ borderRadius: `var(${token})` }} title={token} />
            ))}
          </Muestra>
          <Muestra etiqueta="--control-sm / -md">
            <Button compacto>28 px</Button>
            <Button>32 px</Button>
          </Muestra>
        </Card>
      </Seccion>

      <Seccion id="cat-botones" titulo="Button e IconButton" descripcion="Sin variante de peligro: el sistema no tiene acciones destructivas.">
        <Card className="catalogo-lista">
          <Muestra etiqueta="primary">
            <Button variante="primary" icono={Plus}>
              Nueva regla
            </Button>
            <Button variante="primary" compacto>
              Compacto
            </Button>
            <Button variante="primary" cargando={cargando} icono={Sparkles} onClick={simularCarga}>
              {cargando ? 'Auditando…' : 'Probar cargando'}
            </Button>
            <Button variante="primary" disabled>
              Deshabilitado
            </Button>
            <Button variante="primary" soloIcono icono={Download} aria-label="Descargar" />
          </Muestra>
          <Muestra etiqueta="secondary">
            <Button icono={FolderPlus}>Aperturar expediente</Button>
            <Button compacto>PDF</Button>
            <Button disabled>Deshabilitado</Button>
          </Muestra>
          <Muestra etiqueta="IconButton">
            <IconButton etiqueta="Cerrar" compacto>
              <X size={16} />
            </IconButton>
            <IconButton etiqueta="Actualizar datos" tooltip ocupado={cargando} onClick={simularCarga}>
              <RefreshCw size={16} className="refresh-icon" />
            </IconButton>
            <IconButton etiqueta="Deshabilitado" disabled>
              <X size={16} />
            </IconButton>
          </Muestra>
        </Card>
      </Seccion>

      <Seccion id="cat-etiquetas" titulo="Badge y Tag" descripcion="Badge comunica un estado y siempre lleva texto; Tag es una categoría neutra.">
        <Card className="catalogo-lista">
          <Muestra etiqueta="Badge punto">
            <Badge tono="ok" punto>
              Conforme
            </Badge>
            <Badge tono="warn" punto>
              En revisión
            </Badge>
            <Badge tono="bad" punto>
              No conforme
            </Badge>
            <Badge punto>Neutro</Badge>
          </Muestra>
          <Muestra etiqueta="Badge grande">
            <Badge tono="bad" punto grande>
              No conforme
            </Badge>
            <Badge tono="ok" punto grande>
              Conforme
            </Badge>
          </Muestra>
          <Muestra etiqueta="Badge sin punto">
            <Badge tono="skip">Omitido</Badge>
            <Badge tono="vault">PDF verificado</Badge>
            <Badge>Sello Digital SAT</Badge>
          </Muestra>
          <Muestra etiqueta="Tag">
            <Tag>Todo el expediente</Tag>
            <Tag tipo>Corporativo</Tag>
            <Tag mono>PROVEEDOR_CRITICO</Tag>
            <Tag tabular>90 días</Tag>
          </Muestra>
        </Card>
      </Seccion>

      <Seccion id="cat-datos" titulo="Card y KeyValue" descripcion="Metadatos como lista de definiciones; RFC y hashes con CopyChip.">
        <Card className="catalogo-tarjeta">
          <KeyValueList className="registro-grid">
            <KeyValue etiqueta="Confianza" valorClassName="tabular">
              85%
            </KeyValue>
            <KeyValue etiqueta="Vigencia">Sin reglas aplicables</KeyValue>
            <KeyValue etiqueta="RFC">
              <CopyChip valor="BIM980101XYZ" etiqueta="RFC" />
            </KeyValue>
            <KeyValue etiqueta="Huella evaluada" valorClassName="mono" valorTitulo="b9ea8ab37fcf1adcf4ead6d34a0b7e3a9d17d6b210ca36bf51ebb78c63a86ae9">
              b9ea8ab3…a86ae9
            </KeyValue>
          </KeyValueList>
        </Card>
      </Seccion>

      <Seccion id="cat-form" titulo="Field, Input, Select y filtros" descripcion="Etiquetas estáticas; la ayuda y la validación se enlazan al campo con aria-describedby.">
        <Card className="catalogo-tarjeta catalogo-form">
          <Field etiqueta="Nombre descriptivo (opcional)" ayuda="Máximo 150 caracteres.">
            <Input placeholder="Ej. Contrato de mantenimiento 2026" maxLength={150} />
          </Field>
          <Field
            etiqueta="RFC"
            retro={
              rfc.length === 12
                ? { estado: 'valido', mensaje: 'Formato de RFC válido.' }
                : { estado: 'incompleto', mensaje: `Faltan ${Math.max(0, 12 - rfc.length)} caracteres (persona moral: 12).` }
            }
          >
            <Input
              className="mono"
              estado={rfc.length === 12 ? 'valido' : 'incompleto'}
              value={rfc}
              maxLength={12}
              onChange={(e) => setRfc(e.target.value.toUpperCase())}
            />
          </Field>
          <Field etiqueta="Tipo de persona">
            <Select defaultValue="MORAL">
              <option value="MORAL">Moral (RFC de 12)</option>
              <option value="FISICA">Física (RFC de 13)</option>
            </Select>
          </Field>
          <Field etiqueta="Campo inválido" retro={{ estado: 'invalido', mensaje: 'La fecha embebida (AAMMDD) no es válida.' }}>
            <Input estado="invalido" defaultValue="XAXX991399000" />
          </Field>
        </Card>
        <div className="toolbar">
          <SearchBox value={busqueda} onChange={setBusqueda} placeholder="Buscar por folio o RFC…" label="Buscar" />
          <Segmented
            label="Filtro de ejemplo"
            valor={segmento}
            onChange={setSegmento}
            opciones={[
              { id: 'todos', label: 'Todos', conteo: 12 },
              { id: 'ok', label: 'Conforme', tono: 'ok', conteo: 7 },
              { id: 'bad', label: 'No conforme', tono: 'bad', conteo: 5 },
            ]}
          />
          <Select etiqueta="Filtrar por tipo de expediente" defaultValue="TODOS">
            <option value="TODOS">Todo tipo de expediente</option>
            <option value="CORPORATIVO">Corporativo</option>
          </Select>
        </div>
      </Seccion>

      <Seccion id="cat-overlay" titulo="Tooltip, Modal y EmptyState">
        <Card className="catalogo-lista">
          <Muestra etiqueta="Tooltip">
            <Tooltip texto="Pausar regla" nombra>
              <button type="button" className="icon-button icon-button--sm">
                <X size={14} />
              </button>
            </Tooltip>
            <Tooltip texto="Tooltip sobre un botón de texto">
              <Button compacto>Pasa el cursor o enfoca con Tab</Button>
            </Tooltip>
          </Muestra>
          <Muestra etiqueta="Modal">
            <Button variante="primary" onClick={() => setModal(true)}>
              Abrir modal
            </Button>
            <span className="field-hint">Escape o clic en el velo lo cierran; Tab no sale del panel y el foco vuelve aquí.</span>
          </Muestra>
        </Card>
        <Card>
          <EmptyState icon={FolderPlus} titulo="Aún no hay expedientes" descripcion="Apertura un expediente para empezar a custodiar la documentación de un titular." />
        </Card>
      </Seccion>

      {modal && (
        <Modal title="Modal de ejemplo" subtitle="Trampa de foco y retorno al elemento que lo abrió" onClose={() => setModal(false)}>
          <form className="form-grid" onSubmit={(e) => e.preventDefault()}>
            <Field etiqueta="Campo">
              <Input placeholder="Escribe sin perder el foco" />
            </Field>
            <div className="modal-footer">
              <Button onClick={() => setModal(false)}>Cancelar</Button>
              <Button type="submit" variante="primary">
                Guardar
              </Button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  )
}
