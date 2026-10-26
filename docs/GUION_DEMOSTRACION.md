# Guion de la demostración en vivo

Recorrido de unos 8 minutos con las cuatro cuentas de demostración (`*@example.com`, contraseñas en el [README](../README.md#acceso-y-roles)) sobre una instalación con `docker compose up -d --build`. Se ve lo que hace cada rol, lo que la cuenta de consulta no puede hacer y que un expediente incompleto no se aprueba. Todos los datos son ficticios.

## Antes de empezar

- [ ] `python scripts/prueba_entrega_docker.py --con-ia` sobre el último commit: 20 de 20 comprobaciones.
- [ ] `docker compose up -d --build` con `GROQ_API_KEY` en el `.env` de la raíz; `GET :8001/api/v1/health` responde y avisa que corren los secretos de demostración, como corresponde al compose.
- [ ] A la mano, la constancia ficticia `services/ai-service/evaluacion/gold_standard/documentos/gs-csf-01.pdf` (RFC `PLU180514AB3`, PLURIONE S.A. DE C.V., emitida el 10/09/2026: vigente hasta el 09/12/2026 por RCV-03).
- [ ] Plan B, si la IA no responde: la auditoría entra en la cola de reintento (DOC-05, Tabla 1) y se muestra la del ensayo en [`resultados_validacion/entrega_docker/`](resultados_validacion/entrega_docker/).

## Recorrido

| Paso | Cuenta | Qué se hace | Qué se señala |
|---|---|---|---|
| 1 | `validador@example.com` | Iniciar sesión; registrar la empresa con RFC `PLU180514AB3` y abrir un expediente corporativo | La pantalla de acceso hace una pregunta a la vez; el RFC se valida con el algoritmo del SAT |
| 2 | validador | Subir `gs-csf-01.pdf` | Huella SHA-256 y bóveda cifrada (AES-256-GCM); el semáforo queda **NO_CONFORME**: faltan los obligatorios críticos del expediente corporativo. Subir archivos nunca aprueba un expediente |
| 3 | validador | Auditar la constancia y abrir la cita en el visor | La IA solo extrae; las reglas deciden titularidad (RFC) y vigencia (RCV-03, 90 días). El motivo cita el texto del documento |
| 4 | validador | Preguntar en el chat «¿Cuál es el RFC del documento?» | La respuesta dice su procedencia (datos del dictamen, pasaje o modelo) |
| 5 | `admin@example.com` | En Usuarios, asignar el expediente a `consulta@example.com` y al validador; ver la bitácora | Solo el administrador gestiona cuentas, asignaciones y reglas; cada asignación queda en la bitácora sellada |
| 6 | `auditor@example.com` | Abrir el expediente, el dictamen, la bitácora y descargar el reporte PDF | Ve todo, pero no tiene botones de escritura y el servicio responde 403 si lo intenta; el reporte imprime el último sello de la cadena |
| 7 | `consulta@example.com` | Iniciar sesión | Solo ve el semáforo de los expedientes asignados. No ve empresas, documentos, dictámenes, chat ni bitácora, y no carga ni audita: la interfaz no lo ofrece y la API responde 403 (comprobado en la prueba de entrega) |
| 8 | validador | Volver al expediente | Sigue NO_CONFORME aunque la constancia esté auditada: la completitud y el índice de cumplimiento muestran los obligatorios que faltan |

## Si preguntan

- **¿Y si la cuenta de consulta llama a la API directamente?** Cada servicio autoriza por el rol guardado en la base en cada petición, no por lo que muestra la interfaz (`tests/test_permisos_roles.py` recorre la matriz completa).
- **¿Esto corre así en producción?** No: con `USUARIOS_DEMO=false` no se crean estas cuentas, y el core no arranca con la llave y el `JWT_SECRET` del compose ni sin `BOVEDA_LLAVE` (README, «Los secretos de demostración no llegan a producción»). La contraseña de la base también se cambia: en el `.env` se define una `DB_PASSWORD` propia, porque la del compose (`plurione-demo`) es pública y PostgreSQL queda publicado en el puerto 5433.
