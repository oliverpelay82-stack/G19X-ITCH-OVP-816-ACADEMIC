# Motor de Validación de Cumplimiento Documental

**Alumno:** Oliver Villanueva Pelay · **Matrícula:** G19X-ITCH-OVP-816
**Institución:** Instituto Tecnológico de Chilpancingo (TecNM) · Residencia profesional en PluriOne S.A. de C.V.

Sistema de validación documental automatizada para **PluriOne S.A. de C.V.**, desarrollado como proyecto de residencia profesional. Recibe los expedientes de una empresa, custodia cada documento con su huella SHA-256, lo lee (capa vectorial u OCR), extrae sus datos con un modelo de lenguaje y emite un **dictamen determinista y auditable** con semáforo, alertas y recomendaciones. Un analista ratifica los casos dudosos (Human-in-the-Loop).

La especificación oficial está en [`docs/ESPECIFICACIONES_DOC01_A_DOC08.txt`](docs/ESPECIFICACIONES_DOC01_A_DOC08.txt) (DOC-01 a DOC-08).

## Arquitectura

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| `services/core-service` | 8001 | Titulares, expedientes y documentos (magic bytes, límite de 15 MB, SHA-256, bóveda), dictámenes, bitácora inmutable, semáforo, alertas, reportes PDF/Excel y la reevaluación programada |
| `services/rules-service` | 8002 | Catálogo de reglas del DOC-05 (familias RIE, RCV, RSC, RDS) y evaluación determinista de la vigencia |
| `services/ai-service` | 8003 | Nivel 3 (PyMuPDF + Tesseract con OpenCV) y Nivel 4 (Groq Cloud, `qwen/qwen3.8-27b`), verificación de contenido y chat documental |
| `frontend` | 5173 | Interfaz React 19 + Vite |
| PostgreSQL 17 | 5432 | Base `plurione_compliance`, compartida por core y rules (cada uno con sus tablas) |

### Pipeline de validación (DOC-05)

1. **Integridad estructural y criptográfica:** magic bytes (PDF, JPEG, PNG), 15 MB como máximo y huella SHA-256 (NOM-151-SCFI-2016). Cada lectura del binario la recalcula (RIE-03).
2. **Reglas deterministas:** inventario obligatorio según el tipo de expediente (RIE-01), anexos (RIE-02) y vigencia (RCV-01, RCV-02 y RCV-03).
3. **Extracción de texto:** capa vectorial y, para páginas escaneadas, OCR `spa`.
4. **Análisis semántico:** el modelo **solo extrae** datos; el dictamen lo calculan reglas del servicio. La titularidad se acredita con el RFC o, si el documento no lo trae, con la razón social. Un tipo documental distinto al registrado pasa a revisión. Los elementos que el catálogo exige a cada tipo (reglas RSC/RDS) se verifican con una **cita literal** que se contrasta con el texto; un elemento no localizado deja el documento en revisión con la recomendación del catálogo, nunca lo rechaza (RSC-01).
5. **Gobernanza humana:** con confianza ≥ 0.85 el dictamen es CONFORME, y por debajo pasa a revisión humana. Una confianza baja nunca rechaza un documento: solo lo rechazan una vigencia vencida o un RFC ajeno.

El motor se ejecuta de dos formas, **manual o programada** (DOC-02): por documento o con «Auditar pendientes» en el expediente (HU-32), y con una reevaluación periódica del semáforo (`REEVALUACION_INTERVALO_HORAS`, 24 h por defecto). Subir un archivo nunca lo aprueba ni lo analiza por sí solo.

## Puesta en marcha

### Con Docker Compose

```bash
cp .env.example .env      # y llena GROQ_API_KEY (https://console.groq.com/keys); lo demás es opcional
docker compose up -d --build
```

La interfaz queda en http://localhost:5173 (ver «Acceso y roles» para entrar). La base se crea sola al arrancar, con el catálogo de reglas y las cuentas de demostración. Sin la clave, el sistema funciona completo salvo la auditoría y el chat con IA, que responden con la instrucción para configurarla. `python scripts/prueba_entrega_docker.py [--con-ia]` comprueba la instalación desde un clon limpio del último commit.

El rules-service carga el catálogo de reglas al arrancar (`AUTO_SEED=true`). La precarga es idempotente: solo inserta las reglas que faltan y no toca las editadas.

> **Producción: activar `RFC_DIGITO_ESTRICTO=true`.** Al dar de alta un titular, el core valida el formato, la longitud y la fecha del RFC, y calcula su dígito verificador con el algoritmo del SAT (módulo 11). Por defecto (`false`), un RFC cuyo dígito no coincide se acepta con la etiqueta «Dígito verificador no coincide (permitido en pruebas)», para poder trabajar con RFC ficticios. En producción, agregar `RFC_DIGITO_ESTRICTO=true` al `.env` de la raíz (en local, al `.env` del core-service) para rechazar esos RFC con un 422. La existencia del RFC no se consulta al SAT: se acredita con la Constancia de Situación Fiscal y la Opinión 32-D, cuyo RFC el motor coteja con el del titular durante la auditoría.

### Acceso y roles

Toda la interfaz y las API exigen iniciar sesión (JWT con `Authorization: Bearer`; solo `GET /api/v1/health` y `POST /api/v1/auth/login` son públicos). El `docker-compose.yml` arranca con `USUARIOS_DEMO=true`, que crea una cuenta ficticia por rol del DOC-04, con correos del dominio reservado `example.com`:

| Rol | Correo | Contraseña | Puede |
|---|---|---|---|
| Administrador | `admin@example.com` | `Admin-Demo-2026` | Todo, más cuentas de usuario, asignación de expedientes y alta o pausa de reglas |
| Validador | `validador@example.com` | `Validador-Demo-2026` | Empresas, expedientes, carga, auditoría, chat, ratificación y tipos de documento nuevos |
| Auditor | `auditor@example.com` | `Auditor-Demo-2026` | Consulta de expedientes, dictámenes, bitácora y reportes, sin modificar nada |
| Consulta | `consulta@example.com` | `Consulta-Demo-2026` | Solo el semáforo de los expedientes que el administrador le asigna |

> **Producción: `USUARIOS_DEMO=false`.** Estas contraseñas son públicas. En producción se define `USUARIOS_DEMO=false` en el `.env` de la raíz, junto con un `JWT_SECRET` propio de al menos 32 caracteres (el del compose es de demostración y `/health` del core lo advierte) y `ADMIN_INICIAL_EMAIL` y `ADMIN_INICIAL_CONTRASENA`: si no hay ninguna cuenta, el core crea ese administrador, que debe cambiar la contraseña en su primer acceso y desde la vista Usuarios da de alta al resto. Las cuentas de demostración que ya existan se desactivan desde esa vista (nunca se borran: la bitácora las referencia). Cada cuenta puede activar la verificación en dos pasos con una app autenticadora.

Los avisos por correo (RF-20) a los validadores asignados se encienden con `SMTP_HOST` y las demás variables `SMTP_*`; sin ellas, cada aviso queda en la bitácora como no enviado.

### Base de datos

[`db/base-de-datos.sql`](db/base-de-datos.sql) trae la estructura completa (tablas, índices y los triggers que hacen inmutables la bitácora y los dictámenes) con datos de prueba ficticios: el catálogo de 37 reglas del DOC-05, las cuatro cuentas de demostración, un titular con su expediente y la bitácora de esas altas. Se importa en una base vacía:

```bash
createdb -U postgres plurione_compliance
psql -U postgres -d plurione_compliance -f db/base-de-datos.sql
```

También se puede crear con `python scripts/setup_postgres.py` (sin las cuentas, que el core crea al arrancar con `USUARIOS_DEMO=true`). El archivo se regenera con `python scripts/exportar_base_sql.py`, que lo prueba importándolo en otra base vacía.

### En local

Se necesitan Python 3.12, Node 20.19 o superior, PostgreSQL 17 y Tesseract (con los idiomas `spa` y `eng`). Cada servicio lee su propio `.env`, que se copia de su `.env.example` (`DB_*` en core y rules, con la contraseña de tu PostgreSQL local, que también usa `scripts/setup_postgres.py`; `GROQ_API_KEY`, `TESSERACT_CMD`, `CORE_BASE_URL` y `RULES_BASE_URL` en el ai-service; ver [`services/ai-service/README.md`](services/ai-service/README.md)). Los tres llevan el mismo `JWT_SECRET`, y el del core, `ADMIN_INICIAL_EMAIL` y `ADMIN_INICIAL_CONTRASENA` o `USUARIOS_DEMO=true`.

Un entorno virtual del proyecto (`.venv`) instala las mismas versiones que Docker, más las herramientas de prueba (`requirements-dev.txt`):

```bash
python -m venv .venv
.venv\Scripts\activate                    # Windows (en Linux o macOS: source .venv/bin/activate)
pip install -r requirements-dev.txt
python scripts/setup_postgres.py          # base, tablas, catálogo de reglas y un expediente de demostración

cd services/core-service  && python main.py   # :8001
cd services/rules-service && python main.py   # :8002
cd services/ai-service    && python main.py   # :8003
cd frontend && npm ci && npm run dev          # :5173
```

La documentación interactiva de cada API está en `/docs` (por ejemplo, `http://127.0.0.1:8001/docs`), y el estado de cada servicio en `GET /api/v1/health`.

## Pruebas

Con el `.venv` activado:

```bash
pytest tests/ -v                                # core y rules (usa la base plurione_compliance_test)
cd services/ai-service && pytest tests/ -v      # ai-service, sin red (Groq, core y rules simulados)
cd frontend && npm run lint && npm run build
```

Los scripts de `scripts/` que levantan sus propios servicios (`e2e_api.py`, `prueba_sesion_roles.py`, `prueba_carga_lote.py`, `prueba_respaldo.py`, `prueba_lectura_anticipada.py`, `zap_api.py`) inician sesión con las cuentas de demostración sobre bases aisladas. Los que usan los servicios en marcha (`regresion_visual.py`, `prueba_error_422.py`, `prueba_sondeo_colgado.py`, `prueba_carga_fallida.py`) usan esas cuentas o, si la base local no las tiene, la de `PRUEBAS_EMAIL` y `PRUEBAS_CONTRASENA`.

Las pruebas del core-service recrean `plurione_compliance_test` y una bóveda temporal: nunca escriben en la base de trabajo, porque ahí la bitácora y los dictámenes son inmutables. La suite `test_niveles_3_4.py` del ai-service se omite si el servicio no está corriendo en :8003 con una `GROQ_API_KEY` válida. El workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) ejecuta todo lo anterior en cada push.

## Lo que todavía no funciona

- **Cifrado de la bóveda en reposo (RNF-04):** los documentos se custodian con su huella SHA-256 y se verifican en cada lectura, pero el archivo no se cifra.
- **TLS y aislamiento de red (RNF-05, parcial):** solo va cifrada la conexión con el proveedor de IA. El proxy inverso con TLS es del despliegue de PluriOne, y el docker-compose de demostración publica los puertos de cada servicio.
- **Tablas y pares clave-valor (RF-10, parcial):** se extrae el texto de cada página; los datos que dictamina el motor salen de ese texto, no de una estructura tabular.
- **Disponibilidad (RNF-09):** hay comprobaciones de salud y reinicio automático en Docker, pero no una medición documentada.
- **Búsqueda semántica en todo el corpus (RF-12):** fuera del alcance acordado; la búsqueda dentro de cada documento sí existe (chat documental).
- **IA con el plan gratuito de Groq:** 8,000 tokens por minuto y 200,000 por día. Sin `GROQ_API_KEY`, todo funciona salvo la auditoría con IA y el chat.

El estado de cada requerimiento está en [`docs/ESTADO_DEL_DESARROLLO.md`](docs/ESTADO_DEL_DESARROLLO.md); los requerimientos, en [`docs/PRD.md`](docs/PRD.md), y el producto mínimo viable, en [`docs/MVP.md`](docs/MVP.md).

## Uso de IA

En el desarrollo se usó **Claude Code** (Anthropic, modelo Claude Opus) como asistente de programación. Las instrucciones que sigue están en [`CLAUDE.md`](CLAUDE.md), y cada commit en el que participó lo declara con la línea `Co-Authored-By`.

- **Para qué:** analizar los DOC y redactar requerimientos (PRD, MVP), diseñar los cambios con diagramas UML, escribir código y pruebas, y documentar el estado del desarrollo.
- **Cómo se revisó lo que generó:** cada propuesta de cambio se aprueba antes de tocar el código, con su análisis de impacto. Cada corrección lleva una prueba de regresión que falla sin ella. Las suites de pytest y el lint y build del frontend corren en el CI en cada push. Los resultados se midieron aparte: el Gold Standard de 42 casos ([`services/ai-service/evaluacion/`](services/ai-service/evaluacion/)), OWASP ZAP y los benchmarks ([`docs/resultados_validacion/`](docs/resultados_validacion/)). Las decisiones de alcance y de diseño son del autor.

Esto es distinto de la IA *del producto*: el motor usa un modelo de lenguaje en Groq Cloud solo para extraer datos con evidencia citada; el dictamen lo emiten reglas deterministas y lo ratifica una persona.

## Estructura

```
services/            core-service, rules-service y ai-service (FastAPI)
frontend/            interfaz React 19 (Vite)
db/                  base-de-datos.sql: estructura y datos de prueba
scripts/             instalación, respaldo, exportación de la base y pruebas extremo a extremo
tests/               pruebas de core y rules
storage_vault/       bóveda física de binarios (no versionada)
docs/                especificación oficial (DOC-01 a DOC-08), PRD, MVP, estado del desarrollo, UML y validación
docker-compose.yml   plurione-db, plurione-core, plurione-rules, plurione-ai, plurione-frontend
```
