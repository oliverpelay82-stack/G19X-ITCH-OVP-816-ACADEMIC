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
| Versión del documento | 1.4 — 29 de septiembre de 2026 (1.3: P1; 1.2: 28 de septiembre; 1.0: 27 de septiembre de 2026) |
| Estado del producto | En desarrollo: Sprints 1 y 2 implementados, Sprint 3 implementado parcialmente, Sprint 4 implementado salvo HU-31, Módulo 7 pendiente |
| Documento hermano | [MRD.md](MRD.md) — requerimientos de mercado |

> **Fuentes.** Salvo las extensiones PLUS de la [sección 21](#21-extensiones-plus), que se marcan como tales y citan la norma que las respalda, este PRD no introduce requisitos nuevos: consolida los documentos oficiales del proyecto —el anteproyecto de residencia, los entregables DOC-01 a DOC-08 ([ESPECIFICACIONES_DOC01_A_DOC08.txt](ESPECIFICACIONES_DOC01_A_DOC08.txt)) y el DOCUMENTO GENERAL que los integra— y el estado verificado del sistema en el repositorio. Cada sección indica su fuente entre corchetes; «DG» es el DOCUMENTO GENERAL.

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
15. [Métricas de éxito y resultados medidos](#15-métricas-de-éxito-y-resultados-medidos)
16. [Plan de entrega](#16-plan-de-entrega)
17. [Riesgos](#17-riesgos)
18. [Dependencias y supuestos](#18-dependencias-y-supuestos)
19. [Cambios respecto del anteproyecto](#19-cambios-respecto-del-anteproyecto)
20. [Pendientes y preguntas abiertas](#20-pendientes-y-preguntas-abiertas)
21. [Extensiones PLUS](#21-extensiones-plus)
22. [Glosario](#22-glosario)

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

Tipos de documento: los tres inventarios del DOC-02 (22 tipos: corporativos, jurídicos y regulatorios) [DG Cap. I §1.4, Tablas 2–4], ampliables por el administrador [DG Cap. I, «Extensibilidad del Catálogo»].

### 4.2 Fuera del alcance

- **Documentos de identificación personal**: INE, CURP, actas de nacimiento, comprobantes de domicilio personales, pasaportes y títulos universitarios. El motor procesa exclusivamente documentación corporativa y contractual de organizaciones [DOC-01; DG Cap. I, hallazgo H1].
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

> **Estado:** la autorización por rol **aún no se aplica**. Los roles están definidos y previstos por endpoint, y el Módulo 7 (RF-25, RF-26) está programado para la siguiente iteración [DG Cap. X §10.6].

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

[DG Cap. IV §4.4 — texto oficial de los requerimientos; estado según DG Cap. X §10.6, Tabla 34]

Prioridad tomada de las historias de usuario asociadas (Cap. VII); «—» cuando ninguna historia cubre el requerimiento. Estados: **Implementado**, **Parcial** o **Pendiente**.

### M1 — Gestión de Expedientes

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-01 | Crear expedientes con identificador único, nombre descriptivo, empresa titular y clasificación temática (Jurídico, Corporativo o Regulatorio). | Alta | Implementado | `POST /api/v1/expedientes`; folio único y tipo. |
| RF-02 | Carga de documentos individuales o en lote (PDF, PNG, JPG) asociados a un expediente. | Alta | Parcial | Carga individual; la carga en lote queda pendiente. |
| RF-03 | Cálculo automático de la huella SHA-256 al cargar (ISO 30301, NOM-151). | Alta | Implementado | Nivel 1; verificación RIE-03 en cada lectura. |
| RF-04 | Control de versiones con histórico accesible. | — | Implementado | El archivo más reciente de cada tipo sustituye al anterior, que se conserva con sus dictámenes. |
| RF-05 | Búsqueda y filtrado por nombre, empresa, tipo de expediente, fecha de creación y estatus. | Alta | Implementado | Parámetros `q`, `tipo_expediente`, `estado`, `desde` y `hasta`. |

### M2 — Reglas de Validación Configurables

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-06 | Definir documentos obligatorios y opcionales por tipo de expediente sin alterar el código. | Alta | Implementado | Reglas RIE con `tipo_expediente` (sección 9.3). |
| RF-07 | Configurar anexos obligatorios dependientes de un documento principal. | Alta | Implementado | Reglas RIE-02 con `documento_principal`. |
| RF-08 | Severidad por regla (Crítica, Alta, Media-Alta o Media) y acción ante incumplimiento. | Alta | Implementado | Campos `severidad` y `accion` del catálogo. |
| RF-09 | Interfaz para dar de alta nuevos tipos de documento y definir los criterios que evaluará la IA. | Alta | Parcial | Alta de reglas desde la interfaz; el catálogo de 22 tipos es fijo y el criterio en lenguaje natural (RDS-02) aún no se aplica en el Nivel 4. |

### M3 — Análisis Inteligente de Documentos

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-10 | Extraer texto, tablas y pares clave-valor de documentos escaneados o nativos. | Alta | Implementado | PyMuPDF para la capa vectorial y Tesseract con preprocesamiento OpenCV para lo escaneado. |
| RF-11 | Análisis semántico con Qwen 3.8 (27B) en Groq Cloud para verificar cláusulas obligatorias. | Alta | Implementado | Verificación de contenido del Nivel 4 (RSC-01): cada auditoría verifica los elementos que el catálogo exige al tipo de documento (16 reglas RSC: contrato, NDA, acta constitutiva, poder notarial, póliza y licencia). Un elemento es CUMPLE solo si su cita literal aparece en el texto; si no, NO_LOCALIZADO o NO_VERIFICABLE, el dictamen pasa a revisión humana y se emite la alerta CONTENIDO_NO_LOCALIZADO. Los datos del firmante (RSC-02) se extraen en la misma llamada y se cotejan con los apoderados del expediente (P2, §21.2). |
| RF-12 | Indexación y búsqueda semántica sobre el corpus documental. | — | Parcial | Recuperación BM25 dentro de cada documento; sin búsqueda sobre todo el acervo. |
| RF-13 | Cada resultado de la IA incluye justificación, nivel de confianza y cita textual. | Alta | Implementado | Dictamen con confianza y observaciones; chat con citas. |
| RF-14 | Hallazgos con discrepancia, vigencia no verificable o confianza < 85 % pasan a revisión humana (EN_REVISION) con justificación obligatoria. | Alta | Implementado | `POST /api/v1/dictamenes/{id}/ratificar`. |

### M4 — Verificación de Vigencia

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-15 | Identificar y registrar las fechas de emisión y vencimiento. | Alta | Implementado | Persistidas en el dictamen. |
| RF-16 | Clasificar cada documento en Vigente, Próximo a Vencer o Vencido contra la fecha del servidor. | Alta | Implementado | RCV-01, RCV-02 y RCV-03, recalculadas en cada consulta. |
| RF-17 | Días de anticipación configurables (por defecto 30, 15 y 5). | Media | Implementado | Variable de entorno `UMBRALES_ALERTA_VENCIMIENTO`. |

### M5 — Alertas y Recomendaciones

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-18 | Alertas inmediatas ante documento ausente, vencido, anexo faltante o cláusula incumplida. | Alta | Implementado | Nueve categorías de alerta (sección 10.3); la cláusula incumplida es CONTENIDO_NO_LOCALIZADO. |
| RF-19 | Semáforo Verde / Amarillo / Rojo por expediente. | Alta | Implementado | Reglas del semáforo en la sección 10.2. |
| RF-20 | Notificaciones por correo electrónico ante estatus crítico o vencimiento próximo. | Media | **Pendiente** | Programado para la siguiente iteración del Módulo 5. |
| RF-21 | Recomendación estructurada junto a cada alerta. | Media | Implementado | Campo `recomendacion` de cada alerta. |

### M6 — Reportes y Panel de Control

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-22 | Tablero con porcentaje global de cumplimiento, conformes vs. no conformes y distribución de hallazgos. | Alta | Implementado | Vista de Reportes. |
| RF-23 | Dictamen formal de auditoría por expediente. | Alta | Implementado | `GET /api/v1/reportes/expedientes/{id}`. |
| RF-24 | Exportación en PDF y Excel (.xlsx). | Alta | Implementado | ReportLab y openpyxl; cada exportación se registra en la bitácora. |

### M7 — Administración y Seguridad

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-25 | Autenticación con credenciales corporativas y soporte MFA. | Alta | **Pendiente** | Diseñada en DOC-08 (tabla `usuarios`, JWT HMAC-SHA256). |
| RF-26 | Autorización por rol (RBAC). | Alta | **Pendiente** | Roles definidos (sección 5). |
| RF-27 | Bitácora inmutable protegida por el motor de base de datos. | Alta | Implementado | Disparador `trg_bitacora_inmutable`; el usuario autenticado se registrará con RF-25. |

**Resumen:** 21 implementados, 3 parciales y 3 pendientes de 27. La Tabla 34 del DG reporta 20, 4 y 3; la diferencia es RF-11, que pasa a implementado con la verificación de contenido del Nivel 4 (versión 1.2 de este documento).

---

## 8. Historias de usuario

[DG Cap. VII §7.6, Tablas 13–16 — 33 historias. Estado derivado de la trazabilidad de requerimientos y del código]

| ID | Historia (resumen) | Módulo | Sprint | Prioridad | Horas | Estado |
|---|---|---|---|---|---|---|
| HU-01 | Crear tipos de expediente (jurídico, corporativo, regulatorio). | M1 | 1 | Alta | 6 | Implementado (catálogo de los 3 tipos del DOC-02) |
| HU-02 | Crear un expediente con nombre, empresa y tipo. | M1 | 1 | Alta | 6 | Implementado |
| HU-03 | Cargar PDF e imágenes con cálculo automático de SHA-256. | M1 | 1 | Alta | 8 | Implementado |
| HU-04 | Buscar expedientes por nombre, empresa, tipo o fecha. | M1 | 1 | Alta | 5 | Implementado |
| HU-05 | Gestionar usuarios y asignar roles. | M7 | 1 | Alta | 10 | Pendiente |
| HU-06 | Iniciar sesión y ver solo las funciones del propio rol. | M7 | 1 | Alta | 8 | Pendiente |
| HU-07 | Registrar cada acción en la bitácora (usuario, fecha, acción, IP). | M7 | 1 | Alta | 6 | Parcial (registra un usuario genérico hasta RF-25) |
| HU-08 | Verificar la integridad comparando la huella actual con la original. | M1 | 1 | Media | 5 | Implementado |
| HU-09 | Definir documentos obligatorios y opcionales por tipo de expediente. | M2 | 2 | Alta | 8 | Implementado |
| HU-10 | Vincular anexos obligatorios a documentos principales. | M2 | 2 | Alta | 6 | Implementado |
| HU-11 | Asignar severidad y acción a cada regla. | M2 | 2 | Alta | 5 | Implementado |
| HU-12 | Verificar la completitud y mostrar el porcentaje de documentos presentes. | M2 | 2 | Alta | 6 | Implementado |
| HU-13 | Calcular si cada documento está vigente, próximo a vencer o vencido. | M4 | 2 | Alta | 8 | Implementado |
| HU-14 | Configurar los umbrales de anticipación (30, 15 y 5 días). | M4 | 2 | Media | 4 | Parcial (por variable de entorno, no desde la interfaz) |
| HU-15 | Recibir alertas por documentos faltantes, vencidos o anexos ausentes. | M5 | 2 | Alta | 8 | Implementado |
| HU-16 | Que cada alerta incluya una recomendación. | M5 | 2 | Media | 5 | Implementado |
| HU-17 | Notificaciones por correo ante estatus crítico. | M5 | 2 | Media | 6 | Pendiente |
| HU-18 | Extraer el texto por OCR y almacenarlo segmentado por páginas. | M3 | 3 | Alta | 12 | Implementado |
| HU-19 | Verificar semánticamente las cláusulas obligatorias de un contrato. | M3 | 3 | Alta | 14 | Implementado (reglas RSC-01 del contrato: objeto, vigencia y terminación, penalización, confidencialidad y firmas de las partes, cada una con su cita literal o su recomendación si falta) |
| HU-20 | Cita textual y porcentaje de confianza en cada resultado de la IA. | M3 | 3 | Alta | 6 | Implementado |
| HU-21 | Marcar para revisión manual los hallazgos con confianza < 85 %. | M3 | 3 | Alta | 5 | Implementado |
| HU-22 | Aprobar o rechazar hallazgos de la IA con registro en la bitácora. | M3 | 3 | Alta | 6 | Implementado |
| HU-23 | Extraer los datos del firmante para cotejarlos con el poder notarial. | M3 | 3 | Media | 8 | Implementado (P2, §21.2: firmantes con cita, cotejo con los apoderados del poder o del acta y decisión del analista) |
| HU-24 | Dar de alta tipos de documento con criterios en lenguaje natural. | M2 | 3 | Alta | 10 | Parcial |
| HU-25 | Reutilizar el análisis si el documento no cambió (misma huella). | M3 | 3 | Media | 5 | Implementado (texto e inferencia en caché por huella) |
| HU-26 | Dashboard con porcentaje global, conformes y no conformes. | M6 | 4 | Alta | 10 | Implementado |
| HU-27 | Semáforo visual de cada expediente. | M6 | 4 | Alta | 6 | Implementado |
| HU-28 | Dictamen formal de cumplimiento por expediente. | M6 | 4 | Alta | 8 | Implementado |
| HU-29 | Exportar reportes en PDF y Excel. | M6 | 4 | Alta | 8 | Implementado |
| HU-30 | Consultar la bitácora completa de un expediente. | M7 | 4 | Alta | 5 | Implementado (historial del expediente en la interfaz, `HistorialExpediente.jsx`, sobre `GET /api/v1/bitacora`; eventos consecutivos iguales agrupados) |
| HU-31 | Usuario de consulta: solo el semáforo de sus expedientes asignados. | M7 | 4 | Media | 4 | Pendiente (depende de RF-25/26) |
| HU-32 | Validación completa de un expediente (reglas + IA) con un solo botón. | Integración | 4 | Alta | 14 | Implementado («Auditar pendientes» en el detalle del expediente: audita en secuencia, con reglas e IA, los documentos vigentes sin dictamen y muestra el avance por documento y el semáforo y las alertas antes y después) |
| HU-33 | Manejo controlado de errores (documento ilegible, IA no disponible). | Integración | 4 | Alta | 9 | Implementado (degradación controlada, DG §8.7) |

**Resumen:** 26 implementadas, 3 parciales y 4 pendientes de 33. Respecto de la versión 1.0 pasan a implementadas HU-30 y HU-32 (versión 1.1), HU-19 (versión 1.2) y HU-23 (versión 1.4). Las historias PLUS (HU-34 en adelante) se cuentan en la sección 21.

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

Los demás documentos obligatorios de los inventarios del DOC-02 (poderes, estatutos, actas de asamblea, RFC y aviso de privacidad en el corporativo; certificaciones, fianzas y constancias de capacitación según el sector) forman parte del catálogo de 22 tipos y pueden declararse obligatorios desde la interfaz sin modificar el código.

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
| Documento ilegible | Se notifica que debe recargarse con mejor resolución. | Amarillo |
| Servicio de IA no disponible | Reintentos con espera progresiva; si persiste, el documento queda pendiente sin perderse. | Alerta interna |
| Archivo protegido con contraseña | El Nivel 1 detecta la contraseña de apertura en la carga, custodia el archivo y emite un dictamen No conforme «Archivo protegido, no procesable» (PLUS-02). | Rojo |

Una falla en un documento nunca detiene la validación del resto del expediente.

---

## 11. Requerimientos no funcionales

[DG Cap. IV §4.5 — ISO/IEC 25010 e ISO/IEC 27001]

| ID | Requerimiento | Estado |
|---|---|---|
| RNF-01 | Evaluación determinista de un expediente completo en ≤ 2 s. | Sin medición formal documentada; la evaluación no invoca servicios externos (DG §8.10). |
| RNF-02 | Extracción y análisis con IA de un documento de hasta 20 páginas en ≤ 25 s. | Cumplido: un acta escaneada de 26 páginas se audita en unos 13 s (DG §10.2, §10.7). |
| RNF-03 | ≥ 50 peticiones simultáneas sin degradación. | Sin verificar (no hay prueba de concurrencia documentada). |
| RNF-04 | Cifrado AES-256 de la bóveda en reposo. | Pendiente. |
| RNF-05 | TLS 1.3 entre cliente, microservicios, base de datos y proveedor de inferencia. | Parcial: cifrado solo hacia el proveedor de inferencia. |
| RNF-06 | Al proveedor de IA solo viaja el texto extraído, con Retención Cero de Datos. | Implementado (minimización de datos); ZDR debe activarse en la consola del proveedor. |
| RNF-07 | Interfaz responsiva, resolución mínima de 1366 × 768. | Revisado a 1366 × 768 y 1920 × 1080 sin desbordes horizontales; la regresión visual (`scripts/regresion_visual.py`, 138 capturas en ambas resoluciones y temas) fija la apariencia de cada vista y modal. |
| RNF-08 | Semáforo y hallazgos comprensibles para personal jurídico sin conocimientos técnicos. | Implementado: motivos, alertas y recomendaciones en lenguaje natural. |
| RNF-09 | Disponibilidad ≥ 99.5 % en horario operativo. | Sin medición documentada. |
| RNF-10 | Respaldos automatizados diarios de PostgreSQL (RPO < 24 h). | Pendiente (hoy solo respaldos manuales con `pg_dump`). |
| RNF-11 | Solución contenerizada con Docker Compose. | Implementado (`docker-compose.yml`). |
| RNF-12 | Pruebas y análisis estático en cada confirmación con GitHub Actions. | Implementado (`.github/workflows/ci.yml`, en cada push a `master` y en cada pull request): pytest de core, rules y ai-service sobre PostgreSQL 17, y en el frontend oxlint, equivalencia de marcado del sistema de diseño (`npm run test:ui`) y build de producción. |

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
| Reportes | ReportLab (PDF) y openpyxl (Excel) |

### 12.3 Contratos de API

[DG Cap. VIII §8.4, Tabla 20 — rutas versionadas `/api/v1/`, JSON, errores con el miembro `detail`]

| Servicio | Endpoints principales |
|---|---|
| core-service | `/health`; `/titulares`; `/expedientes` (alta y búsqueda); `/expedientes/{id}`; `/documentos/upload`; `/documentos/{id}/integridad`; `/documentos/{id}/contenido`; `/dictamenes`; `/dictamenes/{id}/ratificar`; `/bitacora`; `/alertas`; `/reportes/expedientes/{id}`; `/reportes/cumplimiento` |
| rules-service | `/health`; `/reglas` (catálogo, alta y pausa); `/reglas/documentos-obligatorios?tipo_expediente=`; `/reglas/evaluar-vigencia` |
| ai-service | `/health`; `/ai/extraer-texto`; `/ai/documentos/{id}/preparar`; `/ai/analisis-semantico`; `/ai/chat-documento`; `/ai/configuracion-ocr` |

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
| `bitacora_auditoria` | Eventos inmutables (protegida por `trg_bitacora_inmutable`). |

Diseñada en DOC-08 y pendiente de implementar: la tabla `usuarios` (email, password_hash bcrypt, nombre_completo, rol, activo) para el Módulo 7.

#### Nota técnica: tipos de datos respecto del diccionario del DOC-08

El diccionario de datos del DOC-08 (Tablas 4 a 8) especifica tipos nativos de PostgreSQL. La implementación usa sus equivalentes portables, como decisión consciente de compatibilidad: la capa de datos se escribe con los tipos genéricos de SQLAlchemy y `config/database.py` admite también `DB_DIALECT=mysql`, así que el esquema no depende de tipos exclusivos de un motor. Verificado en `plurione_compliance` (auditoría del 28/09/2026):

| DOC-08 | Implementación | Por qué | Consecuencia a vigilar |
|---|---|---|---|
| `UUID` en llaves primarias y foráneas | `VARCHAR(36)` con un UUID v4 en texto | `String(36)` funciona igual en PostgreSQL y MySQL; el valor sigue siendo un UUID v4 generado por la aplicación. | Ocupa más que el `UUID` nativo (36 frente a 16 bytes); irrelevante al volumen actual. |
| `TIMESTAMPTZ` | `TIMESTAMP` sin zona | `DateTime` genérico; la aplicación escribe en UTC y los filtros por fecha usan la zona de la sesión de PostgreSQL. | Ver el riesgo «Zona horaria de las marcas de tiempo» (sección 17): migrar a `TIMESTAMPTZ` antes de desplegar en otra zona horaria. |
| `JSONB` (observaciones, metadatos) | `JSON` | `JSON` genérico, portable; ninguna consulta filtra ni indexa dentro de esos campos. | Si se llegan a consultar por su contenido, migrar a `JSONB` para poder indexarlos. |
| `NUMERIC(5,4)` en la confianza del dictamen | `DOUBLE PRECISION` | `Float` genérico. | Precisión de sobra para una confianza en [0, 1]. |

`dictamenes_auditoria` además evolucionó respecto de la Tabla 8: el estatus usa el vocabulario del semáforo (CONFORME, EN_REVISION, NO_CONFORME) en lugar de APROBADO, RECHAZADO y REQUIERE_REVISION_HUMANA; los datos extraídos (tipo, RFC, fechas) son columnas en lugar de un único JSON; la vigencia se guarda como resultado de las reglas RCV (`vigencia_resultado`), y la ratificación registra quién (`revisado_por`), cuándo y con qué justificación, a falta de la tabla `usuarios`.

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

---

## 13. Experiencia de usuario

[DG Cap. IX]

- **Diseño «White & Warm»:** blanco como base, neutros cálidos y color reservado a los estados de auditoría (Conforme, En revisión, No conforme), siempre acompañado de su etiqueta.
- **Navegación:** Cumplimiento (Empresas, Expedientes, Bóveda), Auditoría (Alertas, Reportes) y Configuración (Reglas).
- **Expedientes:** tarjeta con tipo, semáforo, completitud y número de alertas; el detalle muestra documentos exigidos y anexos, estado y vigencia de cada archivo, alertas con recomendación, carga y exportación del dictamen.
- **Panel de Inteligencia Documental:** auditoría en tres etapas visibles (lectura, análisis, reglas de vigencia) con cancelación en cascada, dictamen con medidor de confianza, tabla de cotejo, registro de auditoría con ratificación y chat documental con citas.
- **System Health Strip:** estado, puerto y latencia de los tres microservicios en la cabecera.

---

## 14. Criterios de aceptación del producto

[DG Cap. VII §7.8]

**Funcionales**

- [x] Crear, organizar y buscar expedientes con identificador único y clasificación por tipo.
- [x] Cargar PDF e imágenes con cálculo automático de SHA-256.
- [x] El motor evalúa completitud, vigencia y presencia de anexos.
- [x] Reglas configurables desde la interfaz sin modificar el código.
- [x] El OCR extrae texto legible de documentos escaneados.
- [x] La IA analiza cláusulas contractuales con cita y nivel de confianza *(verificación de contenido RSC-01 con cita literal; los datos del firmante, RSC-02, siguen pendientes)*.
- [x] Los hallazgos de baja confianza requieren ratificación humana.
- [x] Alertas automáticas ante documentos faltantes, vencidos o próximos a vencer.
- [x] Semáforo Verde, Amarillo y Rojo por expediente.
- [x] Reportes exportables en PDF y Excel.

**Seguridad y auditoría**

- [ ] Acceso con autenticación y roles diferenciados *(pendiente: RF-25, RF-26)*.
- [x] Cada acción relevante queda en la bitácora de forma inmutable.
- [ ] Documentos protegidos mediante cifrado y control de acceso *(pendiente: RNF-04, RF-26)*.

**Calidad y entrega**

- [x] Sistema contenerizado, desplegable con un solo comando.
- [ ] Documentación técnica completa: arquitectura, APIs, configuración y manual de usuario *(arquitectura y APIs documentadas; los manuales corresponden a la fase de Documentación, semanas 13–15)*.
- [x] Pruebas funcionales, de integración y de precisión de la IA ejecutadas y documentadas *(las de seguridad corresponden a la fase de Pruebas)*.

---

## 15. Métricas de éxito y resultados medidos

### 15.1 Umbrales definidos en la documentación

| Métrica | Umbral | Fuente |
|---|---|---|
| Tiempo de evaluación determinista por expediente | ≤ 2 s | RNF-01 |
| Tiempo de extracción y análisis por documento (≤ 20 págs.) | ≤ 25 s | RNF-02 |
| Concurrencia sin degradación | ≥ 50 peticiones | RNF-03 |
| Disponibilidad en horario operativo | ≥ 99.5 % | RNF-09 |
| Umbral de confianza para dictamen automático | ≥ 0.85 | RF-14, DOC-08 §6.2 |
| Reducción del tiempo de revisión manual | 90 % (estimación de la propuesta técnica) | DG §6.7 |

### 15.2 Resultados medidos

[DG Cap. X, ejecución del 25 y 27 de septiembre de 2026 en un AMD Ryzen 5 3500U con 8 GB de RAM]

| Resultado | Valor |
|---|---|
| Análisis del Nivel 4 por documento (Groq, sin contención de cuota) | 1.0 a 3.6 s |
| Primera auditoría de un acta escaneada de 26 páginas | ≈ 13 s (11.5 s de OCR y 1.5 s de inferencia) |
| Consulta al chat sobre actas extensas | 1.4 a 2.3 s |
| Lectura ya persistida (sin OCR) | 0.1 a 0.2 s |
| Pruebas automatizadas | 10 suites, 220 de 220 verificaciones aprobadas |

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

| Sprint | Semanas | Objetivo | HU | Estado |
|---|---|---|---|---|
| 1 — Cimientos del sistema | 5–6 | Base de datos, API REST, autenticación con roles y gestión de expedientes con carga. | HU-01 a HU-08 | Implementado, salvo autenticación y roles (HU-05, HU-06) |
| 2 — Motor de reglas y vigencias | 7–8 | Reglas configurables, vigencia y alertas; dictamen determinista sin IA. | HU-09 a HU-17 | Implementado, salvo correo (HU-17) y umbrales desde la interfaz (HU-14) |
| 3 — Análisis inteligente con IA | 9–10 | OCR, análisis semántico, cita y confianza, Human-in-the-Loop. | HU-18 a HU-25 | Implementado parcialmente (HU-24) |
| 4 — Reportes, dashboard e integración | 11–12 | Panel, reportes exportables e integración completa. | HU-26 a HU-33 | Implementado, salvo el usuario de consulta (HU-31, depende del Módulo 7) |

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
- **Zona horaria de las marcas de tiempo:** las columnas TIMESTAMP se guardan en la zona de la sesión de PostgreSQL; se recomienda migrar a TIMESTAMPTZ antes de desplegar en otra zona horaria.

---

## 18. Dependencias y supuestos

**Dependencias externas**

- Groq Cloud (API compatible con OpenAI) y una credencial `GROQ_API_KEY`.
- Binario de Tesseract OCR 5 con los modelos de idioma español e inglés.
- PostgreSQL 17 y Docker Compose en la infraestructura de PluriOne.

**Supuestos** [DG Caps. I, III y VI]

- Los documentos llegan mayoritariamente en PDF, incluidos escaneados (H5).
- Un expediente contiene desde unos diez hasta varias decenas de documentos (H3).
- El catálogo de documentos es la base inicial, no una lista cerrada: el administrador puede ampliarlo (DG Cap. I, «Extensibilidad»).
- La transferencia del texto al proveedor de inferencia debe declararse en el aviso de privacidad de PluriOne (LFPDPPP).

---

## 19. Cambios respecto del anteproyecto

[DG Cap. VI §6.6, Cap. VIII §8.7]

| Anteproyecto | Implementación | Motivo documentado |
|---|---|---|
| Azure AI Document Intelligence para extraer texto | PyMuPDF + Tesseract OCR 5 con preprocesamiento OpenCV, locales | El archivo original no sale de la infraestructura de PluriOne y la capa vectorial se lee de forma exacta (DG §5.2, §8.7). |
| Azure OpenAI + LangChain para el análisis semántico | Groq Cloud (Qwen 3.8, 27B) mediante el SDK compatible con OpenAI | Se evaluó primero un modelo local (Ollama), inviable sin GPU y con 8 GB de RAM; Groq responde en 1–2 s y su plan gratuito cubre la residencia. |
| Azure AI Search | Recuperación de fragmentos BM25 sobre el texto persistido | Método determinista y auditable, sin dependencias adicionales. |
| Power BI para dashboards | Panel y reportes PDF/Excel generados por el propio sistema | No documentado en las fuentes; el alcance funcional (RF-22 a RF-24) se cumple sin Power BI. |
| Microsoft Entra ID | Autenticación JWT HMAC-SHA256 diseñada en DOC-08 | Pendiente de implementar (Módulo 7). |

---

## 20. Pendientes y preguntas abiertas

**Pendientes de implementación** (orden acordado el 29/09/2026: P3 —cadena de custodia sellada—, revisión completa del frontend y, en la fase final, el Módulo 7)

1. Autenticación, usuarios y roles: RF-25, RF-26, HU-05, HU-06 y HU-31; registrar el usuario autenticado en la bitácora (HU-07).
2. Notificaciones por correo electrónico: RF-20, HU-17.
3. Criterios en lenguaje natural para tipos de documento dinámicos (RDS-02): RF-09, HU-24.
4. Carga en lote (RF-02).
5. Requerimientos no funcionales: cifrado AES-256 en reposo (RNF-04), TLS 1.3 interno (RNF-05) y respaldos automatizados (RNF-10); pruebas de concurrencia y disponibilidad (RNF-03, RNF-09).

**Completados desde la versión 1.0 de este documento:** vista de la bitácora en la interfaz (HU-30), validación del expediente completo con un botón (HU-32) e integración continua con GitHub Actions (RNF-12) en la versión 1.1; verificación automática de cláusulas (RSC-01: RF-11 y HU-19) y la categoría de alerta CONTENIDO_NO_LOCALIZADO (RF-18) en la versión 1.2; la ingesta blindada (P1) en la versión 1.3, y los datos del firmante con su cotejo contra el poder o el acta (RSC-02, RN-03, HU-23) en la versión 1.4.

**Preguntas abiertas para el Product Owner**

- ¿Qué documentos adicionales de los inventarios del DOC-02 deben declararse obligatorios por defecto en cada tipo de expediente?
- ¿Qué proveedor de correo y qué destinatarios se usarán para las notificaciones (RF-20)?
- ¿Se requiere MFA desde la primera versión del Módulo 7 (RF-25)?

---

## 21. Extensiones PLUS

Requerimientos que **no forman parte del DOC-04** y se agregan para robustecer el motor sin salir del marco normativo de la documentación (DOC-03: ISO 30301, NOM-151-SCFI-2016, Código Fiscal de la Federación y LFPDPPP). Cada uno se documenta con sus diagramas UML en [`docs/uml/`](uml/README.md) antes de implementarse. El Módulo 7 (RF-25, RF-26) queda para la fase final del proyecto.

### 21.1 P1 — Ingesta blindada

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-01 | **Unicidad de la huella en el expediente.** Si el archivo cargado tiene la misma huella SHA-256 que un documento ya custodiado en el mismo expediente, la carga se rechaza con 409 e identifica el documento existente (tipo, nombre y fecha). Un documento ALTERADO (RIE-03) no cuenta: recargar su original es la corrección que indica su alerta. La misma huella en **otro** expediente sí se admite. | RF-03 y RF-04; ISO 30301 (integridad del expediente). Sin la regla, recargar el mismo archivo lo convierte en la versión vigente sin dictamen y deja como histórico el que ya estaba auditado. | Implementado |
| PLUS-02 | **PDF protegido detectado en el Nivel 1.** Un PDF con contraseña de apertura se custodia (evidencia de lo entregado) con un dictamen No conforme de origen `NIVEL_1` y el evento `ARCHIVO_PROTEGIDO` en la bitácora. El dictamen no admite ratificación: se corrige cargando una versión sin contraseña, que lo sustituye. Un PDF con solo contraseña de propietario (permisos) se abre sin clave y no cuenta como protegido. | DOC-05, Tabla 1: «Archivo protegido con contraseña… El Nivel 1 detecta que el archivo no puede abrirse ni procesarse. Rojo». Hasta ahora se detectaba en el Nivel 3, al auditar. | Implementado |
| PLUS-03 | **Opinión de cumplimiento 32-D.** RCV-04: caducidad estricta de 30 días naturales desde la emisión. RSC-OPIN-SENT: el sentido de la opinión se lee del texto con reglas deterministas (sin IA): **negativo → No conforme**; positivo → elemento cumplido con su cita; sin localizar, ambiguo u otro sentido (sin obligaciones, no inscrito) → revisión humana. Ambas reglas se pausan desde el catálogo. | DOC-05, caducidad estricta: «opiniones de cumplimiento fiscal con vigencia de 30 días naturales a partir de su emisión»; CFF Art. 32-D (DOC-03). | Implementado |

**Historias de usuario**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-34 | Como responsable de cumplimiento, quiero que el sistema rechace un archivo que ya está custodiado en el expediente, para no perder el dictamen vigente ni auditar dos veces el mismo documento. | M1 | Alta | Implementado |
| HU-35 | Como responsable de cumplimiento, quiero saber al cargarlo que un PDF está protegido con contraseña, para pedir al emisor una versión procesable. | M1 | Alta | Implementado |
| HU-36 | Como responsable de cumplimiento, quiero que una opinión 32-D vencida (más de 30 días) o en sentido negativo deje el documento No conforme, con la cita que lo sustenta. | M4 | Alta | Implementado |

**Criterios de aceptación**

- Cargar dos veces el mismo archivo en un expediente responde 409 la segunda vez; no crea documento, no escribe en la bóveda ni cambia el semáforo.
- Dos cargas simultáneas del mismo archivo en el mismo expediente dejan un solo documento (candado por expediente en PostgreSQL).
- Recargar el original de un documento ALTERADO se acepta.
- Un PDF con contraseña de apertura queda custodiado, No conforme, con la alerta `DICTAMEN_NO_CONFORME` y su recomendación; su ratificación responde 409.
- Una opinión emitida hace más de 30 días queda vencida por RCV-04 y la alerta `DOCUMENTO_VENCIDO` cita RCV-04; una en sentido negativo queda No conforme aunque esté vigente.
- Los dictámenes previos no cambian (son inmutables): RCV-04 aplica a las opiniones auditadas después de su alta.

**Implementación y pruebas** (versión 1.3):

| Pieza | Dónde | Pruebas |
|---|---|---|
| PLUS-01: 409 por huella repetida y candado `pg_advisory_xact_lock` por expediente | `core-service/controllers/documento_controller.py` | `tests/test_ingesta_blindada.py` (casos 1–5; el de concurrencia falla sin el candado) |
| PLUS-02: detección con pypdf y dictamen de origen `NIVEL_1` | `core-service/motor/archivo_protegido.py` | `tests/test_ingesta_blindada.py` (casos 6–9) |
| PLUS-03: RCV-04 y RSC-OPIN-SENT en el catálogo | `rules-service/seed_reglas_validacion.py` | `tests/test_rules_service.py` |
| PLUS-03: lectura determinista del sentido (sin Groq) y resultado `NO_CUMPLE` | `ai-service/pipelines/opinion_cumplimiento.py`, `verificacion_contenido.py` | `services/ai-service/tests/test_opinion_cumplimiento.py` (20 casos) |
| PLUS-03: alerta con la cita y la recomendación de la regla incumplida; RCV-04 citada al vencer | `core-service/motor/cumplimiento.py` | `tests/test_ingesta_blindada.py` (casos 10–11) |
| Avisos de la carga, origen `NIVEL_1`, resultado «Incumple», evento `ARCHIVO_PROTEGIDO` | `frontend/src/utils/nivel1.js` y componentes | Verificación en vivo con Playwright |

Verificado en vivo el 29/09/2026 con los tres servicios y Groq (core sobre la base de pruebas): una opinión negativa vigente queda No conforme con su cita sin consultar al modelo para el sentido (la verificación de contenido no gastó tokens); una positiva de 40 días queda vencida por RCV-04; la leyenda «en caso de que la opinión sea en sentido negativo» no se toma como declaración.

**Nombre de la regla.** El diseño la llamó RSC-01-OPIN-SENT; se implementó como **RSC-OPIN-SENT**, la convención del catálogo para los elementos que no son cláusulas contractuales (RSC-ACTA-*, RSC-PODER-*): RSC-01 es la regla de cláusulas contractuales del DOC-05.

**Diagramas:** [casos de uso](uml/p1-casos-de-uso-ingesta-blindada.puml), [actividad de carga](uml/p1-actividad-carga-documento.puml) y [actividad de auditoría de la opinión 32-D](uml/p1-actividad-auditoria-opinion-32d.puml).

### 21.2 P2 — Cotejo del firmante con el apoderado (RSC-02, RN-03, HU-23)

A diferencia de P1, **RSC-02, RN-03 y HU-23 sí están en la documentación** (DOC-05 y DOC-07): P2 los implementa. Lo que se agrega como extensión es la extracción de los apoderados del poder o del acta (HU-37) y el cotejo determinista en cada evaluación (HU-38), que RSC-02 deja al analista y aquí se le presenta ya preparado.

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| RSC-02 | **Datos del firmante.** En la auditoría de un contrato de prestación de servicios o de un NDA, la misma llamada de extracción del Nivel 4 devuelve los firmantes (nombre, cargo, empresa) con su cita. La cita se ancla en el texto y debe contener el nombre; si no, la persona queda «no verificada» y no acredita nada. Se activa con las reglas del catálogo RSC-02-CONT y RSC-02-NDA. El dictamen del contrato queda siempre EN_REVISION: «la decisión final siempre recae en el analista». | DOC-05 RSC-02 (severidad Alta); HU-23 | Implementado |
| HU-37 | **Apoderados del poder o del acta.** En la auditoría de un poder notarial o de un acta constitutiva se extraen, en la misma llamada, las personas con facultades de representación (apoderado, administrador único, presidente del consejo), su cargo, sus facultades y la cita. | DOC-02 Tabla 3 («identificación del otorgante y apoderado»); RSC-PODER-PART, RSC-ACTA-ADMON | Implementado |
| HU-38 | **Cotejo determinista (RN-03).** En cada evaluación del expediente, el core compara el firmante del titular (el de la empresa del titular o sin empresa declarada) con los apoderados de los poderes y actas vigentes, íntegros y del titular: nombres sin acentos, títulos ni partículas; todas las palabras del nombre más corto, al menos dos, deben estar en el más largo. La vigencia del poder se recalcula con RCV-01 (RN-02). Estados: **ACREDITADO**, **NO_ACREDITADO**, **PODER_VENCIDO** y **PENDIENTE** (contrato, poder o acta sin auditar, o firmante no identificado; nunca rechaza). NO_ACREDITADO y PODER_VENCIDO emiten la alerta REPRESENTACION_NO_ACREDITADA (Alta) mientras el contrato no se ratifique. | RN-03; RF-18, RF-21; RN-05 | Implementado |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-37 | Como responsable de cumplimiento, quiero que la auditoría del poder o del acta identifique a los apoderados y sus facultades con su cita, para cotejarlos con quien firma los contratos. | M3 | Media | Implementado |
| HU-38 | Como responsable de cumplimiento, quiero ver en el detalle del contrato si su firmante coincide con un apoderado vigente, con ambas citas, para ratificar la representación con evidencia. | M3 | Alta | Implementado |

**Criterios de aceptación**

- La auditoría de un contrato o NDA devuelve sus firmantes con cita anclada, sin una llamada adicional a Groq, y su dictamen queda EN_REVISION con el motivo RSC-02.
- La de un poder o un acta devuelve sus apoderados con cargo, facultades y cita.
- Firmante del titular que coincide con un apoderado de un poder vigente: ACREDITADO, sin alerta.
- Sin coincidencia con poderes y actas auditados: NO_ACREDITADO y alerta REPRESENTACION_NO_ACREDITADA; coincidencia solo con un poder vencido: PODER_VENCIDO y la misma alerta.
- Poder o acta sin auditar (o auditado antes de P2), contrato sin datos de firmantes o firmante no identificado: PENDIENTE, con la acción que falta; el contrato no se rechaza.
- Un poder ALTERADO o de otro titular (RFC ajeno) no acredita.
- Ratificado el dictamen del contrato, la alerta desaparece (RN-05).
- El detalle del contrato muestra el firmante frente a los apoderados, con sus citas y el documento de origen.

**Consecuencias previstas**

- Los contratos y NDA dejan de poder quedar CONFORME en automático: RSC-02 exige ratificación humana. Los dictámenes previos no cambian (son inmutables).
- Los contratos, poderes y actas auditados antes de P2 no tienen estos datos: su cotejo queda PENDIENTE hasta reauditarlos.
- Los nombres de firmantes y apoderados son datos personales (LFPDPPP, DOC-03): se guardan solo nombre, cargo, empresa, facultades y la cita, en el dictamen, y solo viaja a Groq el texto extraído.
- La extracción de un contrato, poder o acta pide unos cientos de tokens de salida más; el resto de los tipos no cambia.
- Un acta muestra a los representantes que designó al constituirse; si una asamblea posterior los sustituyó, lo decide el analista.

**Modelo de datos:** columna `representacion_legal` (JSON) en `dictamenes_auditoria`, protegida por `trg_dictamen_protegido`.

**Implementación y pruebas** (versión 1.4):

| Pieza | Dónde | Pruebas |
|---|---|---|
| Reglas RSC-02-CONT y RSC-02-NDA (Alta) | `rules-service/seed_reglas_validacion.py` | `tests/test_rules_service.py` |
| Firmantes y apoderados en la misma extracción, con cita anclada; RSC-02 → EN_REVISION | `ai-service/pipelines/representacion.py`, `analisis_semantico.py` | `services/ai-service/tests/test_representacion.py` (7 casos) |
| Columna `representacion_legal` depurada e inmutable | `core-service/controllers/dictamen_controller.py`, `config/database.py` | `tests/test_representacion_legal.py` (la prueba del trigger falla sin la columna protegida) |
| Cotejo determinista, alerta REPRESENTACION_NO_ACREDITADA y `evaluacion.representacion` | `core-service/motor/representacion.py`, `motor/cumplimiento.py` | `tests/test_representacion_legal.py` (16 casos de cotejo) |
| Cotejo en el detalle del contrato | `frontend/src/components/CotejoRepresentacion.jsx` | Verificación en vivo con Playwright |

Verificado en vivo el 29/09/2026 con los tres servicios y Groq (core sobre la base de pruebas), con un contrato y un poder en PDF: el firmante y la contraparte se extrajeron con cita verificada en una sola llamada (la contraparte no se coteja); sin poder, y con el poder sin auditar, el cotejo quedó PENDIENTE; con el poder auditado, ACREDITADO si el apoderado es el firmante y NO_ACREDITADO con alerta ALTA si es otra persona. Una segunda auditoría del mismo contrato reutilizó la inferencia en caché (0 tokens).

**Diagramas:** [casos de uso](uml/p2-casos-de-uso-representacion-legal.puml) y [actividad del cotejo](uml/p2-actividad-cotejo-representacion.puml).

---

## 22. Glosario

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
