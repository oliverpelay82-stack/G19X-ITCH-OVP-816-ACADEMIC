/**
 * Casos de equivalencia del sistema de diseño: cada par es el marcado actual
 * de una vista (copiado del componente que lo usa) y el componente de
 * src/components/ui/ que lo reemplazará. verificar-ui.mjs renderiza ambos y
 * exige el mismo HTML, salvo los atributos de accesibilidad que el
 * componente añade a propósito.
 */
import { Loader2, Plus, RefreshCw, X } from 'lucide-react'
import {
  Badge,
  Button,
  Card,
  Field,
  IconButton,
  Input,
  KeyValue,
  KeyValueList,
  Select,
  Tag,
  Tooltip,
} from '../src/components/ui/index.js'

const nada = () => {}

export const CASOS = [
  {
    nombre: 'Button primario de barra con icono (ExpedientesTab)',
    actual: (
      <button type="button" className="btn btn-primary toolbar-action" onClick={nada} disabled title="Primero registra una empresa">
        <Plus size={14} />
        Aperturar expediente
      </button>
    ),
    nuevo: (
      <Button variante="primary" icono={Plus} className="toolbar-action" onClick={nada} disabled title="Primero registra una empresa">
        Aperturar expediente
      </Button>
    ),
  },
  {
    nombre: 'Button de envío en curso (modal de apertura)',
    actual: (
      <button type="submit" className="btn btn-primary" disabled>
        <Loader2 className="spin" size={14} />
        Crear expediente
      </button>
    ),
    nuevo: (
      <Button type="submit" variante="primary" cargando>
        Crear expediente
      </Button>
    ),
  },
  {
    nombre: 'Button secundario compacto (acciones de fila)',
    actual: (
      <button type="button" className="btn btn-secondary btn-sm" onClick={nada}>
        PDF
      </button>
    ),
    nuevo: (
      <Button compacto onClick={nada}>
        PDF
      </Button>
    ),
  },
  {
    nombre: 'IconButton compacto (visor, modal)',
    actual: (
      <button type="button" className="icon-button icon-button--sm" onClick={nada} aria-label="Cerrar el visor">
        <X size={15} />
      </button>
    ),
    nuevo: (
      <IconButton etiqueta="Cerrar el visor" compacto onClick={nada}>
        <X size={15} />
      </IconButton>
    ),
  },
  {
    nombre: 'IconButton de refresco con tooltip, ocupado (Header)',
    actual: (
      <button type="button" className="icon-button is-busy" onClick={nada} disabled data-tooltip="Actualizar datos" aria-label="Actualizar datos">
        <RefreshCw size={15} className="refresh-icon" />
      </button>
    ),
    nuevo: (
      <IconButton etiqueta="Actualizar datos" tooltip ocupado onClick={nada} disabled>
        <RefreshCw size={15} className="refresh-icon" />
      </IconButton>
    ),
  },
  {
    nombre: 'Badge de estado con punto (Alertas, Reportes, Titulares)',
    actual: (
      <span className="badge badge--bad">
        <span className="status-dot status-dot--bad" aria-hidden="true" />
        No Conforme
      </span>
    ),
    nuevo: (
      <Badge tono="bad" punto>
        No Conforme
      </Badge>
    ),
  },
  {
    nombre: 'Badge grande del semáforo del expediente',
    actual: (
      <span className="badge badge--lg badge--warn">
        <span className="status-dot status-dot--warn" aria-hidden="true" />
        En Revisión
      </span>
    ),
    nuevo: (
      <Badge tono="warn" punto grande>
        En Revisión
      </Badge>
    ),
  },
  {
    nombre: 'Badge neutro sin punto',
    actual: <span className="badge badge--neutral">Dictamen</span>,
    nuevo: <Badge>Dictamen</Badge>,
  },
  {
    nombre: 'Tag de tipo documental (Bóveda)',
    actual: (
      <span className="tag tag--type" title="Acta Constitutiva">
        Acta
      </span>
    ),
    nuevo: (
      <Tag tipo title="Acta Constitutiva">
        Acta
      </Tag>
    ),
  },
  {
    nombre: 'Tag monoespaciado (categoría regulatoria)',
    actual: <span className="tag mono">PROVEEDOR_CRITICO</span>,
    nuevo: <Tag mono>PROVEEDOR_CRITICO</Tag>,
  },
  {
    nombre: 'Card de reporte (ReportesTab)',
    actual: (
      <article className="card report-card">
        <p className="eyebrow">Cumplimiento global</p>
      </article>
    ),
    nuevo: (
      <Card as="article" className="report-card">
        <p className="eyebrow">Cumplimiento global</p>
      </Card>
    ),
  },
  {
    nombre: 'Field con Select de formulario (modal de apertura)',
    actual: (
      <label className="field">
        <span className="field-label">Titular</span>
        <select required value="" onChange={nada}>
          <option value="">Selecciona una empresa…</option>
        </select>
      </label>
    ),
    nuevo: (
      <Field etiqueta="Titular">
        <Select required value="" onChange={nada}>
          <option value="">Selecciona una empresa…</option>
        </Select>
      </Field>
    ),
  },
  {
    nombre: 'Field con Input y ayuda',
    actual: (
      <label className="field">
        <span className="field-label">Nombre descriptivo (opcional)</span>
        <input maxLength={150} placeholder="Ej. Contrato de mantenimiento 2026" value="" onChange={nada} />
        <span className="field-hint">Máximo 150 caracteres.</span>
      </label>
    ),
    nuevo: (
      <Field etiqueta="Nombre descriptivo (opcional)" ayuda="Máximo 150 caracteres.">
        <Input maxLength={150} placeholder="Ej. Contrato de mantenimiento 2026" value="" onChange={nada} />
      </Field>
    ),
  },
  {
    nombre: 'Input inválido con retro de validación (RFC)',
    actual: (
      <label className="field">
        <span className="field-label">RFC</span>
        <input className="input--invalido" value="XXX" onChange={nada} />
        <span className="field-feedback field-feedback--invalido">Formato de RFC inválido.</span>
      </label>
    ),
    nuevo: (
      <Field etiqueta="RFC" retro={{ estado: 'invalido', mensaje: 'Formato de RFC inválido.' }}>
        <Input estado="invalido" value="XXX" onChange={nada} />
      </Field>
    ),
  },
  {
    nombre: 'Select de filtro en barra (AlertasTab)',
    actual: (
      <label className="select-inline">
        <span className="sr-only">Filtrar por categoría</span>
        <select value="TODAS" onChange={nada}>
          <option value="TODAS">Toda categoría</option>
        </select>
      </label>
    ),
    nuevo: (
      <Select etiqueta="Filtrar por categoría" value="TODAS" onChange={nada}>
        <option value="TODAS">Toda categoría</option>
      </Select>
    ),
  },
  {
    nombre: 'Select de filtro con clase de maquetación (ReportesTab)',
    actual: (
      <label className="select-inline report-select">
        <span className="sr-only">Tipo de expediente del reporte</span>
        <select value="" onChange={nada}>
          <option value="">Todos los expedientes</option>
        </select>
      </label>
    ),
    nuevo: (
      <Select etiqueta="Tipo de expediente del reporte" claseContenedor="report-select" value="" onChange={nada}>
        <option value="">Todos los expedientes</option>
      </Select>
    ),
  },
  {
    nombre: 'KeyValue del registro de dictámenes (DictamenesGuardados)',
    actual: (
      <dl className="registro-grid">
        <div>
          <dt>Confianza</dt>
          <dd className="tabular">85%</dd>
        </div>
        <div>
          <dt>Huella evaluada</dt>
          <dd className="mono" title="b9ea8ab37fcf1adcf4ead6d34a0b7e3a">
            b9ea8ab3…a86ae9
          </dd>
        </div>
      </dl>
    ),
    nuevo: (
      <KeyValueList className="registro-grid">
        <KeyValue etiqueta="Confianza" valorClassName="tabular">
          85%
        </KeyValue>
        <KeyValue etiqueta="Huella evaluada" valorClassName="mono" valorTitulo="b9ea8ab37fcf1adcf4ead6d34a0b7e3a">
          b9ea8ab3…a86ae9
        </KeyValue>
      </KeyValueList>
    ),
  },
  {
    nombre: 'KeyValue del detalle del documento (DetalleDocumentoModal)',
    actual: (
      <div className="detail-item detail-item--full">
        <dt>Huella SHA-256 · inmutable (RIE-03)</dt>
        <dd>b9ea8ab3</dd>
      </div>
    ),
    nuevo: (
      <KeyValue etiqueta="Huella SHA-256 · inmutable (RIE-03)" className="detail-item detail-item--full">
        b9ea8ab3
      </KeyValue>
    ),
  },
  {
    nombre: 'Tooltip sobre un botón de icono (Header)',
    actual: (
      <button type="button" className="icon-button" data-tooltip="Tema oscuro" aria-label="Tema oscuro">
        <X size={15} />
      </button>
    ),
    nuevo: (
      <Tooltip texto="Tema oscuro" nombra>
        <button type="button" className="icon-button">
          <X size={15} />
        </button>
      </Tooltip>
    ),
  },
]
