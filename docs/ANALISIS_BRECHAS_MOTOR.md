# Análisis de brechas — Motor de Validación de Cumplimiento Documental

| Campo | Valor |
|---|---|
| Pregunta | ¿Qué le falta al sistema para consolidarse como un motor de validación de cumplimiento documental corporativo o bancario, sin salirse de los DOC-01 a DOC-08, de la Ficha Técnica 045 ni de los compromisos con PluriOne? |
| Fecha | 29 de septiembre de 2026 (tras cerrar P1, P2 y P3; PRD versión 1.5) |
| Fuentes | Ficha Técnica 045 (PDF de PluriOne); texto íntegro de DOC-01 a DOC-08 ([ESPECIFICACIONES_DOC01_A_DOC08.txt](ESPECIFICACIONES_DOC01_A_DOC08.txt)); [PRD.md](PRD.md) v1.5; código del repositorio, contra el que se verificó cada afirmación |
| Criterio | Solo es brecha lo que exige alguno de esos documentos. Donde un requisito bancario va más allá de lo documentado, se indica. |
| Documentos hermanos | [PRD.md](PRD.md), [MRD.md](MRD.md), [AUDITORIA_TECNICA.md](AUDITORIA_TECNICA.md) |

---

## 1. Nivel normativo y de negocio (DOC-01 a DOC-05)

### 1.1 Cobertura de las cuatro familias de reglas del DOC-05

| Regla | Exigencia del DOC-05 | Estado |
|---|---|---|
| RIE-01 Completitud | Porcentaje de obligatorios del tipo de expediente; bloqueante | Cumple. El catálogo base exige 3 de los 8 obligatorios corporativos del DOC-02 (ver C9). |
| RIE-02 Anexos | La ausencia de un anexo invalida el documento principal | Cumple por tipo de anexo. El DOC-02 pide «los anexos referenciados en el contrato principal»: no se coteja lo que el contrato cita. |
| RIE-03 Integridad | Recalcular el SHA-256 al consultar y bloquear | Cumple en cada lectura del binario; un archivo que nadie lee puede estar alterado sin detectarse (ver 2.2). |
| RCV-01 Vigencia | Vencido, próximo a vencer (0–30 días) o vigente | Cumple, con umbrales de 30, 15 y 5 días (RF-17). |
| RCV, caducidad estricta | Vigencia legal fija desde la emisión | Cumple: RCV-02 domicilio (90 días), RCV-03 constancia fiscal (90), RCV-04 opinión 32-D (30). |
| RSC-01 Cláusulas esenciales | Cláusula con cita; «omisión contractual relevante» si falta | Cumple: 16 reglas RSC con cita literal anclada al texto. |
| RSC-02 Datos del firmante | Extraer al firmante; decide el analista | Cumple (P2), con el cotejo preparado para el analista. |
| RDS-01 Alta dinámica de requisitos | Nuevo tipo de documento desde la interfaz | Parcial: se dan de alta reglas, pero los 22 tipos de documento son un catálogo fijo en el código. |
| RDS-02 Criterio en lenguaje natural | La instrucción del usuario se guarda y se evalúa | Pendiente: no se aplica en el Nivel 4 (RF-09 y HU-24 parciales). |
| RDS-03 Ejecución supervisada | Todo lo dinámico pasa por ratificación humana | Cumple. |

**Cobertura: 8 de 10 reglas completas, 1 parcial y 1 pendiente (≈ 85 %).**

La brecha de mayor peso es RDS-02: es lo que el DOC-01 y el DOC-03 describen como la extensibilidad fundamental del sistema (ejemplo del DOC-03: «penalización por mora del 15 %, que excede el tope configurado del 10 %»). Tampoco se evalúan los criterios cuantitativos del DOC-02: coberturas y montos mínimos de las pólizas (RSC-POL-COB verifica que la cobertura exista, no su monto), monto de la fianza y organismo certificador válido.

### 1.2 Excepciones del DOC-05 (Tabla 1) y excepciones legales

| Excepción | Exigencia | Estado |
|---|---|---|
| Documento ilegible | Amarillo: «Documento ilegible, se requiere recarga» | Parcial: pasa a revisión humana por lectura no fiable, sin un estado ni un aviso de recarga; el analista no distingue «ilegible» de «dudoso». |
| Servicio de IA no disponible | Tres reintentos; el documento queda pendiente para procesamiento posterior; alerta «Procesamiento diferido» | Parcial: los reintentos existen (los del SDK, `GROQ_MAX_RETRIES`); no hay reprocesamiento diferido, el documento queda sin auditar hasta que alguien lo relance. |
| Archivo protegido con contraseña | Rojo: «Archivo protegido, no procesable» | Cumple (PLUS-02). |
| Poder revocado | DOC-02: los poderes «pueden tener vigencia limitada o ser revocados» | Pendiente: no hay forma de registrar una revocación; lo decide el analista. |
| Vigencia ligada a otro documento | DOC-02: fianza y convenio modificatorio ligados a la vigencia del contrato | Pendiente: no hay dependencias de fechas entre documentos. |
| Acta de asamblea que sustituye representantes | DOC-02: orden cronológico de las actas | Lo decide el analista (declarado en P2, PRD §21.2). |
| Documentos de identificación personal | DOC-01: excluidos del alcance | Cumple: el catálogo no incluye INE, CURP ni pasaporte (el DOC-08, Tabla 7, cita «INE» como ejemplo de tipo documental). |

### 1.3 Inconsistencias entre documentos

Ninguna es un defecto del sistema, pero un auditor que lea los documentos en orden las encontraría, y varias las resuelve hoy el PRD sin declararlas.

| # | Contradicción | Implementación | Acción |
|---|---|---|---|
| C1 | El DOC-08 describe un monolito modular de dos contenedores, puerto 8000, inferencia local con Ollama (Qwen2.5:7b) y PostgreSQL 16. | Tres microservicios (DG Cap. VIII), Groq Cloud y PostgreSQL 17. | Completar la sección 19 del PRD (monolito → microservicios, Ollama → Groq, PostgreSQL 16 → 17, puertos). |
| C2 | Límite de carga: 50 MB en el DOC-08. | 15 MB (`documento_controller.py`, `MAX_FILE_SIZE_BYTES`). | Documentar el origen del límite de 15 MB. |
| C3 | Umbral de revisión humana: el DOC-04 (RF-14) dice menor a 80 %; el DOC-05 y el DOC-08 dicen 85 % con la banda 0.70–0.84. | 85 % (DOC-05 y DOC-08). | El PRD reescribió RF-14 como 85 % sin nota: declarar la decisión. |
| C4 | Severidades: Alta/Media/Baja (DOC-04, RF-08); Crítica/Alta/Media (HU-11); cuatro niveles (DOC-05). | Cuatro niveles del DOC-05. | Declarar la decisión. |
| C5 | Amarillo del semáforo: «Próximo a vencer» (DOC-03), «próximos a vencer o pendientes de ratificación» (DOC-04), «Advertencia» (DOC-06). | Más amplio: también documentos sin auditar y obligatorios no críticos faltantes. | Declarar la decisión. |
| **C6** | Modelo de puntuación del DOC-05: porcentaje = reglas cumplidas ÷ reglas evaluadas × 100, con bloqueo por criticidad. | No existe: se calcula el porcentaje de documentos obligatorios presentes (`motor/cumplimiento.py`). | **Brecha real.** Es la causa de que la interfaz muestre «Completitud 100 %» junto a «Cumplimiento global 0 %» en un expediente No conforme. |
| C7 | Estado `BLOQUEADO` del expediente (DOC-08). | Documento ALTERADO con respuesta 409 (RIE-03). | Equivalente funcional; declararlo. |
| C9 | El DOC-02 (Tabla 2) marca 8 obligatorios corporativos: acta constitutiva, poderes, estatutos, actas de asamblea, RFC, constancia de situación fiscal, aviso de privacidad y comprobante de domicilio. | El catálogo base exige 3. | Decisión del Product Owner (pregunta abierta del PRD §20). Consecuencia: activarlos como Críticos lleva a No conforme a todos los expedientes corporativos existentes. |
| C10 | ISO 30301 (DOC-03): metadatos obligatorios, entre ellos el emisor oficial. | El emisor no se guarda. | Agregarlo a la extracción del Nivel 4. |

Además, el PRD marca RF-10 como implementado, pero el DOC-04 pide «texto plano, estructura tabular y pares clave-valor» y el sistema extrae texto plano: RF-10 es **parcial**.

---

## 2. Nivel de auditoría externa y seguridad (DOC-06 a DOC-08)

Acotado a lo que exigen el DOC-03 (ISO/IEC 27001, ISO 30301, NOM-151-SCFI-2016), el DOC-04 y el protocolo de auditoría del DOC-05.

### 2.1 Identidad y no repudio — brecha crítica

- La identidad de quien ratifica viaja en el cuerpo de la petición (`revisado_por = dto.usuario` en `dictamen_controller.py`; valor por defecto `"OPERADOR"`).
- No hay autenticación y CORS admite cualquier origen (`allow_origins=["*"]`): desde la red se puede ratificar a nombre de otro o descargar cualquier binario vía `/contenido`.
- El DOC-03 (Tabla 1) exige «segregación de funciones» (ISO/IEC 27001): por ejemplo, que quien custodia un documento no sea quien ratifica su dictamen.

Mientras no exista el Módulo 7, la bitácora sellada prueba **qué** ocurrió pero no **quién** lo hizo. Queda cubierto por RF-25, RF-26, HU-05, HU-06, HU-07 y HU-31, programados para la fase final del proyecto.

### 2.2 Conservación de la evidencia

| Requisito | Fuente | Estado |
|---|---|---|
| Cifrado AES-256 en reposo | RNF-04; ISO/IEC 27001 A.8.24 | Pendiente: la bóveda está en claro. Además, la SQLite del ai-service guarda el texto completo extraído (con datos personales de apoderados y firmantes) en claro, fuera de la cadena de custodia y de cualquier respaldo. |
| TLS 1.3 entre componentes | RNF-05 | Parcial: solo hacia el proveedor de inferencia. |
| Respaldos diarios con RPO < 24 h | RNF-10 | Pendiente: solo `pg_dump` manual. Un respaldo de la base sin la bóveda no sirve como evidencia: ambos deben respaldarse en el mismo punto, o RIE-03 marcará como alterados documentos que simplemente no se restauraron. |
| Fecha y hora UTC en la bitácora | RF-27; ISO/IEC 27001 A.8.15 | Parcial: columnas `TIMESTAMP` sin zona. El sello de P3 incluye la fecha serializada: migrar a `TIMESTAMPTZ` sin conservar esa serialización rompería la verificación de la cadena existente. |
| Integridad permanente | RIE-03; ISO 30301 | Parcial: se comprueba al leer. Falta un barrido programado de integridad de la bóveda, que cabe en la reevaluación programada (sin IA). |
| Anclaje externo de la cadena | NOM-151 (trazabilidad) | Parcial: la cadena detecta alteraciones parciales, pero quien administre PostgreSQL podría recalcularla entera. Dentro de lo documentado: imprimir el último hash sellado en cada dictamen exportado, de modo que cada copia en manos de un auditor funcione como ancla. La constancia de un Prestador de Servicios de Certificación sigue fuera del alcance y así se declara. |

### 2.3 Reproducibilidad del dictamen (protocolo de auditoría del DOC-05)

Se registran la regla, el resultado, la confianza, la cita, la IP, el modelo y la temperatura. Falta guardar en el dictamen la **versión de la lectura** (`VERSION_PIPELINE`, idiomas, DPI) y la **versión de las instrucciones al modelo**: sin ellas no se puede explicar por qué dos dictámenes del mismo archivo difieren con meses de distancia.

### 2.4 Pruebas que exige la documentación

| Prueba | Fuente | Estado en el repositorio |
|---|---|---|
| Precisión de la IA con un conjunto de referencia (precisión, exhaustividad y F1) | DOC-03 (ISO/IEC 25010); DOC-01, H12 | Pendiente: no hay conjunto de referencia ni script de métricas. El PRD da el criterio por cumplido citando el DG Cap. X. |
| RNF-01 (≤ 2 s), RNF-03 (50 peticiones simultáneas), RNF-09 (disponibilidad) | DOC-04 | Sin medición. |
| RNF-02 (≤ 25 s para 20 páginas) | DOC-04 | En riesgo: el PRD cita 13 s para 26 páginas, pero la medición más reciente, tras la detección de sellos (Nivel 3, versión 3.2), es de 24.3 s para 14 páginas en frío; extrapolada a 20 páginas, unos 33 s. Debe volver a medirse. |
| Pruebas de seguridad | Ficha 045, actividad 6 | Pendiente (fase de QA). |

---

## 3. Balance general frente a la Ficha 045

### 3.1 Madurez por dimensión

Fórmula: implementado = 1, parcial = 0.5, pendiente = 0.

| Dimensión | Base | Madurez |
|---|---|---|
| Requerimientos funcionales (27) | 20 implementados, 4 parciales (RF-10 corregido), 3 pendientes | 81 % |
| Historias de usuario (33 del DOC-07) | 26, 3 y 4 | 83 % |
| Reglas y excepciones (DOC-05) | 10 reglas y 3 excepciones | 80 % |
| Criterios de aceptación del DOC-07 (16) | 10 de 10 funcionales; seguridad 1 de 3; calidad 1 de 3 | 75 % |
| Requerimientos no funcionales (12) | 5.5 implementados y 1 parcial | ≈ 50 % |
| Seguridad y auditoría (RF-25, RF-26, RF-27, HU-07, RNF-04, RNF-05, RNF-10 y protocolo) | Promedio de 8 requisitos | ≈ 35 % |

- **Madurez del producto de software** (funcional 50 %, reglas 15 %, seguridad 20 %, no funcionales 15 %): **≈ 70 %**.
- **Madurez del proyecto frente a la Ficha 045** (10 actividades: requerimientos, propuesta, arquitectura y plan terminados; desarrollo en unos dos tercios de lo que la Ficha exige al sistema, incluido el panel administrativo con usuarios y roles; QA, manuales, mantenimiento, capacitación e informe final pendientes): **≈ 55 %**.

Contexto de calendario: según la Tabla 8 del DOC-07, el 29 de septiembre corresponde a la semana 5 (inicio del Sprint 1). El desarrollo va adelantado respecto del plan; los entregables de cierre (semanas 13 a 16) no están atrasados.

### 3.2 Huecos antes de dar por terminado el proyecto

**Estructurales**

1. Módulo 7: identidad, roles, segregación de funciones, CORS restringido y protección de `/contenido`. Sin él no se cumple el criterio de aceptación «acceso con autenticación y roles diferenciados».
2. Protección de la evidencia: cifrado en reposo de la bóveda y de la SQLite, respaldos conjuntos de base y bóveda, UTC en la bitácora sin romper la cadena, TLS interno.
3. Índice de cumplimiento del DOC-05 (C6).

**Funcionales**

4. RDS-02, RF-09 y HU-24: tipos de documento dinámicos con criterio en lenguaje natural.
5. Excepciones del DOC-05: estado «ilegible, se requiere recarga» y reprocesamiento diferido cuando la IA no responde.
6. RF-20 (correo, a la espera del proveedor que defina el Product Owner), RF-02 (carga en lote), HU-14 (umbrales desde la interfaz), el emisor como metadato (C10) y la versión de lectura e instrucciones en el dictamen.
7. Barrido programado de integridad (RIE-03) y último sello impreso en los reportes.

**De evidencia (Ficha 045, actividades 6 a 10)**

8. Conjunto de referencia con precisión, exhaustividad y F1; pruebas de carga y de seguridad; nueva medición de RNF-02.
9. Manual técnico y de usuario, plan de mantenimiento (incluida la actualización de reglas), acta de capacitación e informe final.

**Documentales (sin código)**

10. Declarar en la sección 19 del PRD las decisiones C1 a C5, C7 y el estado real de RF-10.
11. Decisión del Product Owner sobre los obligatorios del DOC-02 (C9) y su efecto en los semáforos existentes.

---

## 4. Decisiones tomadas sobre este análisis (29/09/2026)

- **C6 se resuelve dentro del Lote 3 de la revisión del frontend:** el core calculará el índice de cumplimiento del DOC-05 (reglas cumplidas ÷ reglas evaluadas, con bloqueo por criticidad) como un campo nuevo de la evaluación, sin romper contratos de la API, y el tablero dejará de presentar la completitud documental como si fuera cumplimiento.
- **El Módulo 7 (autenticación, usuarios y roles) queda para el final del proyecto.** Hasta entonces el trabajo se concentra en el frontend (lotes 0 a 5 aprobados).
- Los demás huecos quedan registrados aquí como insumo de las siguientes iteraciones; cada uno se propondrá para aprobación antes de implementarse.
