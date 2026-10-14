import { useState } from 'react'
import { Check, Copy } from '../iconos.js'
import useToast from '../../hooks/useToast.js'
import { copiarAlPortapapeles } from '../../utils/format.js'

/** Valor monoespaciado (RFC, hash) con copiado de un clic y confirmación. */
export default function CopyChip({ valor, visible, etiqueta, completo = false }) {
  const [copiado, setCopiado] = useState(false)
  const toast = useToast()

  const copiar = async (e) => {
    e.stopPropagation()
    if (await copiarAlPortapapeles(valor)) {
      setCopiado(true)
      toast.exito(`${etiqueta} copiado`, visible ?? valor)
      setTimeout(() => setCopiado(false), 1400)
    } else {
      toast.error('No se pudo copiar', 'El navegador bloqueó el portapapeles.')
    }
  }

  return (
    <button
      type="button"
      className={`copy-chip ${completo ? 'copy-chip--full' : ''}`}
      onClick={copiar}
      data-tooltip={copiado ? 'Copiado' : `Copiar ${etiqueta}`}
    >
      <span className="mono">{visible ?? valor}</span>
      {copiado ? <Check size={12} className="copy-ok" aria-hidden="true" /> : <Copy size={12} aria-hidden="true" />}
    </button>
  )
}
