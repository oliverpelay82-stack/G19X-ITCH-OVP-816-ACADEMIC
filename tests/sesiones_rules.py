"""
Sesiones para las pruebas del rules-service (Módulo 7, PRD §5.1).

Las suites del rules leen el catálogo de la base de desarrollo sin modificarlo, así
que no se crean cuentas en ella:

- ``cliente(app)`` firma cada petición con un token SISTEMA nuevo (vida de 5 min),
  salvo que la petición traiga su propio Authorization. SISTEMA puede leer el
  catálogo y evaluar la vigencia, como el core y el ai-service.
- ``persona(rol)`` da las cabeceras de una cuenta ficticia que solo existe para
  este módulo de pruebas: se instala en la ``buscar_cuenta`` del rules activo y,
  para cualquier otro id, responde la base. La consulta real a ``usuarios`` la
  prueba ``test_rules_autorizacion`` contra la base de pruebas.

Se crea después de ``servicios.activar("rules-service")`` y de importar ``main``, y
se queda con esos módulos.
"""
from fastapi.testclient import TestClient


class SesionesRules:
    def __init__(self) -> None:
        from config import autorizacion, seguridad

        self._seguridad = seguridad
        self._cuenta = autorizacion.Cuenta
        self._ficticias: dict[str, object] = {}
        buscar_real = autorizacion.buscar_cuenta

        def buscar(db, usuario_id):
            return self._ficticias.get(usuario_id) or buscar_real(db, usuario_id)

        autorizacion.buscar_cuenta = buscar

    def persona(self, rol: str, *, activo: bool = True) -> dict[str, str]:
        id_ = f"ficticia-{rol.lower()}-{'activa' if activo else 'inactiva'}"
        correo = f"{id_}@example.com"
        self._ficticias[id_] = self._cuenta(id_, correo, rol, activo, False)
        token, _ = self._seguridad.emitir_token(id_, correo, f"Prueba {rol}", rol)
        return {"Authorization": f"Bearer {token}"}

    def cliente(self, app, **kwargs) -> TestClient:
        cliente = TestClient(app, **kwargs)

        def firmar(peticion):
            if "authorization" not in peticion.headers:
                peticion.headers.update(self._seguridad.cabeceras_sistema("pruebas"))

        cliente.event_hooks = {"request": [firmar], "response": []}
        return cliente
