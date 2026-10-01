# MRD — Motor de Validación de Cumplimiento Documental

**Market Requirements Document**

| Campo | Valor |
|---|---|
| Producto | Motor de Validación de Cumplimiento Documental mediante Inteligencia Artificial |
| Empresa | PluriOne S.A. de C.V. (Develop Talent & Technology) — Puebla 46, Col. Roma Norte, Alcaldía Cuauhtémoc, C.P. 06700, Ciudad de México |
| Línea de negocio | Portafolio de soluciones LegalTech de PluriOne |
| Patrocinador de negocio | Lic. Juan Méndez Herrera, Director Comercial (asesor empresarial y Product Owner) |
| Elaborado por | Oliver Villanueva Pelay, residente — Instituto Tecnológico de Chilpancingo |
| Versión del documento | 1.9 — 30 de septiembre de 2026 (1.8: correcciones de la documentación; 1.7: 30 de septiembre; 1.6: 29 de septiembre; 1.5: índice de cumplimiento; 1.4: P3; 1.3: P2; 1.2: P1; 1.1: 28 de septiembre; 1.0: 27 de septiembre de 2026) |
| Documento hermano | [PRD.md](PRD.md) — requerimientos del producto |

> **Fuentes.** Este MRD se construye exclusivamente con el anteproyecto de residencia, los entregables DOC-01 a DOC-08 ([ESPECIFICACIONES_DOC01_A_DOC08.txt](ESPECIFICACIONES_DOC01_A_DOC08.txt)) y el DOCUMENTO GENERAL («DG»). La información de mercado que esas fuentes no contienen —tamaño de mercado, precio o modelo comercial— no se estima: se declara en la [sección 13](#13-información-de-mercado-no-documentada) como pendiente de definir con PluriOne.

---

## Índice

1. [Resumen ejecutivo](#1-resumen-ejecutivo)
2. [Contexto de la empresa y oportunidad](#2-contexto-de-la-empresa-y-oportunidad)
3. [Problema de mercado](#3-problema-de-mercado)
4. [Mercado objetivo y segmentos](#4-mercado-objetivo-y-segmentos)
5. [Usuarios y compradores](#5-usuarios-y-compradores)
6. [Voz del cliente](#6-voz-del-cliente)
7. [Entorno regulatorio](#7-entorno-regulatorio)
8. [Panorama competitivo](#8-panorama-competitivo)
9. [Propuesta de valor](#9-propuesta-de-valor)
10. [Requisitos de mercado](#10-requisitos-de-mercado)
11. [Restricciones del mercado](#11-restricciones-del-mercado)
12. [Viabilidad](#12-viabilidad)
13. [Información de mercado no documentada](#13-información-de-mercado-no-documentada)
14. [Criterios de éxito](#14-criterios-de-éxito)
15. [Riesgos de mercado](#15-riesgos-de-mercado)
16. [Trazabilidad MRD → PRD](#16-trazabilidad-mrd--prd)

---

## 1. Resumen ejecutivo

Las organizaciones que administran expedientes jurídicos y corporativos validan su cumplimiento documental de forma manual: revisan documento por documento, controlan vigencias en hojas de cálculo y dependen de la experiencia de cada revisor para saber qué anexos exige cada expediente. El resultado son documentos vencidos que se descubren hasta la auditoría, anexos omitidos, criterios que cambian según quién revise y ninguna evidencia objetiva de lo que se validó [Anteproyecto; DOC-01].

PluriOne, empresa de consultoría y desarrollo de software con clientes del ámbito jurídico y corporativo, identifica en ese problema una oportunidad para su portafolio **LegalTech**: un motor que valide automáticamente la integridad, la vigencia, los anexos obligatorios y los requisitos regulatorios de cada expediente, con reglas configurables por sector, análisis de contenido con inteligencia artificial, supervisión humana y una bitácora inmutable que sirva de evidencia ante auditorías [Anteproyecto, «Justificación»; DG Cap. VI].

El mercado exige cuatro cosas que este documento traduce en requisitos: **automatizar la validación sin perder el criterio humano**, **adaptarse a regulaciones distintas por sector sin reprogramar**, **proteger la información sensible de los expedientes** y **demostrar ante una auditoría qué se validó, cuándo y con qué resultado**.

---

## 2. Contexto de la empresa y oportunidad

[Anteproyecto, «Planteamiento del Problema» y «Justificación»]

- **Quién es PluriOne:** empresa del sector de servicios de consultoría, desarrollo de software y capacitación en tecnologías de la información, con un equipo multidisciplinario que atiende a organizaciones de diversos sectores.
- **Relación con el problema:** como parte de su portafolio, PluriOne trabaja con clientes del ámbito jurídico y corporativo que manejan expedientes sujetos a marcos regulatorios y requisitos de cumplimiento.
- **Oportunidad:** fortalecer su portafolio de soluciones LegalTech con una herramienta de compliance documental que responde a una necesidad real del mercado. Para la industria, el beneficio declarado es reducir incumplimientos y mejorar la calidad de la documentación empresarial.

---

## 3. Problema de mercado

### 3.1 Cómo se valida hoy

[Anteproyecto, «Planteamiento del Problema»; DOC-01]

| Proceso | Cómo se hace hoy | Consecuencia |
|---|---|---|
| Integridad del expediente | Revisión manual, documento por documento, sin lista de verificación común. | Varias horas por expediente; documentos faltantes desapercibidos; resultados que varían según el revisor. |
| Vigencia de documentos | Hojas de cálculo que no siempre están actualizadas. | Documentos vencidos que permanecen en el expediente hasta que una auditoría los evidencia; sin alertas anticipadas. |
| Anexos obligatorios | Depende del conocimiento del revisor. | Con rotación de personal o requisitos nuevos, se omiten anexos obligatorios sin que nadie lo advierta. |
| Requisitos regulatorios | Cruce manual contra listas de verificación. | Errores, inconsistencias y criterios obsoletos cuando la regulación cambia. |
| Preparación de auditorías | Compilación manual de reportes desde diversas fuentes. | Proceso reactivo: las deficiencias aparecen cuando ya no hay tiempo para corregirlas; sin visibilidad en tiempo real. |

### 3.2 Costo de no resolverlo

[Anteproyecto, «Justificación»; DG Cap. III §3.1]

- Riesgos regulatorios, sanciones económicas y pérdida de credibilidad.
- Contingencias legales, sanciones administrativas, suspensión de operaciones o inhabilitación comercial por documentos vencidos o apócrifos.
- Un documento vencido que pasa desapercibido puede invalidar un trámite completo.
- Sin respaldo documental automatizado, la organización queda expuesta a observaciones de auditoría que pudieron prevenirse.
- Los problemas crecen al mismo ritmo que el volumen de documentación.

---

## 4. Mercado objetivo y segmentos

### 4.1 Mercado objetivo

Organizaciones empresariales —personas morales y sus representantes— que administran **expedientes documentales sujetos a marcos regulatorios** y que forman parte de la cartera de clientes de PluriOne o de su ámbito jurídico y corporativo [Anteproyecto; DG Cap. IV §4.2]. El producto **no** se dirige a la validación de documentos de identidad personal [DOC-01, H1].

### 4.2 Segmentos por tipo de expediente

[DG Cap. II §2.2, Tabla 5]

| Segmento | Qué contiene el expediente | Ejemplo de contexto |
|---|---|---|
| Jurídico | Documentación legal sujeta a obligaciones contractuales, normativas o jurisdiccionales. | Un contrato de prestación de servicios con sus anexos legales. |
| Corporativo | Documentación para la operación legal y administrativa de la empresa. | La constitución de una empresa con acta constitutiva, poderes y registros. |
| Regulatorio | Documentación exigida por marcos normativos sectoriales para operar en un giro. | Una constructora con licencias, permisos y certificaciones del sector. |

### 4.3 Segmentos por sector del cliente

[DG Cap. III §3.1 y §3.4; DOC-01]

Los clientes de PluriOne pertenecen a sectores distintos —construcción, tecnología, servicios, finanzas, transporte y manufactura— y cada uno se rige por requisitos propios:

| Sector | Requisitos documentales característicos |
|---|---|
| Construcción | Licencias de construcción y de uso de suelo, permisos ambientales, pólizas de obra civil contra terceros, dictámenes técnicos y sus anexos. |
| Tecnología y servicios financieros | Certificaciones ISO 27001, convenios de confidencialidad estrictos (NDA) y contratos de niveles de servicio (SLA). |
| Servicios industriales | Pólizas de seguros patronales y certificaciones de protección civil. |

### 4.4 Relación del titular con la empresa

[DG Cap. VIII, Tabla 21]

Los expedientes pertenecen a titulares categorizados como **proveedor**, **proveedor crítico** o **cliente**, lo que sitúa el producto en procesos de alta y seguimiento de proveedores y clientes. Entre las obligaciones documentales que el diseño contempla están la opinión de cumplimiento del SAT (CFF Art. 32-D) y la documentación del Régimen de Subcontratación Especializada (REPSE) [DG Cap. VI §6.7].

---

## 5. Usuarios y compradores

[DG Cap. IV §4.3, Tabla 8; Cap. VII §7.3]

| Actor | Rol en el mercado | Necesidad principal |
|---|---|---|
| PluriOne (Dirección Comercial) | Comprador y dueño del producto; lo integra a su portafolio LegalTech. | Una herramienta de compliance que responda a una necesidad real de sus clientes. |
| Administrador del sistema (TI de PluriOne) | Configura la plataforma. | Adaptar reglas, tipos de expediente y usuarios a cada cliente sin reprogramar. |
| Responsable de cumplimiento (abogados y analistas) | Usuario principal. | Dictaminar expedientes más rápido, con criterios uniformes y con la última palabra sobre los hallazgos de la IA. |
| Auditor (legal, fiscal o de calidad) | Usuario de supervisión. | Evidencia verificable: bitácora inmutable, nivel de confianza y reportes exportables. |
| Usuario de consulta (clientes u operadores) | Usuario final externo. | Conocer el estado de cumplimiento (semáforo) de sus expedientes sin acceso a configuraciones. |

---

## 6. Voz del cliente

[DOC-01 — entrevista no estructurada con el Lic. Juan Méndez Herrera, Director Comercial de PluriOne, realizada de forma remota]

### 6.1 Testimonios

> «Lo que el sistema valida son expedientes de empresas: contratos, pólizas de seguro, licencias de operación, certificaciones, permisos, actas constitutivas, poderes notariales, avisos de privacidad, constancias fiscales de la empresa y los anexos que les pidan según su regulación.»

> «Depende del tipo de expediente y del sector del cliente. Puede tener desde unos diez documentos hasta varias decenas. […] Cada uno tiene que estar completo y vigente.»

> «Las licencias, permisos, certificaciones, pólizas y muchos contratos tienen vigencia. El problema de ahorita es que eso lo llevan en Excel y no siempre está actualizado, entonces cuando algo se vence nadie se entera hasta que les cae la auditoría.»

> «La mayoría en PDF, que es lo estándar en el ámbito jurídico. Algunos vienen escaneados. La idea es que el sistema pueda leer esos PDFs y extraer su contenido.»

### 6.2 Hallazgos

[DG Cap. I §1.3]

| ID | Hallazgo |
|---|---|
| H1 | Solo expedientes jurídicos y corporativos; no documentos personales (INE, CURP, actas). |
| H2 | Contratos, pólizas, licencias, certificaciones, documentación corporativa y anexos obligatorios, con la posibilidad de agregar nuevos documentos según se requieran. |
| H3 | Un expediente puede tener de diez a varias decenas de documentos. |
| H4 | Múltiples documentos tienen vigencia definida (licencias, permisos, pólizas, contratos). |
| H5 | El formato predominante es PDF, incluidos escaneados. |
| H6–H10 | La validación opera en dos niveles: un motor de reglas determinista, sin servicios externos, y un análisis inteligente que extrae el texto y lo interpreta con un modelo de lenguaje. |
| H11–H13 | Las validaciones deterministas son exactas; la precisión de la IA se evalúa con pruebas y métricas; cada validación queda en un registro de auditoría. |
| H14 | Alineación con ISO/IEC 25010, ISO/IEC 27001 e ISO 30301. |

**Extensibilidad:** por indicación del asesor empresarial, el catálogo de documentos es una base inicial y no una lista cerrada; el administrador debe poder agregar nuevos tipos de documento y definir los criterios que evaluará la IA sin modificar el código [DG Cap. I, «Extensibilidad del Catálogo»].

---

## 7. Entorno regulatorio

[DG Cap. III — el cumplimiento regulatorio es a la vez el problema del cliente y un requisito del producto]

### 7.1 Marcos aplicables

| Marco | Relevancia para el mercado |
|---|---|
| ISO/IEC 25010 | Calidad del software: exactitud del análisis, fiabilidad, mantenibilidad y usabilidad. |
| ISO/IEC 27001 | Seguridad de la información: control de acceso por roles, criptografía y registros de auditoría. |
| ISO 30301 | Gestión de documentos: integridad, metadatos, ciclo de vida y trazabilidad del expediente. |
| Código de Comercio y NOM-151-SCFI-2016 | Validez de mensajes de datos, digitalización y conservación íntegra de documentos electrónicos. |
| Ley General de Sociedades Mercantiles | Validez de actas constitutivas, estatutos y facultades de los poderes notariales. |
| LFPDPPP | Protección de los datos de representantes, accionistas y prestadores contenidos en contratos y actas. |
| Código Fiscal de la Federación (Arts. 27 y 32-D) | Constancia de situación fiscal y opinión de cumplimiento del SAT. |
| Ley Federal del Trabajo (REPSE) | Obligaciones documentales del régimen de subcontratación especializada. |

### 7.2 Implicaciones para el producto

- **La regulación varía por sector y cambia con el tiempo:** las reglas no pueden vivir en el código; deben configurarse (DG §3.4).
- **La evidencia debe ser defendible:** huella criptográfica de cada documento y registro inalterable de cada validación (NOM-151, ISO 27001).
- **El uso de IA debe ser explicable y supervisado:** cita del fragmento que sustenta cada hallazgo y decisión humana en los casos dudosos (DG §3.6).
- **Privacidad:** los datos personales contenidos en los expedientes no deben exponerse ni usarse para fines ajenos a la validación (LFPDPPP).

---

## 8. Panorama competitivo

### 8.1 Alternativa actual

La competencia directa del producto dentro de los clientes es el **proceso manual con hojas de cálculo** descrito en la sección 3: sin costo de licencia, pero lento, inconsistente y sin trazabilidad.

### 8.2 Soluciones similares identificadas

[Anteproyecto, «Sistemas similares»]

| Solución | Descripción documentada | Aportación |
|---|---|---|
| Kofax TotalAgility | Plataforma de procesamiento inteligente de documentos que captura, clasifica y valida documentos empresariales mediante automatización e inteligencia artificial. | Automatización de flujos de trabajo documentales en entornos corporativos regulados. |
| ABBYY Vantage | Plataforma de procesamiento inteligente de documentos que usa aprendizaje automático para extraer datos de documentos no estructurados y validar su contenido. | Facilidad de uso e integración con sistemas empresariales existentes, orientada a digitalizar procesos de compliance. |

### 8.3 Enfoque diferencial del producto

La documentación no contiene una comparación funcional detallada ni de precios contra estas plataformas. El enfoque propio del motor, según las fuentes, es:

| Enfoque | Fuente |
|---|---|
| Especialización en **cumplimiento documental de expedientes** (completitud, anexos, vigencia e integridad), no en la captura documental genérica. | Anteproyecto; DG Cap. V |
| **Reglas configurables por tipo de expediente y sector**, sin modificar el código. | DG Cap. III §3.4, RF-06 a RF-09 |
| **Marco regulatorio mexicano** integrado en el catálogo: NOM-151, CFF, LGSM, LFPDPPP y REPSE. | DG Cap. III |
| **Veredicto determinista y auditable:** la IA extrae datos, pero el dictamen lo calculan reglas; una confianza baja nunca produce un rechazo. | DG Cap. V §5.2 |
| **Supervisión humana obligatoria** en los casos dudosos, con justificación registrada. | RN-05, RF-14 |
| **Bitácora inmutable** protegida por el propio motor de base de datos. | RF-27 |
| **Minimización de datos:** el archivo original no sale de la infraestructura; al proveedor de IA solo viaja el texto. | DG Cap. III §3.6, RNF-06 |
| Despliegue en la infraestructura de PluriOne con Docker Compose, sin licenciamiento propietario salvo la inferencia del Nivel 4. | DG Cap. VI §6.7 |

---

## 9. Propuesta de valor

**Para** los responsables de cumplimiento y auditores de organizaciones con expedientes jurídicos, corporativos y regulatorios,
**que** hoy validan a mano y descubren los incumplimientos hasta la auditoría,
**el Motor de Validación de Cumplimiento Documental** es una aplicación web
**que** evalúa automáticamente la completitud, los anexos, la vigencia y la integridad de cada expediente, analiza su contenido con IA bajo supervisión humana y deja evidencia inalterable de cada validación.
**A diferencia de** la revisión manual con hojas de cálculo, aplica los mismos criterios a todo expediente del mismo tipo, alerta antes de que un documento venza y permite demostrar el cumplimiento ante un auditor.

### Beneficios esperados

[DG Cap. VI §6.8; Anteproyecto, «Justificación»]

| Beneficio | Qué resuelve |
|---|---|
| Detección preventiva de documentos vencidos | Identifica de forma anticipada pólizas, licencias, permisos y certificaciones por vencer, en lugar de descubrirlos en una auditoría externa. |
| Estandarización de criterios | Reglas deterministas y parametrizadas: todo expediente del mismo tipo se evalúa con los mismos criterios de completitud, vigencia y anexos. |
| Trazabilidad y auditoría inmutable | Cada validación registra la huella SHA-256 del documento, el dictamen y la ratificación humana, como evidencia verificable. |
| Menor tiempo de revisión | La propuesta técnica estima una reducción del 90 % del tiempo de revisión manual de un expediente típico, sin sustituir el criterio del analista en los hallazgos de baja confianza. |

---

## 10. Requisitos de mercado

Cada requisito de mercado (MR) expresa **qué necesita el mercado**; el PRD define **cómo** lo resuelve el producto. Prioridad: **Imprescindible** si sin ella el producto no resuelve el problema central, **Importante** si mejora la adopción o el valor, **Deseable** si no cubre una necesidad expresada como problema.

| ID | Requisito de mercado | Origen | Prioridad |
|---|---|---|---|
| MR-01 | Verificar automáticamente que cada expediente contenga todos los documentos obligatorios de su tipo e indicar cuáles faltan. | P1 (integridad); H3 | Imprescindible |
| MR-02 | Distinguir expedientes jurídicos, corporativos y regulatorios, cada uno con su propio inventario documental. | DG Tabla 5; H2 | Imprescindible |
| MR-03 | Detectar los anexos obligatorios ausentes de un documento principal. | P3 (anexos) | Imprescindible |
| MR-04 | Controlar la vigencia de cada documento y alertar antes de su vencimiento. | P2 (vigencia); H4; testimonio sobre Excel | Imprescindible |
| MR-05 | Adaptar las reglas a la regulación de cada sector y a sus cambios sin reprogramar el sistema. | P4 (regulación); DG §3.4 | Imprescindible |
| MR-06 | Agregar nuevos tipos de documento y definir qué debe buscar la IA en ellos. | Extensibilidad del catálogo; H2 | Importante |
| MR-07 | Leer PDF nativos y escaneados y extraer su contenido. | H5; testimonio sobre PDFs | Imprescindible |
| MR-08 | Analizar el contenido de los documentos (cláusulas, titularidad, fechas) con IA explicable, citando la evidencia. | Anteproyecto (análisis semántico); DG §3.6 | Imprescindible |
| MR-09 | Mantener la decisión final en manos de un analista en los casos dudosos. | DG §3.6; RN-05 | Imprescindible |
| MR-10 | Demostrar ante una auditoría qué se validó, cuándo, con qué criterio y con qué resultado. | P5 (auditorías); Justificación | Imprescindible |
| MR-11 | Detectar cualquier alteración de un documento después de su carga. | NOM-151; ISO 30301 | Imprescindible |
| MR-12 | Mostrar el estado de cumplimiento de forma inmediata (semáforo) y generar alertas con la acción correctiva. | P5 (visibilidad) | Imprescindible |
| MR-13 | Generar reportes de cumplimiento exportables en PDF y Excel. | P5 (reportes manuales) | Importante |
| MR-14 | Notificar por correo a los responsables ante estatus crítico o vencimiento próximo. | Anteproyecto, Módulo 5 | Importante |
| MR-15 | Controlar el acceso por rol, de modo que cada actor vea solo lo que le corresponde. | ISO 27001; Módulo 7 | Imprescindible |
| MR-16 | Proteger la confidencialidad de los expedientes: el archivo original no debe salir de la infraestructura. | LFPDPPP; DG §3.6 | Imprescindible |
| MR-17 | Operar dentro de la infraestructura de PluriOne, con despliegue reproducible y sin hardware especializado. | Anteproyecto (viabilidad); DG §6.7 | Importante |
| MR-18 | Buscar expedientes por nombre, empresa, tipo, fecha y estatus. | Anteproyecto, Módulo 1 | Importante |
| MR-19 | Buscar conceptualmente dentro del acervo documental. | Anteproyecto (Azure AI Search), ISO 30301 | Deseable |
| MR-20 | Rechazar en la recepción los archivos que no aportan evidencia válida —duplicados del mismo expediente, PDF protegidos con contraseña y opiniones 32-D caducas o negativas— antes de que consuman revisión. | DOC-05 (Tabla 1 y caducidad estricta); CFF Art. 32-D; ISO 30301. Extensión PLUS (PRD §21) | Importante |
| MR-21 | Demostrar ante un auditor externo que la bitácora no se alteró y entregar la historia completa de un documento (huellas, versiones, dictámenes, ratificaciones). | DOC-03 (ISO 30301; NOM-151: «sustento en auditorías externas»); DOC-05 (protocolo de auditoría). Extensión PLUS (PRD §21.3) | Importante |
| MR-22 | Consultar un documento en lenguaje natural y obtener al instante los datos ya verificados, con su cita, sin depender de la cuota del proveedor de IA. | DOC-05 (cita textual de la evidencia); RF-13, HU-20; ISO/IEC 25010 (eficiencia de desempeño). Extensión PLUS (PRD §21.4) | Importante |

---

## 11. Restricciones del mercado

[DG Caps. III, VI y VIII]

- **Confidencialidad:** los expedientes contienen información estratégica, secretos comerciales y poderes de representación legal; el procesamiento debe minimizar los datos que salen de la organización (DG §3.2, §3.6).
- **Idioma y formato:** documentos en español, mayoritariamente PDF, con una proporción escaneada de calidad heterogénea (H5; DG §5.2).
- **Infraestructura del cliente:** la solución no debe requerir GPU en los equipos de PluriOne (DG §6.6); la inferencia local se evaluó en el equipo de desarrollo, sin GPU y con 8 GB de RAM, y resultó inviable (DG §8.7).
- **Costo operativo:** el plan gratuito del proveedor de inferencia cubre el volumen de la residencia; en producción, el costo por tokens se acota limitando el contexto por consulta y extrayendo el texto de cada documento una sola vez (DG §8.7).
- **Continuidad:** sin conexión a Internet, el análisis semántico no está disponible; el resto del motor debe seguir operando (DG §8.7).
- **Decisiones legales:** ninguna decisión con impacto contractual puede tomarse de forma exclusivamente automática (DG §3.6).

---

## 12. Viabilidad

[DG Cap. VI §6.7]

| Dimensión | Conclusión documentada |
|---|---|
| Técnica | Stack de código abierto en todas sus capas salvo la inferencia del Nivel 4, que se consume como servicio mediante una interfaz compatible con OpenAI; el resto se ejecuta en hardware local con contenedores Docker, sin licenciamiento propietario. |
| Operativa | El flujo Human-in-the-Loop reduce, según la estimación de la propuesta, un 90 % el tiempo de revisión manual, sin sustituir el criterio del analista en los hallazgos de baja confianza. |
| Legal y regulatoria | Bitácora inmutable, huellas SHA-256 y control de documentos alinean el sistema con la NOM-151-SCFI-2016, los Artículos 27 y 32-D del CFF y las obligaciones documentales del REPSE. |

El proyecto se ejecuta en **16 semanas y 500 horas** dentro de la residencia profesional, conforme al cronograma del anteproyecto [PRD §16].

---

## 13. Información de mercado no documentada

Las fuentes oficiales del proyecto no contienen los siguientes datos, que un MRD comercial suele incluir. No se estiman aquí para no introducir información no respaldada; deben definirse con la Dirección Comercial de PluriOne:

| Dato | Estado |
|---|---|
| Tamaño del mercado (TAM, SAM, SOM) y número de clientes potenciales | No documentado. |
| Volumen de expedientes procesados por cliente o por mes | Solo se documenta el tamaño de un expediente (de diez a varias decenas de documentos, H3). |
| Modelo de negocio y precio (licencia, suscripción o servicio) | No documentado. |
| Canales de venta y estrategia de comercialización | No documentado; el producto se integra al portafolio LegalTech de PluriOne. |
| Metas comerciales (clientes, ingresos, adopción) | No documentado. |
| Comparación funcional y de precios detallada contra Kofax TotalAgility y ABBYY Vantage | No documentado; solo su descripción general (sección 8). |
| Métricas de la línea base actual (horas por expediente, porcentaje de incumplimientos detectados) | El marco metodológico del anteproyecto prevé considerarlas, pero no se reportan valores. |

---

## 14. Criterios de éxito

Derivados de los objetivos y umbrales documentados [Anteproyecto; DG Caps. IV, VI y VII]:

| Criterio | Medida | Estado al 29/09/2026 |
|---|---|---|
| El motor detecta documentos faltantes, vencidos y anexos ausentes de forma automática. | Criterios de aceptación funcionales (DG §7.8). | Cumplido (PRD §14). |
| Los vencimientos se detectan antes de ocurrir. | Alertas con 30, 15 y 5 días de anticipación (RF-17). | Cumplido; notificación por correo pendiente. |
| Todo expediente del mismo tipo se evalúa con los mismos criterios. | Reglas por tipo de expediente en el catálogo (RF-06). | Cumplido. |
| Cada validación es demostrable ante una auditoría. | Bitácora inmutable y dictamen exportable (RF-23, RF-27). | Cumplido; el usuario autenticado se registrará con el Módulo 7. |
| El análisis de un documento es operativo en tiempo de revisión. | ≤ 25 s por documento de hasta 20 páginas (RNF-02). | Cumplido (≈ 13 s para 26 páginas), medido antes de la detección de sellos; por volver a medir ([análisis de brechas](ANALISIS_BRECHAS_MOTOR.md), §2.4). |
| El personal jurídico entiende el estado y los hallazgos sin conocimientos técnicos, en una pantalla de portátil. | Lenguaje llano en interfaz, alertas y reportes (RNF-08); vistas legibles a 1366 × 768 (RNF-07). | Cumplido (PRD §13.1, revisión del frontend). |
| El acceso está controlado por rol. | RF-25 y RF-26. | Pendiente. |
| La reducción del tiempo de revisión se confirma con el cliente. | Estimación del 90 % (DG §6.7). | Por medir con PluriOne en la evaluación post-implementación (semana 16). |

---

## 15. Riesgos de mercado

[DG Cap. VII §7.9 y Cap. VIII §8.7]

| Riesgo | Efecto en el mercado | Mitigación documentada |
|---|---|---|
| Los requisitos cambian durante el desarrollo o la regulación cambia. | El producto quedaría desactualizado. | Reglas configurables en la base de datos; Scrum incorpora cambios en cada sprint. |
| Baja precisión de la IA en cláusulas. | Pérdida de confianza del usuario. | Pruebas de precisión y revisión humana de los resultados dudosos; el veredicto es determinista. |
| Documentos escaneados de baja calidad. | Resultados poco fiables. | Detección de ilegibles, solicitud de recarga y confianza acotada por la calidad del OCR. |
| Dependencia de un proveedor externo de IA. | Indisponibilidad del análisis semántico; cambio de condiciones del proveedor. | Degradación controlada; el proveedor y el modelo se cambian por configuración, sin modificar el código. |
| Percepción de riesgo de privacidad al usar IA en la nube. | Resistencia a la adopción. | Solo viaja el texto extraído, cifrado y con Retención Cero de Datos; la transferencia debe declararse en el aviso de privacidad. |

---

## 16. Trazabilidad MRD → PRD

| Requisito de mercado | Requerimientos del producto (PRD) | Estado |
|---|---|---|
| MR-01 Completitud del expediente | RF-06, RIE-01, HU-09, HU-12 | Implementado |
| MR-02 Tipos de expediente | RF-01, HU-01, HU-02 | Implementado |
| MR-03 Anexos obligatorios | RF-07, RIE-02, HU-10 | Implementado |
| MR-04 Vigencia y alertas anticipadas | RF-15, RF-16, RF-17, RCV-01 a RCV-04, HU-13, HU-14 | Implementado (umbrales por configuración) |
| MR-05 Reglas configurables por sector | RF-06, RF-08, HU-09, HU-11 | Implementado |
| MR-06 Nuevos tipos de documento con criterios para la IA | RF-09, RDS-01, RDS-02, HU-24 | Parcial |
| MR-07 Lectura de PDF nativos y escaneados | RF-10, HU-18 | Parcial (texto plano de PDF nativos y escaneados; tablas y pares clave-valor pendientes: PRD, RF-10) |
| MR-08 Análisis de contenido explicable | RF-11, RF-13, RSC-01, RSC-02, HU-19, HU-20, HU-23 | Cumplido (cláusulas verificadas con cita literal, RSC-01; datos del firmante cotejados con los apoderados del poder o del acta, RSC-02 y RN-03, con decisión del analista: PRD §21.2) |
| MR-09 Decisión humana en casos dudosos | RF-14, RN-05, HU-21, HU-22 | Implementado |
| MR-10 Evidencia para auditorías | RF-23, RF-27, HU-28, HU-30 | Implementado (dictamen exportable, bitácora inmutable y su historial en el detalle del expediente) |
| MR-11 Detección de alteraciones | RF-03, RIE-03, HU-08 | Implementado |
| MR-12 Semáforo y alertas con acción correctiva | RF-18, RF-19, RF-21, HU-15, HU-16, HU-27; índice de cumplimiento del DOC-05 (PRD §10.5) | Implementado, con el índice de cumplimiento del DOC-05 (C6 del análisis de brechas) |
| MR-13 Reportes PDF y Excel | RF-22, RF-24, HU-26, HU-29 | Implementado (el tablero propio sustituye a Power BI: PRD §19) |
| MR-14 Notificación por correo | RF-20, HU-17 | Pendiente |
| MR-15 Acceso por rol | RF-25, RF-26, HU-05, HU-06, HU-31 | Pendiente |
| MR-16 Confidencialidad de los expedientes | RNF-04, RNF-05, RNF-06; PRD §12.5 | Parcial (minimización implementada; cifrado en reposo, TLS en el borde y red interna aislada pendientes) |
| MR-17 Despliegue en la infraestructura de PluriOne | RNF-11 | Implementado |
| MR-18 Búsqueda de expedientes | RF-05, HU-04 | Implementado |
| MR-19 Búsqueda conceptual en el acervo | RF-12 | Fuera del alcance de la residencia (PRD 2.1: sin historia de usuario ni prioridad, y no interviene en el dictamen) |
| MR-20 Recepción blindada de la evidencia | PLUS-01, PLUS-02, PLUS-03 (RCV-04, RSC-OPIN-SENT), HU-34 a HU-36 | Implementado (PRD §21.1; diagramas en `docs/uml/`) |
| MR-21 Custodia verificable ante auditorías externas | PLUS-04, PLUS-05, PLUS-06, HU-39 a HU-41 | Implementado (PRD §21.3; diagramas en `docs/uml/`) |
| MR-22 Consulta inmediata del documento con evidencia | PLUS-07 a PLUS-11, HU-42, HU-43 | Implementado (PRD §21.4; diagrama en `docs/uml/`) |
