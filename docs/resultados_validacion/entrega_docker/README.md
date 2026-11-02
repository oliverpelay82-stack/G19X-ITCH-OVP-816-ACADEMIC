# Prueba de entrega en Docker — 02/11/2026, commit `749a67e`

Evidencia de la instalación tal como la recibe PluriOne (RNF-11): un clon limpio del último commit de `main`, levantado con `docker compose up --build` en un proyecto propio (`plurione_entrega`, con su base y sus volúmenes nuevos) y recorrido con datos ficticios.

| Campo | Valor |
|---|---|
| Fecha | 2 de noviembre de 2026, 09:54 (UTC−6) |
| Commit | `749a67e` (`main`, el commit de la entrega) |
| Comando | `python scripts/prueba_entrega_docker.py --con-ia` |
| Entorno | Windows 11, Docker Engine 29.9.2, Docker Compose 5.6.1 |
| Resultado | **20 de 20 comprobaciones**, código de salida 0; `docker compose up --build` en 152 s |

`--con-ia` hace una auditoría y una pregunta reales al proveedor de IA (Groq) con la clave del equipo de desarrollo, que solo se escribió en el `.env` del clon temporal. Al terminar, la prueba bajó los contenedores con sus volúmenes y borró el clon. Sin `--con-ia`, la misma prueba comprueba que la auditoría responde 503 con la instrucción para configurar la clave.

Esta corrida repite la del 26/10 (`998b221`) porque las correcciones de la prueba funcional del 01/11/2026 (retroalimentación del corte 7) tocaron código y el `docker-compose.yml`: fechas impresas en la zona del negocio (`5da135d`), reinicio automático de los contenedores (`c633520`), pruebas con el «hoy» del sistema (`881ab27`) y nombres en lenguaje llano de tres eventos de la bitácora (`749a67e`). `boveda_y_salud.txt` se volvió a tomar en los contenedores de esta corrida (con `--conservar`; después se bajaron con sus volúmenes y se borró el clon).

Las capturas siguen siendo las de `d812943`: ninguna de las nueve vistas muestra lo que cambió desde entonces (la interfaz ya mostraba las fechas en la hora local, y el historial del expediente no aparece en ellas). La única diferencia visible es el folio del expediente de la corrida, que en `d812943` se generaba con la hora UTC del contenedor; desde `5da135d` lleva la hora de México.

**Resultado de la auditoría con IA: EN_REVISION.** La constancia de la prueba es un PDF sintético que declara no tener validez fiscal. El modelo, aun a temperatura 0, no es determinista entre corridas: el mismo PDF salió CONFORME sobre `8fadc84`, `e4a42bf` y `0709293` y en el ensayo de la demostración del 26/10 ([`../ensayo_demostracion_2026-10-26.md`](../ensayo_demostracion_2026-10-26.md)), y EN_REVISION sobre `e394be0`, `d812943`, `998b221` y en esta corrida. La salida de la prueba registra el estatus, no su motivo; en la corrida sobre `d812943` el motivo fue una discrepancia de tipo: se esperaba «Constancia de Situación Fiscal (SAT)» y el modelo identificó «Constancia de Situación Fiscal». Un documento EN_REVISION pasa a ratificación humana y no se rechaza. Por eso la prueba comprueba que la auditoría se guarde, no su veredicto. En todas las corridas el expediente queda NO_CONFORME. En esta y en la de `d812943`, con un índice de cumplimiento del 60 % (3 de 5 reglas, bloqueado por dos reglas críticas); en la de `d812943`, con 3 alertas: los dos documentos obligatorios críticos que faltan y la ratificación pendiente.

**Reinicio automático y hora del negocio (corte 7).** En los contenedores de esta corrida, los cinco tienen `restart: unless-stopped`. Al terminar el proceso principal del rules-service desde dentro de su contenedor, sin `docker stop`, Docker lo volvió a levantar en unos 2 s y su `/health` respondió 200 (en `boveda_y_salud.txt` el contador va de 1 a 2 porque antes se hizo la misma comprobación a mano). El contenedor del core corre en UTC (15:54) y el folio del expediente, `EXP-EMP2-202611020954`, lleva las 09:54 de México; el PDF del dictamen imprime la apertura, la verificación de la cadena y la trazabilidad en esa misma hora, como su encabezado.

**Candado de secretos (cortes del 21/10 y del 23/10/2026).** Con `USUARIOS_DEMO=false`, el core no arranca con el `JWT_SECRET` ni con la `BOVEDA_LLAVE` de demostración del compose, que son públicos, ni sin `BOVEDA_LLAVE`, porque guardaría los documentos en claro (RNF-04). `boveda_y_salud.txt` lo muestra en el contenedor construido. La comprobación de arranque rechaza los valores de demostración y la llave ausente fuera del modo demostración. Pasa con valores propios y con `USUARIOS_DEMO=true`, que es como levanta la entrega.

## Archivos

| Archivo | Qué muestra |
|---|---|
| [`salida_2026-11-02_749a67e.txt`](salida_2026-11-02_749a67e.txt) | Salida completa de la corrida de la entrega: las mismas 20 comprobaciones (auditoría guardada: EN_REVISION; cadena de la bitácora íntegra, 14 eventos). |
| [`salida_2026-10-26_998b221.txt`](salida_2026-10-26_998b221.txt) | Corrida del 26/10, sobre `998b221` (corte 5): 20 de 20, con el mismo resultado. |
| [`salida_2026-10-23_d812943.txt`](salida_2026-10-23_d812943.txt) | Corrida anterior, sobre `d812943`. Salida completa de la prueba: salud de los servicios, 401 sin sesión, inicio de sesión de las cuatro cuentas de demostración, permisos de la cuenta de consulta, catálogo de reglas, empresa con RFC ficticio, carga, auditoría con IA (guardada; EN_REVISION), chat, semáforo de un expediente incompleto (NO_CONFORME), cadena de la bitácora íntegra y reportes PDF y Excel con la ficha de custodia. |
| [`boveda_y_salud.txt`](boveda_y_salud.txt) | Contenedores con su política de reinicio, y versiones; el documento custodiado dentro del contenedor del core, cifrado (cabecera `PLVC1`, sin el `%PDF` del original; RNF-04); `GET /health` del core con sus dos advertencias de demostración (secreto de sesión y llave de la bóveda); los cuatro casos del candado de secretos; el reinicio automático del rules-service; el folio y las fechas del PDF del dictamen en la hora de México, y el frontend respondiendo. |
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
