import { Component } from 'react'
import { RefreshCw, ServerOff } from 'lucide-react'
import { Button, Card, EmptyState } from './ui/index.js'

/**
 * Si una vista no carga (su código no llegó tras una actualización del sistema,
 * o falla al pintarse), se avisa en su lugar con la opción de recargar, en vez
 * de dejar la pantalla en blanco. App la monta con `key` de la sección: cambiar
 * de sección la reinicia. Es un componente de clase porque React solo atrapa
 * errores de render con getDerivedStateFromError.
 */
export default class ErrorVista extends Component {
  state = { error: null }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Vista con error:', error, info?.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <Card>
        <EmptyState
          icon={ServerOff}
          titulo="No se pudo cargar esta sección"
          descripcion="Suele pasar tras una actualización del sistema. Recargar trae la versión vigente; los datos no se pierden."
        >
          <Button compacto icono={RefreshCw} onClick={() => window.location.reload()}>
            Recargar
          </Button>
        </EmptyState>
      </Card>
    )
  }
}
