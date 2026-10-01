import { createLucideIcon } from 'lucide-react'

/**
 * Iconos propios del Motor (I2) para los conceptos del dominio que Lucide
 * solo resuelve con una figura genérica: el expediente, la bóveda que
 * custodia, el catálogo de reglas y el semáforo. Se crean con
 * createLucideIcon, así que heredan del LucideProvider el grosor de trazo
 * (1.5) y aceptan size y className como cualquier icono de Lucide; usan la
 * misma retícula de 24 y la hoja con la esquina doblada de LogoMotor.
 */

/** Expediente: carpeta con su pestaña y la hoja que asoma por detrás del frente. */
export const IconoExpediente = createLucideIcon('IconoExpediente', [
  ['path', { d: 'M3 13V5.5A1.5 1.5 0 0 1 4.5 4H8.5l2 2.5h9A1.5 1.5 0 0 1 21 8v5', key: 'fondo' }],
  ['path', { d: 'M7 11V9.5a1 1 0 0 1 1-1h8a1 1 0 0 1 1 1V11', key: 'hoja' }],
  ['path', { d: 'M3 13a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z', key: 'frente' }],
])

/** Bóveda: la hoja del documento custodiado con su candado. */
export const IconoBoveda = createLucideIcon('IconoBoveda', [
  ['path', { d: 'M11 21H7.5A2.5 2.5 0 0 1 5 18.5v-13A2.5 2.5 0 0 1 7.5 3H13l5 5v3.5', key: 'hoja' }],
  ['path', { d: 'M13 3v3a2 2 0 0 0 2 2h3', key: 'esquina' }],
  ['rect', { x: '13.5', y: '16', width: '7.5', height: '5', rx: '1.25', key: 'candado' }],
  ['path', { d: 'M15.25 16v-1.25a2 2 0 0 1 4 0V16', key: 'arco' }],
])

/** Reglas: la ficha del catálogo con sus criterios verificados. */
export const IconoReglas = createLucideIcon('IconoReglas', [
  ['rect', { x: '3', y: '3', width: '18', height: '18', rx: '2.5', key: 'ficha' }],
  ['path', { d: 'M7 9l1.5 1.5 3-3', key: 'check-1' }],
  ['path', { d: 'M14 9h3', key: 'renglon-1' }],
  ['path', { d: 'M7 15l1.5 1.5 3-3', key: 'check-2' }],
  ['path', { d: 'M14 15h3', key: 'renglon-2' }],
])

/** Semáforo: tres luces con la de abajo encendida. */
export const IconoSemaforo = createLucideIcon('IconoSemaforo', [
  ['rect', { x: '7', y: '2', width: '10', height: '20', rx: '5', key: 'cuerpo' }],
  ['circle', { cx: '12', cy: '6.75', r: '1.75', key: 'luz-1' }],
  ['circle', { cx: '12', cy: '12', r: '1.75', key: 'luz-2' }],
  ['circle', { cx: '12', cy: '17.25', r: '1.75', fill: 'currentColor', key: 'luz-3' }],
])
