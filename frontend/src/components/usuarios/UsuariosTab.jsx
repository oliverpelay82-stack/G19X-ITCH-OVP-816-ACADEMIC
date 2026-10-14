import { useEffect, useMemo, useState } from 'react'
import { Plus, UsersThree } from '../iconos.js'
import { Avatar, Badge, Button, Card, EmptyRow, SearchBox } from '../ui/index.js'
import { SkeletonRows } from '../Skeleton.jsx'
import { CORE_FUERA_DE_LINEA, sinRespuesta } from '../sinRespuesta.js'
import { getUsuarios } from '../../services/api.js'
import useSesion from '../../hooks/useSesion.js'
import { coincideEn, normalizar } from '../../utils/busqueda.js'
import { aFecha, formatRelativo } from '../../utils/format.js'
import { NOMBRE_ROL } from '../../utils/permisos.js'
import AltaUsuario from './AltaUsuario.jsx'
import EditarUsuario from './EditarUsuario.jsx'
import AsignarExpedientes from './AsignarExpedientes.jsx'

/** Estado de la cuenta en palabras: lo que impide entrar va primero. */
function EstadoCuenta({ usuario }) {
  if (!usuario.activo) return <Badge tono="neutral" punto>Desactivada</Badge>
  if (usuario.bloqueado_hasta && aFecha(usuario.bloqueado_hasta) > new Date()) {
    return <Badge tono="bad" punto>Bloqueada por intentos</Badge>
  }
  if (usuario.debe_cambiar_contrasena) return <Badge tono="warn" punto>Contraseña temporal</Badge>
  return <Badge tono="ok" punto>Activa</Badge>
}

/**
 * Vista Usuarios (solo el administrador; HU-05, HU-31): las cuentas con su rol,
 * su estado y su segundo factor; alta con contraseña temporal; cambios de rol,
 * estado, contraseña y MFA; y los expedientes asignados a cada persona. Cada
 * cambio queda en la bitácora del core.
 */
export default function UsuariosTab({ expedientes, isOnline }) {
  const { usuario: yo } = useSesion()
  const [usuarios, setUsuarios] = useState([])
  const [cargando, setCargando] = useState(true)
  const [errorCarga, setErrorCarga] = useState(null)
  const [busqueda, setBusqueda] = useState('')
  const [alta, setAlta] = useState(false)
  const [editando, setEditando] = useState(null)
  const [asignando, setAsignando] = useState(null)

  useEffect(() => {
    let vigente = true
    getUsuarios()
      .then((lista) => vigente && (setUsuarios(lista), setErrorCarga(null)))
      .catch((err) => vigente && setErrorCarga(err.message))
      .finally(() => vigente && setCargando(false))
    return () => {
      vigente = false
    }
  }, [])

  const filtrados = useMemo(
    () => usuarios.filter((u) => coincideEn([u.nombre_completo, u.email, NOMBRE_ROL[u.rol]], normalizar(busqueda))),
    [usuarios, busqueda]
  )

  const vacio =
    errorCarga && usuarios.length === 0
      ? sinRespuesta(CORE_FUERA_DE_LINEA, errorCarga)
      : { icon: UsersThree, titulo: 'Ninguna cuenta coincide', descripcion: 'Prueba con otro nombre, correo o rol.' }

  const actualizado = (usuario) => {
    setUsuarios((lista) => lista.map((u) => (u.id === usuario.id ? usuario : u)))
    setEditando((actual) => (actual?.id === usuario.id ? usuario : actual))
  }

  return (
    <div className="tab-panel">
      <div className="toolbar">
        <SearchBox
          value={busqueda}
          onChange={setBusqueda}
          placeholder="Buscar por nombre, correo o rol…"
          label="Buscar cuentas"
        />
        <Button variante="primary" icono={Plus} className="toolbar-action" onClick={() => setAlta(true)} disabled={!isOnline}>
          Nueva cuenta
        </Button>
      </div>

      <Card className="table-card">
        <div className="table-scroll">
          <table className="data-table">
            <colgroup>
              <col style={{ width: '30%' }} />
              <col style={{ width: '16%' }} />
              <col style={{ width: '18%' }} />
              <col style={{ width: '9%' }} />
              <col style={{ width: '11%' }} />
              <col style={{ width: 196 }} />
            </colgroup>
            <thead>
              <tr>
                <th scope="col">Cuenta</th>
                <th scope="col">Rol</th>
                <th scope="col">Estado</th>
                <th scope="col">Dos pasos</th>
                <th scope="col">Último acceso</th>
                <th scope="col">
                  <span className="sr-only">Acciones</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {cargando ? (
                <SkeletonRows rows={4} cols={6} />
              ) : filtrados.length === 0 ? (
                <EmptyRow columnas={6} {...vacio} />
              ) : (
                filtrados.map((u) => (
                  <tr key={u.id}>
                    <td>
                      <div className="identity">
                        <Avatar nombre={u.nombre_completo} />
                        <div className="cell-stack">
                          <span className="identity-name">
                            {u.nombre_completo}
                            {u.id === yo.id && <span className="cell-muted"> · tú</span>}
                          </span>
                          <span className="cell-sub">{u.email}</span>
                        </div>
                      </div>
                    </td>
                    <td>{NOMBRE_ROL[u.rol] || u.rol}</td>
                    <td>
                      <EstadoCuenta usuario={u} />
                    </td>
                    <td>{u.mfa_habilitado ? <Badge tono="ok">Activa</Badge> : <span className="cell-muted">—</span>}</td>
                    <td className="tabular">{u.ultimo_acceso ? formatRelativo(u.ultimo_acceso) : 'Nunca'}</td>
                    <td>
                      <div className="usuarios-acciones">
                        <Button compacto onClick={() => setAsignando(u)} disabled={!isOnline}>
                          Expedientes
                        </Button>
                        <Button compacto onClick={() => setEditando(u)} disabled={!isOnline}>
                          Editar
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {alta && (
        <AltaUsuario
          onCerrar={() => setAlta(false)}
          onCreado={(usuario) => {
            setUsuarios((lista) => [...lista, usuario])
            setAlta(false)
          }}
        />
      )}
      {editando && (
        <EditarUsuario
          usuario={editando}
          esPropia={editando.id === yo.id}
          onCerrar={() => setEditando(null)}
          onActualizado={actualizado}
        />
      )}
      {asignando && (
        <AsignarExpedientes
          usuario={asignando}
          expedientes={expedientes}
          onCerrar={() => setAsignando(null)}
          onGuardado={() => setAsignando(null)}
        />
      )}
    </div>
  )
}
