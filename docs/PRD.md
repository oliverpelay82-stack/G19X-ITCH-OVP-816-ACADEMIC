# PRD — Motor de Validación de Cumplimiento Documental

**Product Requirements Document**

| Campo | Valor |
|---|---|
| Producto | Motor de Validación de Cumplimiento Documental mediante Inteligencia Artificial |
| Cliente | PluriOne S.A. de C.V. (Develop Talent & Technology) |
| Proyecto | Residencia profesional — Instituto Tecnológico de Chilpancingo, periodo agosto–diciembre 2026 |
| Responsable del producto (Product Owner) | Lic. Juan Méndez Herrera, Director Comercial de PluriOne |
| Desarrollo (Scrum Master / Desarrollador) | Oliver Villanueva Pelay, residente (No. de control 21520500) |
| Stakeholder evaluador | Edgar Loheffelmman (PluriOne) |
| Asesor interno | Dr. Wilfrido Campos Francisco |
| Documentos relacionados | [MVP.md](MVP.md) — producto mínimo viable; [ESTADO_DEL_DESARROLLO.md](ESTADO_DEL_DESARROLLO.md) — avance de la implementación |

> **Fuentes.** Este PRD consolida los requerimientos de los documentos oficiales del proyecto, todos anteriores al desarrollo: el anteproyecto de residencia y los entregables DOC-01 a DOC-08 (13 al 18 de septiembre de 2026; [ESPECIFICACIONES_DOC01_A_DOC08.txt](ESPECIFICACIONES_DOC01_A_DOC08.txt)), que el DOCUMENTO GENERAL integra. Cada sección indica su fuente entre corchetes; «DG» es el DOCUMENTO GENERAL. El PRD define qué debe hacer el sistema y por qué; el estado de cada requerimiento, los resultados medidos, los cambios y las extensiones agregadas durante el desarrollo están en [ESTADO_DEL_DESARROLLO.md](ESTADO_DEL_DESARROLLO.md).

---

## Índice

1. [Resumen del producto](#1-resumen-del-producto)
2. [Problema](#2-problema)
3. [Objetivos](#3-objetivos)
4. [Alcance](#4-alcance)
5. [Usuarios, roles y permisos](#5-usuarios-roles-y-permisos)
6. [Flujos principales](#6-flujos-principales)
7. [Requerimientos funcionales](#7-requerimientos-funcionales)
8. [Historias de usuario](#8-historias-de-usuario)
9. [Reglas de negocio y catálogo de validación](#9-reglas-de-negocio-y-catálogo-de-validación)
10. [Pipeline de validación y semáforo](#10-pipeline-de-validación-y-semáforo)
11. [Requerimientos no funcionales](#11-requerimientos-no-funcionales)
12. [Arquitectura y solución técnica](#12-arquitectura-y-solución-técnica)
13. [Experiencia de usuario](#13-experiencia-de-usuario)
14. [Criterios de aceptación del producto](#14-criterios-de-aceptación-del-producto)
15. [Métricas de éxito](#15-métricas-de-éxito)
16. [Plan de entrega](#16-plan-de-entrega)
17. [Riesgos](#17-riesgos)
18. [Dependencias y supuestos](#18-dependencias-y-supuestos)
19. [Glosario](#19-glosario)

---

## 1. Resumen del producto

Aplicación web empresarial que automatiza la dictaminación del cumplimiento documental de expedientes **jurídicos, corporativos y regulatorios** de personas morales. Combina tres capas [DG Cap. IV §4.1, Cap. VI §6.3]:

1. **Motor de reglas determinista.** Evalúa la completitud del expediente (documentos obligatorios y anexos), la vigencia de cada documento y su integridad criptográfica, sin inteligencia artificial y con resultados exactos.
2. **Análisis inteligente.** Extrae el texto de los documentos (PyMuPDF y Tesseract OCR) y lo analiza con un modelo de lenguaje (Qwen 3.8 de 27B, servido por Groq Cloud) para identificar el tipo documental, el RFC, la razón social y las fechas.
3. **Supervisión humana (Human-in-the-Loop).** Los resultados dudosos se turnan al analista, que confirma o corrige con una justificación que queda en una bitácora inmutable.

El resultado se expresa como un **semáforo por expediente** (Verde = Conforme, Amarillo = En revisión, Rojo = No conforme), con **alertas y recomendaciones correctivas**, y se exporta como **dictamen formal en PDF y Excel**.

---

## 2. Problema

[Anteproyecto, «Planteamiento del Problema»; DG Cap. I y Cap. VI §6.2]

Las organizaciones que manejan expedientes jurídicos y corporativos deben verificar decenas de documentos por expediente en cuanto a integridad, vigencia, obligatoriedad de anexos y cumplimiento de requisitos regulatorios. Hoy esa validación es manual y genera cinco problemas concretos:

| # | Proceso actual | Problema |
|---|---|---|
| P1 | Verificación de integridad: el responsable revisa cada documento a mano. | Toma varias horas por expediente; los documentos faltantes pasan desapercibidos y el resultado varía según el revisor, porque no existe una lista de verificación común. |
| P2 | Control de vigencia en hojas de cálculo. | Las hojas no siempre están actualizadas: los documentos vencidos se descubren hasta la auditoría («cuando algo se vence nadie se entera hasta que les cae la auditoría», DOC-01). |
| P3 | Verificación de anexos según la experiencia del revisor. | Con rotación de personal o requisitos nuevos, se omiten anexos obligatorios sin que nadie lo advierta. |
| P4 | Cumplimiento regulatorio cruzando listas de verificación a mano. | Errores e inconsistencias; criterios obsoletos cuando cambia la regulación. |
| P5 | Preparación de auditorías reactiva. | No hay registro de qué se validó, con qué criterio ni cuándo; los reportes se compilan a mano, sin visibilidad en tiempo real. |

---

## 3. Objetivos

### 3.1 Objetivo general

Desarrollar un motor inteligente de validación de cumplimiento documental para PluriOne S.A. de C.V. que valide automáticamente la integridad de expedientes jurídicos y corporativos mediante reglas configurables, inteligencia artificial y análisis semántico, evaluando la obligatoriedad de anexos, la vigencia de documentos y el cumplimiento de requisitos regulatorios, y que genere alertas y recomendaciones para facilitar auditorías y procesos de compliance [Anteproyecto, «Objetivo General»].

### 3.2 Objetivos específicos

| ID | Objetivo [Anteproyecto] | Entregable asociado |
|---|---|---|
| OE-01 | Analizar los requisitos documentales y regulatorios. | DOC-01 a DOC-04 (DG Caps. I–IV) |
| OE-02 | Diseñar la arquitectura tecnológica: microservicios, APIs, modelo de datos en PostgreSQL e integración de IA. | DOC-08 (DG Cap. VIII) |
| OE-03 | Implementar las reglas de validación, el análisis inteligente y el frontend. | Sistema en el repositorio |
| OE-04 | Validar la precisión y el desempeño: pruebas funcionales, de integración, de precisión de la IA y de seguridad. | DG Cap. X |
| OE-05 | Elaborar la documentación técnica y el plan de soporte. | Manuales (fase de Documentación) |

### 3.3 Objetivos de producto

Derivados de los problemas P1–P5 y de los beneficios esperados [DG Cap. VI §6.8]:

- **Detección preventiva de vencimientos** (P2): alertar antes del vencimiento y marcar automáticamente los documentos vencidos.
- **Estandarización de criterios** (P1, P3, P4): que todo expediente del mismo tipo se evalúe con las mismas reglas, configurables sin modificar código.
- **Trazabilidad y auditoría inmutable** (P5): cada validación registrada con la huella SHA-256 del documento, el resultado y, en su caso, la ratificación humana.

---

## 4. Alcance

### 4.1 Dentro del alcance

Siete módulos funcionales [Anteproyecto, «Alcances»; DG Cap. IV §4.2, Cap. VI §6.4]:

| Módulo | Propósito |
|---|---|
| M1 Gestión de Expedientes | Crear, clasificar (jurídico, corporativo, regulatorio), buscar y versionar expedientes; cargar documentos con huella SHA-256. |
| M2 Reglas de Validación Configurables | Definir documentos obligatorios por tipo de expediente, anexos, severidad y acción, sin modificar el código. |
| M3 Análisis Inteligente | Extracción de texto (OCR) y análisis semántico con cita de evidencia y nivel de confianza. |
| M4 Verificación de Vigencia | Control determinista de fechas de emisión y vencimiento, con ventanas de anticipación. |
| M5 Alertas y Recomendaciones | Alertas ante documentos faltantes, vencidos, anexos ausentes o desviaciones, con recomendación correctiva. |
| M6 Reportes y Panel de Control | Indicadores de cumplimiento y reportes exportables en PDF y Excel. |
| M7 Administración y Seguridad | Autenticación, roles y permisos (RBAC) y bitácora inmutable de auditoría. |

Tipos de documento: los tres inventarios del DOC-02 (corporativos, jurídicos y regulatorios) [DG Cap. I §1.4, Tablas 2–4]; el catálogo base del código tiene 23: 21 tipos del DOC-02, cuyas Tablas 2 a 4 suman 22 filas porque el poder notarial aparece en la corporativa y en la jurídica, más la opinión de cumplimiento 32-D y la carátula bancaria que ya custodiaba el expediente B2B, ampliables por el administrador [DG Cap. I, «Extensibilidad del Catálogo»].

### 4.2 Fuera del alcance

- **Documentos de identificación personal**: INE, CURP, actas de nacimiento, comprobantes de domicilio personales, pasaportes y títulos universitarios. El motor procesa exclusivamente documentación corporativa y contractual de organizaciones [DOC-01; DG Cap. I, hallazgo H1].
- **Indexación y búsqueda semántica sobre todo el corpus documental (RF-12):** no tiene historia de usuario, prioridad ni lugar en el cronograma, y no interviene en el dictamen; la búsqueda dentro de cada documento la cubre el chat documental.
- La decisión contractual final: el sistema asiste, pero ninguna decisión con impacto legal se toma de forma exclusivamente automática [DG Cap. III §3.6, RN-05].

---

## 5. Usuarios, roles y permisos

[DG Cap. IV §4.3, Tabla 8 — modelo RBAC alineado con ISO/IEC 27001]

| Rol | Quién es | Permisos principales |
|---|---|---|
| Administrador del Sistema | Personal de TI y administradores de PluriOne. | Gestión de usuarios, repositorios de almacenamiento, tipos de expediente y reglas de validación; supervisión de bitácoras. |
| Responsable de Cumplimiento (Validador) | Abogados corporativos y analistas operativos. | Carga de expedientes y documentos, ejecución del motor, revisión de alertas, alta de documentos por sector y ratificación de hallazgos de la IA. |
| Auditor | Supervisión legal, fiscal o de calidad. | Solo lectura de expedientes validados, bitácora inmutable, nivel de confianza y exportación de reportes. |
| Usuario de Consulta | Clientes u operadores. | Solo el semáforo de sus expedientes asignados, sin edición ni configuración. |

El catálogo de endpoints (DOC-08) define la jerarquía de acceso ADMIN > AUDITOR > OPERADOR, más el perfil SISTEMA para las llamadas entre microservicios [DG Cap. VIII §8.4, Tabla 20].


**Roles.** Los cuatro del DOC-04 (Tabla 1), de la HU-05 y del criterio de aceptación: `ADMIN`, `VALIDADOR`, `AUDITOR` y `CONSULTA`. El `OPERADOR` del DOC-08 es el `VALIDADOR`. La jerarquía lineal ADMIN > AUDITOR > OPERADOR del DOC-08 se sustituye por la matriz de §5.1, porque le daría al Auditor la edición del Operador, contra el «solo lectura» del DOC-04, y no contempla al Usuario de Consulta de la HU-31 (ESTADO_DEL_DESARROLLO §4). `SISTEMA` es el perfil de servicio del DOC-08: nunca se asigna a una persona.

### 5.1 Matriz de permisos

[DOC-04 Tabla 1; DOC-05 RDS-01 («el administrador o validador puede dar de alta… un nuevo tipo de documento»); DOC-08 Tabla 3; [diagrama de casos de uso](uml/m7-casos-de-uso-acceso.puml)]

Por acción (lo que ve cada rol en la interfaz):

| Acción | ADMIN | VALIDADOR | AUDITOR | CONSULTA |
|---|:-:|:-:|:-:|:-:|
| Gestionar usuarios: alta, rol, desactivar o reactivar, restablecer contraseña o MFA (HU-05) | ✔ | | | |
| Asignar usuarios a un expediente (HU-31, RF-20) | ✔ | | | |
| Pausar o reactivar reglas; dar de alta reglas de cualquier familia | ✔ | | | |
| Dar de alta un tipo de documento nuevo con su criterio para la IA (RF-09, RDS-01) | ✔ | ✔ | | |
| Registrar empresas y expedientes, cargar documentos y corregir datos de captura | ✔ | ✔ | | |
| Auditar documentos, usar el chat documental y ratificar dictámenes | ✔ | ✔ | | |
| Consultar expedientes, documentos, visor, dictámenes, alertas, reglas y bitácora; exportar reportes y descargar el original | ✔ | ✔ | ✔ | |
| Ver el semáforo de sus expedientes asignados (HU-31) | ✔ | ✔ | ✔ | ✔ |
| Iniciar sesión, cambiar su contraseña y activar su MFA | ✔ | ✔ | ✔ | ✔ |

Por endpoint (lo que aplica cada servicio; «Lectura» = ADMIN, VALIDADOR y AUDITOR; «Operación» = ADMIN y VALIDADOR):

| Servicio | Endpoint | Acceso |
|---|---|---|
| Los tres | `GET /health` | Público |
| core | `POST /auth/login` | Público |
| core | `GET /auth/me`, `POST /auth/cambiar-contrasena`, `POST /auth/mfa/generar`, `POST /auth/mfa/activar`, `POST /auth/mfa/desactivar` | Cualquier usuario autenticado |
| core | `GET`, `POST /usuarios`; `PATCH /usuarios/{id}` | ADMIN |
| core | `GET`, `PUT /expedientes/{id}/asignaciones`; `GET`, `PUT /usuarios/{id}/expedientes` (las mismas asignaciones vistas desde la cuenta, para la vista Usuarios) | ADMIN |
| core | `GET /expedientes/asignados` | Cualquier usuario autenticado (devuelve solo los suyos) |
| core | `POST /titulares`, `PATCH /titulares/{id}`, `POST /expedientes`, `PATCH /expedientes/{id}`, `POST /documentos/upload`, `POST /dictamenes/{id}/ratificar` | Operación |
| core | `GET /titulares`, `GET /expedientes`, `GET /expedientes/{id}`, `GET /alertas`, `GET /bitacora`, `GET /bitacora/verificar-cadena`, `GET /reportes/*` | Lectura |
| core | `GET /documentos`, `GET /documentos/{id}`, `GET /documentos/expediente/{id}`, `GET /documentos/{id}/integridad`, `GET /dictamenes`, `GET /dictamenes/{id}` | Lectura y SISTEMA |
| core | `GET /documentos/{id}/contenido?descarga=true` (descarga del original) | Lectura |
| core | `GET /documentos/{id}/contenido` (lectura de máquina), `POST /dictamenes`, `POST /documentos/{id}/procesamiento-diferido` | Solo SISTEMA |
| rules | `GET /reglas`, `GET /reglas/{id}`, `GET /reglas/version`, `GET /reglas/tipos-documento`, `GET /reglas/documentos-obligatorios`, `POST /reglas/evaluar-vigencia` | Lectura y SISTEMA |
| rules | `POST /reglas` | ADMIN (cualquier familia); VALIDADOR solo con `familia_regla` RDS |
| rules | `PATCH /reglas/{id}/activo` | ADMIN |
| ai | `POST /ai/analisis-semantico`, `POST /ai/documentos/{id}/preparar`, `POST /ai/documentos/{id}/anticipar`, `POST /ai/chat-documento`, `POST /ai/extraer-texto` | Operación |
| ai | `GET /ai/documentos/{id}/visor`, `GET /ai/documentos/{id}/paginas/{n}`, `POST /ai/documentos/{id}/localizar`, `GET /ai/configuracion-ocr` | Lectura |

Sin token, con un token inválido o vencido, o con la cuenta desactivada: 401. Con un rol sin permiso: 403. La interfaz oculta lo que el rol no puede hacer, pero la regla la aplica el servicio. Una prueba recorre la matriz completa (cada endpoint con cada rol y el estado esperado).

### 5.2 Diseño del Módulo 7

[DOC-08: JWT HMAC-SHA256, bcrypt, tabla `usuarios`, perfil SISTEMA; DOC-04 RF-20, RF-25 a RF-27; DOC-03: ISO/IEC 27001 A.5.15, A.5.17, A.8.5 y A.8.15. Diagramas: [inicio de sesión](uml/m7-secuencia-inicio-sesion.puml), [propagación SISTEMA](uml/m7-secuencia-propagacion-sistema.puml) y [correo](uml/rf20-actividad-notificacion-correo.puml)]

**Autenticación (RF-25, HU-06).**
- Cuentas locales con correo y contraseña (bcrypt). No se usa Microsoft Entra ID (ESTADO_DEL_DESARROLLO §4): el token es un JWT HS256 firmado con `JWT_SECRET`, con `sub`, `email`, `nombre`, `rol`, `iat` y `exp`. Vigencia: `JWT_EXPIRACION_MINUTOS` (480 por omisión, una jornada), sin tokens de renovación. La interfaz lo guarda en `sessionStorage` y lo envía como `Authorization: Bearer`.
- **MFA (RF-25; [diagrama](uml/m7-actividad-mfa.puml)):** TOTP opcional por usuario (RFC 6238, apps autenticadoras). El propio usuario lo da de alta en dos pasos: `POST /auth/mfa/generar` con su contraseña (devuelve el secreto y la URI `otpauth://`) y `POST /auth/mfa/activar` con el primer código de su app. Con MFA habilitado, `POST /auth/login` responde `{requiere_codigo: true}` sin token hasta recibir el código, y un código inválido cuenta como intento fallido. `POST /auth/mfa/desactivar` pide la contraseña y un código vigente. El administrador puede restablecer el MFA de una cuenta (teléfono perdido) con `PATCH /usuarios/{id}` `{restablecer_mfa: true}`.
- Contraseña de al menos 10 caracteres. Tras cinco intentos fallidos seguidos (contraseña o código), la cuenta se bloquea 15 min (429). Un correo inexistente y una contraseña incorrecta reciben el mismo 401, para no revelar qué cuentas existen.
- Una cuenta creada o restablecida por el administrador tiene una contraseña temporal y `debe_cambiar_contrasena`: hasta cambiarla, el token solo sirve para `/auth/me` y `/auth/cambiar-contrasena`.

**Autorización (RF-26).**
- El core lee la cuenta en cada petición y autoriza con su rol guardado, no con el del token: desactivar una cuenta o cambiarle el rol surte efecto en la siguiente petición.
- El rules-service comparte la base y hace la misma comprobación antes de crear o pausar una regla.
- El ai-service confirma la cuenta con `GET /auth/me` del core (60 s en memoria por token).
- El módulo `config/seguridad.py` (firma y lectura del JWT, roles y dependencias de FastAPI) es idéntico en los tres servicios, porque cada uno se construye en su propio contexto de Docker; una prueba compara las tres copias.

**Propagación entre servicios (DOC-08, perfil SISTEMA).**
- El ai-service valida el token del usuario y llama al core y al rules con un token SISTEMA de 5 min, firmado con el mismo secreto, más la cabecera `X-Usuario-Actor` con el correo de quien pidió la acción. El core llama al rules con un token SISTEMA.
- `X-Usuario-Actor` solo cuenta con un token SISTEMA. Así la bitácora registra a la persona que pidió la auditoría (HU-07), y `POST /dictamenes` deja de estar abierto: solo el ai-service puede registrar un dictamen.
- Las tareas de fondo (lectura anticipada, procesamiento diferido y reevaluación programada) actúan como `SISTEMA`.

**Bitácora (RF-27, HU-07).**
- `usuario` guarda el correo autenticado (o `SISTEMA`) e `ip_origen` la IP de la petición.
- Eventos nuevos: `INICIO_SESION`, `INICIO_SESION_FALLIDO`, `ALTA_USUARIO`, `ACTUALIZACION_USUARIO` (rol, estado, restablecimientos; con el valor anterior y el nuevo), `CAMBIO_CONTRASENA`, `CAMBIO_MFA`, `ASIGNACION_EXPEDIENTE` y `NOTIFICACION_CORREO`.
- La ratificación toma `revisado_por` del token; el campo `usuario` de su cuerpo deja de usarse (sigue siendo opcional para no romper el contrato).
- Los eventos anteriores al Módulo 7 conservan «OPERADOR»: la bitácora es inmutable y su cadena sellada no cambia.

**Datos (migración idempotente en el core).**
- `usuarios`: las columnas del DOC-08 (`id`, `email` único, `password_hash`, `nombre_completo`, `rol` con CHECK de los cuatro roles, `activo`, `creado_en`), más `debe_cambiar_contrasena`, `intentos_fallidos`, `bloqueado_hasta`, `ultimo_acceso`, `mfa_secreto` y `mfa_habilitado`.
- `expediente_asignaciones` (`expediente_id`, `usuario_id`, `asignado_por`, `creado_en`; únicos por par): no la define el DOC-08, pero la exigen la HU-31 («sus expedientes asignados») y el RF-20 («los responsables asignados»).
- Sin borrado físico de usuarios (RN-04): una cuenta se desactiva. Una asignación sí se retira, y el cambio queda en la bitácora con la lista anterior y la nueva.

**Usuario de consulta (HU-31).** `GET /expedientes/asignados` devuelve folio, nombre, empresa, semáforo y fecha de actualización de los expedientes asignados al usuario. La interfaz de CONSULTA es solo esa lista, sin documentos, dictámenes, reglas ni configuración.

**Interfaz (HU-06).**
- Pantalla de inicio de sesión (con el paso del código TOTP) y cambio obligatorio de contraseña.
- Menú y rutas por rol, y acciones ocultas según el permiso.
- En la cabecera, el nombre y el rol, con un botón para cerrar sesión. Vista **Usuarios** (ADMIN), con la asignación de expedientes, y vista de **Consulta**.
- Un 401 regresa al inicio de sesión («Tu sesión expiró»).
- Las páginas del visor se piden con `fetch` y se muestran desde una URL de objeto, porque `<img src>` no puede enviar la cabecera de autorización.

**Correo (RF-20, HU-17).**
- **Cuándo:** cuando el semáforo de un expediente pasa a NO CONFORME (estatus crítico), y en la reevaluación programada cuando un documento cruza el umbral de 30, 15 o 5 días antes de vencer (RF-17).
- **A quién:** a los usuarios activos con rol VALIDADOR asignados al expediente.
- **Cómo:** SMTP genérico (`SMTP_HOST`, `SMTP_PORT`, `SMTP_USUARIO`, `SMTP_CONTRASENA`, `SMTP_REMITENTE`, `SMTP_STARTTLS`), en un hilo que no retrasa la petición. El mensaje va en lenguaje llano, con un enlace a `FRONTEND_URL`.
- Cada aviso queda en la bitácora (`NOTIFICACION_CORREO`: ENVIADO, FALLIDO, SIN_DESTINATARIOS o ENVIO_DESACTIVADO), y el aviso de un umbral no se repite. Sin `SMTP_HOST`, el envío está apagado.

**Arranque y entrega.**
- Si no hay ningún usuario, el core crea el administrador inicial de `ADMIN_INICIAL_EMAIL` y `ADMIN_INICIAL_CONTRASENA`, que debe cambiar la contraseña en su primer acceso.
- Con `USUARIOS_DEMO=true`, como en el `docker-compose.yml` de la entrega, crea además un usuario ficticio por rol, con correos del dominio reservado `example.com` (RFC 2606) y contraseñas documentadas en el README, para que PluriOne pruebe el RBAC de inmediato.
- `JWT_SECRET` se lee del `.env`. El compose trae uno de demostración, y `/health` del core advierte mientras siga en uso.
- `CORS_ORIGENES` sustituye `allow_origins=["*"]` (informe de ZAP).

**Riesgos aceptados.**
- El token en `sessionStorage` es legible por un script inyectado (XSS). React escapa el contenido y la interfaz no inserta HTML; la alternativa con cookies exige protección CSRF entre tres orígenes.
- El secreto TOTP se guarda sin cifrar en la base, como el resto de los datos hasta que exista el cifrado en reposo (RNF-04).
- Un código TOTP sigue sirviendo dentro de su ventana (±30 s) aunque ya se haya usado: quien lo viera y además supiera la contraseña podría reutilizarlo en ese lapso. Impedirlo exige guardar el último paso usado por cuenta; no se agrega en la versión mínima.

---

## 6. Flujos principales

[DG Cap. IV, Figuras 1–6; Cap. V, Figura 9; Cap. VIII, Figura 12]

**F1 — Alta de expediente y carga de documentos (M1).** El usuario registra al titular (RFC único), abre un expediente con su tipo y nombre y carga los documentos. En la carga se validan la firma binaria, el tamaño (máximo 15 MB) y se calcula la huella SHA-256. El semáforo se recalcula en cada carga y **subir archivos nunca aprueba un expediente**.

**F2 — Configuración de reglas (M2).** El administrador da de alta o pausa reglas desde la interfaz: documento, tipo de expediente al que aplica, anexo vinculado, severidad, acción y días de vigencia. El inventario exigido cambia sin tocar el código.

**F3 — Auditoría de un documento (M3, M4).** Se verifica la integridad (RIE-03), se extrae el texto (Nivel 3), el modelo extrae los datos (Nivel 4) y el rules-service aplica las reglas de vigencia. El dictamen se persiste y el semáforo del expediente se recalcula.

**F4 — Ratificación humana (Nivel 5).** Un dictamen en revisión se confirma o corrige con una justificación de al menos 10 caracteres; la decisión humana prevalece y queda en la bitácora.

**F5 — Alertas y corrección (M5).** Cada hallazgo genera una alerta con recomendación; al cargar el documento corregido, la alerta desaparece en la siguiente evaluación.

**F6 — Reportes (M6).** Consulta de indicadores y exportación del dictamen por expediente o del reporte global en PDF o Excel; cada exportación queda en la bitácora.

---

## 7. Requerimientos funcionales

[DG Cap. IV §4.4 — texto oficial de los requerimientos]

Prioridad tomada de las historias de usuario asociadas (Cap. VII); «—» cuando ninguna historia cubre el requerimiento.

### M1 — Gestión de Expedientes

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-01 | Crear expedientes con identificador único, nombre descriptivo, empresa titular y clasificación temática (Jurídico, Corporativo o Regulatorio). | Alta |
| RF-02 | Carga de documentos individuales o en lote (PDF, PNG, JPG) asociados a un expediente. | Alta |
| RF-03 | Cálculo automático de la huella SHA-256 al cargar (ISO 30301, NOM-151). | Alta |
| RF-04 | Control de versiones con histórico accesible. | — |
| RF-05 | Búsqueda y filtrado por nombre, empresa, tipo de expediente, fecha de creación y estatus. | Alta |

### M2 — Reglas de Validación Configurables

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-06 | Definir documentos obligatorios y opcionales por tipo de expediente sin alterar el código. | Alta |
| RF-07 | Configurar anexos obligatorios dependientes de un documento principal. | Alta |
| RF-08 | Severidad por regla (Crítica, Alta, Media-Alta o Media) y acción ante incumplimiento. | Alta |
| RF-09 | Interfaz para dar de alta nuevos tipos de documento y definir los criterios que evaluará la IA. | Alta |

### M3 — Análisis Inteligente de Documentos

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-10 | Extraer texto, tablas y pares clave-valor de documentos escaneados o nativos. | Alta |
| RF-11 | Análisis semántico con un modelo de lenguaje para verificar cláusulas obligatorias. El proveedor y el modelo son decisiones de diseño (§12.2, ESTADO_DEL_DESARROLLO §4): Qwen 3.8 (27B) en Groq Cloud. | Alta |
| RF-12 | Indexación y búsqueda semántica sobre el corpus documental. | — |
| RF-13 | Cada resultado de la IA incluye justificación, nivel de confianza y cita textual. | Alta |
| RF-14 | Hallazgos con discrepancia, vigencia no verificable o confianza < 85 % pasan a revisión humana (EN_REVISION) con justificación obligatoria. | Alta |

### M4 — Verificación de Vigencia

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-15 | Identificar y registrar las fechas de emisión y vencimiento. | Alta |
| RF-16 | Clasificar cada documento en Vigente, Próximo a Vencer o Vencido contra la fecha del servidor. | Alta |
| RF-17 | Días de anticipación configurables (por defecto 30, 15 y 5). | Media |

### M5 — Alertas y Recomendaciones

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-18 | Alertas inmediatas ante documento ausente, vencido, anexo faltante o cláusula incumplida. | Alta |
| RF-19 | Semáforo Verde / Amarillo / Rojo por expediente. | Alta |
| RF-20 | Notificaciones por correo electrónico ante estatus crítico o vencimiento próximo. | Media |
| RF-21 | Recomendación estructurada junto a cada alerta. | Media |

### M6 — Reportes y Panel de Control

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-22 | Tablero con porcentaje global de cumplimiento, conformes vs. no conformes y distribución de hallazgos. | Alta |
| RF-23 | Dictamen formal de auditoría por expediente. | Alta |
| RF-24 | Exportación en PDF y Excel (.xlsx). | Alta |

### M7 — Administración y Seguridad

| ID | Requerimiento | Prioridad |
|---|---|---|
| RF-25 | Autenticación con credenciales corporativas y soporte MFA. | Alta |
| RF-26 | Autorización por rol (RBAC). | Alta |
| RF-27 | Bitácora inmutable protegida por el motor de base de datos. | Alta |


---

## 8. Historias de usuario

[DG Cap. VII §7.6, Tablas 13–16 — 33 historias]

| ID | Historia (resumen) | Módulo | Sprint | Prioridad | Horas |
|---|---|---|---|---|---|
| HU-01 | Clasificar el expediente en uno de los tres tipos del DOC-02 (jurídico, corporativo o regulatorio). | M1 | 1 | Alta | 6 |
| HU-02 | Crear un expediente con nombre, empresa y tipo. | M1 | 1 | Alta | 6 |
| HU-03 | Cargar PDF e imágenes con cálculo automático de SHA-256. | M1 | 1 | Alta | 8 |
| HU-04 | Buscar expedientes por nombre, empresa, tipo o fecha. | M1 | 1 | Alta | 5 |
| HU-05 | Gestionar usuarios y asignar roles. | M7 | 1 | Alta | 10 |
| HU-06 | Iniciar sesión y ver solo las funciones del propio rol. | M7 | 1 | Alta | 8 |
| HU-07 | Registrar cada acción en la bitácora (usuario, fecha, acción, IP). | M7 | 1 | Alta | 6 |
| HU-08 | Verificar la integridad comparando la huella actual con la original. | M1 | 1 | Media | 5 |
| HU-09 | Definir documentos obligatorios y opcionales por tipo de expediente. | M2 | 2 | Alta | 8 |
| HU-10 | Vincular anexos obligatorios a documentos principales. | M2 | 2 | Alta | 6 |
| HU-11 | Asignar severidad y acción a cada regla. | M2 | 2 | Alta | 5 |
| HU-12 | Verificar la completitud y mostrar el porcentaje de documentos presentes. | M2 | 2 | Alta | 6 |
| HU-13 | Calcular si cada documento está vigente, próximo a vencer o vencido. | M4 | 2 | Alta | 8 |
| HU-14 | Configurar los umbrales de anticipación (30, 15 y 5 días). | M4 | 2 | Media | 4 |
| HU-15 | Recibir alertas por documentos faltantes, vencidos o anexos ausentes. | M5 | 2 | Alta | 8 |
| HU-16 | Que cada alerta incluya una recomendación. | M5 | 2 | Media | 5 |
| HU-17 | Notificaciones por correo ante estatus crítico. | M5 | 2 | Media | 6 |
| HU-18 | Extraer el texto por OCR y almacenarlo segmentado por páginas. | M3 | 3 | Alta | 12 |
| HU-19 | Verificar semánticamente las cláusulas obligatorias de un contrato. | M3 | 3 | Alta | 14 |
| HU-20 | Cita textual y porcentaje de confianza en cada resultado de la IA. | M3 | 3 | Alta | 6 |
| HU-21 | Marcar para revisión manual los hallazgos con confianza < 85 %. | M3 | 3 | Alta | 5 |
| HU-22 | Aprobar o rechazar hallazgos de la IA con registro en la bitácora. | M3 | 3 | Alta | 6 |
| HU-23 | Extraer los datos del firmante para cotejarlos con el poder notarial. | M3 | 3 | Media | 8 |
| HU-24 | Dar de alta tipos de documento con criterios en lenguaje natural. | M2 | 3 | Alta | 10 |
| HU-25 | Reutilizar el análisis si el documento no cambió (misma huella). | M3 | 3 | Media | 5 |
| HU-26 | Dashboard con porcentaje global, conformes y no conformes. | M6 | 4 | Alta | 10 |
| HU-27 | Semáforo visual de cada expediente. | M6 | 4 | Alta | 6 |
| HU-28 | Dictamen formal de cumplimiento por expediente. | M6 | 4 | Alta | 8 |
| HU-29 | Exportar reportes en PDF y Excel. | M6 | 4 | Alta | 8 |
| HU-30 | Consultar la bitácora completa de un expediente. | M7 | 4 | Alta | 5 |
| HU-31 | Usuario de consulta: solo el semáforo de sus expedientes asignados. | M7 | 4 | Media | 4 |
| HU-32 | Validación completa de un expediente (reglas + IA) con un solo botón. | Integración | 4 | Alta | 14 |
| HU-33 | Manejo controlado de errores (documento ilegible, IA no disponible). | Integración | 4 | Alta | 9 |


---

## 9. Reglas de negocio y catálogo de validación

### 9.1 Reglas de negocio

[DG Cap. IV §4.6]

| ID | Regla |
|---|---|
| RN-01 | **Incompletitud impeditiva:** ningún expediente puede ser Conforme si falta un documento obligatorio o un anexo mandatorio. |
| RN-02 | **Vigencia mandatoria:** un documento que alcanza su vencimiento sin actualizarse cambia automáticamente el expediente a No Conforme y genera una alerta de severidad alta. |
| RN-03 | **Consistencia de representación legal:** en expedientes con contratos mercantiles, el apoderado que suscribe debe tener facultades vigentes en el poder o el acta. |
| RN-04 | **Imposibilidad de borrado físico:** documentos y expedientes solo se marcan como inactivos o versionados. |
| RN-05 | **Prevalencia de la ratificación humana:** ante una discrepancia, prevalece la decisión del analista, registrada con su justificación. |

### 9.2 Familias de reglas

[DG Cap. V §5.4]

| Familia | Alcance | Reglas definidas |
|---|---|---|
| RIE — Integridad y Estructura | Niveles 1 y 2 | RIE-01 Completitud del expediente; RIE-02 Vinculación obligatoria de anexos; RIE-03 Integridad criptográfica del archivo. |
| RCV — Cronológicas y de Vigencia | Nivel 2 | RCV-01 Vigencia mandatoria (vencido < 0 días, próximo 0–30, vigente > 30); RCV-02 Caducidad del comprobante de domicilio (90 días desde la emisión); RCV-03 Caducidad de la constancia de situación fiscal (90 días); RCV-04 Caducidad de la opinión de cumplimiento 32-D (30 días; extensión PLUS-03). |
| RSC — Semánticas y Contractuales | Nivel 4 (IA) | RSC-01 Cláusulas esenciales (confidencialidad, penalización, vigencia y terminación) y elementos de contenido por tipo, entre ellos el sentido de la opinión 32-D (RSC-OPIN-SENT, lectura determinista; extensión PLUS-03); RSC-02 Datos del firmante (RSC-02-CONT y RSC-02-NDA, cotejados con los apoderados: P2). |
| RDS — Dinámicas y Sectoriales | Configurables | RDS-01 Alta dinámica de requisitos; RDS-02 Criterio en lenguaje natural para la IA; RDS-03 Ejecución supervisada obligatoria. |

Severidades: Crítica, Alta, Media-Alta y Media [RF-08]. Toda regla puede pausarse sin borrarse [DG Tabla 24].

### 9.3 Matriz de documentos obligatorios por tipo de expediente

[DG Cap. II §2.3, Tabla 6 — inventario base del catálogo]

| Tipo de expediente | Documento obligatorio | Regla | Severidad | Condición |
|---|---|---|---|---|
| Corporativo | Constancia de situación fiscal | RIE-01-CSF | Crítica | Siempre; antigüedad máxima de 90 días (RCV-03) |
| Corporativo | Comprobante de domicilio fiscal | RIE-01-DOM | Crítica | Siempre; antigüedad máxima de 90 días (RCV-02) |
| Corporativo | Acta constitutiva | RIE-01-ACTA | Crítica | Siempre |
| Jurídico | Contrato de prestación de servicios | RIE-01-JUR-CONT | Crítica | Siempre |
| Jurídico | Acuerdo de confidencialidad (NDA) | RIE-01-JUR-NDA | Crítica | Siempre |
| Jurídico | Poder notarial del representante | RIE-01-JUR-PODER | Crítica | Siempre |
| Regulatorio | Licencia de operación | RIE-01-REG-LIC | Crítica | Siempre |
| Regulatorio | Permiso municipal o sectorial | RIE-01-REG-PERM | Crítica | Siempre |
| Regulatorio | Póliza de seguro | RIE-01-REG-POL | Crítica | Siempre |
| Regulatorio | Registro ante autoridad sectorial | RIE-01-REG-REGS | Crítica | Siempre |
| Cualquiera | Anexo legal del contrato | RIE-02-CONT-ANX | Alta | Solo si el expediente contiene un contrato de prestación de servicios |

Los demás documentos obligatorios de los inventarios del DOC-02 (poderes, estatutos, actas de asamblea, RFC y aviso de privacidad en el corporativo; certificaciones, fianzas y constancias de capacitación según el sector) forman parte del catálogo base de 23 tipos y pueden declararse obligatorios desde la interfaz sin modificar el código.

---

## 10. Pipeline de validación y semáforo

### 10.1 Pipeline en cinco niveles

[DG Cap. V §5.2, Cap. VIII §8.6]

| Nivel | Responsable | Qué hace |
|---|---|---|
| 1. Estructural y criptográfico | core-service | Firma binaria (`%PDF-`, `FF D8 FF`, `89 50 4E 47`), máximo 15 MB, huella SHA-256 (NOM-151-SCFI-2016), unicidad de la huella en el expediente (PLUS-01) y detección de PDF protegido con contraseña (PLUS-02). |
| 2. Determinista | core-service y rules-service | Completitud por tipo de expediente (RIE-01), anexos (RIE-02) y vigencia (RCV-01 a RCV-04). No usa IA. |
| 3. Extracción de texto | ai-service | Capa vectorial con PyMuPDF; si una página rinde menos de 120 caracteres, rasterizado a 300 ppp y OCR con Tesseract 5.4 (español e inglés) tras preprocesamiento OpenCV. Texto persistido por huella SHA-256. |
| 4. Análisis semántico | ai-service + Groq Cloud | Qwen 3.8 (27B) a temperatura 0.0 con salida JSON estricta. **El modelo solo extrae datos**; el veredicto lo calculan reglas deterministas. |
| 5. Gobernanza humana | Analista | Confianza ≥ 0.85: Conforme; 0.70–0.84: revisión humana; < 0.70: lectura no fiable, revisión humana. **Una confianza baja nunca produce un rechazo.** |

### 10.2 Semáforo del expediente

[DG Cap. V §5.5; RF-19]

- **Rojo (No conforme):** falta un obligatorio de severidad crítica, falta un anexo exigido, o un documento vigente tiene dictamen No conforme, está vencido o fue alterado.
- **Amarillo (En revisión):** falta un obligatorio no crítico, o hay documentos sin auditar, pendientes de ratificación o próximos a vencer.
- **Verde (Conforme):** todos los obligatorios presentes y todos sus dictámenes conformes.

La **completitud** es el porcentaje de documentos obligatorios presentes, incluidos los anexos que se volvieron exigibles. La vigencia se **recalcula en cada consulta**, así que un documento que vence después de auditarse lleva el expediente a No conforme sin reauditarse (RN-02).

### 10.3 Alertas

[DG Cap. VIII §8.10.3, Tabla 30]

| Categoría | Se genera cuando | Severidad |
|---|---|---|
| DOCUMENTO_FALTANTE | Falta un documento obligatorio del tipo de expediente. | La de su regla RIE |
| ANEXO_FALTANTE | Falta el anexo de un documento principal presente. | La de su regla RIE-02 (Alta) |
| DOCUMENTO_VENCIDO | Se rebasó la fecha de vencimiento o la antigüedad máxima. | Alta |
| PROXIMO_A_VENCER | Faltan 30 días o menos para el vencimiento. | Media (≤ 30), Media-Alta (≤ 15) o Alta (≤ 5) |
| INTEGRIDAD_COMPROMETIDA | La huella SHA-256 no coincide con la de la carga. | Crítica |
| DICTAMEN_NO_CONFORME | El dictamen vigente es No conforme. | Alta |
| PENDIENTE_RATIFICACION | El dictamen quedó en revisión humana. | Media |
| PENDIENTE_AUDITORIA | Un obligatorio está custodiado pero sin dictamen. | Media |
| REPRESENTACION_NO_ACREDITADA | El firmante del titular en un contrato o NDA no coincide con ningún apoderado de un poder o acta vigente del expediente, o solo con uno vencido; desaparece al ratificarse el dictamen del contrato (RSC-02, RN-03; P2). | Alta |
| CONTENIDO_NO_LOCALIZADO | Un elemento que el catálogo exige al documento (regla RSC o RDS) quedó NO_LOCALIZADO o NO_VERIFICABLE en el dictamen vigente; desaparece al ratificarse el dictamen. | La de su regla (Media-Alta por defecto) |

Cada alerta incluye su recomendación correctiva (RF-21). Las alertas se derivan de la evaluación y no se almacenan: desaparecen al corregirse el hallazgo.

### 10.4 Manejo de excepciones

[DG Cap. V §5.3, Tabla 9]

| Escenario | Acción del sistema | Estatus |
|---|---|---|
| Documento ilegible | La extracción no obtiene texto suficiente: el documento queda «Documento ilegible, se requiere recarga», distinto de la revisión humana por contenido, y se pide recargarlo con mejor resolución (DOC-05, Tabla 1). | Amarillo |
| Servicio de IA no disponible | Hasta 3 reintentos con espera progresiva; si la falla persiste, el documento se marca para procesamiento posterior y se reintenta solo, dentro de la cuota diaria del proveedor (DOC-05, Tabla 1). | Alerta interna «Procesamiento diferido» |
| Archivo protegido con contraseña | El Nivel 1 detecta la contraseña de apertura en la carga, custodia el archivo y emite un dictamen No conforme «Archivo protegido, no procesable» (PLUS-02). | Rojo |

Una falla en un documento nunca detiene la validación del resto del expediente. Las dos primeras excepciones tienen su propia categoría de alerta: «Documento ilegible» y «Procesamiento diferido».

### 10.5 Índice de cumplimiento del expediente (C6)

[DOC-05, «Modelo de Puntuación de Cumplimiento y Semáforo» y RDS-03; [análisis de brechas](ANALISIS_BRECHAS_MOTOR.md), C6; diagrama [c6-actividad-indice-cumplimiento.puml](uml/c6-actividad-indice-cumplimiento.puml)]


**Fórmula.** `índice = cumplidas / (cumplidas + incumplidas + pendientes) × 100`. Cada evaluación de una regla termina en cumplida, incumplida, pendiente o no aplica (no cuenta). Sin reglas aplicables, el índice no tiene valor.

| Unidad | Cumplida | Incumplida | Pendiente o no aplica |
|---|---|---|---|
| RIE-01, cada obligatorio del tipo | Presente | Ausente (bloqueante si es Crítica) | — |
| RIE-02, cada anexo exigible | Presente | Ausente | — |
| RIE-03, cada documento vigente | Íntegro | Alterado (bloqueante; del documento alterado solo cuenta esta regla) | — |
| RCV, cada documento auditado | Vigente o próximo a vencer | Vencido (bloqueante) | Sin fechas o permanente: no aplica |
| Titularidad (DOC-08 §6), cada documento auditado | RFC coincide | RFC ajeno | Sin RFC o razón social distinta: pendiente |
| RSC y RDS, cada elemento del dictamen (incluye RSC-02: firmante identificado) | CUMPLE | NO_CUMPLE | NO_LOCALIZADO o NO_VERIFICABLE: pendiente |
| RN-03, cotejo del firmante de un contrato o NDA (P2) | ACREDITADO | NO_ACREDITADO o PODER_VENCIDO | PENDIENTE |
| Documento sin auditar | — | — | Una unidad pendiente |
| PDF protegido (PLUS-02) | — | Una unidad: archivo no legible | — |

Con el dictamen ratificado, la decisión del analista prevalece (RN-05) en todo lo que viene del dictamen —titularidad, contenido y cotejo—: cumplidas si lo ratificó conforme, incumplidas si lo ratificó no conforme. Lo que el motor calcula a la fecha (integridad y vigencia) no cambia con la ratificación (RN-02).

**Decisiones.**

1. Lo pendiente cuenta en el denominador: por RDS-03, un resultado sin validar no deja que el expediente «alcance el 100 % de cumplimiento».
2. Sin ponderación por severidad: el DOC-05 define un porcentaje directo; la severidad actúa solo por el bloqueo.
3. Próximo a vencer cuenta como cumplida: es una advertencia (semáforo amarillo), no un incumplimiento. Un expediente puede mostrar 100 % en amarillo solo por esta causa.
4. Un documento sin auditar vale una unidad pendiente: sus reglas de contenido se conocen al auditarlo, así que el índice puede bajar después de una auditoría.
5. El índice global es el promedio de los índices de los expedientes: cada expediente pesa igual.

**Bloqueo por criticidad.** Si falta un obligatorio Crítico, un documento venció o fue alterado —los tres ejemplos del DOC-05—, el índice se marca bloqueado con las reglas que bloquean. El porcentaje no se altera: el semáforo es Rojo «sin importar el porcentaje». El semáforo conserva sus propias reglas (§10.2) y puede ser Rojo sin bloqueo crítico (un dictamen No conforme de severidad Alta).

**Contrato.** Campo opcional `evaluacion.indice_cumplimiento` (porcentaje, cumplidas, incumplidas, pendientes, aplicables, bloqueado, bloqueos y el detalle por regla). Se deriva en cada consulta, sin consultas adicionales ni datos persistidos. El tablero muestra el índice promedio como «Cumplimiento» y la completitud por separado, como «Documentos obligatorios presentes»; el indicador del RF-22 de expedientes conformes se conserva con ese nombre.


---

## 11. Requerimientos no funcionales

[DG Cap. IV §4.5 — ISO/IEC 25010 e ISO/IEC 27001]

| ID | Requerimiento |
|---|---|
| RNF-01 | Evaluación determinista de un expediente completo en ≤ 2 s. |
| RNF-02 | Extracción y análisis con IA de un documento de hasta 20 páginas en ≤ 25 s. |
| RNF-03 | ≥ 50 peticiones simultáneas sin degradación. |
| RNF-04 | Cifrado AES-256 de la bóveda en reposo. |
| RNF-05 | TLS 1.3 en el borde (entre el cliente y el sistema, mediante un proxy inverso) y hacia el proveedor de inferencia; los microservicios y la base de datos en una red interna aislada, sin puertos expuestos. Cifrar el tráfico entre contenedores de una misma red aislada añade certificados internos sin una protección equivalente; la segregación de redes cumple el objetivo (ISO/IEC 27001, A.8.22). |
| RNF-06 | Al proveedor de IA solo viaja el texto extraído, con Retención Cero de Datos. |
| RNF-07 | Interfaz responsiva, resolución mínima de 1366 × 768. |
| RNF-08 | Semáforo y hallazgos comprensibles para personal jurídico sin conocimientos técnicos. |
| RNF-09 | Disponibilidad ≥ 99.5 % en horario operativo, medida con las comprobaciones de salud de cada servicio (reinicio automático en Docker y registro de disponibilidad a partir de sus sondeos). |
| RNF-10 | Respaldos automatizados diarios, en un mismo punto, de PostgreSQL, la bóveda y la base del ai-service (RPO < 24 h), con una prueba de restauración. Un respaldo de la base sin la bóveda no sirve como evidencia, y al restaurarlo RIE-03 marcaría como alterados los documentos no restaurados. |
| RNF-11 | Solución contenerizada con Docker Compose. |
| RNF-12 | Pruebas y análisis estático en cada confirmación con GitHub Actions. |


---

## 12. Arquitectura y solución técnica

### 12.1 Arquitectura

[DG Cap. VIII §8.2–8.3, Figura 10]

Microservicios desacoplados orquestados con Docker Compose en la red `plurione-net`, conforme a OE-02:

| Contenedor | Puerto | Responsabilidad |
|---|---|---|
| plurione-core | 8001 | Titulares, expedientes, documentos (Nivel 1 y bóveda), semáforo, alertas, dictámenes, bitácora y reportes. |
| plurione-rules | 8002 | Catálogo de reglas (RIE, RCV, RSC, RDS), documentos obligatorios por tipo y evaluación de vigencia. |
| plurione-ai | 8003 | Niveles 3 y 4: extracción de texto, análisis con Groq Cloud y chat documental; texto persistido en SQLite propio. |
| plurione-frontend | 5173 | Aplicación React 19 + Vite; Nivel 1 en el navegador (WebCrypto) y System Health Strip. |
| plurione-db | 5432 | PostgreSQL 17 compartido por core y rules. |
| storage_vault | — | Bóveda de binarios con huella verificada en cada lectura. |

**Aislamiento de fallas:** si el rules-service o el ai-service caen, el core-service y la interfaz siguen operando; la salud de cada servicio se muestra en vivo (`GET /api/v1/health`).

### 12.2 Stack tecnológico

[DG Cap. VI §6.6, Tabla 10]

| Capa | Tecnología |
|---|---|
| Frontend | React 19 con Vite |
| Backend | FastAPI con Python 3.12, Pydantic v2, SQLAlchemy 2 |
| Base de datos | PostgreSQL 17 con disparadores PL/pgSQL de inmutabilidad |
| Orquestación | Docker Compose |
| Extracción e IA | PyMuPDF, Tesseract OCR 5 con OpenCV, Groq Cloud (qwen/qwen3.8-27b) |
| Reportes | ReportLab (PDF) y openpyxl (Excel), ambos con sus módulos de gráficas |
| Gráficas del tablero | Recharts 3 (licencia MIT), cargada solo en la vista de Reportes (sustituye a Power BI, ESTADO_DEL_DESARROLLO §4); las vistas se cargan por separado |

### 12.3 Contratos de API

[DG Cap. VIII §8.4, Tabla 20 — rutas versionadas `/api/v1/`, JSON, errores con el miembro `detail`]

| Servicio | Endpoints principales |
|---|---|
| core-service | `/health`; `/titulares`; `/expedientes` (alta y búsqueda); `/expedientes/{id}`; `/documentos/upload`; `/documentos/{id}/integridad`; `/documentos/{id}/contenido`; `/dictamenes`; `/dictamenes/{id}/ratificar`; `PATCH /titulares/{id}` y `PATCH /expedientes/{id}` (corrección de datos de captura); `/documentos/{id}/contenido?descarga=true` (descarga del original); `/bitacora`; `/bitacora/verificar-cadena` (P3); `/alertas`; `/reportes/expedientes/{id}`; `/reportes/cumplimiento`; `/reportes/documentos/{id}/custodia` (P3) |
| rules-service | `/health`; `/reglas` (catálogo, alta y pausa); `/reglas/documentos-obligatorios?tipo_expediente=`; `/reglas/tipos-documento` (tipos declarados por reglas RDS, RF-09); `/reglas/evaluar-vigencia` |
| ai-service | `/health`; `/ai/extraer-texto`; `/ai/documentos/{id}/preparar`; `/ai/analisis-semantico`; `/ai/chat-documento`; `/ai/configuracion-ocr` |

Módulo 7 (§5.1 y §5.2), en el core: `/auth/login`, `/auth/me`, `/auth/cambiar-contrasena`, `/usuarios` y `/usuarios/{id}`, `/expedientes/{id}/asignaciones` y `/expedientes/asignados`, y `/auth/mfa/generar|activar|desactivar`. Todos los endpoints salvo `/health` y `/auth/login` exigen `Authorization: Bearer`.

Documentación interactiva OpenAPI en `/docs` de cada servicio.

### 12.4 Modelo de datos

[DG Cap. VIII §8.5, Figura 11, Tablas 21–26 — 3FN en PostgreSQL 17]

| Tabla | Contenido |
|---|---|
| `titulares_expediente` | Personas físicas y morales (RFC único). |
| `expedientes` | Folio, tipo de expediente, nombre, semáforo, completitud y fechas. |
| `documentos` | Archivo custodiado, huella SHA-256 y estado de integridad. |
| `reglas_validacion` | Catálogo de reglas, con tipo de expediente y documento principal (anexos). |
| `dictamenes_auditoria` | Resultado de cada auditoría y su ratificación humana (protegido por `trg_dictamen_protegido`), con los firmantes o apoderados extraídos en `representacion_legal` (P2). |
| `bitacora_auditoria` | Eventos inmutables (protegida por `trg_bitacora_inmutable`), sellados en cadena con `secuencia`, `hash_anterior` y `hash_evento` (P3). |

Módulo 7 (§5.2): la tabla `usuarios` del DOC-08 (email, password_hash bcrypt, nombre_completo, rol con CHECK de los cuatro roles, activo, creado_en), con las columnas de operación de la sesión y del segundo factor (`mfa_secreto`, `mfa_habilitado`, F3), y `expediente_asignaciones` (HU-31, RF-20), única por par y con FK RESTRICT. `bitacora_auditoria.usuario` y `dictamenes_auditoria.revisado_por` se ampliaron a 150 caracteres para guardar el correo.


Integridad garantizada por la base, además de la API:
- Claves foráneas de custodia con `ON DELETE RESTRICT` (titular → expediente → documento → dictamen): nada se borra en cascada.
- Restricciones `CHECK` de estados del semáforo y del dictamen, tipo de expediente, tipo documental, estado de integridad y familia normativa, construidas en el arranque con los mismos enums que valida la API. `OTRO` se admite como tipo documental heredado (dos documentos custodiados anteriores al catálogo actual).
- Triggers de inmutabilidad de la bitácora (RF-27) y de los dictámenes (RN-04, RN-05).
- Índices en la huella SHA-256, el folio (único), el tipo de expediente y `documentos.expediente_id`.

### 12.5 Privacidad y uso de IA

[DG Cap. III §3.6, Cap. VIII §8.7 y §8.9.1]

- El archivo original nunca sale de la infraestructura de PluriOne: al proveedor solo viaja el texto extraído, cifrado en tránsito.
- Groq no retiene por defecto las entradas ni salidas ni entrena con ellas; la Retención Cero de Datos elimina incluso el registro temporal de diagnóstico.
- Modelo e identificador fijados por configuración (`GROQ_MODEL`), temperatura 0.0 y registro del modelo en cada dictamen, para reproducibilidad y auditoría.
- **Datos personales en la base del ai-service** (LFPDPPP, DOC-03): la SQLite guarda el texto extraído de cada documento, con nombres de firmantes y apoderados. Su finalidad es exclusivamente verificar el cumplimiento: reproducir el dictamen con la misma lectura, responder el chat documental con evidencia y no repetir el OCR. Se conserva lo mismo que su documento (§12.6) y se respalda junto con la base y la bóveda (RNF-10). No se comparte con terceros salvo el texto que viaja al proveedor de inferencia, con Retención Cero de Datos. El acceso queda restringido por rol con el Módulo 7, y su cifrado en reposo forma parte de RNF-04.

### 12.6 Conservación de la evidencia

[DOC-03: ISO 30301, NOM-151-SCFI-2016 y Código Fiscal de la Federación]

| Registro | Conservación | Fundamento |
|---|---|---|
| Documentos custodiados (incluidas las versiones sustituidas) | Mientras exista el expediente y, como mínimo, 5 años desde su carga | CFF, art. 30 (conservación de la documentación fiscal: constancias, opiniones 32-D y comprobantes del expediente); ISO 30301 (retención y disposición controladas) |
| Dictámenes y ratificaciones | Lo mismo que su documento | Protocolo de auditoría del DOC-05: deben poder demostrar el fundamento de cada validación |
| Bitácora sellada | Sin eliminación: es la cadena de custodia | NOM-151-SCFI-2016 (trazabilidad); P3 |
| Texto extraído (ai-service) | Lo mismo que su documento | §12.5 |

El sistema **no elimina** ningún registro: una sustitución conserva la versión anterior y su historia. La disposición al vencer el plazo es una decisión de PluriOne, que deberá ejecutarse con un rol autorizado (Módulo 7) y quedar registrada en la bitácora.

---

## 13. Experiencia de usuario

[DG Cap. IX]

- **Diseño «White & Warm»:** blanco como base, neutros cálidos y color reservado a los estados de auditoría (Conforme, En revisión, No conforme), siempre acompañado de su etiqueta.
- **Navegación:** Cumplimiento (Empresas, Expedientes, Bóveda), Auditoría (Alertas, Reportes) y Configuración (Reglas). La sección y el expediente desplegado viven en la URL (`#/expedientes/<folio>`): recargar conserva la vista y un enlace lleva directo a un expediente. La pantalla de inicio es Expedientes.
- **Expedientes:** tarjeta con tipo, semáforo, índice de cumplimiento y documentos obligatorios presentes; el detalle va de por qué a qué hacer: cada motivo del semáforo lleva debajo la recomendación de su alerta, después los documentos exigidos con su estado y vigencia, las reglas evaluadas para el índice y el historial; a la derecha, el índice, la carga y la exportación del dictamen.
- **Bóveda y catálogo de reglas:** la Bóveda muestra por defecto solo los documentos vigentes, con el estado de su dictamen, y el histórico completo a un clic; el catálogo se pliega por familia y muestra el detalle completo de cada regla.
- **Panel de Inteligencia Documental:** abre con el encabezado de veredicto (estado del documento y las acciones de ratificar y ver el documento) y se organiza en Resultado, Evidencia, Registro técnico y Chat; auditoría en tres etapas visibles (lectura, análisis, reglas de vigencia) con cancelación en cascada, dictamen con medidor de confianza, tabla de cotejo, registro de auditoría con ratificación y chat documental con citas. La ratificación se abre desde el encabezado de veredicto, y el dictamen vigente que coincide con la auditoría recién hecha se resume en una línea con su historial.
- **Etiquetas de estado:** mayúscula inicial en todas las pantallas («En revisión», «No conforme»).
- **Movimiento:** discreto y con propósito, solo con `transform`, `opacity` y la altura de las filas, y desactivado con «reducir movimiento»: indicador deslizante en los selectores, barras que crecen al aparecer, despliegue del expediente con altura animada, entrada con dirección al navegar entre documentos, destello de un estado que cambia, sombra de la cabecera al desplazarse, conteo de las métricas en la primera carga y fundido al cambiar de tema.
- **Salud del sistema:** un indicador en la cabecera con el peor estado de los tres microservicios («Servicios en línea», «1 servicio sin respuesta»); al pasar el cursor o con el foco muestra puerto, latencia y modelo de cada uno. Junto al botón de refrescar, la antigüedad de los datos («Actualizado hace 12 s»); el sondeo se pausa con la pestaña oculta.


---

## 14. Criterios de aceptación del producto

[DG Cap. VII §7.8]

**Funcionales**

- Crear, organizar y buscar expedientes con identificador único y clasificación por tipo.
- Cargar PDF e imágenes con cálculo automático de SHA-256.
- El motor evalúa completitud, vigencia y presencia de anexos.
- Reglas configurables desde la interfaz sin modificar el código.
- El OCR extrae texto legible de documentos escaneados.
- La IA analiza cláusulas contractuales con cita y nivel de confianza.
- Los hallazgos de baja confianza requieren ratificación humana.
- Alertas automáticas ante documentos faltantes, vencidos o próximos a vencer.
- Semáforo Verde, Amarillo y Rojo por expediente.
- Reportes exportables en PDF y Excel.

**Seguridad y auditoría**

- Acceso con autenticación y roles diferenciados.
- Cada acción relevante queda en la bitácora de forma inmutable.
- Documentos protegidos mediante cifrado y control de acceso.

**Calidad y entrega**

- Sistema contenerizado, desplegable con un solo comando.
- Documentación técnica completa: arquitectura, APIs, configuración y manual de usuario.
- Pruebas funcionales, de integración y de precisión de la IA ejecutadas y documentadas.

---

## 15. Métricas de éxito

### 15.1 Umbrales definidos en la documentación

| Métrica | Umbral | Fuente |
|---|---|---|
| Tiempo de evaluación determinista por expediente | ≤ 2 s | RNF-01 |
| Tiempo de extracción y análisis por documento (≤ 20 págs.) | ≤ 25 s | RNF-02 |
| Concurrencia sin degradación | ≥ 50 peticiones | RNF-03 |
| Disponibilidad en horario operativo | ≥ 99.5 % | RNF-09 |
| Umbral de confianza para dictamen automático | ≥ 0.85 | RF-14, DOC-08 §6.2 |
| Reducción del tiempo de revisión manual | 90 % (estimación de la propuesta técnica) | DG §6.7 |


---

## 16. Plan de entrega

### 16.1 Cronograma

[Anteproyecto, «Cronograma»; DG Cap. VII §7.5, Tabla 12 — 16 semanas, 500 horas]

| Fase | Semanas | Horas | Entregable |
|---|---|---|---|
| Análisis y Detección de Necesidades | 1–2 | 50 | Documento de Requerimientos (SRS) |
| Propuesta y Planificación | 2–3 | 30 | Propuesta Técnica y Plan del Proyecto |
| Diseño de Arquitectura | 3–5 | 50 | Documento de Arquitectura de Software |
| Desarrollo del Motor | 5–12 | 240 | Sistema funcional (7 módulos) |
| Pruebas y Validación | 11–14 | 55 | Reporte de pruebas (funcionales, integración, precisión de la IA y seguridad) |
| Documentación | 13–15 | 35 | Manual técnico, manual de usuario y documentación de APIs |
| Mantenimiento, Capacitación y Cierre | 14–16 | 40 | Plan de soporte, capacitación, evaluación e informe final |
| **Total** | **16** | **500** | |

### 16.2 Sprints de desarrollo (Scrum)

[DG Cap. VII §7.4–7.7 — sprints de dos semanas, unas 60 horas cada uno]

| Sprint | Semanas | Objetivo | HU |
|---|---|---|---|
| 1 — Cimientos del sistema | 5–6 | Base de datos, API REST, autenticación con roles y gestión de expedientes con carga. | HU-01 a HU-08 |
| 2 — Motor de reglas y vigencias | 7–8 | Reglas configurables, vigencia y alertas; dictamen determinista sin IA. | HU-09 a HU-17 |
| 3 — Análisis inteligente con IA | 9–10 | OCR, análisis semántico, cita y confianza, Human-in-the-Loop. | HU-18 a HU-25 |
| 4 — Reportes, dashboard e integración | 11–12 | Panel, reportes exportables e integración completa. | HU-26 a HU-33 |

---

## 17. Riesgos

[DG Cap. VII §7.9, Tabla 18]

| Riesgo | Probabilidad | Impacto | Mitigación |
|---|---|---|---|
| Cambio en los requisitos durante el desarrollo. | Media | Medio | Scrum incorpora cambios en cada sprint; las reglas son configurables en la base de datos. |
| Baja precisión de la IA en la detección de cláusulas. | Media | Alto | 13 horas de pruebas de precisión; los resultados dudosos pasan a revisión humana. |
| Documentos escaneados de baja calidad. | Alta | Medio | Se detectan documentos ilegibles y se solicita la recarga. |
| Retraso por complejidad de integración. | Media | Alto | Se priorizan los módulos de mayor valor para asegurar un producto mínimo viable. |
| Indisponibilidad de servicios externos de IA u OCR. | Baja | Medio | El Nivel 2 funciona sin dependencias externas; reintentos automáticos. |

Riesgos adicionales identificados en la implementación [DG §8.7 y §10.7]:

- **Cuota del plan gratuito de Groq** (8,000 tokens por minuto): el tiempo de respuesta sube a 10–18 s si se encadenan consultas. Mitigación: contexto acotado a 6,500 caracteres, caché del texto y de la inferencia; un plan de pago elimina la espera.
- **Dependencia de conexión a Internet para el Nivel 4:** degradación controlada; los Niveles 1 a 3 siguen operando.
- **Zona horaria de las marcas de tiempo:** las columnas TIMESTAMP se guardan en UTC porque la sesión de PostgreSQL se fija en UTC; migrar a TIMESTAMPTZ haría explícita la zona, pero cambiaría la serialización que sella la bitácora (ANALISIS_BRECHAS).

---

## 18. Dependencias y supuestos

**Dependencias externas**

- Groq Cloud (API compatible con OpenAI) y una credencial `GROQ_API_KEY`. El plan gratuito limita `qwen/qwen3.8-27b` a 8,000 tokens por minuto y **200,000 tokens por día** (medido el 30/09/2026 al agotarse): ≈ 28 auditorías de un documento largo (≈ 7,000 tokens) o ≈ 125 turnos de chat con modelo al día. Las respuestas sin modelo (PLUS-07, PLUS-08) y el caché (PLUS-10) no consumen esa cuota; un despliegue con más volumen requiere el plan de pago.
- Binario de Tesseract OCR 5 con el modelo de idioma español (`OCR_LANG=spa` desde el 30/09/2026).
- PostgreSQL 17 y Docker Compose en la infraestructura de PluriOne.

**Supuestos** [DG Caps. I, III y VI]

- Los documentos llegan mayoritariamente en PDF, incluidos escaneados (H5).
- Un expediente contiene desde unos diez hasta varias decenas de documentos (H3).
- El catálogo de documentos es la base inicial, no una lista cerrada: el administrador puede ampliarlo (DG Cap. I, «Extensibilidad»).
- La transferencia del texto al proveedor de inferencia debe declararse en el aviso de privacidad de PluriOne (LFPDPPP).

---

## 19. Glosario

| Término | Definición |
|---|---|
| Expediente | Agrupador de la documentación de un titular, clasificado como jurídico, corporativo o regulatorio. |
| Titular | Persona física o moral dueña del expediente, identificada por su RFC. |
| Dictamen | Resultado de auditar un documento: Conforme, En revisión o No conforme. |
| Semáforo | Estado consolidado del expediente (Verde, Amarillo, Rojo). |
| Completitud | Porcentaje de documentos obligatorios presentes en el expediente. |
| Anexo | Documento que se vuelve obligatorio cuando el expediente contiene su documento principal (RIE-02). |
| Huella SHA-256 | Resumen criptográfico del archivo; si cambia, el documento fue alterado (RIE-03). |
| Human-in-the-Loop (HITL) | Ratificación humana de los dictámenes que el motor no resuelve con certeza. |
| Bóveda (storage_vault) | Directorio de custodia de los archivos originales. |
| OCR | Reconocimiento óptico de caracteres de documentos escaneados. |
| LPU | Language Processing Unit, procesador de inferencia de Groq. |
| ZDR | Zero Data Retention, política del proveedor que elimina el registro temporal de las inferencias. |
| RIE / RCV / RSC / RDS | Familias de reglas: Integridad y Estructura, Cronológicas y de Vigencia, Semánticas y Contractuales, Dinámicas y Sectoriales. |
