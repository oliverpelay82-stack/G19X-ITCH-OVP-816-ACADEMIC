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
| Versión del documento | 3.6 — 10 de octubre de 2026 (3.6: rubro que nombra lo preguntado en el chat, §21.9; 3.5: lectura anticipada y prioridad del OCR, RNF-02, §21.9; 3.4: frontend sin redundancias, §13.1; 3.3: PLUS-23, elementos expresos y cargo del apoderado, §21.9; 3.2: auditoría técnica y OCR en flujo continuo, §21.9; 3.1: depuración del alcance, §21.8; 3.0: RNF-10, respaldos; 2.9: RF-09, corrección de datos y RF-02; 2.8: Fase B del plan visual; 2.7: gráficas, Fase A; 2.6: P7 implementado; 2.5: P7 documentado; 2.4: P6; 2.3: P5 implementado; 2.2: P5 documentado; 2.1: revisión de requerimientos; 2.0: correcciones de la documentación; 1.9: revisión visual del frontend; 1.8: chat documental eficiente; 1.7: revisión del frontend; 1.6: índice de cumplimiento; 1.5: P3; 1.4: P2; 1.3: P1; 1.2: 28 de septiembre; 1.0: 27 de septiembre de 2026) |
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

Tipos de documento: los tres inventarios del DOC-02 (corporativos, jurídicos y regulatorios) [DG Cap. I §1.4, Tablas 2–4]; el catálogo base del código tiene 23: 21 tipos del DOC-02, cuyas Tablas 2 a 4 suman 22 filas porque el poder notarial aparece en la corporativa y en la jurídica, más la opinión de cumplimiento 32-D y la carátula bancaria que ya custodiaba el expediente B2B, ampliables por el administrador [DG Cap. I, «Extensibilidad del Catálogo»].

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

[DG Cap. IV §4.4 — texto oficial de los requerimientos; estado según DG Cap. X §10.7, Tabla 33]

Prioridad tomada de las historias de usuario asociadas (Cap. VII); «—» cuando ninguna historia cubre el requerimiento. Estados: **Implementado**, **Parcial** o **Pendiente**.

### M1 — Gestión de Expedientes

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-01 | Crear expedientes con identificador único, nombre descriptivo, empresa titular y clasificación temática (Jurídico, Corporativo o Regulatorio). | Alta | Implementado | `POST /api/v1/expedientes`; folio único y tipo. |
| RF-02 | Carga de documentos individuales o en lote (PDF, PNG, JPG) asociados a un expediente. | Alta | Implementado | Carga en lote implementada el 02/10/2026 ([rf02-actividad-carga-en-lote.puml](uml/rf02-actividad-carga-en-lote.puml)), en la Bóveda y en el detalle del expediente: la zona de carga admite varios archivos; cada uno pasa el Nivel 1 en el navegador y lleva su propio tipo, sin tipo por omisión (con uno solo para todos, cada archivo sustituiría al anterior, RF-04), y se avisa cuando dos comparten tipo. No se envían las huellas repetidas dentro del lote ni la copia de un archivo que el lote ya custodió (el core respondería 409, PLUS-01). Los archivos van uno a uno a `POST /documentos/upload`, sin endpoint nuevo: cada uno conserva el Nivel 1 del core, sus advertencias (PLUS-02, PLUS-18) y su evento INGESTA_DOCUMENTO. Una falla no detiene el lote: el rechazado queda en la lista con el motivo del core para reintentarlo, y un solo aviso resume el resultado. Prueba: `scripts/prueba_carga_lote.py`. |
| RF-03 | Cálculo automático de la huella SHA-256 al cargar (ISO 30301, NOM-151). | Alta | Implementado | Nivel 1; verificación RIE-03 en cada lectura. |
| RF-04 | Control de versiones con histórico accesible. | — | Implementado | El archivo más reciente de cada tipo sustituye al anterior, que se conserva con sus dictámenes. |
| RF-05 | Búsqueda y filtrado por nombre, empresa, tipo de expediente, fecha de creación y estatus. | Alta | Implementado | Parámetros `q`, `tipo_expediente`, `estado`, `desde` y `hasta`. |

### M2 — Reglas de Validación Configurables

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-06 | Definir documentos obligatorios y opcionales por tipo de expediente sin alterar el código. | Alta | Implementado | Reglas RIE con `tipo_expediente` (sección 9.3). |
| RF-07 | Configurar anexos obligatorios dependientes de un documento principal. | Alta | Implementado | Reglas RIE-02 con `documento_principal`. |
| RF-08 | Severidad por regla (Crítica, Alta, Media-Alta o Media) y acción ante incumplimiento. | Alta | Implementado | Campos `severidad` y `accion` del catálogo. |
| RF-09 | Interfaz para dar de alta nuevos tipos de documento y definir los criterios que evaluará la IA. | Alta | Implementado | Implementado el 01/10/2026 ([rf09-actividad-tipo-documento-nuevo.puml](uml/rf09-actividad-tipo-documento-nuevo.puml)). En Reglas, «Nuevo tipo de documento» pide el nombre (el código se deriva), lo que debe verificar la IA en lenguaje natural (RDS-02), qué hacer si no se cumple y, opcional, en qué tipo de expediente es obligatorio. Crea la regla RDS que declara el tipo en `reglas_validacion` (RDS-01, sin tablas nuevas) y, si es obligatorio, su regla RIE-01 (RF-06). El rules-service publica los tipos declarados (`GET /reglas/tipos-documento`); el core los admite en la carga si están activos y los nombra en alertas y reportes (`motor/tipos_documento.py`, caché de 60 s); la CHECK de `documentos.tipo_documento` valida el formato del código y no la lista de 23 del catálogo base. El Nivel 4 verifica el criterio con su cita y RDS-03 lleva cada documento a revisión humana. Nota para el DOCUMENTO GENERAL: el diccionario de datos de `documentos.tipo_documento` («uno de los 22 tipos») ya no aplica. |

### M3 — Análisis Inteligente de Documentos

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-10 | Extraer texto, tablas y pares clave-valor de documentos escaneados o nativos. | Alta | Parcial | Se extrae el texto plano (PyMuPDF para la capa vectorial; Tesseract con preprocesamiento OpenCV para lo escaneado). La estructura tabular y los pares clave-valor que pide el DOC-04 no se extraen como tales: el Nivel 4 obtiene los datos clave del texto. |
| RF-11 | Análisis semántico con un modelo de lenguaje para verificar cláusulas obligatorias. El proveedor y el modelo son decisiones de diseño (§12.2, §19): hoy, Qwen 3.8 (27B) en Groq Cloud. | Alta | Implementado | Verificación de contenido del Nivel 4 (RSC-01): cada auditoría verifica los elementos que el catálogo exige al tipo de documento (16 reglas RSC: contrato, NDA, acta constitutiva, poder notarial, póliza y licencia). Un elemento es CUMPLE solo si su cita literal aparece en el texto; si no, NO_LOCALIZADO o NO_VERIFICABLE, el dictamen pasa a revisión humana y se emite la alerta CONTENIDO_NO_LOCALIZADO. Los datos del firmante (RSC-02) se extraen en la misma llamada y se cotejan con los apoderados del expediente (P2, §21.2). |
| RF-12 | Indexación y búsqueda semántica sobre el corpus documental. | — | Fuera del alcance | Sin historia de usuario, prioridad ni lugar en el cronograma, y no interviene en el dictamen. La búsqueda dentro de cada documento la cubre la recuperación BM25 del chat (P4). Se declara fuera del alcance de la residencia (versión 2.1). |
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
| RF-18 | Alertas inmediatas ante documento ausente, vencido, anexo faltante o cláusula incumplida. | Alta | Implementado | Once categorías de alerta (sección 10.3; P5 suma DOCUMENTO_ILEGIBLE y PROCESAMIENTO_DIFERIDO); la cláusula incumplida es CONTENIDO_NO_LOCALIZADO. |
| RF-19 | Semáforo Verde / Amarillo / Rojo por expediente. | Alta | Implementado | Reglas del semáforo en la sección 10.2. |
| RF-20 | Notificaciones por correo electrónico ante estatus crítico o vencimiento próximo. | Media | **Pendiente** | Programado para la siguiente iteración del Módulo 5. |
| RF-21 | Recomendación estructurada junto a cada alerta. | Media | Implementado | Campo `recomendacion` de cada alerta. |

### M6 — Reportes y Panel de Control

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-22 | Tablero con porcentaje global de cumplimiento, conformes vs. no conformes y distribución de hallazgos. | Alta | Implementado | Vista de Reportes. El índice de cumplimiento del DOC-05 (§10.5) se agrega junto al porcentaje de expedientes conformes. Las gráficas del tablero sustituyen a la integración con Power BI que menciona el DOC-04 (§19). |
| RF-23 | Dictamen formal de auditoría por expediente. | Alta | Implementado | `GET /api/v1/reportes/expedientes/{id}`. |
| RF-24 | Exportación en PDF y Excel (.xlsx). | Alta | Implementado | ReportLab y openpyxl; cada exportación se registra en la bitácora. |

### M7 — Administración y Seguridad

| ID | Requerimiento | Prioridad | Estado | Evidencia / nota |
|---|---|---|---|---|
| RF-25 | Autenticación con credenciales corporativas y soporte MFA. | Alta | **Pendiente** | Diseñada en DOC-08 (tabla `usuarios`, JWT HMAC-SHA256). |
| RF-26 | Autorización por rol (RBAC). | Alta | **Pendiente** | Roles definidos (sección 5). |
| RF-27 | Bitácora inmutable protegida por el motor de base de datos. | Alta | Implementado | Disparador `trg_bitacora_inmutable` y, desde P3, cada evento sellado en cadena y verificable (`/bitacora/verificar-cadena`); el usuario autenticado se registrará con RF-25. |

**Resumen:** 22 implementados, 1 parcial, 3 pendientes y 1 fuera del alcance de 27 (versión 2.1: RF-10 pasa a parcial y RF-12 sale del alcance; versión 2.9: RF-09 y RF-02 pasan a implementados). La Tabla 33 del DG (§10.7, corte al 03/10/2026) reporta las mismas cifras.

---

## 8. Historias de usuario

[DG Cap. VII §7.6, Tablas 13–16 — 33 historias. Estado derivado de la trazabilidad de requerimientos y del código]

| ID | Historia (resumen) | Módulo | Sprint | Prioridad | Horas | Estado |
|---|---|---|---|---|---|---|
| HU-01 | Clasificar el expediente en uno de los tres tipos del DOC-02 (jurídico, corporativo o regulatorio). | M1 | 1 | Alta | 6 | Implementado (catálogo de los 3 tipos del DOC-02). La redacción original, «crear tipos de expediente», prometía tipos nuevos; el DOC-02 define exactamente estos tres (versión 2.1). |
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
| HU-24 | Dar de alta tipos de documento con criterios en lenguaje natural. | M2 | 3 | Alta | 10 | Implementado (RF-09) |
| HU-25 | Reutilizar el análisis si el documento no cambió (misma huella). | M3 | 3 | Media | 5 | Implementado (texto e inferencia en caché por huella) |
| HU-26 | Dashboard con porcentaje global, conformes y no conformes. | M6 | 4 | Alta | 10 | Implementado |
| HU-27 | Semáforo visual de cada expediente. | M6 | 4 | Alta | 6 | Implementado |
| HU-28 | Dictamen formal de cumplimiento por expediente. | M6 | 4 | Alta | 8 | Implementado |
| HU-29 | Exportar reportes en PDF y Excel. | M6 | 4 | Alta | 8 | Implementado |
| HU-30 | Consultar la bitácora completa de un expediente. | M7 | 4 | Alta | 5 | Implementado (historial del expediente en la interfaz, `HistorialExpediente.jsx`, sobre `GET /api/v1/bitacora`; eventos consecutivos iguales agrupados) |
| HU-31 | Usuario de consulta: solo el semáforo de sus expedientes asignados. | M7 | 4 | Media | 4 | Pendiente (depende de RF-25/26) |
| HU-32 | Validación completa de un expediente (reglas + IA) con un solo botón. | Integración | 4 | Alta | 14 | Implementado («Auditar pendientes» en el detalle del expediente: audita en secuencia, con reglas e IA, los documentos vigentes sin dictamen y muestra el avance por documento y el semáforo y las alertas antes y después) |
| HU-33 | Manejo controlado de errores (documento ilegible, IA no disponible). | Integración | 4 | Alta | 9 | Implementado: una falla no detiene el resto del expediente (DG §8.7), y las dos excepciones del DOC-05, «Documento ilegible, se requiere recarga» y «Procesamiento diferido», se implementan en P5 (§21.5) |

**Resumen:** 27 implementadas, 2 parciales y 4 pendientes de 33 (HU-33 pasó a parcial en la versión 2.1 y se completó con P5). Respecto de la versión 1.0 pasan a implementadas HU-30 y HU-32 (versión 1.1), HU-19 (versión 1.2), HU-23 (versión 1.4) y HU-24 (versión 2.9). Las historias PLUS (HU-34 en adelante) se cuentan en la sección 21.

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
| Documento ilegible | La extracción no obtiene texto suficiente: el documento queda «Documento ilegible, se requiere recarga», distinto de la revisión humana por contenido, y se pide recargarlo con mejor resolución (DOC-05, Tabla 1). Implementado en P5 (§21.5). | Amarillo |
| Servicio de IA no disponible | Hasta 3 reintentos con espera progresiva; si la falla persiste, el documento se marca para procesamiento posterior y se reintenta solo, dentro de la cuota diaria del proveedor (DOC-05, Tabla 1). Implementado en P5 (§21.5). | Alerta interna «Procesamiento diferido» |
| Archivo protegido con contraseña | El Nivel 1 detecta la contraseña de apertura en la carga, custodia el archivo y emite un dictamen No conforme «Archivo protegido, no procesable» (PLUS-02). | Rojo |

Una falla en un documento nunca detiene la validación del resto del expediente. Las dos primeras excepciones se implementaron en P5 (§21.5), con dos categorías de alerta nuevas: «Documento ilegible» y «Procesamiento diferido».

### 10.5 Índice de cumplimiento del expediente (C6)

[DOC-05, «Modelo de Puntuación de Cumplimiento y Semáforo» y RDS-03; [análisis de brechas](ANALISIS_BRECHAS_MOTOR.md), C6; diagrama [c6-actividad-indice-cumplimiento.puml](uml/c6-actividad-indice-cumplimiento.puml)]

No es una extensión PLUS: el DOC-05 lo define («el porcentaje se obtiene dividiendo el número de reglas cumplidas entre el total de reglas evaluadas, multiplicado por 100») y no estaba implementado. Hasta la versión 1.6 el producto solo medía la **completitud** (documentos obligatorios presentes, HU-12), y el tablero la presentaba junto al porcentaje de expedientes conformes: un expediente No conforme con todos sus obligatorios cargados mostraba «Completitud 100 %».

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

**Decisiones aprobadas (29/09/2026).**

1. Lo pendiente cuenta en el denominador: por RDS-03, un resultado sin validar no deja que el expediente «alcance el 100 % de cumplimiento».
2. Sin ponderación por severidad: el DOC-05 define un porcentaje directo; la severidad actúa solo por el bloqueo.
3. Próximo a vencer cuenta como cumplida: es una advertencia (semáforo amarillo), no un incumplimiento. Un expediente puede mostrar 100 % en amarillo solo por esta causa.
4. Un documento sin auditar vale una unidad pendiente: sus reglas de contenido se conocen al auditarlo, así que el índice puede bajar después de una auditoría.
5. El índice global es el promedio de los índices de los expedientes: cada expediente pesa igual.

**Bloqueo por criticidad.** Si falta un obligatorio Crítico, un documento venció o fue alterado —los tres ejemplos del DOC-05—, el índice se marca bloqueado con las reglas que bloquean. El porcentaje no se altera: el semáforo es Rojo «sin importar el porcentaje». El semáforo conserva sus propias reglas (§10.2) y puede ser Rojo sin bloqueo crítico (un dictamen No conforme de severidad Alta).

**Contrato.** Campo nuevo y opcional `evaluacion.indice_cumplimiento` (porcentaje, cumplidas, incumplidas, pendientes, aplicables, bloqueado, bloqueos y el detalle por regla). Se deriva en cada consulta, sin consultas adicionales ni datos persistidos. El tablero muestra el índice promedio como «Cumplimiento» y la completitud por separado, como «Documentos obligatorios presentes»; el indicador del RF-22 de expedientes conformes se conserva con ese nombre.

**Estado:** implementado (revisión del frontend, Lote 3).

| Pieza | Dónde | Pruebas |
|---|---|---|
| Cálculo y bloqueo; campo `evaluacion.indice_cumplimiento` | `core-service/motor/cumplimiento.py` (`indice_cumplimiento`), `schemas/expediente_schema.py` | `tests/test_indice_cumplimiento.py` (16 casos, incluido el expediente de desarrollo: 11 de 16) |
| Índice en el dictamen PDF y Excel, hoja «Reglas» y reporte global («Expedientes conformes» e «Índice de cumplimiento promedio») | `core-service/motor/reportes.py` | `tests/test_tipos_anexos_alertas.py` (la hoja cuadra con la API) |
| Tarjeta «Cumplimiento», fila y bloque del detalle, tablero | `frontend/src/utils/indice.js`, `components/IndiceCumplimiento.jsx`, `MetricsCards.jsx`, `ExpedientesTab.jsx`, `ReportesTab.jsx` | Capturas a 1366 × 768 en ambos temas y regresión visual |

Verificado en vivo el 29/09/2026: el expediente de desarrollo (Grupo Bimbo, No conforme con sus tres obligatorios) muestra 69 % de cumplimiento (11 de 16 reglas; 2 incumplidas, 3 pendientes) junto a «Documentos obligatorios: 3 de 3».

---

## 11. Requerimientos no funcionales

[DG Cap. IV §4.5 — ISO/IEC 25010 e ISO/IEC 27001]

| ID | Requerimiento | Estado |
|---|---|---|
| RNF-01 | Evaluación determinista de un expediente completo en ≤ 2 s. | **Cumple** (01/10/2026): p95 de `GET /expedientes/{id}` de 72.5 ms con 15 documentos y 58.5 ms con una lectura OCR de 20 páginas en curso (`scripts/benchmark_rendimiento.py`; VALIDACION_CUANTITATIVA §10.3). |
| RNF-02 | Extracción y análisis con IA de un documento de hasta 20 páginas en ≤ 25 s. | **Cumple para el analista desde el 04/10/2026** (§21.9): al custodiar, el documento se lee de fondo y la auditoría solo espera al Nivel 4 (≈ 3 s; la resolución del texto del acta real de 26 páginas bajó a 0 ms). Sin lectura anticipada, la auditoría lee directo todas las páginas: 30.2 s por el acta real de 26 páginas densas en el equipo de desarrollo (34 a 41 s antes), ≈ 26 s por cada 20 páginas con el Nivel 4; con documentos sintéticos, contrato escaneado de 20 páginas en 8.8 s de lectura. Tesseract es el 95 % del tiempo y el límite es el procesador (VALIDACION_CUANTITATIVA §10.3). |
| RNF-03 | ≥ 50 peticiones simultáneas sin degradación. | **Cumple el criterio de la validación** (01/10/2026): 50 simultáneas sin 5xx ni transacciones perdidas (100/100 cargas con documento y evento, cadena íntegra), p95 de consulta 1.07 s; la latencia se degrada (×17) con un solo proceso de uvicorn y las cargas se serializan por el candado de la bitácora (VALIDACION_CUANTITATIVA §10.3). |
| RNF-04 | Cifrado AES-256 de la bóveda en reposo. | Pendiente. |
| RNF-05 | TLS 1.3 en el borde (entre el cliente y el sistema, mediante un proxy inverso) y hacia el proveedor de inferencia; los microservicios y la base de datos en una red interna aislada, sin puertos expuestos. Redefinido en la versión 2.1: cifrar el tráfico entre contenedores de una misma red aislada añade certificados internos sin una protección equivalente; la segregación de redes cumple el objetivo (ISO/IEC 27001, A.8.22). | Parcial: cifrado solo hacia el proveedor de inferencia; proxy inverso y aislamiento de puertos pendientes. |
| RNF-06 | Al proveedor de IA solo viaja el texto extraído, con Retención Cero de Datos. | Implementado (minimización de datos); ZDR debe activarse en la consola del proveedor. |
| RNF-07 | Interfaz responsiva, resolución mínima de 1366 × 768. | Implementado. Revisión del frontend (§13.1): a 1366 × 768 ninguna vista se desborda ni recorta textos que deban leerse (tipos de documento, folios, huellas, categorías, placeholders); las métricas solo acompañan a Expedientes (desde el 04/10/2026, §13.1), el catálogo de reglas se pliega por familia (de 3,268 a 768 px de alto) y el modal del documento abre con el dictamen. La regresión visual (`scripts/regresion_visual.py`, 158 capturas en 1366 × 768 y 1920 × 1080, en ambos temas, con modales completos y escenarios interactivos) fija la apariencia de cada vista y modal. |
| RNF-08 | Semáforo y hallazgos comprensibles para personal jurídico sin conocimientos técnicos. | Implementado. Revisión del frontend (§13.1): la interfaz, los motivos del semáforo, las alertas y los reportes PDF y Excel no citan requisitos (RF-, RN-, RNF-, DOC-), niveles del pipeline, el proveedor de IA ni códigos internos, y las fechas se escriben en palabras (`motor/redaccion.py`); los códigos de regla se conservan donde identifican una regla. El índice de cumplimiento (§10.5) separa el cumplimiento de la completitud documental. Las pruebas del core fallan si un motivo, una alerta o el PDF del dictamen traen códigos o referencias. Observación: las observaciones que redacta el modelo se muestran tal como quedaron en el dictamen (inmutable); si el modelo escribe un código de su catálogo (p. ej. «se clasifica como OTRO»), el ajuste corresponde a las instrucciones del ai-service. |
| RNF-09 | Disponibilidad ≥ 99.5 % en horario operativo, medida con las comprobaciones de salud de cada servicio (reinicio automático en Docker y registro de disponibilidad a partir de sus sondeos). Precisado en la versión 2.1. | Sin medición documentada. |
| RNF-10 | Respaldos automatizados diarios, en un mismo punto, de PostgreSQL, la bóveda y la base del ai-service (RPO < 24 h), con una prueba de restauración. Ampliado en la versión 2.1: un respaldo de la base sin la bóveda no sirve como evidencia, y al restaurarlo RIE-03 marcaría como alterados los documentos no restaurados. | Implementado el 02/10/2026 ([rnf10-actividad-respaldo.puml](uml/rnf10-actividad-respaldo.puml)). `scripts/respaldo.py crear` genera un paquete con el volcado de `plurione_compliance`, la bóveda comprimida, la SQLite del ai-service (copiada con la API de respaldo de SQLite) y un manifiesto con el SHA-256 de cada pieza y el último eslabón de la bitácora. Corre con los servicios en marcha: el volcado es una instantánea y la bóveda solo agrega archivos, así que la copia posterior es un superconjunto. Cada paquete pasa enseguida su prueba de restauración: se restaura en una base temporal, se recalcula la huella de cada documento contra la bóveda (RIE-03), se verifica la cadena de la bitácora (PLUS-05) con el eslabón del manifiesto y la integridad de la SQLite. Retención de los paquetes verificados más recientes (`RESPALDO_RETENCION`, 14) y segunda copia opcional dentro de la infraestructura (`RESPALDO_SECUNDARIO`). `programar` registra la tarea diaria, que corre al encender el equipo si la hora pasó con él apagado (RPO < 24 h). El DOC-04 pide además almacenamiento redundante en la nube: como el paquete contiene los originales y MR-16 exige que no salgan de la infraestructura, la nube queda como pregunta abierta (§20), sujeta al cifrado de RNF-04. Primer respaldo real verificado el 02/10/2026; prueba: `scripts/prueba_respaldo.py`. |
| RNF-11 | Solución contenerizada con Docker Compose. | Implementado (`docker-compose.yml`). |
| RNF-12 | Pruebas y análisis estático en cada confirmación con GitHub Actions. | Implementado (`.github/workflows/ci.yml`, en cada push a `master` y en cada pull request): pytest de core, rules y ai-service sobre PostgreSQL 17, y en el frontend oxlint, equivalencia de marcado del sistema de diseño (`npm run test:ui`) y build de producción. |

**Extensiones PLUS no funcionales** (no forman parte del DOC-04; versión 2.1):

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-12 | Accesibilidad WCAG 2.1 nivel AA: navegación completa por teclado, foco visible y atrapado en los modales, roles y estados ARIA, contraste mínimo de 4.5:1 en el texto y respeto a «reducir movimiento». | ISO/IEC 25010 (usabilidad › accesibilidad), citada en el DOC-03 | Parcial: implementado en la interfaz (trampa de foco, `aria-sort`, contraste AA de los tokens, «reducir movimiento»); falta su verificación automática. |
| PLUS-13 | Conservación de la evidencia: documentos (con sus versiones sustituidas), dictámenes, bitácora y texto extraído se conservan al menos 5 años y mientras exista el expediente; el sistema no elimina registros (§12.6). | CFF, art. 30; ISO 30301 | Implementado por diseño (no hay eliminación); la disposición al vencer el plazo depende del Módulo 7. |

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
| Gráficas del tablero | Recharts 3 (licencia MIT), cargada solo en la vista de Reportes (sustituye a Power BI, §19); las vistas se cargan por separado |

### 12.3 Contratos de API

[DG Cap. VIII §8.4, Tabla 20 — rutas versionadas `/api/v1/`, JSON, errores con el miembro `detail`]

| Servicio | Endpoints principales |
|---|---|
| core-service | `/health`; `/titulares`; `/expedientes` (alta y búsqueda); `/expedientes/{id}`; `/documentos/upload`; `/documentos/{id}/integridad`; `/documentos/{id}/contenido`; `/dictamenes`; `/dictamenes/{id}/ratificar`; `PATCH /titulares/{id}` y `PATCH /expedientes/{id}` (corrección de datos de captura); `/documentos/{id}/contenido?descarga=true` (descarga del original); `/bitacora`; `/bitacora/verificar-cadena` (P3); `/alertas`; `/reportes/expedientes/{id}`; `/reportes/cumplimiento`; `/reportes/documentos/{id}/custodia` (P3) |
| rules-service | `/health`; `/reglas` (catálogo, alta y pausa); `/reglas/documentos-obligatorios?tipo_expediente=`; `/reglas/tipos-documento` (tipos declarados por reglas RDS, RF-09); `/reglas/evaluar-vigencia` |
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
| `bitacora_auditoria` | Eventos inmutables (protegida por `trg_bitacora_inmutable`), sellados en cadena con `secuencia`, `hash_anterior` y `hash_evento` (P3). |

Diseñada en DOC-08 y pendiente de implementar: la tabla `usuarios` (email, password_hash bcrypt, nombre_completo, rol, activo) para el Módulo 7.

#### Nota técnica: tipos de datos respecto del diccionario del DOC-08

El diccionario de datos del DOC-08 (Tablas 4 a 8) especifica tipos nativos de PostgreSQL. La implementación declara las columnas con los tipos genéricos de SQLAlchemy, que en PostgreSQL se materializan como sus tipos nativos. PostgreSQL es el único motor: la opción `DB_DIALECT=mysql` se retiró el 04/10/2026 porque nunca pudo funcionar (los triggers de inmutabilidad, `pg_advisory_xact_lock`, `clock_timestamp()` y las columnas JSON son de PostgreSQL). Verificado en `plurione_compliance` (auditoría del 28/09/2026):

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

### 13.1 Revisión del frontend (29/09/2026)

Revisión completa de la interfaz después de P1 a P3, en lotes aprobados por el responsable del proyecto y verificados con la regresión visual en cada paso:

| Lote | Alcance | Requerimientos |
|---|---|---|
| 0 | La regresión visual cubre el cotejo de P2 y la cadena de P3. | RNF-07 |
| 1 | Correcciones puntuales: botón deshabilitado legible, textos recortados a 1366 × 768, concordancia de número, categorías y tipo heredado en palabras, barra de completitud neutra. | RNF-07, RNF-08 |
| 2 | Lenguaje llano en la interfaz, los motivos, las alertas y los reportes. | RNF-08 |
| 3 | Índice de cumplimiento del DOC-05 (§10.5); navegación en la URL con inicio en Expedientes; métricas solo en Expedientes y Reportes; detalle del expediente, modal del documento y Bóveda reorganizados. | RF-19, RF-22, RNF-07, RNF-08 |
| 4 | Refactor sin cambio visual (hojas de estilo por contexto y componentes divididos; 0 capturas distintas y el CSS del build idéntico) y catálogo de reglas plegable por familia. | RNF-07; mantenibilidad (ISO/IEC 25010) |
| 5 | Documentación: CLAUDE.md, este PRD y el MRD. | — |
| Refinamiento | Contenido centrado con ancho máximo; Bóveda con solo los vigentes por defecto; detalle del expediente con columna lateral fija, motivos en filas y alertas compactas; modal del documento con encabezado de veredicto y secciones (Resultado, Evidencia, Registro técnico, Chat) en bloques delimitados. | RNF-07, RNF-08 |
| Proporciones (30/09/2026) | Sin cambiar paleta ni tokens, en siete tandas con regresión visual entre cada una: etiquetas de estado con mayúscula inicial y espaciados con tokens; modal del documento sin estados repetidos, un solo acceso a la ratificación y sin tarjetas anidadas; detalle del expediente con cada motivo y su qué hacer (los documentos ya no se listan tres veces), tabla con el código de regla bajo el nombre y filtro de fechas como un solo control; huella de la Bóveda en un renglón; bandeja de Alertas agrupada por severidad, con el expediente en una columna propia y renglones de unos 100 caracteres; Reportes en cuatro secciones con título (reporte global arriba, métricas, hallazgos, seguimiento del analista y dictamen por expediente), sin la tarjeta «Expedientes conformes», que repetía la métrica «Expedientes»; Reglas sin encabezados vacíos. | RF-18, RF-21, RN-05, RNF-07, RNF-08 |
| Pulido de producto (30/09/2026) | Dos niveles de título (secciones y etiquetas de tarjeta) y títulos de página iguales al menú; tablas con encabezados en mayúscula inicial, orden por columna, encabezado fijo y fechas «27 sep»; Reglas sin la columna «Acción»; indicador único de salud del sistema; contador solo en Alertas; Expedientes por prioridad; confirmación al pausar o activar una regla; atajo «/» al buscador; estados vacíos con su acción. | RF-18, RF-22, RNF-07, RNF-08 |
| Gráficas, Fase A (01/10/2026) | Plan visual aprobado el 01/10/2026: cada vista se carga al abrirla (el paquete principal baja de 418 a 334 KB) y Reportes incorpora Recharts con cuatro gráficas: semáforo de los expedientes como anillo con el índice promedio al centro; hallazgos por área y severidad apilados; vencimientos de los próximos 90 días como puntos por área, con las franjas de las alertas de vigencia (5 y 30 días) y acceso al expediente; y cambios del semáforo de los últimos 30 días (mejoras y deterioros) a partir de la bitácora, sin guardar historia nueva. Cada gráfica trae leyenda con cifras, tooltip y «Ver datos» en tabla, y respeta el tema oscuro y «reducir movimiento». El reporte global en PDF abre con un resumen ejecutivo en gráficas y el Excel agrega la hoja «Gráficas» con gráficas nativas. Colores en tokens `--chart-*`, validados con un verificador de paletas (separación entre estados y para daltonismo, rampa de un solo tono para la severidad); los tokens de estado no cambian. Se descartó guardar una fotografía diaria del índice: ningún DOC la pide y la tendencia del semáforo ya sale de la bitácora. | RF-22, RF-24, RNF-07, RNF-08 |
| Experiencia, Fase B (01/10/2026) | Paleta de comandos con Ctrl+K (expedientes por folio, nombre, empresa o RFC; documentos; secciones; tema y actualizar), búsqueda sin acentos y por palabras; vista previa del expediente al detenerse en un folio (semáforo, índice, obligatorios y alerta más grave) en Alertas, Bóveda, Reportes, el tablero y Empresas; «Deshacer» en el aviso al pausar o activar una regla (la ratificación no lo ofrece: es definitiva, RN-05), con avisos que no se retiran mientras se leen; check que se dibuja al pasar a Conforme a la vista; anillo de progreso en «Auditar pendientes»; y escala de iconos en tres tamaños (12, 14 y 16). La gráfica de tendencia pasa a llamarse «Tendencia del semáforo» para no repetir el título de la tarjeta de cambios recientes. | RF-19, RF-22, HU-32, RN-05, RNF-07 |
| Marca e iconos propios (01/10/2026) | Marca del Motor (`LogoMotor.jsx`): la hoja de un expediente con su check de validación y la esquina doblada en sólido, en la barra lateral y en el favicon, con su versión para tema oscuro. Es la marca del sistema, no el logotipo oficial de PluriOne. Iconos propios (`IconosMotor.jsx`) para los cuatro conceptos que Lucide solo resolvía con figuras genéricas: Expediente (carpeta con su hoja), Bóveda (la hoja con candado, custodia del documento), Reglas (ficha del catálogo con criterios verificados) y Semáforo (en la tarjeta de cumplimiento). Heredan el trazo y la escala de los iconos de Lucide; los demás iconos no cambian. Sin cambios de paleta ni de tokens. | RNF-07, RNF-08 |
| Detalle de la empresa (01/10/2026) | Cada empresa tiene su página (`#/empresas/<RFC>`, se puede compartir y recargar), a la que se entra desde su tarjeta o su fila. Muestra sus datos (razón social, RFC con su verificación, tipo de persona, categoría y alta), un resumen en una línea (expedientes por semáforo, documentos vigentes y alertas por severidad), todos sus expedientes de lo más grave a lo conforme (folio, tipo, semáforo, índice de cumplimiento, obligatorios presentes y alertas) y sus alertas más graves con su recomendación. Antes, la tarjeta mostraba solo el último expediente y un «+N». Sin cambios en el backend ni tarjetas de métricas: los datos salen del listado de expedientes ya cargado. Diagrama: [ui-actividad-detalle-empresa.puml](uml/ui-actividad-detalle-empresa.puml). | RF-01, RF-05, RF-18, RF-19, RF-21; HU-02, HU-04, HU-27 |
| Descarga del archivo original (01/10/2026) | El detalle del documento ofrece «Descargar original»: el archivo custodiado con su nombre de carga, entregado solo si su huella coincide con la registrada (RIE-03). Cada descarga queda en la bitácora (DESCARGA_DOCUMENTO), como las exportaciones de reportes; la lectura del binario que hace el ai-service no se registra. | RF-03, RF-24, RF-27; HU-29 |
| Empresas en la paleta de comandos (01/10/2026) | Ctrl+K encuentra las empresas por razón social o RFC y abre su detalle. | RF-05; HU-04 |
| Corrección de datos de captura (01/10/2026) | En el detalle de la empresa, «Corregir datos» edita la razón social y la categoría; en el detalle del expediente, «Renombrar» edita su nombre. El RFC, el tipo de persona y el tipo de expediente no se editan: identifican al titular o deciden qué se exige, y un error ahí se resuelve con un registro nuevo. Cada cambio queda en la bitácora sellada con el valor anterior y el nuevo (ACTUALIZACION_TITULAR, ACTUALIZACION_EXPEDIENTE); los dictámenes emitidos no cambian (RN-05). Diagrama: [ui-actividad-correccion-datos.puml](uml/ui-actividad-correccion-datos.puml). | RF-01, RF-27; RN-04, RN-05; HU-02, HU-07 |
| Depuración de redundancias (01/10/2026) | Revisión vista por vista con el residente: cada dato se dice una vez, en el lugar donde se actúa. Detalle del expediente: el recuadro de bloqueo del índice ya no repite la lista de faltantes (están en los motivos con su qué hacer), la fila desplegada no repite el índice del bloque lateral y el bloque de auditar pendientes no deja una tarjeta vacía. Tarjetas de métricas: el expediente muestra su reparto por tipo, porque el semáforo ya está en los filtros y en la gráfica. Reportes: la tarjeta de vencimientos y la de cambios del semáforo se retiran (lo dicen las gráficas, y la de cambios absorbe la lista de los últimos con su enlace, con una sola consulta a la bitácora); «Por categoría» y «Pendientes del analista» quedan en una sola tarjeta. Alertas: si todas son de un mismo expediente, la columna del expediente se sustituye por un enlace en el resumen. Una vista que no carga muestra un aviso con «Recargar» en lugar de dejar la pantalla en blanco. | RF-19, RF-21, RF-22, HU-26; RNF-07, RNF-08 |
| Alertas y Reportes (03/10/2026) | A petición del residente. Alertas: cada severidad (Crítica, Alta, Media-alta y Media) es un grupo plegable; las críticas entran abiertas, las demás plegadas, y filtrar por una severidad la abre. Reportes: el anillo del semáforo tiene esquinas redondeadas y una entrada de 800 ms (sin animación si se pide reducir movimiento); un clic en un sector filtra por ese estado la tabla «Dictamen por expediente» y atenúa los demás sectores, con el mismo filtro como control segmentado sobre la tabla (también para teclado). «Por categoría» ya no repite los folios en cada barra: cada categoría es una etiqueta con su conteo («2 documentos»); los expedientes de cada hallazgo están en Alertas y en la tabla. | RF-18, RF-22, HU-26; RNF-07, RNF-08 |
| Sin redundancias, mejoras visuales y movimiento (04/10/2026) | A petición del residente: ninguna pantalla repite otra ni ofrece un botón que lleve a lo mismo. **Reportes** ya no tiene la fila de métricas (idéntica a la de Expedientes) ni la tabla «Dictamen por expediente» (repetía la lista de Expedientes y el botón de exportación del detalle). Queda el reporte global con sus gráficas, y un sector del anillo abre Expedientes ya filtrado por ese estado. El dictamen de cada expediente se exporta desde su detalle. **Detalle de la empresa:** sus alertas más graves se resumen en una línea cada una, y «Ver las N en Alertas» abre la bandeja filtrada por su RFC. **Detalle del expediente:** los motivos con la misma causa (p. ej., cuatro documentos pendientes de ratificación) van en una sola fila con un solo «qué hacer». **Modal del documento:** «Dictamen automático» solo aparece si la ratificación cambió el estatus. **Empresas:** el aviso del RFC es una etiqueta de advertencia con su explicación al pasar el cursor; la tarjeta muestra el índice de cumplimiento bajo el semáforo y el folio en la identidad. **Bóveda:** el folio cabe completo a 1366 px. **Movimiento:** los desplegables nativos se abren con altura animada, las reglas de una familia entran en cascada y las pestañas del panel de IA se funden; todo respeta «reducir movimiento». | RF-18, RF-21, RF-22, RF-23, RF-24, HU-26, HU-28; RN-05; RNF-07, RNF-08 |
| Código sin duplicados (04/10/2026) | Aprobado por el residente tras la revisión del código del frontend. Los buscadores de Expedientes, Empresas, Bóveda, Alertas y Reglas usan el de la paleta Ctrl+K (`utils/busqueda.js`): ignoran acentos y aceptan varias palabras en cualquier orden («situacion fiscal», «bimbo grupo»), cuando antes cada vista distinguía acentos y exigía la frase exacta. El detalle de la empresa ya no tiene el botón «← Empresas», que repetía la miga del encabezado. Sin cambio visual: una sola insignia de estado (`EstadoBadge`), un solo avatar (`ui/Avatar`), una sola lista de alertas por expediente (`utils/alertas.js`) y un solo `plural()`; `test:ui` comprueba con 29 casos que el HTML no cambió. | RF-05, RF-18; RNF-07, RNF-08; ISO/IEC 25010 (mantenibilidad) |
| Paleta solo de búsqueda (13/10/2026) | A petición del residente: Ctrl+K ya no lista las secciones ni las acciones de tema y actualizar, que repetían el menú lateral y los botones del encabezado (PRD §13.1). Solo busca empresas, expedientes y documentos; sin texto, indica qué se puede buscar. Se retira el pie de atajos de teclado. | RF-05; RNF-07 |
| «Actualizado» solo al actualizar (13/10/2026) | A petición del residente: la cabecera ya no muestra fija la antigüedad de los datos («Actualizado hace…»); «Actualizado ahora» aparece al terminar «Actualizar datos» con éxito y se desvanece a los 3 s, en un espacio reservado para que los botones no se muevan. El sondeo automático no lo muestra. | RNF-07 |
| Menú lateral sin versión (13/10/2026) | A petición del residente: se retira el pie «Versión 1.0.0» del menú lateral. La versión de cada servicio sigue en `GET /api/v1/health` y la del catálogo, en los dictámenes y reportes. | RNF-07 |
| Iconos del menú con Phosphor (13/10/2026) | A petición del residente: los seis iconos del menú lateral pasan a Phosphor (`@phosphor-icons/react`): Empresas, Expedientes, Bóveda, Alertas, Reportes y Reglas, en peso regular y duotone en la sección activa. El resto de la interfaz conserva Lucide e IconosMotor. El paquete principal crece 4.5 KB comprimido. | RNF-07 |
| Marca con Phosphor (13/10/2026) | A petición del residente: la marca del Motor (`LogoMotor.jsx`) y el favicon pasan de la hoja con check a SealCheck de Phosphor (sello de validación, relleno), con su versión para tema oscuro en el favicon; también los botones de la cabecera (buscar, actualizar y tema) y las cuatro métricas de Expedientes (Buildings, FolderOpen, Vault y TrafficSignal). Se retiran IconoBoveda e IconoSemaforo, que quedaron sin uso. | RNF-07 |
| Iconos Phosphor, tanda 1 (13/10/2026) | A petición del residente, en dos tandas: las primitivas (`Button`, `Modal`, `SearchBox`, `CopyChip`, `EmptyState`) y las vistas principales (Empresas, Expedientes, Bóveda, Alertas, Reglas, Reportes, detalle de empresa y de expediente, carga, orden de tablas, paleta y migas) pasan de Lucide a Phosphor en peso regular; los estados vacíos de Expedientes y Reglas usan FolderOpen y ListChecks en lugar de los iconos propios. Los iconos de las primitivas llevan `aria-hidden` explícito (Lucide lo ponía por defecto) y `equivalencia-ui.jsx` se actualizó a los mismos iconos (29 de 29). Sin optimizar, el paquete principal crecía 26.5 KB comprimido (cada icono de Phosphor trae sus seis pesos); lo resuelve la tanda 2. | RNF-07, RNF-08 |
| Iconos Phosphor, tanda 2 y peso (13/10/2026) | El panel de IA del documento, el visor, los dictámenes, los avisos, el error de vista, el historial y el catálogo `#/ui` pasan a Phosphor; se retiran `lucide-react`, el `LucideProvider` de `main.jsx` e `IconosMotor.jsx`. Optimización: `scripts/generar-iconos.mjs` (`npm run iconos`) genera `src/components/iconos.js` con los iconos que importa la interfaz y solo los pesos que usa (regular, más los que su archivo nombra en `weight`), sobre el `IconBase` de Phosphor; todo icono sin `aria-label` sale con `aria-hidden`, como en Lucide. `test:ui` falla si el módulo está desactualizado. Frente al último commit (todo Lucide), la carga inicial pasa de 119 a 122 KB comprimidos y el total de JS de 252 a 253 KB. | RNF-07, RNF-08 |

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

- Groq Cloud (API compatible con OpenAI) y una credencial `GROQ_API_KEY`. El plan gratuito limita `qwen/qwen3.8-27b` a 8,000 tokens por minuto y **200,000 tokens por día** (medido el 30/09/2026 al agotarse): ≈ 28 auditorías de un documento largo (≈ 7,000 tokens) o ≈ 125 turnos de chat con modelo al día. Las respuestas sin modelo (PLUS-07, PLUS-08) y el caché (PLUS-10) no consumen esa cuota; un despliegue con más volumen requiere el plan de pago.
- Binario de Tesseract OCR 5 con el modelo de idioma español (`OCR_LANG=spa` desde el 30/09/2026).
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
| Power BI para el tablero (DOC-04: «visualización de métricas ejecutivas en dashboard con integración a Power BI») | Tablero propio con gráficas de una librería de código abierto (licencia MIT) y reportes PDF y Excel con gráficas generadas por el sistema | Power BI requiere licencia de pago para publicar y compartir tableros, y conectarlo exigiría exponer los datos de cumplimiento a un servicio externo. El tablero integrado cubre RF-22 a RF-24 sin costo de licencia, con los datos dentro de la infraestructura de PluriOne (RNF-06) y con el mismo semáforo y vocabulario que el resto del sistema. |
| Microsoft Entra ID | Autenticación JWT HMAC-SHA256 diseñada en DOC-08 | Pendiente de implementar (Módulo 7). |

**Decisiones respecto de los DOC-04, DOC-05 y DOC-08** (declaradas a partir del análisis de brechas, C1 a C5 y C7):

| Documento | Implementación | Motivo |
|---|---|---|
| DOC-08: monolito modular en dos contenedores (backend en el puerto 8000, PostgreSQL 16) e inferencia local con Ollama (Qwen2.5:7b) | Tres microservicios (core 8001, rules 8002, ai 8003), frontend en 5173, PostgreSQL 17 y Groq Cloud | La arquitectura de microservicios es la del DOCUMENTO GENERAL (Cap. VIII): el catálogo de reglas y la IA se despliegan y fallan por separado, y el motor de reglas (Nivel 2) sigue operando sin la IA (riesgo del DOC-07). Ollama se descartó por falta de GPU (fila anterior). PostgreSQL 17 es la versión estable vigente en el arranque del proyecto. |
| DOC-08: carga de hasta 50 MB | Hasta 15 MB por archivo (`MAX_FILE_SIZE_BYTES`) | Límite fijado desde la primera versión de la implementación. Su origen no está documentado: queda como pregunta abierta (§20). |
| DOC-04, RF-14: revisión humana con confianza inferior al 80 % | Bandas del DOC-05 y del DOC-08 §6.2: CONFORME desde 85 %; de 70 % a 84 % y por debajo de 70 %, revisión humana | El DOC-05 y el DOC-08, posteriores y más específicos, fijan 85 %; se aplica el criterio más estricto. |
| DOC-04 (RF-08): severidades Alta, Media y Baja; DOC-07 (HU-11): Crítica, Alta y Media | Las cuatro severidades del DOC-05: Crítica, Alta, Media-Alta y Media | El DOC-05 es el que define el catálogo de reglas y su criticidad. |
| Amarillo del semáforo: «próximo a vencer» (DOC-03), «próximos a vencer o pendientes de ratificación» (DOC-04), «advertencia» (DOC-06) | Amarillo también con documentos sin auditar y obligatorios no críticos faltantes (§10.2) | Un expediente con documentos sin revisar no puede mostrarse en verde: subir archivos nunca aprueba un expediente. |
| DOC-08: estado `BLOQUEADO` del expediente | El documento alterado queda ALTERADO, con un dictamen No conforme y respuesta 409 (RIE-03) | Equivalente funcional: el bloqueo se aplica al documento comprometido y el expediente pasa a No conforme por ese dictamen. |

---

## 20. Pendientes y preguntas abiertas

**Pendientes de implementación** (orden acordado el 29/09/2026: P1 a P3 y la revisión completa del frontend terminados; en la fase final, el Módulo 7)

1. Autenticación, usuarios y roles: RF-25, RF-26, HU-05, HU-06 y HU-31; registrar el usuario autenticado en la bitácora (HU-07).
2. Notificaciones por correo electrónico: RF-20, HU-17.
3. Requerimientos no funcionales: cifrado AES-256 en reposo (RNF-04), TLS 1.3 en el borde y red interna aislada (RNF-05); pruebas de concurrencia y disponibilidad (RNF-03, RNF-09).
4. Después de P5 (revisión de requerimientos, versión 2.1): ciclo de vida del expediente activo, cerrado y archivado, sin eliminar nada, para que un expediente concluido deje de evaluarse y de alertar (complementa la conservación de §12.6). La corrección de los datos de una empresa o un expediente con registro en la bitácora, que este punto también pedía, se implementó en la versión 2.9 (`PATCH /titulares/{id}` y `PATCH /expedientes/{id}`).
5. Iteración posterior: revocación de poderes y vigencias ligadas entre documentos (fianza y convenio modificatorio atados a la vigencia del contrato), que exige el DOC-02.

**Completados desde la versión 1.0 de este documento:** vista de la bitácora en la interfaz (HU-30), validación del expediente completo con un botón (HU-32) e integración continua con GitHub Actions (RNF-12) en la versión 1.1; verificación automática de cláusulas (RSC-01: RF-11 y HU-19) y la categoría de alerta CONTENIDO_NO_LOCALIZADO (RF-18) en la versión 1.2; la ingesta blindada (P1) en la versión 1.3, los datos del firmante con su cotejo contra el poder o el acta (RSC-02, RN-03, HU-23) en la versión 1.4, y la cadena de custodia sellada con su ficha de trazabilidad (P3) en la versión 1.5; tipos de documento nuevos con su criterio para la IA (RF-09, HU-24), corrección de datos de captura y carga en lote (RF-02) en la versión 2.9; respaldo diario conjunto con prueba de restauración (RNF-10) en la versión 3.0.

**Preguntas abiertas para el Product Owner**

- ¿Qué documentos adicionales de los inventarios del DOC-02 deben declararse obligatorios por defecto en cada tipo de expediente?
- ¿Qué proveedor de correo y qué destinatarios se usarán para las notificaciones (RF-20)?
- ¿Se requiere MFA desde la primera versión del Módulo 7 (RF-25)?
- ¿Dónde se guarda la segunda copia de los respaldos (RNF-10)? El DOC-04 pide almacenamiento redundante en la nube, pero el paquete contiene los originales y MR-16 exige que no salgan de la infraestructura: ¿un recurso de red de PluriOne, o una nube aprobada una vez que el respaldo vaya cifrado (RNF-04)?
- ¿Se mantiene el límite de 15 MB por archivo (§19) o se adopta el de 50 MB del DOC-08? Un acta escaneada de muchas páginas puede rebasar 15 MB.
- ¿Confirma PluriOne el plazo de conservación de §12.6 o aplica uno mayor por contrato o por regulación sectorial?

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

### 21.3 P3 — Cadena de custodia sellada y ficha de trazabilidad

Hoy la bitácora es inmutable **porque la base lo impide** (triggers de RF-27): quien administre PostgreSQL puede desactivar los triggers y reescribir un evento sin dejar rastro. P3 hace que cualquier alteración se pueda **comprobar**, y entrega a un auditor externo la historia de un documento en una ficha. Respaldo: DOC-03 (ISO 30301 «captura, integridad, metadatos y trazabilidad»; NOM-151-SCFI-2016 «conservación íntegra y constancia de existencia temporal… para sustento en auditorías externas») y el protocolo de auditoría del DOC-05 («estos registros son inmutables… la empresa pueda demostrar de forma transparente el fundamento de cada validación»).

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-04 | **Sellado encadenado de la bitácora.** Cada evento nuevo recibe `secuencia`, `hash_anterior` y `hash_evento` = SHA-256 del JSON canónico (secuencia, evento, expediente, documento, dictamen, usuario, IP, detalle, fecha y hash anterior). `pg_advisory_xact_lock` serializa los sellos hasta el COMMIT y un índice único en `secuencia` impide una bifurcación aunque el candado fallara. La fecha la da el reloj de la base, para que la guardada sea la sellada. El historial previo (sin sello) queda cubierto por un evento **SELLO_GENESIS** con su número de eventos y la huella de todos ellos, en orden. | RF-27; DOC-05 (protocolo); ISO 30301; NOM-151 | Implementado |
| PLUS-05 | **Verificación de la cadena.** `GET /api/v1/bitacora/verificar-cadena` recorre los eventos sellados, recalcula cada hash y su enlace, comprueba la huella del génesis y detecta eventos sin sellar posteriores al génesis (insertados por fuera del motor). Responde íntegra o comprometida, con los eventos sellados, los previos, el último hash y los hallazgos. | RF-27; HU-07; HU-30 | Implementado |
| PLUS-06 | **Ficha de custodia de un documento.** `GET /api/v1/reportes/documentos/{id}/custodia?formato=pdf\|xlsx`: huella SHA-256 de la carga y su recálculo a la fecha (RIE-03), versiones del mismo tipo en el expediente (RF-04), dictámenes con la huella evaluada, ratificaciones (quién, cuándo, justificación), eventos del documento con su sello y el resultado de la verificación de la cadena. La exportación queda en la bitácora (EXPORTACION_REPORTE, FICHA_CUSTODIA). | RF-23, RF-24; ISO 30301; NOM-151 | Implementado |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-39 | Como administrador, quiero que cada evento de la bitácora quede sellado con el anterior, para que una alteración directa en la base sea detectable. | M7 | Alta | Implementado |
| HU-40 | Como auditor, quiero verificar en cualquier momento que la cadena de la bitácora está íntegra y ver el indicador en el historial del expediente. | M7 | Alta | Implementado |
| HU-41 | Como auditor externo, quiero descargar la ficha de custodia de un documento en PDF o Excel, con su huella, versiones, dictámenes, ratificaciones y sellos. | M6 | Alta | Implementado |

**Criterios de aceptación**

- Todo evento nuevo queda sellado y enlazado con el anterior; el primero crea el génesis, que resume el historial previo.
- Dos transacciones concurrentes nunca producen dos eventos con la misma secuencia.
- La verificación de una cadena sin tocar es íntegra; si un evento se altera con los triggers desactivados, o se borra uno, o se inserta uno sin sello después del génesis, la verificación lo señala con su secuencia.
- La ficha, en PDF y en Excel, lista la huella de la carga y su recálculo, las versiones, los dictámenes con su huella, las ratificaciones y los eventos con su sello, e incluye el resultado de la verificación y la leyenda sobre NOM-151.
- El historial del expediente muestra un indicador sobrio de la integridad de la cadena y el detalle del documento, un botón para descargar la ficha.

**Consecuencias previstas**

- **Rendimiento:** los eventos de la bitácora se sellan uno a la vez; una transacción que registra un evento retiene el candado hasta su COMMIT (en la carga, eso incluye la consulta al rules-service para reevaluar el semáforo). Con el volumen de la residencia es imperceptible; si RNF-03 (50 peticiones simultáneas) lo exige, el siguiente paso sería registrar el evento al final de la transacción.
- **Datos existentes:** los eventos previos no se modifican (los triggers lo impiden): los cubre la huella del génesis. Las columnas nuevas quedan vacías en ellos.
- **Dialecto:** el candado es de PostgreSQL; en otro motor el índice único de la secuencia sigue impidiendo bifurcaciones, pero una carga concurrente puede fallar y reintentarse.
- **Alcance normativo:** la ficha está **alineada** con NOM-151-SCFI-2016 e ISO 30301; **no sustituye** la constancia de conservación que emite un Prestador de Servicios de Certificación acreditado, y así lo declara.

**Modelo de datos:** columnas `secuencia` (única), `hash_anterior` y `hash_evento` en `bitacora_auditoria`; evento nuevo `SELLO_GENESIS`.

**Implementación y pruebas** (versión 1.5):

| Pieza | Dónde | Pruebas |
|---|---|---|
| Sellado encadenado, génesis y candado | `core-service/motor/bitacora.py`, `models/bitacora.py`, `config/database.py` | `tests/test_cadena_custodia.py` (la prueba de concurrencia falla sin el candado: UniqueViolation) |
| `GET /bitacora/verificar-cadena` | `core-service/controllers/bitacora_controller.py` | Alteración con triggers desactivados, borrado, evento sin sello e historial previo alterado: detectados y restaurados |
| Ficha de custodia PDF y Excel | `core-service/motor/reportes.py`, `controllers/reporte_controller.py` | Cinco hojas, versión 1 de 2, ratificación, sellos, documento alterado y 404 |
| Botones de la ficha e indicador en el historial | `frontend/src/components/DetalleDocumentoModal.jsx`, `HistorialExpediente.jsx` | Verificación en vivo con Playwright |

Verificado en vivo el 29/09/2026 con los tres servicios (core sobre la base de pruebas): la ficha PDF se descarga desde el detalle del documento; para un documento cuyo binario ya no está en la bóveda la ficha lo reporta ALTERADO con la cadena íntegra (239 eventos sellados y 11 previos cubiertos por el génesis), y el historial muestra «Cadena de custodia íntegra · 240 eventos sellados».

**Diagramas:** [casos de uso](uml/p3-casos-de-uso-custodia.puml), [actividad del sellado y la verificación](uml/p3-actividad-sellado-verificacion.puml) y [actividad de la ficha de custodia](uml/p3-actividad-ficha-custodia.puml).

### 21.4 P4 — Chat documental eficiente

El chat es la herramienta con la que el auditor consulta un documento sin leerlo completo (RF-13 y HU-20: cita y confianza en cada resultado de la IA). Hoy cada turno envía al modelo las instrucciones, el estado del documento en el sistema, hasta 6,500 caracteres del documento y el historial. Medición base ([VALIDACION_CUANTITATIVA.md](VALIDACION_CUANTITATIVA.md) §10.1, documentos de 1 a 3 páginas): 1,581 tokens por turno (≈ 5 turnos por minuto con el límite de 8,000 del plan gratuito de Groq), latencia p50 de 0.7 s y p95 de 4.8 s, exactitud del 95 % y 39/39 citas verificadas; en documentos largos el contexto llega al tope y el costo por turno crece. Una auditoría consume de 1,700 a 4,400 tokens, así que auditar y conversar en el mismo minuto compiten por la cuota. Las cuatro preguntas que sugiere la interfaz («¿Qué le falta?», «¿Qué recomiendas corregir?», «¿Cuándo vence?», «Resume los datos clave») se responden con datos que la auditoría ya extrajo y ancló al texto. P4 responde sin modelo lo que ya está verificado, acota el contexto de lo demás y conserva el contrato de `POST /api/v1/ai/chat-documento` (solo se agregan campos opcionales). Respaldo: RF-13, HU-20 y DOC-05 (cita textual de la evidencia); RNF-02 e ISO/IEC 25010 (eficiencia de desempeño); límite de tokens del proveedor de inferencia (§12.2).

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-07 | **Respuestas desde los datos del dictamen (T0).** Al auditar, el ai-service guarda en su SQLite una ficha del documento por huella SHA-256 y versión del Nivel 3 (tipo, RFC, razón social, fechas, personas y verificaciones RSC con su cita anclada y página, sello digital SAT, sentido de la 32-D). Un enrutador de intención determinista responde las preguntas factuales y las sugeridas con una plantilla que lleva el dato en negritas y la cita del dictamen, sin llamar al modelo. Solo responde si la huella del dictamen coincide con la del documento vigente, **nunca afirma una ausencia** (si el dato falta, la pregunta pasa al modelo) y lo que cambia con el tiempo (estatus, vigencia, ratificación) se lee del core en cada turno. Los montos no se agregan a la extracción de la auditoría. Implementado en `pipelines/respuestas_directas.py` (tabla `fichas_documento`; `origen_respuesta` DATOS_DEL_DICTAMEN). Medido: 15 de 38 turnos sin modelo en documentos breves y 3 de 8 en el contrato de 20 páginas, −39 % de tokens por turno, p95 de 4.8 s a 2.0 s y exactitud de 95 % a 97 % ([VALIDACION_CUANTITATIVA.md](VALIDACION_CUANTITATIVA.md) §10.1). | RF-13, HU-20; DOC-05 (cita textual); RN-05 | Implementado |
| PLUS-08 | **Pasaje literal del documento (T1).** Una pregunta que nombra una cláusula o pregunta por un monto, con un fragmento BM25 claramente superior al siguiente, se responde con el pasaje literal y su página, rotulado como pasaje, sin interpretarlo. Implementado en `pipelines/pasajes.py` (`origen_respuesta` PASAJE_DEL_DOCUMENTO): en un monto solo compiten los renglones con una cantidad en pesos y, si varias empatan (tres sumas aseguradas), responde el modelo; en una cláusula el tramo debe superar en 30 % al siguiente; un seguimiento de un solo término va al modelo. En las 8 preguntas extensas, 1 respondida con su pasaje literal; en las 38 breves, 2 (contraprestación y capital social), todas correctas (VALIDACION_CUANTITATIVA §10.1, 01/10/2026). | RF-13, HU-20 | Implementado |
| PLUS-09 | **Contexto acotado (T2).** Presupuesto de contexto según el tipo de pregunta, reordenamiento léxico local de los fragmentos (se mantiene BM25 sin embeddings), estado del sistema completo solo en preguntas de cumplimiento, historial de 2 turnos en el servidor, instrucciones compactas y `max_tokens` propio del chat. Implementado (`fragmentos.seleccionar_enfocado`; `CHAT_PRESUPUESTO_PUNTUAL` 3,000, `CHAT_FRAGMENTOS_PUNTUALES` 3, historial de 4 mensajes con las respuestas previas recortadas, estado breve en preguntas puntuales, `CHAT_MAX_TOKENS` 600) salvo la compactación de las instrucciones, que cambia el comportamiento del modelo y se decidirá con medición. En el contrato de 20 páginas, las preguntas puntuales reciben su respuesta en 1,130 a 2,842 caracteres contra 6,442. Medido con Groq el 01/10/2026: −71 % de tokens por turno en el documento de 20 páginas (3,006 → 863) y −59 % en los breves (1,581 → 646), sin perder exactitud (VALIDACION_CUANTITATIVA §10.1). | RNF-02; ISO/IEC 25010 | Implementado (parcial: sin compactar instrucciones) |
| PLUS-10 | **Caché de respuestas (T3).** A temperatura 0.0, la respuesta de un primer turno se reutiliza ante la misma petición (la huella incluye el estado del sistema, así que una ratificación la invalida sola) y ante la misma pregunta normalizada. Implementado en `pipelines/cache_chat.py` (tabla `inferencias`, prefijo `chat:`); la respuesta indica `origen_respuesta` y la petición admite `forzar_modelo`. Medido: una pregunta repetida baja de ≈ 0.75–1.1 s a ≈ 25 ms sin tokens ([VALIDACION_CUANTITATIVA.md](VALIDACION_CUANTITATIVA.md) §10.1). | RNF-02 | Implementado |
| PLUS-11 | **Presupuesto de tokens y estado en memoria (T4).** El dictamen y los criterios se consultan en paralelo y se conservan en memoria por documento y dictamen; un presupuesto local de tokens por minuto, compartido con la auditoría, reduce el contexto o responde por PLUS-07/PLUS-08 en lugar de esperar los reintentos del SDK. Implementado en `pipelines/presupuesto_tokens.py` (`GROQ_TOKENS_POR_MINUTO`, 0 lo desactiva) y en el chat: criterios en memoria `CHAT_TTL_CRITERIOS_SEGUNDOS`; el dictamen se lee en vivo en cada turno, en paralelo con el texto, para que una ratificación se vea de inmediato. Medido tras una auditoría de 20 páginas: la espera del chat baja de 68.3 s a 38.5 s y sus tokens un 39 %, sin perder aciertos; no se elimina porque la auditoría consume casi toda la cuota del minuto ([VALIDACION_CUANTITATIVA.md](VALIDACION_CUANTITATIVA.md) §10.1). | RNF-02 | Implementado |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-42 | Como analista, quiero que las preguntas sobre datos ya verificados del documento (titular, fechas, qué le falta, firmantes) se respondan al instante y con la misma cita que el dictamen. | M3 | Alta | Implementado (PLUS-07) |
| HU-43 | Como analista, quiero seguir consultando el documento aunque se haya auditado otro en el mismo minuto, sin esperas por el límite del proveedor de IA. | M3 | Media | Parcial: PLUS-07 y PLUS-10 no consumen cuota; PLUS-11 reduce la espera de las demás un 44 % pero no la elimina |

**Criterios de aceptación**

- En la batería de pruebas del chat ([VALIDACION_CUANTITATIVA.md](VALIDACION_CUANTITATIVA.md) §6), cada paso reduce los tokens por turno sin bajar la exactitud factual ni la proporción de citas verificadas respecto de la medición base.
- Una respuesta sin modelo nunca afirma que un dato no aparece en el documento.
- Las citas de las respuestas sin modelo se marcan como verificadas con la misma regla (`cita_literal`) y abren el visor en su página.
- El contrato de `POST /api/v1/ai/chat-documento` no cambia (solo se agregan `origen_respuesta` y el uso de tokens en cero) y las pruebas existentes del ai-service siguen pasando.

**Consecuencias previstas**

- **Coherencia con el dictamen:** las respuestas sin modelo repiten lo que el dictamen extrajo; si el dictamen se equivocó, el chat no lo contradice. Por eso cada respuesta nombra su fuente y la petición admite un campo opcional para preguntar directamente al modelo.
- **Datos existentes:** los documentos auditados antes de P4 no tienen ficha; su chat sigue por el modelo hasta que se vuelvan a auditar. Los dictámenes guardados no se tocan.
- **Evaluación:** la exactitud del chat se mide contra la verdad fundamental del Gold Standard, así que P4 queda cubierto por la misma validación cuantitativa.

**Diagramas:** [actividad del turno del chat](uml/p4-actividad-chat-documental.puml).

---

### 21.5 P5 — Integridad permanente y dictamen reproducible

Cuatro brechas del análisis de brechas (sección 5) aprobadas por el residente el 30/09/2026. Dos son extensiones PLUS; las otras dos cumplen lo que el DOC-05 ya exige (el protocolo de auditoría y las excepciones de su Tabla 1) y completan HU-33.

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-14 | **Barrido programado de integridad.** En cada reevaluación programada (sin IA), el core recalcula el SHA-256 de todos los documentos íntegros de la bóveda. Una discrepancia o un binario ausente se registra igual que en una lectura (RIE-03): documento ALTERADO, dictamen No conforme de origen RIE-03 y evento ALERTA_INTEGRIDAD, con la nota «detectado en el barrido programado». Cada barrido deja la constancia VERIFICACION_INTEGRIDAD en la bitácora sellada (documentos revisados, alterados y duración). Se desactiva con `BARRIDO_INTEGRIDAD=false`. | RIE-03 (hoy solo al leer); ISO 30301 (integridad durante toda la conservación) | Implementado (`motor/integridad.barrer`; pruebas `test_integridad_permanente`) |
| PLUS-15 | **Último sello de la cadena en cada reporte.** El PDF y el Excel del expediente, el global y la ficha de custodia imprimen el último eslabón de la bitácora antes de la exportación (secuencia, sello SHA-256, fecha) y el resultado de verificar la cadena. Cada copia en manos de un auditor funciona como ancla externa. | NOM-151-SCFI-2016 (trazabilidad); P3 | Implementado (`reportes._ancla`; la ficha de custodia ya lo imprimía) |
| — | **Dictamen reproducible.** Cada dictamen del Nivel 4 guarda la versión de la lectura del Nivel 3 (`version_lectura()`: pipeline, Tesseract, idioma, DPI y lectura de sellos) y la huella de las instrucciones al modelo (SHA-256 abreviado de las instrucciones del sistema y de verificación). Ambas son campos opcionales nuevos del contrato de `POST /api/v1/dictamenes`, quedan protegidas por el trigger de RN-05 y se muestran en el registro técnico. | Protocolo de auditoría del DOC-05 («demostrar de forma transparente el fundamento de cada validación»); análisis de brechas 2.3 | Implementado (`pipelines/version_instrucciones.py`; también en la hoja «Evidencia» del Excel) |
| — | **Excepciones del DOC-05 (Tabla 1).** *Documento ilegible:* si la lectura completa no tiene texto, o tiene menos de `LEGIBILIDAD_MIN_CARACTERES` (50) por página con una confianza de OCR menor a `LEGIBILIDAD_MIN_CONFIANZA` (0.40), el ai-service no llama al modelo y emite un dictamen En revisión de origen NIVEL_3, «Documento ilegible, se requiere recarga», con su alerta. *Procesamiento diferido:* si Groq no responde tras sus 3 intentos, la auditoría entra en una cola del ai-service y se reintenta sola con espera creciente (de 15 min a 24 h, hasta `DIFERIDOS_MAX_INTENTOS`), una a la vez y dentro del presupuesto de tokens; el core marca el documento y muestra la alerta «Procesamiento diferido» en lugar de «Sin auditar», y la quita al guardarse el dictamen. | DOC-05, Tabla 1; HU-33; riesgo del DOC-07 («documentos escaneados de baja calidad») | Implementado (`pipelines/legibilidad.py`, `pipelines/diferidos.py`; alertas DOCUMENTO_ILEGIBLE y PROCESAMIENTO_DIFERIDO en el core) |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-44 | Como responsable de cumplimiento, quiero que el sistema detecte la alteración de un archivo aunque nadie lo haya abierto, y que deje constancia de cada verificación. | M7 | Alta | Implementado (PLUS-14) |
| HU-45 | Como auditor externo, quiero que cada reporte traiga el último sello de la cadena de custodia, para comprobar después que la historia no se reescribió. | M6 | Alta | Implementado (PLUS-15) |
| HU-46 | Como auditor externo, quiero saber con qué versión de la lectura y de las instrucciones se emitió cada dictamen, para explicar por qué dos dictámenes del mismo archivo difieren. | M3 | Media | Implementado |
| HU-47 | Como analista, quiero distinguir un documento ilegible de uno con contenido dudoso, para pedir la recarga en lugar de revisarlo. | M3 | Alta | Implementado |
| HU-48 | Como analista, quiero que una auditoría que falló porque la IA no respondió se reintente sola y que el expediente me lo indique. | Integración | Alta | Implementado |

**Criterios de aceptación**

- Un binario alterado o eliminado sin que nadie lo lea se detecta en el siguiente barrido, con el mismo dictamen, alerta y evento que una lectura (prueba que lo altera en la bóveda de pruebas).
- El barrido no llama a la IA ni consume tokens, y registra exactamente un evento VERIFICACION_INTEGRIDAD por ejecución.
- El último sello impreso en un reporte coincide con el último `hash_evento` sellado antes de la exportación.
- Un dictamen nuevo trae `version_lectura` y `version_instrucciones`; la ratificación no puede modificarlos (trigger RN-05); los dictámenes previos quedan con esos campos vacíos.
- Un documento sin texto suficiente no llama al modelo y queda «Documento ilegible, se requiere recarga», con su alerta y sin poder ratificarse como Conforme.
- Con Groq simulado como no disponible, la auditoría queda diferida, el expediente muestra la alerta y, al volver Groq, el ciclo guarda el dictamen y retira la alerta.
- Los contratos existentes solo ganan campos opcionales; las pruebas del core, rules y ai-service siguen pasando.

**Consecuencias previstas**

- **Datos existentes:** los dictámenes anteriores no tienen versión de lectura ni de instrucciones y así se muestran («no registrada»); no se reescriben (RN-04).
- **Primer barrido:** al activarse, el barrido revisa toda la bóveda una vez; un archivo alterado o perdido antes de P5 aparecerá como alterado ese día.
- **Cuota del proveedor:** los reintentos diferidos van de uno en uno y respetan el presupuesto de tokens (PLUS-11); con la cuota diaria agotada esperan al día siguiente.
- **Umbrales de legibilidad:** los valores iniciales son conservadores (solo lo claramente ilegible) y se calibran con el Gold Standard escaneado.

**Diagramas:** [casos de uso](uml/p5-casos-de-uso-integridad-reproducibilidad.puml), [barrido y ancla](uml/p5-actividad-barrido-integridad.puml) y [excepciones y reproducibilidad](uml/p5-actividad-excepciones-auditoria.puml).

---

### 21.6 P6 — Autenticidad del archivo, trazabilidad del catálogo y operación

Nueve puntos del análisis más profundo del 30/09/2026, aprobados por el residente e implementados el mismo día. Hasta P5 el motor verifica **qué dice** un documento; P6 agrega señales sobre **si el archivo es auténtico**, con qué catálogo se dictaminó y qué tanto se está quedando atrás la revisión. Ninguna señal rechaza un documento por sí sola: lo lleva a revisión humana con el motivo explicado, igual que una confianza baja (Nivel 5).

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| — | **RFC validado en el servidor (M1).** Al registrar un titular, el core rechaza (422) un RFC con formato incorrecto, con una longitud que no corresponde al tipo de persona (12 moral, 13 física) o con una fecha AAMMDD imposible. Calcula además el dígito verificador con el algoritmo público del SAT y responde `rfc_verificacion`: `VERIFICADO`, `GENERICO` (XAXX010101000 y XEXX010101000) o `DIGITO_NO_COINCIDE`. Por decisión del residente, mientras se trabaja con RFC de prueba un dígito que no coincide se **acepta con advertencia**; `RFC_DIGITO_ESTRICTO=true` lo rechaza. Un RFC real (por ejemplo, BIM011108DJ5) se verifica completo. | DOC-02 (titular identificado por su RFC); exactitud (ISO/IEC 25010) | Implementado (`motor/rfc.py`; pruebas `test_rfc_titular`) |
| PLUS-16 | **Señales de edición del PDF (M2).** En la carga, el core lee los metadatos del PDF: programa que lo generó, fecha de creación y de modificación, guardados incrementales (sin contar los de una firma ni la linealización). En la constancia de situación fiscal y la opinión 32-D, que el SAT emite electrónicamente, una modificación posterior a la emisión, un guardado incremental o un editor de PDF conocido son señal de retoque: la auditoría queda En revisión con el motivo y se emite la alerta «Posible edición del archivo». En los demás tipos (escaneos, actas) las señales solo se informan, porque procesar un escaneo es lo normal. | NOM-151 (integridad desde el origen); falsificación más común en la revisión de proveedores | Retirado el 02/10/2026 (§21.8) |
| PLUS-17 | **Código QR de verificación del SAT (M3).** Al auditar una constancia fiscal o una opinión 32-D, el ai-service busca el QR en la primera y la última página (detector de OpenCV, ya instalado). Si lo encuentra, guarda el enlace, comprueba que lleve a un dominio `sat.gob.mx` y coteja el RFC del enlace con el del documento y el del titular. Un QR ajeno al SAT o con otro RFC deja la auditoría En revisión; el analista recibe el enlace oficial para validarlo en el portal. **El motor no consulta al SAT**: no hay llamada automática a un servicio externo. Un QR ausente o ilegible solo se informa (un escaneo puede perderlo). | DOC-02 (32-D y constancia fiscal) | Retirado el 02/10/2026 (§21.8) |
| PLUS-18 | **Contenido activo en el PDF (M4).** En la carga, el core busca JavaScript, acciones de apertura o ejecución (`/OpenAction`, `/Launch`, `/AA`), archivos incrustados, medios enriquecidos y formularios XFA. El archivo se custodia igual (es la evidencia de lo que se entregó), la respuesta de la carga advierte, la auditoría queda En revisión y la alerta «Contenido activo en el PDF» (alta) recomienda pedir una versión sin contenido activo. El visor del motor no ejecuta nada: muestra páginas rasterizadas. | ISO/IEC 27001, A.8.7 (protección contra malware) | Implementado (`motor/senales_pdf.py`; tope de revisión en el ai-service) |
| — | **El mismo archivo en expedientes de titulares distintos (M5).** Si la huella de un documento vigente aparece en el expediente de **otro titular**, la evaluación emite la alerta «Archivo presente en el expediente de otro titular» con el folio: media-alta en documentos de un solo titular (constancia, opinión, acta, poder, comprobante) y media en contratos, NDA, anexos y convenios, que dos titulares pueden compartir legítimamente (solo las cuatro severidades del DOC-05, §19). La carga se sigue admitiendo; dentro del mismo expediente PLUS-01 la sigue rechazando. | Titularidad (RN-03 y el cruce del Nivel 4); DOC-05 | Implementado (`cumplimiento._huellas_en_otros_titulares`; pruebas `test_senales_archivo`) |
| — | **Versión del catálogo de reglas (M6).** El rules-service publica `GET /api/v1/reglas/version`: huella SHA-256 abreviada (`cat-…`) del catálogo completo (código, estado, severidad, parámetros y alcance de cada regla). Cada dictamen nuevo guarda `version_catalogo` (protegida por el trigger de RN-05, como las versiones de P5); la evaluación del expediente la informa, tomada de la cabecera `X-Version-Catalogo` del inventario que ya consulta (sin otra petición), y los reportes la imprimen. Así se sabe con qué catálogo se dictaminó cada documento aunque después se pause o cambie una regla. | Protocolo de auditoría del DOC-05; complemento del dictamen reproducible (P5) | Implementado (`motor/version_catalogo.py` del rules-service; pruebas `test_version_catalogo`, `test_rules_version_catalogo`) |
| PLUS-19 | **Cuota diaria del proveedor de IA visible (S3).** El ai-service suma los tokens que consume por día (UTC) en su SQLite y detecta la respuesta 429 por cuota diaria, con su tiempo de espera. `GET /api/v1/health` informa `cuota_diaria` (límite `GROQ_TOKENS_POR_DIA`, 200,000; usados; restantes; agotada y hasta cuándo) y el detalle de salud de la cabecera la muestra. Con la cuota agotada, el ciclo de procesamiento diferido (P5) espera en lugar de gastar intentos. Es una **estimación**: solo cuenta lo que consume esta instancia. | RNF-02; límite real medido el 30/09/2026 (PRD §17); procesamiento diferido (P5) | Implementado (`pipelines/cuota_diaria.py`; pruebas ai `test_cuota_diaria`) |
| PLUS-20 | **Antigüedad de lo pendiente (U1).** Cada documento En revisión sin ratificar informa `dias_en_espera` desde su dictamen. La alerta «Pendiente de ratificación» lo dice («lleva 12 días esperando»), la bandeja de alertas ordena por antigüedad dentro de la severidad y el tablero de Reportes muestra cuántos dictámenes esperan, el más antiguo y el promedio. | ISO 30301 (seguimiento de la gestión documental); indicador de operación del área de cumplimiento | Implementado (`cumplimiento._dias_en_espera`; pruebas `test_antiguedad_pendientes`) |
| — | **Pruebas exhaustivas de fechas límite (Q-a).** Umbrales de 30, 15 y 5 días exactos, el día del vencimiento y el siguiente, caducidad desde la emisión que cruza un 29 de febrero, emisión el 29 de febrero, cambio de año y la fecha del servidor frente a UTC. Un error encontrado se corrige con su prueba. | RN-02 (vigencia recalculada); DOC-05 (RCV) | Implementado (`test_fechas_limite`, `test_rules_fechas_limite`). Error encontrado y corregido: «hoy» salía de la zona del servidor y un contenedor corre en UTC, así que desde las 18:00 de México un documento vencía un día antes; ahora se cuenta en `ZONA_HORARIA` (America/Mexico_City) |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-49 | Como analista, quiero que el sistema rechace un RFC mal formado y me avise si su dígito verificador no coincide, para no registrar un titular equivocado. | M1 | Alta | Implementado |
| HU-50 | Como analista, quiero saber si una constancia o una opinión del SAT fue modificada después de emitida, para no aceptar un documento retocado. | M2 | Alta | Retirada (§21.8) |
| HU-51 | Como analista, quiero el enlace oficial del código QR de un documento del SAT y saber si su RFC coincide, para validarlo en el portal. | M3 | Media | Retirada (§21.8) |
| HU-52 | Como responsable de seguridad, quiero que un PDF con contenido activo quede señalado, para no abrirlo en un lector que lo ejecute. | M2 | Alta | Implementado |
| HU-53 | Como analista, quiero saber si un archivo ya está en el expediente de otro titular, para detectar una carga equivocada o un documento ajeno. | M2 | Media | Implementado |
| HU-54 | Como auditor externo, quiero saber con qué versión del catálogo de reglas se emitió cada dictamen. | M3 | Media | Implementado |
| HU-55 | Como administrador, quiero ver cuánta cuota diaria del proveedor de IA queda, para planear las auditorías. | Integración | Media | Implementado |
| HU-56 | Como responsable de cumplimiento, quiero ver cuántos días lleva cada dictamen esperando ratificación, para atender primero lo más atrasado. | M5 | Alta | Implementado |

**Criterios de aceptación**

- Un RFC con fecha imposible o con longitud distinta a la de su tipo de persona responde 422 con el motivo en lenguaje llano. Un RFC real conocido queda `VERIFICADO`, los genéricos del SAT `GENERICO` y uno inventado se acepta con `DIGITO_NO_COINCIDE`; con `RFC_DIGITO_ESTRICTO=true` este último responde 422.
- Una constancia fiscal guardada de nuevo con un editor (guardado incremental o fecha de modificación posterior) queda En revisión con el motivo y la alerta; la misma constancia sin tocar no genera señal. Un acta escaneada con las mismas señales solo las informa.
- Un QR con dominio ajeno al SAT o con otro RFC deja la auditoría En revisión; sin QR, el estatus no cambia. Ninguna prueba ni flujo llama al SAT.
- Un PDF con JavaScript se custodia, la carga advierte, la auditoría queda En revisión y aparece la alerta alta; un PDF sin contenido activo no cambia.
- El mismo archivo en el expediente de otro titular genera la alerta con el folio; en el mismo expediente sigue el 409 de PLUS-01.
- Cada dictamen nuevo trae `version_catalogo`; la ratificación no la modifica; pausar una regla cambia la versión publicada.
- El detalle de salud muestra la cuota diaria; con la cuota agotada (simulada), el ciclo diferido no gasta intentos.
- Un dictamen pendiente informa sus días en espera y la bandeja lo ordena por antigüedad.
- Las pruebas de fechas límite cubren los casos listados. Los contratos existentes solo ganan campos opcionales; las suites del core, rules y ai-service siguen pasando.

**Consecuencias previstas**

- **Titulares existentes:** no se revalidan ni se bloquean; el RFC de prueba del titular actual (BIM980101XYZ) aparece con su advertencia. Cambiarlo por el real es decisión del residente.
- **Documentos ya custodiados:** su contenido activo (PLUS-18) se calcula en el siguiente barrido programado (PLUS-14), que ya lee cada binario; no cambian sus dictámenes vigentes, solo agregan la alerta. La próxima auditoría aplica la revisión.
- **Dictámenes previos:** quedan sin `version_catalogo` («no registrada»), como los de P5 sin versiones.
- **Falsos positivos:** las señales de edición (PLUS-16) dejaban en revisión los documentos de prueba hechos con un procesador de texto; por eso se retiraron el 02/10/2026 (§21.8).
- **Privacidad:** el QR se lee del archivo ya custodiado; el enlace solo se muestra al analista y nada sale del motor.

**Diagramas:** [casos de uso](uml/p6-casos-de-uso-autenticidad.puml), [señales del archivo en la carga y la auditoría](uml/p6-actividad-senales-archivo.puml) y [catálogo, cuota y antigüedad](uml/p6-actividad-trazabilidad-operacion.puml).

---

### 21.7 P7 — Operación trazable, fecha cierta y aseguramiento de la calidad

Cinco puntos que quedaban después de P6, decididos por el residente el 30/09/2026 con un criterio para todos: **el sistema lo levantarán agentes de PluriOne con documentos y datos ficticios, además de reales, así que cada función debe servir con ambos.** Lo que depende de un servicio externo es opcional y su falla nunca detiene el motor.

| ID | Requerimiento | Fundamento | Estado |
|---|---|---|---|
| PLUS-21 | **Identificador de petición entre servicios (S2).** Cada petición lleva la cabecera `X-Request-ID` (`id_peticion`): el frontend genera una por llamada; cada servicio acepta la recibida (hasta 64 caracteres alfanuméricos y guiones) o crea una, la devuelve en la respuesta y la propaga al llamar a los otros dos. Cada servicio escribe un registro estructurado por petición (servicio, `id_peticion`, método, ruta, estado y duración). Los eventos de la bitácora registrados durante una petición llevan su `id_peticion`, y un error no controlado la devuelve; el aviso de error de la interfaz la muestra como «Folio de seguimiento». Así una auditoría puede seguirse de punta a punta: interfaz, ai-service, core, rules y bitácora. | ISO/IEC 27001, A.8.15 (registro de eventos); RNF-05 (trazabilidad); operación | Implementado (`config/observabilidad.py` en cada servicio; pruebas `test_folio_seguimiento` en core y ai) |
| PLUS-22 | **Sello de tiempo de un tercero sobre la bitácora (S1).** Si `SELLO_TIEMPO_URL` apunta a una autoridad de sellado RFC 3161, el core pide una vez al día (en la reevaluación programada) y a demanda un sello sobre el `hash_evento` del último eslabón de la cadena: **solo viaja esa huella**, ningún dato. El sello (token DER, autoridad, fecha cierta y número de serie) se guarda en la tabla `sellos_tiempo`, de solo inserción, y deja el evento SELLO_TIEMPO en la bitácora; la ficha de custodia y los reportes imprimen el último. Prueba que la bitácora existía en esa fecha aunque alguien con acceso a la base intente reescribirla, y cualquiera puede verificarlo con `openssl ts -verify`. **Apagado por omisión** (`SELLO_TIEMPO_URL` vacío): un entorno de pruebas o una red que bloquee el servicio no se ven afectados, y una falla solo se registra y se reintenta en el siguiente ciclo. No sustituye la constancia de conservación de un Prestador de Servicios de Certificación acreditado (NOM-151) y así se declara. Si el último eslabón ya es un SELLO_TIEMPO no se pide otro, y la verificación de la cadena reporta un hallazgo si la huella que cubrió un sello ya no está en la cadena (la bitácora se reescribió después de esa fecha). Endpoints: `POST /bitacora/sello-tiempo` (a demanda; 409 si está apagado, 502 si la autoridad falla), `GET /bitacora/sellos-tiempo` y `GET /bitacora/sellos-tiempo/{id}/token`. | NOM-151-SCFI-2016 (fecha cierta); P3 y PLUS-15 (cadena sellada y ancla externa) | Retirado el 02/10/2026 (§21.8) |
| — | **Aviso de nueva auditoría al cambiar el catálogo (M7).** El rules-service publica, además de la versión del catálogo (M6), la de las reglas que aplican a cada tipo de documento (las de ese tipo y las generales de vigencia y contenido). Cada dictamen nuevo guarda la de su tipo (`version_reglas_tipo`, protegida por el trigger de RN-05). Si después cambian esas reglas (se agrega, pausa o edita una), la evaluación emite la alerta «Requiere nueva auditoría» (media): el dictamen no verificó las reglas vigentes. El aviso dice que se agregó, pausó o editó una regla de ese tipo; cuál cambió se consulta en el catálogo, porque el core solo conoce las versiones. Un cambio en las reglas de otro tipo no la emite, y los dictámenes previos a P7 (sin versión) tampoco. La alerta desaparece al auditar de nuevo. | Protocolo de auditoría del DOC-05 (dictamen con las reglas vigentes); M6 | Implementado (`version_catalogo.por_tipo`; pruebas `test_version_catalogo`, `test_rules_version_catalogo`) |
| — | **Pruebas de extremo a extremo en CI (Q-b).** `scripts/e2e_api.py` recorre por HTTP real el flujo completo: alta de un titular con RFC real y otro con RFC ficticio, expediente, carga de PDF (y su repetición, 409), dictamen del Nivel 4 simulado (sin Groq, con la vigencia calculada por el rules-service), ratificación (y su segundo intento, 409), alertas, índice, reportes PDF y Excel, ficha de custodia, verificación de la cadena y el seguimiento de la carga por su `id_peticion` en la bitácora y en el registro de los dos servicios. Corre en un trabajo propio del CI y localmente con el mismo comando. **Ajuste respecto del plan:** el script levanta su propio core y rules-service (puertos 8101 y 8102) sobre la base `plurione_compliance_e2e`, recreada en cada corrida, y una bóveda temporal, en lugar de usar los servicios en marcha: la bitácora y los dictámenes son inmutables, así que cada corrida dejaría para siempre titulares de prueba en `plurione_compliance`. `--core-url` y `--rules-url` permiten correrlo contra un entorno de aceptación. | ISO/IEC 25010 (adecuación funcional); Ficha 045, actividad 6 | Implementado (trabajo `e2e` del CI; local: código 0 en 4 s; con `RFC_DIGITO_ESTRICTO=true` falla, como debe, en el RFC ficticio) |
| — | **Prueba de seguridad del API (Q-c).** OWASP ZAP en modo de análisis de API sobre el OpenAPI del core, del rules-service y del ai-service, en un trabajo del CI y una corrida local registrada en `docs/resultados_validacion/`. Los hallazgos altos hacen fallar el trabajo; los que se encuentren se corrigen (por ejemplo, cabeceras de seguridad en las respuestas) o se justifican por escrito. El Módulo 7 (autenticación) sigue congelado, así que ZAP lo informará y quedará justificado. **Como se implementó:** `scripts/zap_api.py` levanta los tres servicios sobre `plurione_compliance_zap`, sin clave de Groq (el escaneo activo enviaría miles de peticiones de ataque a la base real y a la bitácora inmutable). ZAP no marcó la falta de autenticación (el escaneo de API no tiene un contexto de sesión), así que se declara por escrito junto con el CORS abierto. | Ficha 045, actividad 6 (pruebas de seguridad); ISO/IEC 27001 | Implementado ([informe](resultados_validacion/seguridad_zap.md); trabajo `zap` del CI). Línea base: 0 altos, 0 medios, 8 bajos. Corregidos: dos errores 500 (carácter nulo hacia PostgreSQL en el core; desbordamiento de la espera de reintentos en el ai-service) y las cabeceras `X-Content-Type-Options`, `Cross-Origin-Resource-Policy` y `Cache-Control`. Pasada final: 0 altos, 0 medios y 1 bajo justificado (503 previsto sin proveedor de IA) |

**Historias de usuario nuevas**

| ID | Historia | Módulo | Prioridad | Estado |
|---|---|---|---|---|
| HU-57 | Como administrador, quiero seguir una petición que falló por los tres servicios con un solo folio, para diagnosticarla sin adivinar. | Integración | Alta | Implementado |
| HU-58 | Como auditor externo, quiero un sello de tiempo de un tercero sobre la bitácora, para comprobar que existía en esa fecha. | M6 | Media | Retirada (§21.8) |
| HU-59 | Como analista, quiero saber qué documentos deben auditarse de nuevo porque cambiaron sus reglas. | M3 | Alta | Implementado |
| HU-60 | Como responsable del proyecto, quiero que cada cambio pase por una prueba del flujo completo antes de integrarse. | QA | Alta | Implementado |
| HU-61 | Como responsable de seguridad, quiero un análisis automático de vulnerabilidades del API con sus hallazgos atendidos. | QA | Alta | Implementado |

**Criterios de aceptación**

- Una petición con `X-Request-ID` lo recibe de vuelta; sin ella, la respuesta trae uno nuevo. El ai-service lo propaga al core y al rules-service, el evento de bitácora de la acción lo lleva y el registro de cada servicio tiene una línea con él. Un error 500 lo devuelve y la interfaz lo muestra.
- Con `SELLO_TIEMPO_URL` vacío no se hace ninguna llamada externa. Con una autoridad simulada, el sello se guarda, cubre el último `hash_evento`, la tabla no admite cambios y el evento SELLO_TIEMPO queda en la bitácora; una autoridad caída no detiene la reevaluación.
- Agregar o pausar una regla de un tipo emite «Requiere nueva auditoría» en sus documentos auditados antes, no en los de otro tipo; auditar de nuevo la retira.
- `scripts/e2e_api.py` termina con código 0 localmente y en el CI, con un RFC real y uno ficticio, sin escribir en `plurione_compliance`.
- El análisis de ZAP no deja hallazgos altos sin corregir o justificar.
- Los contratos solo ganan campos y cabeceras opcionales; las suites siguen pasando.

**Consecuencias previstas**

- **Datos y entornos ficticios:** nada de P7 distingue entre datos reales y de prueba. El sello de tiempo (PLUS-22), la única integración externa, se retiró el 02/10/2026 (§21.8).
- **Bitácora:** los eventos nuevos llevan `id_peticion` en su detalle; los anteriores no se tocan (RN-04).
- **Dictámenes previos:** sin `version_reglas_tipo`, no generan el aviso de nueva auditoría; la siguiente auditoría lo establece.
- **Registro:** los servicios escriben una línea JSON por petición en su salida estándar, que el despliegue de PluriOne puede recolectar.

**Diagramas:** [casos de uso](uml/p7-casos-de-uso-operacion-calidad.puml), [seguimiento de una petición](uml/p7-actividad-folio-seguimiento.puml) (el sello de tiempo se retiró, §21.8) y [aviso de nueva auditoría](uml/p7-actividad-nueva-auditoria.puml).

---

### 21.8 Depuración del alcance (02/10/2026)

Antes de la entrega, el residente pidió revisar todo el motor contra la documentación: el sistema se entrega dockerizado y los agentes de PluriOne lo probarán con datos ficticios. Se retiraron cuatro extensiones que ningún DOC pide y que, en esas condiciones, nunca se ejecutaban o perjudicaban:

| Retirado | Motivo | Qué se conserva |
|---|---|---|
| PLUS-16, señales de edición del PDF (HU-50) | Una constancia o una opinión 32-D de prueba hecha en un procesador de texto, o guardada de nuevo, quedaba En revisión con la alerta «Posible edición del archivo». | El contenido activo (PLUS-18). Las señales ya guardadas en `documentos.senales_pdf` se ignoran. |
| PLUS-17, código QR del SAT (HU-51) | Los documentos de prueba no traen QR; la auditoría leía de nuevo el binario sin resultado. | La columna `dictamenes_auditoria.qr_sat`, sin uso (la protege el trigger de RN-05). |
| PLUS-22, sello de tiempo RFC 3161 (HU-58) | Apagado por omisión (`SELLO_TIEMPO_URL` vacía): nunca se ejecutaba. | La cadena sellada (PLUS-04/05) y el último sello en los reportes (PLUS-15). En una base existente, la tabla `sellos_tiempo` queda vacía e inerte. |
| Sellos en tinta de color (Nivel 3) | Apagados por omisión (`OCR_RELEER_SELLOS=false`); en el acta real medida la relectura no se activó en ninguna página. | El Sello Digital SAT (DOC-08), detectado en el texto. La versión de lectura conserva «sin-sellos», así que las extracciones guardadas y los dictámenes siguen válidos. |

En la misma revisión se corrigió lo que una instalación limpia en Docker hacía visible: la auditoría sin clave del proveedor de IA respondía un error interno (ahora 503 con la instrucción), los servicios no tenían `.dockerignore`, las dependencias no tenían versión fija y un aviso usaba nombres internos.

---

### 21.9 Auditoría técnica del código (03/10/2026)

El residente pidió una auditoría del repositorio (código sin uso, redundancias, dependencias ocultas y rendimiento de la IA y del OCR) y aprobó tres pasos. Ninguno agrega funciones ni cambia el contrato de la API.

| Paso | Qué se hizo | Respaldo |
|---|---|---|
| Limpieza | Se retiraron `TipoDocumentoEnum` (repetía `config/catalogo.TIPOS_DOCUMENTO`), `extraccion_pipeline.palabras_ocr`, tres reglas CSS y las exportaciones que solo usaba su propio archivo. Se corrigieron la descripción del preprocesamiento de `GET /api/v1/ai/configuracion-ocr` y el candado de cada lectura completa, que quedaba en memoria para siempre. | Mantenibilidad (ISO/IEC 25010) |
| Bóveda | El contenedor del ai-service ya no monta `storage_vault/`: lee cada binario por el core, que verifica su huella (RIE-03). | DOC-03: ISO/IEC 27001 (control de acceso), NOM-151 |
| OCR en flujo continuo | En la lectura completa (auditoría), cada página escaneada entra al pool de OCR en cuanto se rasteriza, con hasta 2 × `OCR_WORKERS` páginas en vuelo. Antes iba por tandas de `OCR_WORKERS` que esperaban a la página más lenta. El texto es idéntico (misma función por página), así que `VERSION_PIPELINE` sigue en 3.3 y lo persistido es válido; la lectura parcial del chat sigue por tandas. | RNF-02 |

Medición del Nivel 3 en frío, mismas condiciones del equipo y 5 corridas ([`rendimiento_ocr_continuo.json`](resultados_validacion/rendimiento_ocr_continuo.json)): contrato escaneado de 20 páginas, de 10.9 s a 8.8 s (−19 %); el mismo a color con sellos, de 14.2 s a 10.1 s (−29 %); acta real de 26 páginas, de 39.1 s a 37.7 s, dentro del ruido. El acta ya ocupa todos los hilos del equipo: lo que limita es el cómputo de Tesseract, no la espera entre tandas. Precisión del Gold Standard sin cambios (estatus 100 %, 0 falsas conformidades, 87/87 citas ancladas).

**Discrepancia de tipo documental (03/10/2026).** El Cap. I del DOC-01 asigna a la IA confirmar «que el documento sea del tipo que el usuario seleccionó». Cuando el tipo detectado no es compatible con el registrado (`TIPOS_COMPATIBLES`), el dictamen se contradecía: una INE registrada como Poder notarial salía No conforme por «la vigencia del documento ya expiró», calculada con las reglas del poder; el motivo podía hablar de la titularidad («el documento no incluye RFC…»), y se exigían al archivo los elementos RSC del poder y se extraían sus «apoderados» para el cotejo RN-03. Corrección, sin cambiar las instrucciones del modelo:

- La discrepancia decide el dictamen: En revisión (la clasificación es del modelo y la confirma un analista; nunca se rechaza por ella), con el único motivo «Discrepancia de documento: Se esperaba el documento «X» pero la inteligencia artificial identificó «Y». No es posible validar los criterios de cumplimiento del documento solicitado».
- Al archivo no se le aplican la vigencia RCV, los elementos RSC/RDS ni la representación del tipo esperado. El dictamen persistido no lleva sus fechas ni su representación, para que el core no recalcule con ellas la vigencia ni el cotejo del documento esperado.
- La respuesta de `POST /api/v1/ai/analisis-semantico` agrega campos opcionales: `tipo_esperado`, `tipo_esperado_nombre`, `tipo_detectado`, `tipo_detectado_nombre`, `discrepancia_tipo` y `descripcion_coherente` (el motivo del estatus vigente, que la interfaz muestra junto al veredicto). La ficha del documento del core agrega `nombre_tipo_documento`.
- En el mismo trabajo: cuando una señal del archivo (PLUS-18) pasaba un dictamen de Conforme a En revisión, su motivo de Conforme seguía apareciendo junto al veredicto; ahora se retira.

**Nombre del documento real (03/10/2026, a pedido del residente).** Con discrepancia, el dictamen nombra el documento que se cargó, no solo su categoría: «Distinto» decía poco ante una INE o un formato de evaluación.

- **Cuándo se consulta:** solo cuando hay discrepancia. Una consulta breve aparte (≈ 500 tokens, con el encabezado del documento) pide al modelo `nombre_documento_real`, un nombre canónico, formal y corto en español. La extracción no cambia, así que la caché de inferencias y las casetes del resto siguen válidas. La huella `version_instrucciones` incluye la consulta nueva.
- **Sin un nombre válido** (falla o respuesta de más de 120 caracteres), se usa el de la categoría detectada.
- **Dónde se usa el nombre:**
  - el motivo («…identificó «Credencial para Votar»…»);
  - la interfaz: «Distinto («…»)» en el resumen y en la columna «Detectado»;
  - el chat: el estado del sistema lo indica solo con discrepancia, y las respuestas sin modelo a «¿qué le falta?», «resume» y «¿qué tipo de documento es?» empiezan con «Este documento ha sido identificado por el motor de IA como…».
- **Core:** guarda el nombre en la columna nueva `dictamenes_auditoria.nombre_documento_real`, con migración idempotente y protegida por el trigger de RN-05, y lo sella en el evento DICTAMEN_IA.
- **Gold Standard:** solo GS-ACTA-04 hace la consulta («Poder General», 504 tokens grabados); los 42 casos siguen en 100 % de estatus.

Evidencia previa: con el modelo real, un contrato, un NDA y una constancia fiscal registrados como Poder notarial se clasificaron con su tipo real (3 de 3): el modelo no recibe el tipo esperado y no se sesga por él, así que no se modificaron sus instrucciones (la caché de inferencias y las casetes del Gold Standard siguen válidas). Pruebas: `test_discrepancia_tipo` (ai) y `test_tipos_documento_nuevos` (core). Respaldo: DOC-01 Cap. I; DOC-05, Nivel 5 (revisión humana); RNF-08.

**Elementos expresos y cargo del apoderado (04/10/2026, aprobado por el residente).** Dos pendientes de la validación cuantitativa (§10.2 de `VALIDACION_CUANTITATIVA.md`):

- **Verificación de contenido (RSC-01, RF-11, HU-19):** la regla 1 de las instrucciones de verificación exige que el elemento esté pactado o enunciado de forma expresa; una mención de paso, una definición o un antecedente no lo prueban, y si el modelo tendría que deducirlo lo marca como no presente. Antes, dos omisiones del Gold Standard se daban por cumplidas y solo las corregía la salvaguarda `declara_deduccion`; ahora el propio modelo las niega y la salvaguarda queda como segunda línea. Cambia `version_instrucciones` (los dictámenes nuevos lo registran, P5) y se regrabaron las verificaciones de los casetes; la extracción no cambió. Métricas: 0 falsas conformidades y 0 omisiones indebidas, estatus 42/42.
- **Cargo del apoderado (RSC-02, HU-23):** un acta que nombra a la apoderada solo por el poder que le confiere («Se otorga a … poder general…») dejaba su cargo vacío. Si el modelo no da cargo y la cita verificada de esa persona le confiere un poder, el cargo es «Apoderado». No cambia las instrucciones ni el cotejo RN-03, que usa nombre y rol. Cargo 45/45 en el Gold Standard (antes 40/45).

**Lectura anticipada y prioridad del OCR (04/10/2026, RNF-02, a pedido del residente).** El OCR de un acta real de 26 páginas densas cuesta ≈ 30 s en el equipo de desarrollo: Tesseract es el 95 % (≈ 3.9 s de CPU por página), el preprocesamiento suma 0.2 s por página, y ni bajar a 250 dpi, ni otros workers (4, 6, 10), ni desactivar el reintento de texto invertido lo reducen (VALIDACION_CUANTITATIVA §10.3). No se lee ninguna página menos; cambia cuándo se leen ([diagrama](uml/rnf02-actividad-lectura-anticipada.puml)):

- **Lectura anticipada.** Al custodiar un documento, el frontend pide `POST /api/v1/ai/documentos/{id}/anticipar` (202). El ai-service lee todas sus páginas en segundo plano, un documento a la vez, sin el modelo y sin tokens, y las guarda en su SQLite. La auditoría encuentra el texto listo y solo espera al Nivel 4.
- **Prioridad del OCR.** El pool atiende primero las páginas de la auditoría, el chat y el visor, y después las de la lectura anticipada. Si una auditoría pide un documento que se está leyendo de fondo, sus páginas pendientes pasan a primer plano y espera esa misma lectura, sin repetir el OCR.
- **Lectura completa directa.** La auditoría de un documento sin leer va directo al flujo continuo con todas las páginas, sin la lectura parcial previa (6 páginas en tandas y una barrera antes del resto, que dejaba hilos ociosos).
- El texto es idéntico: la misma función por página, así que `VERSION_PIPELINE` sigue en 3.3 y la persistencia, las casetes y los dictámenes siguen valiendo.

**Rubro que nombra lo preguntado en el chat (10/10/2026, a pedido del residente).** Al regenerar las capturas del DG, «¿Cuál es el capital social y cómo está representado?» sobre el acta real de 26 páginas respondió que el monto «no aparece». En el acta, las reglas para aumentar el capital repiten «capital social» en un tercio de las ventanas (41 de 129), así que BM25 dejaba el «ARTÍCULO SEXTO. - CAPITAL SOCIAL» en el lugar 8 y el reordenamiento de T2 no le daba el bono de encabezado, reservado a términos presentes en menos del 30 % de las ventanas. Además, el contexto reducido de T4 (el chat que sigue a una auditoría) usaba BM25 simple.

- Un encabezado cuyo rubro (lo que nombra la cláusula, sin el cuerpo que el OCR deja en el mismo renglón) contiene un par de palabras seguidas de la pregunta suma el bono aunque cada palabra sea común (`fragmentos._reordenar`, `_rubro`). Afecta solo al chat (T1 y T2): la auditoría selecciona con `seleccionar_por_criterios`, sin reordenamiento, así que el Gold Standard no cambia.
- T4 acota el contexto con la misma estrategia del turno: una pregunta puntual conserva el contexto enfocado.
- Resultado: la pregunta se responde con el pasaje literal del Artículo Sexto (p. 4, $55,000.00) sin el modelo, y con el modelo forzado también lo cita. Las baterías corta y extensa del chat se reproducen sin ninguna huella nueva (sus contextos no cambian). Prueba: `test_contexto_enfocado.py::test_el_capital_social_llega_a_su_rubro` (falla sin la corrección).

**Compresión de las respuestas (03/10/2026, a pedido del residente).** El core y el rules-service comprimen con GZip las respuestas JSON de más de 1 KB, como la lista de expedientes con su evaluación, que el panel consulta cada 15 s. Los originales de la bóveda y los reportes no se comprimen de nuevo: ya van comprimidos. No se agregó una caché de las métricas de Reportes, porque no existe ese endpoint: Reportes calcula todo con `GET /expedientes`, el mismo que usan Expedientes y Alertas. Cachearlo mostraría el semáforo anterior tras una carga, auditoría o ratificación, y retrasaría el recálculo de la vigencia (RN-02) y el registro de sus cambios en la bitácora. Respaldo: RNF-01; ISO/IEC 25010 (eficiencia).

| ID | Extensión | Respaldo | Estado |
|---|---|---|---|
| PLUS-23 | **Sello de integridad de cada reporte (03/10/2026, a pedido del residente).** Al exportar el dictamen del expediente, el reporte global o la ficha de custodia, en PDF o en Excel, el core calcula el SHA-256 de los datos del reporte en forma canónica (JSON con claves ordenadas: evaluación, dictámenes, eventos y la constancia de la cadena de PLUS-15) y lo imprime como «Sello de integridad forense (SHA-256)»: en el pie de cada página del PDF y en la hoja de resumen del Excel. Un archivo no puede llevar impresa la huella de sus propios bytes, porque imprimirla los cambia; por eso el evento EXPORTACION_REPORTE de la bitácora sellada guarda las dos huellas, la de los datos (`sello_contenido`) y la del archivo emitido (`hash_archivo`). Quien recibe el reporte calcula el SHA-256 del archivo y lo encuentra en la bitácora junto con el sello impreso: si no aparece, el archivo cambió después de emitirse. No es una firma electrónica con llave: no identifica a un firmante, prueba integridad frente a la bitácora del motor ([diagrama](uml/plus23-actividad-sello-reporte.puml)). | NOM-151 (huella del mensaje de datos); ISO/IEC 27001 A.8.15; RF-23, RF-24, RF-27; complementa PLUS-15 | Implementado (ccfb16e; `tests/test_sello_reporte.py`) |

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
