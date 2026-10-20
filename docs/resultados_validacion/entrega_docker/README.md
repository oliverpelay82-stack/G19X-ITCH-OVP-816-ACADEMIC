# Prueba de entrega en Docker — 20/10/2026, commit `e394be0`

Evidencia de la instalación tal como la recibe PluriOne (RNF-11): un clon limpio del commit publicado en `main`, levantado con `docker compose up --build` en un proyecto propio (`plurione_entrega`, con su base y sus volúmenes nuevos) y recorrido con datos ficticios.

| Campo | Valor |
|---|---|
| Fecha | 20 de octubre de 2026, 15:36 a 15:37 (UTC−6) |
| Commit | `e394be0` (`origin/main`) |
| Comando | `python scripts/prueba_entrega_docker.py --con-ia --conservar` |
| Entorno | Windows 11, Docker Engine 29.9.1, Docker Compose 5.6.0 |
| Resultado | **20 de 20 comprobaciones**, código de salida 0; `docker compose up --build` en 37 s |

`--con-ia` hace una auditoría y una pregunta reales al proveedor de IA (Groq) con la clave del equipo de desarrollo, que solo se escribió en el `.env` del clon temporal. `--conservar` dejó los contenedores en marcha para tomar las capturas y revisar la bóveda; después se bajaron con sus volúmenes y se borró el clon. Sin `--con-ia`, la misma prueba comprueba que la auditoría responde 503 con la instrucción para configurar la clave.

**Resultado de la auditoría con IA: EN_REVISION.** La constancia de la prueba es un PDF sintético que declara no tener validez fiscal y no trae régimen, domicilio ni cadena original. En esta corrida el modelo la clasificó como otro tipo de documento y el motor la envió a ratificación humana (confianza 0.95, huella RIE-03 verificada): ante una discrepancia de tipo, el motor no aprueba solo. En las dos corridas del mismo día sobre `8fadc84` y `e4a42bf`, el mismo PDF salió CONFORME; el modelo, aun a temperatura 0, no es determinista entre corridas, y la prueba comprueba que la auditoría se guarde, no su veredicto. Por eso el expediente queda con 3 alertas (los dos obligatorios críticos faltantes y la ratificación pendiente).

## Archivos

| Archivo | Qué muestra |
|---|---|
| [`salida_2026-10-20_e394be0.txt`](salida_2026-10-20_e394be0.txt) | Salida completa de la prueba: salud de los servicios, 401 sin sesión, inicio de sesión de las cuatro cuentas de demostración, permisos de la cuenta de consulta, catálogo de reglas, empresa con RFC ficticio, carga, auditoría con IA (guardada; EN_REVISION), chat, semáforo de un expediente incompleto (NO_CONFORME), cadena de la bitácora íntegra y reportes PDF y Excel con la ficha de custodia. |
| [`boveda_y_salud.txt`](boveda_y_salud.txt) | Contenedores y versiones; el documento custodiado dentro del contenedor del core, cifrado (cabecera `PLVC1`, sin el `%PDF` del original; RNF-04); `GET /health` del core con sus dos advertencias de demostración (secreto de sesión y llave de la bóveda), y el frontend respondiendo. |
| [`capturas/`](capturas/) | Pantallas principales a 1366 × 768 con la cuenta de administración, sobre los datos que dejó la corrida. |

## Capturas

| Captura | Vista |
|---|---|
| [`00_acceso.png`](capturas/00_acceso.png) | Inicio de sesión, una pregunta a la vez, con el indicador de servicios en línea |
| [`01_expedientes.png`](capturas/01_expedientes.png) | Expedientes con sus métricas (1.6 KB bajo custodia): el expediente de la corrida, No conforme |
| [`02_expediente_detalle.png`](capturas/02_expediente_detalle.png) | El expediente desplegado: motivos (dos obligatorios críticos faltantes y la constancia pendiente de ratificación), índice de cumplimiento (60 %, bloqueado por dos reglas críticas) y documentos requeridos |
| [`03_empresas.png`](capturas/03_empresas.png) | Empresas |
| [`04_boveda.png`](capturas/04_boveda.png) | Bóveda: la constancia custodiada, En revisión, con su huella SHA-256 |
| [`05_alertas.png`](capturas/05_alertas.png) | Alertas del expediente, de la más grave a la menos grave, con su recomendación |
| [`06_reportes.png`](capturas/06_reportes.png) | Reportes con sus gráficas |
| [`07_reglas.png`](capturas/07_reglas.png) | Catálogo de reglas del DOC-05 |
| [`08_usuarios.png`](capturas/08_usuarios.png) | Usuarios: las cuatro cuentas de demostración, una por rol |

## Reproducir

Desde la raíz del repositorio, con Docker en marcha y los puertos 5433, 8001 a 8003 y 5173 libres:

```bash
python scripts/prueba_entrega_docker.py            # sin clave de IA
python scripts/prueba_entrega_docker.py --con-ia   # con GROQ_API_KEY en el entorno o en services/ai-service/.env
```

La prueba siempre baja los contenedores, borra sus volúmenes y el clon, salvo con `--conservar`.
