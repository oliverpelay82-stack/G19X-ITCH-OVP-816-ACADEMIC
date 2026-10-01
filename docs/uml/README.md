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
| QA — Validación cuantitativa (Fase 5, no PLUS) | [qa-actividad-evaluacion.puml](qa-actividad-evaluacion.puml) | Actividades | — | §15; RNF-01 a RNF-03; [VALIDACION_CUANTITATIVA.md](../VALIDACION_CUANTITATIVA.md) | — |

## Generar las imágenes

Con Java 17 o posterior y el JAR de PlantUML (no se versiona en el repositorio):

```bash
java -jar plantuml.jar -charset UTF-8 -tpng docs/uml/*.puml
```

Las imágenes generadas no se versionan: la fuente de verdad es el `.puml`.
