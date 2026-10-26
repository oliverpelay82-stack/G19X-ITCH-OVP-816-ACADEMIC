# Ensayo de la demostración: 26/10/2026, commit `15a6438`

Recorrido completo de [`docs/GUION_DEMOSTRACION.md`](../GUION_DEMOSTRACION.md), en voz alta y cronometrado, sobre un clon limpio del repositorio levantado con `docker compose up -d --build`. Solo con el `.env` copiado de `.env.example` y la `GROQ_API_KEY`.

- Equipo: computadora del residente (Windows 11, Docker 29.9.2)
- Hora de inicio: 17:07 (primer intento de acceso)
- Tiempo de `docker compose up -d --build` hasta que `GET :8001/api/v1/health` responde: 53 s (17:04:52 a 17:05:45, con las imágenes en la caché de Docker; en un equipo sin ellas la construcción tarda más).

## Antes de empezar

| Punto | Resultado |
|---|---|
| `GET :8001/api/v1/health` responde y avisa de los secretos de demostración | Sí: base conectada y las dos advertencias (`JWT_SECRET` y `BOVEDA_LLAVE` de demostración) |
| `GET :8002/api/v1/health` y `GET :8003/api/v1/health` responden; el ai-service reporta el motor de inferencia | Sí: Groq Cloud disponible, temperatura 0.0 |
| La interfaz abre en http://localhost:5173 | Sí (200) |
| `gs-csf-01.pdf` a la mano | Sí: se subió en el paso 2 |

La prueba `prueba_entrega_docker.py --con-ia` no se corre aquí: va al final, sobre el commit que se entregue.

## Recorrido

| Paso | Cuenta | Resultado | Tiempo | Igual que el guion |
|---|---|---|---|---|
| 1 | validador | Sesión 17:09:52; empresa y expediente corporativo `EXP-PLU1-202610262310` 17:10:52; semáforo NO_CONFORME | 1:00 | Sí |
| 2 | validador | `gs-csf-01.pdf` custodiado 17:12:20 (huella SHA-256) | 1:28 | Sí |
| 3 | validador | Auditoría 17:12:56: CONFORME, confianza 0.95, VIGENTE | 0:36 | Sí |
| 4 | validador | «¿Cuál es el RFC del documento?»: respuesta correcta con su procedencia («datos del dictamen») | 1:15 (hasta la sesión del admin, con el cambio de cuenta) | Sí |
| 5 | admin | Sesión 17:14:11; asignación 17:14:49 a `consulta@example.com` | 1:15 | No: no se asignó al validador |
| 6 | auditor | Sesión 17:15:24; reporte PDF de cumplimiento global 17:15:52 | 0:35 | Sí: solo lectura y descarga, sin botones para modificar ni cargar |
| 7 | consulta | Sesión 17:16:25; solo el semáforo del expediente asignado, sin documentos ni bitácora | 0:26 | Sí |
| 8 | validador | Sesión 17:16:51; el expediente sigue NO_CONFORME por los obligatorios críticos faltantes | no registrado (cierre hacia las 17:17) | Sí |

**Total:** unos 7:30 desde la sesión del validador (17:09:52) hasta el cierre de ~17:17, o 10 min contando los intentos de acceso del inicio (el guion promete unos 8 minutos). Horas tomadas de la bitácora sellada del clon (`bitacora_auditoria`, eventos 13 a 24).

## Lo que salió distinto

- 17:07:00 a 17:07:25: seis intentos de acceso fallidos con una cuenta personal, que no existe en una instalación limpia; solo existen las cuatro `*@example.com`. Se entró como admin a las 17:07:57, antes del paso 1.
- Paso 5: el guion pide asignar el expediente a consulta y al validador; se asignó solo a consulta.

Ninguna diferencia viene del sistema: las dos son de operación y el guion ya las cubre (las contraseñas de las cuatro cuentas están en el README y el paso 5 pide las dos asignaciones). El guion no cambia.

## Preguntas que costó explicar

Ninguna.

## Cierre

`docker compose down -v` (contenedores y volúmenes) a las 17:18:01.
