# MVP — Motor de Validación de Cumplimiento Documental

**Producto mínimo viable**

| Campo | Valor |
|---|---|
| Producto | Motor de Validación de Cumplimiento Documental mediante Inteligencia Artificial |
| Cliente | PluriOne S.A. de C.V. (Develop Talent & Technology) |
| Fuente | DOC-07, Plan de Proyecto y Product Backlog (septiembre de 2026, anterior al desarrollo) |
| Documentos relacionados | [PRD.md](PRD.md) — requerimientos completos; [ESTADO_DEL_DESARROLLO.md](ESTADO_DEL_DESARROLLO.md) — avance de la implementación |

> **Fuente.** El DOC-07 define el MVP al ordenar el backlog: «primero los cimientos del sistema (Sprint 1), luego el motor de reglas deterministas (Sprint 2), después la inteligencia artificial (Sprint 3) y finalmente los reportes y la integración completa (Sprint 4). Esta secuencia asegura que, en caso de retraso, el producto mínimo viable (**motor de reglas sin IA**) ya estaría operativo al finalizar el Sprint 2». Su matriz de riesgos lo repite: ante un retraso por complejidad de integración, «se priorizan los módulos con mayor valor funcional para asegurar un producto mínimo viable». Este documento desarrolla esa definición; no agrega requisitos.

---

## 1. Qué es el MVP

Un **motor de reglas determinista, sin inteligencia artificial**, que ya resuelve el problema central: decirle al responsable de cumplimiento, para cada expediente, qué documentos faltan, cuáles vencieron o están por vencer, qué anexos exige y si el expediente cumple, con un registro inmutable de todo lo que se hizo.

La IA (lectura de documentos escaneados, verificación de cláusulas y extracción de datos) y los reportes ejecutivos son incrementos sobre esa base: mejoran la profundidad del dictamen, pero el valor principal ya existe sin ellos.

## 2. Hipótesis que valida

| # | Hipótesis | Problema del PRD que ataca |
|---|---|---|
| H1 | Un catálogo de reglas configurable por tipo de expediente detecta los documentos y anexos faltantes que hoy se pasan por alto. | P1 (revisión manual sin lista común), P3 (anexos según la experiencia del revisor) |
| H2 | El cálculo automático de la vigencia, con alertas anticipadas, evita descubrir los vencimientos en la auditoría. | P2 (control de vigencia en hojas de cálculo) |
| H3 | Un semáforo por expediente con alertas y su recomendación le dice al analista qué hacer, sin revisar documento por documento. | P4 (cruce manual de listas de verificación) |
| H4 | La huella SHA-256 y una bitácora inmutable dejan la evidencia lista para una auditoría. | P5 (preparación reactiva de auditorías) |

## 3. Alcance del MVP

Las historias de los Sprints 1 y 2 del DOC-07 (HU-01 a HU-17), con los requerimientos que cubren:

| Sprint | Historia | Módulo | Prioridad | Requerimientos |
|---|---|---|---|---|
| 1 | HU-01 Clasificar el expediente en uno de los tres tipos del DOC-02. | M1 | Alta | RF-01 |
| 1 | HU-02 Crear un expediente con nombre, empresa y tipo. | M1 | Alta | RF-01 |
| 1 | HU-03 Cargar PDF e imágenes con cálculo automático de SHA-256. | M1 | Alta | RF-02, RF-03 |
| 1 | HU-04 Buscar expedientes por nombre, empresa, tipo o fecha. | M1 | Alta | RF-05 |
| 1 | HU-05 Gestionar usuarios y asignar roles. | M7 | Alta | RF-26 |
| 1 | HU-06 Iniciar sesión y ver solo las funciones del propio rol. | M7 | Alta | RF-25, RF-26 |
| 1 | HU-07 Registrar cada acción en la bitácora (usuario, fecha, acción, IP). | M7 | Alta | RF-27 |
| 1 | HU-08 Verificar la integridad comparando la huella actual con la original. | M1 | Media | RF-03 |
| 2 | HU-09 Definir documentos obligatorios y opcionales por tipo de expediente. | M2 | Alta | RF-06 |
| 2 | HU-10 Vincular anexos obligatorios a documentos principales. | M2 | Alta | RF-07 |
| 2 | HU-11 Asignar severidad y acción a cada regla. | M2 | Alta | RF-08 |
| 2 | HU-12 Verificar la completitud y mostrar el porcentaje de documentos presentes. | M2 | Alta | RF-06, RF-19 |
| 2 | HU-13 Calcular si cada documento está vigente, próximo a vencer o vencido. | M4 | Alta | RF-15, RF-16 |
| 2 | HU-14 Configurar los umbrales de anticipación (30, 15 y 5 días). | M4 | Media | RF-17 |
| 2 | HU-15 Recibir alertas por documentos faltantes, vencidos o anexos ausentes. | M5 | Alta | RF-18 |
| 2 | HU-16 Que cada alerta incluya una recomendación. | M5 | Media | RF-21 |
| 2 | HU-17 Notificaciones por correo ante estatus crítico. | M5 | Media | RF-20 |

La extracción de las fechas de emisión y vencimiento del documento (RF-15) llega con la IA en el Sprint 3. Mientras un documento no tiene dictamen, cuenta como pendiente de auditoría y deja el expediente en Amarillo (PRD §10.2 y §10.3): nunca se da por vigente.

### Reglas que aplica

- **Familias RIE y RCV del DOC-05** (PRD §9.2): completitud (RIE-01), anexos (RIE-02), integridad criptográfica (RIE-03) y vigencia (RCV-01 a RCV-03).
- **Reglas de negocio** (PRD §9.1): RN-01 (sin obligatorios no hay Conforme), RN-02 (un documento vencido lleva el expediente a No conforme), RN-04 (sin borrado físico) y RN-05 (la decisión humana prevalece).
- **Semáforo** (PRD §10.2): Rojo, Amarillo y Verde con las mismas reglas que el producto completo. Subir archivos nunca aprueba un expediente.

### Flujos

F1 (alta de expediente y carga), F2 (configuración de reglas) y F5 (alertas y corrección) del PRD §6, con los Niveles 1 y 2 del pipeline (PRD §10.1).

## 4. Fuera del MVP

| Incremento | Historias | Qué agrega |
|---|---|---|
| Sprint 3 — Análisis inteligente con IA | HU-18 a HU-25 | OCR de documentos escaneados, verificación de cláusulas con cita literal, extracción de datos y del firmante, nivel de confianza y revisión humana de los hallazgos de la IA (Niveles 3 a 5). |
| Sprint 4 — Reportes, dashboard e integración | HU-26 a HU-33 | Tablero con indicadores, dictamen formal y exportación en PDF y Excel, consulta de la bitácora, usuario de consulta y validación completa de un expediente con un solo botón. |
| Extensiones PLUS | — | Requerimientos agregados durante el desarrollo, fuera del DOC-04 ([ESTADO_DEL_DESARROLLO §6](ESTADO_DEL_DESARROLLO.md#6-extensiones-plus)). |

## 5. Criterios de aceptación del MVP

Tomados de los criterios del producto (PRD §14) y de los requerimientos no funcionales que aplican sin IA:

- Crear, organizar y buscar expedientes con identificador único y clasificación por tipo.
- Cargar PDF e imágenes con cálculo automático de SHA-256; una huella que no coincide marca el documento como alterado.
- El motor evalúa completitud, vigencia y presencia de anexos, con reglas configurables desde la interfaz sin modificar el código.
- Alertas automáticas, con su recomendación, ante documentos faltantes, vencidos o próximos a vencer.
- Semáforo Verde, Amarillo y Rojo por expediente.
- Acceso con autenticación y roles diferenciados; cada acción relevante queda en la bitácora de forma inmutable.
- Evaluación determinista de un expediente completo en 2 s o menos (RNF-01).
- Sistema contenerizado, desplegable con un solo comando (RNF-11).

## 6. Cómo se verifica

- **Pruebas automatizadas** de core y rules (`pytest tests/`): integridad del Nivel 1, completitud, anexos, vigencia, semáforo, alertas, bitácora sellada, autenticación y permisos por rol.
- **Entrega en Docker** (`python scripts/prueba_entrega_docker.py`): desde un clon limpio, inicia sesión con los cuatro roles, registra una empresa con RFC ficticio, carga un documento y comprueba que un expediente incompleto queda No conforme y que la cadena de la bitácora está íntegra.
- **Rendimiento** (`python scripts/benchmark_rendimiento.py`): RNF-01 sobre una base aislada.

El estado de cada historia y de cada sprint está en [ESTADO_DEL_DESARROLLO §1](ESTADO_DEL_DESARROLLO.md#1-estado-de-los-requerimientos).
