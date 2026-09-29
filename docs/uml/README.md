# Diagramas UML de las extensiones PLUS

Diagramas en PlantUML (`.puml`) de los requerimientos que se agregan al producto después de la versión 1.2 del [PRD](../PRD.md). Cada diagrama se escribe **antes** de implementar su requerimiento y cita en su encabezado los requerimientos (RF, HU, reglas) que refleja y el archivo donde se implementa.

Estos diagramas complementan los del DOCUMENTO GENERAL (Cap. IV, Figuras 1–6, flujos F1–F6 del PRD §6); no lo sustituyen ni lo modifican. Los que dicen «Actualiza F*n*» describen la versión vigente de ese flujo.

## Índice y trazabilidad

| Requerimiento | Diagrama | Tipo | Flujo del PRD | PRD | MRD |
|---|---|---|---|---|---|
| P1 — Ingesta blindada | [p1-casos-de-uso-ingesta-blindada.puml](p1-casos-de-uso-ingesta-blindada.puml) | Casos de uso | F1, F3 | §21 PLUS-01 a PLUS-03; HU-34 a HU-36 | MR-11, MR-20 |
| P1 — Ingesta blindada | [p1-actividad-carga-documento.puml](p1-actividad-carga-documento.puml) | Actividades | Actualiza F1 | PLUS-01, PLUS-02; RF-02 a RF-04 | MR-11, MR-20 |
| P1 — Ingesta blindada | [p1-actividad-auditoria-opinion-32d.puml](p1-actividad-auditoria-opinion-32d.puml) | Actividades | Actualiza F3 | PLUS-03; RCV-04, RSC-OPIN-SENT | MR-04, MR-20 |
| P2 — Cotejo de representación legal | [p2-casos-de-uso-representacion-legal.puml](p2-casos-de-uso-representacion-legal.puml) | Casos de uso | F3, F4 | §21.2 RSC-02, HU-23, HU-37, HU-38; RN-03 | MR-08 |
| P2 — Cotejo de representación legal | [p2-actividad-cotejo-representacion.puml](p2-actividad-cotejo-representacion.puml) | Actividades | Actualiza F3 y F4 | RSC-02, RN-03, RCV-01, RN-05; alerta REPRESENTACION_NO_ACREDITADA | MR-08 |

## Generar las imágenes

Con Java 17 o posterior y el JAR de PlantUML (no se versiona en el repositorio):

```bash
java -jar plantuml.jar -charset UTF-8 -tpng docs/uml/*.puml
```

Las imágenes generadas no se versionan: la fuente de verdad es el `.puml`.
