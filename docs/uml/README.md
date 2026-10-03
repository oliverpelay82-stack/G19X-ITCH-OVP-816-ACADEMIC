# Diagramas UML de los requerimientos implementados después de la versión 1.2 del PRD

Diagramas en PlantUML (`.puml`) de las extensiones PLUS y de los requerimientos de la documentación que se implementan después de la versión 1.2 del [PRD](../PRD.md) (C6: modelo de puntuación del DOC-05, detectado en el [análisis de brechas](../ANALISIS_BRECHAS_MOTOR.md)). Cada diagrama se escribe **antes** de implementar su requerimiento y cita en su encabezado los requerimientos (RF, HU, reglas) que refleja y el archivo donde se implementa.

Estos diagramas complementan los del DOCUMENTO GENERAL (Cap. IV, Figuras 1–6, flujos F1–F6 del PRD §6); no lo sustituyen ni lo modifican. Los que dicen «Actualiza F*n*» describen la versión vigente de ese flujo.

## Índice y trazabilidad

| Requerimiento | Diagrama | Tipo | Flujo del PRD | PRD | MRD |
|---|---|---|---|---|---|
| P1 — Ingesta blindada | [p1-casos-de-uso-ingesta-blindada.puml](p1-casos-de-uso-ingesta-blindada.puml) | Casos de uso | F1, F3 | §21 PLUS-01 a PLUS-03; HU-34 a HU-36 | MR-11, MR-20 |
| P1 — Ingesta blindada | [p1-actividad-carga-documento.puml](p1-actividad-carga-documento.puml) | Actividades | Actualiza F1 | PLUS-01, PLUS-02; RF-02 a RF-04 | MR-11, MR-20 |
| P1 — Ingesta blindada | [p1-actividad-auditoria-opinion-32d.puml](p1-actividad-auditoria-opinion-32d.puml) | Actividades | Actualiza F3 | PLUS-03; RCV-04, RSC-OPIN-SENT | MR-04, MR-20 |
| P2 — Cotejo de representación legal | [p2-casos-de-uso-representacion-legal.puml](p2-casos-de-uso-representacion-legal.puml) | Casos de uso | F3, F4 | §21.2 RSC-02, HU-23, HU-37, HU-38; RN-03 | MR-08 |
| P2 — Cotejo de representación legal | [p2-actividad-cotejo-representacion.puml](p2-actividad-cotejo-representacion.puml) | Actividades | Actualiza F3 y F4 | RSC-02, RN-03, RCV-01, RN-05; alerta REPRESENTACION_NO_ACREDITADA | MR-08 |
| P3 — Custodia sellada | [p3-casos-de-uso-custodia.puml](p3-casos-de-uso-custodia.puml) | Casos de uso | F6 y bitácora | §21.3 PLUS-04 a PLUS-06; HU-39 a HU-41 | MR-10, MR-11, MR-21 |
| P3 — Custodia sellada | [p3-actividad-sellado-verificacion.puml](p3-actividad-sellado-verificacion.puml) | Actividades | Bitácora (RF-27) | PLUS-04, PLUS-05 | MR-21 |
| P3 — Custodia sellada | [p3-actividad-ficha-custodia.puml](p3-actividad-ficha-custodia.puml) | Actividades | Actualiza F6 | PLUS-06; RF-23, RF-24 | MR-10, MR-21 |
| C6 — Índice de cumplimiento (DOC-05, no PLUS) | [c6-actividad-indice-cumplimiento.puml](c6-actividad-indice-cumplimiento.puml) | Actividades | Actualiza F5 y F6 | §10.5; RF-19, RF-22, HU-12, HU-26; RN-01, RN-05 | MR-12 |
| P4 — Chat documental eficiente | [p4-actividad-chat-documental.puml](p4-actividad-chat-documental.puml) | Actividades | Chat del panel de IA | §21.4 PLUS-07 a PLUS-11; HU-42, HU-43; RF-13, HU-20 | MR-22 |
| P5 — Integridad permanente y dictamen reproducible | [p5-casos-de-uso-integridad-reproducibilidad.puml](p5-casos-de-uso-integridad-reproducibilidad.puml) | Casos de uso | F3, F6 y reevaluación programada | §21.5 PLUS-14, PLUS-15; HU-33, HU-44 a HU-48 | MR-11, MR-21, MR-23 |
| P5 — Integridad permanente y dictamen reproducible | [p5-actividad-barrido-integridad.puml](p5-actividad-barrido-integridad.puml) | Actividades | Reevaluación programada y actualiza F6 | PLUS-14, PLUS-15; RIE-03, RF-23, RF-24, RF-27 | MR-11, MR-21, MR-23 |
| P5 — Integridad permanente y dictamen reproducible | [p5-actividad-excepciones-auditoria.puml](p5-actividad-excepciones-auditoria.puml) | Actividades | Actualiza F3 | DOC-05 (Tabla 1 y protocolo); HU-33, HU-46 a HU-48; RF-13, RF-18 | MR-23 |
| P6 — Autenticidad del archivo, catálogo y operación | [p6-casos-de-uso-autenticidad.puml](p6-casos-de-uso-autenticidad.puml) | Casos de uso | F1, F3 y Reportes | §21.6 M1, M5, M6, PLUS-18 a PLUS-20; HU-49, HU-52 a HU-56 | MR-24 |
| P6 — Autenticidad del archivo, catálogo y operación | [p6-actividad-senales-archivo.puml](p6-actividad-senales-archivo.puml) | Actividades | Actualiza F1 y F3 | PLUS-18, M5; ISO/IEC 27001 A.8.7, DOC-02 | MR-24 |
| P6 — Autenticidad del archivo, catálogo y operación | [p6-actividad-trazabilidad-operacion.puml](p6-actividad-trazabilidad-operacion.puml) | Actividades | F3, salud y Reportes | M6, PLUS-19, PLUS-20; protocolo del DOC-05, RNF-02 | MR-24 |
| P7 — Operación trazable y calidad | [p7-casos-de-uso-operacion-calidad.puml](p7-casos-de-uso-operacion-calidad.puml) | Casos de uso | Operación, F3 y CI | §21.7 PLUS-21, M7, Q-b, Q-c; HU-57, HU-59 a HU-61 | MR-25 |
| P7 — Operación trazable y calidad | [p7-actividad-folio-seguimiento.puml](p7-actividad-folio-seguimiento.puml) | Actividades | Todas las peticiones | PLUS-21; ISO/IEC 27001 A.8.15 | MR-25 |
| P7 — Operación trazable y calidad | [p7-actividad-nueva-auditoria.puml](p7-actividad-nueva-auditoria.puml) | Actividades | Actualiza F3 | M7; protocolo del DOC-05 | MR-25 |
| QA — Validación cuantitativa (Fase 5, no PLUS) | [qa-actividad-evaluacion.puml](qa-actividad-evaluacion.puml) | Actividades | — | §15; RNF-01 a RNF-03; [VALIDACION_CUANTITATIVA.md](../VALIDACION_CUANTITATIVA.md) | — |
| Detalle de la empresa (interfaz, no PLUS) | [ui-actividad-detalle-empresa.puml](ui-actividad-detalle-empresa.puml) | Actividades | Empresas → F2 | §13.1; RF-01, RF-05, RF-18, RF-19, RF-21; HU-02, HU-04, HU-27 | MR-12, MR-18 |
| Corrección de datos de captura (no PLUS) | [ui-actividad-correccion-datos.puml](ui-actividad-correccion-datos.puml) | Actividades | Empresas y F2 | §13.1; RF-01, RF-27; RN-04, RN-05; HU-02, HU-07 | MR-10 |
| RF-09 — Tipos de documento nuevos (DOC-04, no PLUS) | [rf09-actividad-tipo-documento-nuevo.puml](rf09-actividad-tipo-documento-nuevo.puml) | Actividades | Reglas, F1 y F3 | §7 RF-09, HU-24; RDS-01 a RDS-03; RF-06, RIE-01 | MR-06 |
| RF-02 — Carga en lote (DOC-04, no PLUS) | [rf02-actividad-carga-en-lote.puml](rf02-actividad-carga-en-lote.puml) | Actividades | Actualiza F1 | §7 RF-02, HU-03; RF-03, RF-04; PLUS-01, PLUS-02, PLUS-18; RN-01 | MR-11, MR-20 |
| RNF-10 — Respaldo diario y prueba de restauración (DOC-04, no PLUS) | [rnf10-actividad-respaldo.puml](rnf10-actividad-respaldo.puml) | Actividades | — | §11 RNF-10; RF-03, RIE-03; PLUS-04, PLUS-05 | MR-10, MR-16, MR-17 |

Las señales de edición (PLUS-16), el QR del SAT (PLUS-17) y el sello de tiempo (PLUS-22) se retiraron el 02/10/2026 ([PRD §21.8](../PRD.md)); el 03/10/2026 los diagramas de P6 y P7 se actualizaron al código vigente y el de actividad de P7 pasó de `p7-actividad-peticion-sello.puml` a `p7-actividad-folio-seguimiento.puml`.

## Generar las imágenes

Con Java 17 o posterior y el JAR de PlantUML (no se versiona en el repositorio):

```bash
java -jar plantuml.jar -charset UTF-8 -tpng docs/uml/*.puml
```

Las imágenes generadas no se versionan: la fuente de verdad es el `.puml`.
