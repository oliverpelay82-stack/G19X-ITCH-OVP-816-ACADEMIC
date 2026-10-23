# Prueba de entrega en Docker — 23/10/2026, commit `d812943`

Evidencia de la instalación tal como la recibe PluriOne (RNF-11): un clon limpio del último commit de `main`, levantado con `docker compose up --build` en un proyecto propio (`plurione_entrega`, con su base y sus volúmenes nuevos) y recorrido con datos ficticios.

| Campo | Valor |
|---|---|
| Fecha | 23 de octubre de 2026, 09:16 (UTC−6) |
| Commit | `d812943` (`main`; incluye el candado de secretos de los cortes del 21/10 y del 23/10/2026) |
| Comando | `python scripts/prueba_entrega_docker.py --con-ia --conservar` |
| Entorno | Windows 11, Docker Engine 29.9.2, Docker Compose 5.6.1 |
| Resultado | **20 de 20 comprobaciones**, código de salida 0; `docker compose up --build` en 174 s |

`--con-ia` hace una auditoría y una pregunta reales al proveedor de IA (Groq) con la clave del equipo de desarrollo, que solo se escribió en el `.env` del clon temporal. `--conservar` dejó los contenedores en marcha para tomar las capturas y revisar la bóveda; después se bajaron con sus volúmenes y se borró el clon. Sin `--con-ia`, la misma prueba comprueba que la auditoría responde 503 con la instrucción para configurar la clave.

**Resultado de la auditoría con IA: EN_REVISION.** La constancia de la prueba es un PDF sintético que declara no tener validez fiscal. El modelo, aun a temperatura 0, no es determinista entre corridas: el mismo PDF salió CONFORME sobre `8fadc84`, `e4a42bf` y `0709293`, y EN_REVISION sobre `e394be0`, en una primera corrida del 21/10 y en esta. En esta corrida, el motivo es una discrepancia de tipo: se esperaba «Constancia de Situación Fiscal (SAT)» y el modelo identificó «Constancia de Situación Fiscal». El documento pasa a ratificación humana y no se rechaza. Por eso la prueba comprueba que la auditoría se guarde, no su veredicto. El expediente queda NO_CONFORME con 3 alertas: los dos documentos obligatorios críticos que faltan y la ratificación pendiente (índice de cumplimiento del 60 %, 3 de 5 reglas, bloqueado por dos reglas críticas).

**Candado de secretos (cortes del 21/10 y del 23/10/2026).** Con `USUARIOS_DEMO=false`, el core no arranca con el `JWT_SECRET` ni con la `BOVEDA_LLAVE` de demostración del compose, que son públicos, ni sin `BOVEDA_LLAVE`, porque guardaría los documentos en claro (RNF-04). `boveda_y_salud.txt` lo muestra en el contenedor construido. La comprobación de arranque rechaza los valores de demostración y la llave ausente fuera del modo demostración. Pasa con valores propios y con `USUARIOS_DEMO=true`, que es como levanta la entrega.

## Archivos

| Archivo | Qué muestra |
|---|---|
| [`salida_2026-10-23_d812943.txt`](salida_2026-10-23_d812943.txt) | Salida completa de la prueba: salud de los servicios, 401 sin sesión, inicio de sesión de las cuatro cuentas de demostración, permisos de la cuenta de consulta, catálogo de reglas, empresa con RFC ficticio, carga, auditoría con IA (guardada; EN_REVISION), chat, semáforo de un expediente incompleto (NO_CONFORME), cadena de la bitácora íntegra y reportes PDF y Excel con la ficha de custodia. |
| [`boveda_y_salud.txt`](boveda_y_salud.txt) | Contenedores y versiones; el documento custodiado dentro del contenedor del core, cifrado (cabecera `PLVC1`, sin el `%PDF` del original; RNF-04); `GET /health` del core con sus dos advertencias de demostración (secreto de sesión y llave de la bóveda); los cuatro casos del candado de secretos y el frontend respondiendo. |
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
