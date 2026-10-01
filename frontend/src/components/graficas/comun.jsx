import { Card } from '../ui/index.js'

/**
 * Piezas compartidas por las gráficas de Reportes (Recharts). Los colores son
 * tokens de index.css (--chart-*): el tema oscuro los redefine y las gráficas
 * cambian solas. El texto nunca lleva el color de la serie: la identidad la da
 * la marca de color junto a él.
 */

/**
 * Contenido del tooltip: el valor manda y la etiqueta lo acompaña; cada fila
 * lleva un trazo corto del color de su serie.
 */
export function TooltipGrafica({ titulo, filas = [], nota }) {
  return (
    <div className="grafica-tooltip" role="status">
      {titulo && <p className="grafica-tooltip-titulo">{titulo}</p>}
      <ul>
        {filas.map((f) => (
          <li key={f.etiqueta}>
            <span className="grafica-trazo" style={{ background: f.color }} aria-hidden="true" />
            <strong className="tabular">{f.valor}</strong>
            <span>{f.etiqueta}</span>
          </li>
        ))}
      </ul>
      {nota && <p className="grafica-tooltip-nota">{nota}</p>}
    </div>
  )
}

/** Leyenda con su cifra: la identidad nunca depende solo del color. */
export function Leyenda({ elementos, forma = 'cuadro' }) {
  return (
    <ul className="grafica-leyenda">
      {elementos.map((e) => (
        <li key={e.etiqueta}>
          <span className={`grafica-muestra grafica-muestra--${forma}`} style={{ background: e.color }} aria-hidden="true" />
          <span className="grafica-leyenda-etiqueta">{e.etiqueta}</span>
          {e.valor != null && <span className="grafica-leyenda-valor tabular">{e.valor}</span>}
        </li>
      ))}
    </ul>
  )
}

/** Los mismos datos en una tabla, para quien no puede o no quiere leer la gráfica. */
export function DatosDeLaGrafica({ columnas, filas }) {
  return (
    <details className="grafica-datos">
      <summary>Ver datos</summary>
      <table className="grafica-tabla">
        <thead>
          <tr>
            {columnas.map((c, i) => (
              <th key={c} className={i ? 'col-right' : undefined}>
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {filas.map((fila) => (
            <tr key={fila[0]}>
              {fila.map((celda, i) => (
                <td key={i} className={i ? 'col-right tabular' : undefined}>
                  {celda}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </details>
  )
}

/** Tarjeta de una gráfica: título, una línea que dice qué responde, la gráfica y su leyenda. */
export function TarjetaGrafica({ titulo, subtitulo, children, className = '' }) {
  return (
    <Card as="article" className={`report-card grafica-card ${className}`.trim()}>
      <header className="grafica-cabecera">
        <p className="eyebrow">{titulo}</p>
        {subtitulo && <p className="grafica-subtitulo">{subtitulo}</p>}
      </header>
      {children}
    </Card>
  )
}
