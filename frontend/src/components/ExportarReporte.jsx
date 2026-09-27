import { useState } from 'react'
import { FileSpreadsheet, FileText, Loader2 } from 'lucide-react'
import useToast from '../hooks/useToast.js'
import { descargarReporte } from '../services/api.js'

const FORMATOS = [
  { id: 'pdf', label: 'PDF', icon: FileText },
  { id: 'xlsx', label: 'Excel', icon: FileSpreadsheet },
]

/**
 * Botones de exportación de un reporte de auditoría en PDF y Excel (RF-24).
 * `ruta` es la del core-service; `params` se agrega a la consulta.
 */
export default function ExportarReporte({ ruta, params, disabled = false, compacto = false }) {
  const toast = useToast()
  const [descargando, setDescargando] = useState(null)

  const exportar = async (formato) => {
    setDescargando(formato)
    try {
      const nombre = await descargarReporte(ruta, { ...params, formato })
      toast.exito('Reporte generado', nombre)
    } catch (err) {
      toast.error('No se pudo generar el reporte', err.message)
    } finally {
      setDescargando(null)
    }
  }

  return (
    <div className="export-row" role="group" aria-label="Exportar reporte">
      {FORMATOS.map(({ id, label, icon: Icono }) => (
        <button
          key={id}
          type="button"
          className={`btn btn-secondary ${compacto ? 'btn-sm' : ''}`}
          onClick={() => exportar(id)}
          disabled={disabled || descargando !== null}
        >
          {descargando === id ? <Loader2 className="spin" size={14} /> : <Icono size={14} />}
          {label}
        </button>
      ))}
    </div>
  )
}
