# Motor de Validación de Cumplimiento Documental — CLAUDE.md

Residencia profesional para **PluriOne S.A. de C.V.** (Develop Talent & Technology). El motor dictamina el cumplimiento de expedientes jurídicos, corporativos y regulatorios en cinco niveles (DOC-05): reglas deterministas más una IA que solo extrae, con evidencia citada y ratificación humana.

---

## 1. Fuentes de verdad (en orden de prioridad)

1. `docs/ESPECIFICACIONES_DOC01_A_DOC08.txt` — texto íntegro de DOC-01 a DOC-08 (entrevistas, requisitos, regulaciones, SRS, validación y reglas, propuesta, backlog, arquitectura y BD).
2. `docs/PRD.md` — requerimientos, estado de implementación y extensiones PLUS (§21); `docs/MRD.md` — requisitos de mercado trazados al PRD.
3. `docs/ANALISIS_BRECHAS_MOTOR.md` — brechas vigentes; `docs/VALIDACION_CUANTITATIVA.md` — metodología y resultados de QA.
4. `docs/uml/` — diagramas PlantUML de cada requerimiento posterior al PRD 1.2 (índice en `docs/uml/README.md`).

`docs/AUDITORIA_TECNICA.md` es un **documento histórico de referencia** (14/09/2026): las fuentes vivas de estado y brechas son `PRD.md` y `ANALISIS_BRECHAS_MOTOR.md`.

**Prohibido inventar** tablas, nombres de producto, roles o categorías: toda decisión técnica se fundamenta en esos documentos.

---

## 2. Reglas del proyecto

- **No abrir, leer ni modificar `DOCUMENTO GENERAL.docx`** (entregable académico que gestiona el residente). La documentación se actualiza solo en los markdown del repositorio; los datos que parezcan requerir ese documento se toman de las fuentes de §1 o se piden al residente.
- **Documentar antes de implementar:** cada requerimiento nuevo lleva primero sus diagramas en `docs/uml/` y su trazabilidad en PRD y MRD (primer commit); después, la implementación con sus pruebas.
- Lo que no proviene del DOC-04 se marca como **extensión PLUS** y cita la norma que la respalda (DOC-03: ISO/IEC 25010, 27001, 30301, NOM-151, CFF, LFPDPPP); nunca se presenta como requerimiento original.
- **Módulo 7** (autenticación JWT y roles: RF-25, RF-26, HU-05, HU-06, HU-31) queda congelado hasta que el residente indique que empieza esa fase.
- Ante una petición de análisis o de propuesta, **presentar la propuesta y esperar aprobación** antes de tocar código. Cada mejora trae su análisis de segundo orden: qué evidencia se pierde, qué requisitos toca, qué pasa con los dictámenes y cachés existentes y qué pruebas dependen del comportamiento actual.
- Un problema encontrado dentro del alcance se corrige en el mismo trabajo, con una prueba de regresión que falle sin la corrección.
- Los commits se registran exclusivamente con el usuario configurado en el entorno local (Oliver Villanueva) con mensajes atómicos en español, sin líneas ni metadatos de coautoría externa. Formato *conventional commits*; el cuerpo explica el porqué, la evidencia y el resultado de las pruebas, y cita los requisitos (RF, HU, RN, reglas). No se versionan artefactos regenerados sin cambio real.
- No alterar tablas existentes sin migración idempotente. Código con tipado estático y manejo estricto de excepciones HTTP.
- Idioma de trabajo, documentación y commits: español.

---

## 3. Arquitectura (DOC-08)

Microservicios FastAPI desacoplados en `services/`, orquestados con Docker Compose.

| Servicio | Puerto | Responsabilidad | Datos |
|---|---|---|---|
| `core-service` | 8001 | Titulares, expedientes, documentos (Nivel 1), dictámenes y ratificación, semáforo, índice de cumplimiento, alertas, reportes PDF/Excel, bitácora sellada | PostgreSQL `plurione_compliance` |
| `rules-service` | 8002 | Catálogo DOC-05 (RIE, RCV, RSC, RDS), obligatorios por tipo de expediente, vigencia determinista (`POST /api/v1/reglas/evaluar-vigencia`) | La misma PostgreSQL, tablas propias |
| `ai-service` | 8003 | Niveles 3 y 4, chat documental, visor de evidencia | SQLite propia en `services/ai-service/data/` |
| `frontend` | 5173 | Interfaz oficial, React 19 (Vite) | — |

- `core-service` y `rules-service` definen cada uno un módulo `config.database` con el mismo nombre: **no se importan en el mismo proceso**. Los scripts usan subprocesos por servicio y las pruebas aíslan módulos con `tests/servicios.py:activar`.
- Bóveda física en `storage_vault/` (`STORAGE_VAULT_PATH` en Docker). El ai-service lee los binarios solo a través del core (`/documentos/{id}/contenido`, verificado por RIE-03) y persiste cada dictamen con `POST /api/v1/dictamenes`.
- SQLite del ai-service, indexada por SHA-256: `extracciones` y `palabras_ocr` (columna `version` = `version_lectura()`), `inferencias` (respuestas del modelo a temperatura 0.0; las del chat llevan el prefijo `chat:`) y `fichas_documento` (lo verificado en la última auditoría, ligado a su `dictamen_id`).
- **Estabilidad:** los clientes entre servicios usan `requests` síncrono con timeouts y excepciones traducidas (no migrar a async). Los contratos de API solo admiten campos opcionales nuevos; `GET /api/v1/health` lo consume `SystemHealth.jsx`. Cada `main.py` registra el middleware `errores_no_controlados` antes de CORS. Los `.env` nunca se versionan.
- Proveedor de inferencia: Groq Cloud, `qwen/qwen3.8-27b` (cambio respecto de Azure documentado en PRD §19). Al modelo solo viaja el texto extraído, nunca el documento. Plan gratuito: **8,000 tokens por minuto y 200,000 por día**.

---

## 4. Motor de validación (DOC-05)

### Nivel 1 — Integridad (core)
- Firma binaria (PDF, JPEG, PNG), 15 MB y huella SHA-256 (NOM-151).
- PLUS-01: una huella repetida en el mismo expediente responde 409 (`pg_advisory_xact_lock`). PLUS-02: un PDF con contraseña se custodia con un dictamen NO_CONFORME de origen `NIVEL_1`.
- RIE-03: toda lectura del binario recalcula la huella; si no coincide, el documento queda ALTERADO, con un dictamen NO_CONFORME y respuesta 409.

### Nivel 2 — Reglas deterministas (rules y core)
- Completitud contra los obligatorios del tipo de expediente que declara el rules-service (con respaldo DOC-02); los anexos RIE-02 se exigen solo si su documento principal está presente.
- Vigencia RCV, recalculada en cada consulta (RN-02): RCV-01 (días para el vencimiento; alertas a 30, 15 y 5 días) y caducidad estricta desde la emisión: RCV-02 comprobante de domicilio (90 días), RCV-03 constancia fiscal (90), RCV-04 opinión 32-D (30).
- Semáforo: NO_CONFORME si falta un obligatorio crítico o un anexo exigido, o si un documento vigente es NO_CONFORME o venció; EN_REVISION si hay obligatorios no críticos faltantes, documentos sin auditar, pendientes de ratificación o próximos a vencer; CONFORME solo con todo presente y conforme. **Subir archivos nunca aprueba un expediente.**
- Índice de cumplimiento (C6, PRD §10.5): cumplidas / (cumplidas + incumplidas + pendientes); el bloqueo por criticidad no altera el porcentaje.
- Las alertas se derivan de la evaluación (sin tabla); bandeja en `GET /api/v1/alertas`. La reevaluación programada (`REEVALUACION_INTERVALO_HORAS`) no ejecuta la IA.
- Bitácora: `motor/bitacora.registrar` es el único punto de escritura y sella cada evento en cadena (PLUS-04/05). Los triggers impiden modificar la bitácora y los dictámenes, salvo la ratificación, una sola vez.
- P5 (PRD §21.5): la reevaluación programada barre antes la integridad de toda la bóveda (`integridad.barrer`, PLUS-14, constancia VERIFICACION_INTEGRIDAD); cada reporte imprime el último sello de la cadena (PLUS-15); cada dictamen guarda `version_lectura` y `version_instrucciones`, protegidas por el trigger de RN-05.
- Excepciones del DOC-05, Tabla 1: sin texto suficiente (`pipelines/legibilidad.py`) el ai-service no llama al modelo y emite un dictamen de origen NIVEL_3_ILEGIBLE (no se ratifica como conforme); si Groq no responde, la auditoría entra en la cola de `pipelines/diferidos.py`, el core la marca (`/documentos/{id}/procesamiento-diferido`) y un ciclo la reintenta con espera de 15 min a 24 h.

### Nivel 3 — Extracción de texto (ai-service)
- Capa vectorial con PyMuPDF. Página escaneada: raster en grises a `OCR_DPI` (300), preprocesamiento OpenCV (normalización de la iluminación, filtro bilateral, Otsu con respaldo adaptativo) y Tesseract `spa`, en un pool único de `OCR_WORKERS` procesos (por defecto, los hilos lógicos).
- Lectura vigente: `VERSION_PIPELINE` 3.3. **Subir `VERSION_PIPELINE` al cambiar cualquier paso de la extracción**: la persistencia se invalida por versión.
- La auditoría (`/preparar` y `/analisis-semantico`) lee el documento completo. El chat de un documento sin auditar responde con la lectura parcial (`MAX_PAGINAS_OCR`) y programa la completa.
- Una sola lectura como fuente de verdad: texto, confianza y palabras con recuadro salen de la misma llamada a Tesseract, así que el dictamen y el visor ven lo mismo.
- Sellos en tinta de color (`pipelines/sellos.py`): apagados por defecto (`OCR_RELEER_SELLOS=false`), porque ningún DOC los exige; su retiro se decide con el Gold Standard escaneado. El Sello Digital SAT (DOC-08) se detecta en el texto.
- Visor de evidencia (HU-20, RF-13): páginas renderizadas desde el binario verificado y localización de citas (`POST /api/v1/ai/documentos/{id}/localizar`).

### Nivel 4 — Análisis semántico (ai-service)
- Groq a temperatura 0.0 con JSON estricto. **El modelo solo extrae**; titularidad, vigencia y estatus preliminar los calculan reglas deterministas. Titularidad por RFC o por razón social normalizada; sin RFC y con otra razón social → EN_REVISION; tipo incompatible con el registrado (`TIPOS_COMPATIBLES`) → EN_REVISION.
- Contexto: encabezado más fragmentos por BM25 (`pipelines/fragmentos.py`). BM25 léxico, sin embeddings: decisión documentada.
- Verificación de contenido RSC/RDS: `CUMPLE` solo con una cita literal anclada al texto (`cita_literal`, semejanza ≥ 0.93 para errores de OCR; **las cifras deben coincidir exactamente** y una paráfrasis no pasa). `NO_LOCALIZADO` o `NO_VERIFICABLE` → EN_REVISION; las RDS siempre pasan a ratificación (RDS-03). El sentido de la opinión 32-D (RSC-OPIN-SENT) se lee sin modelo; negativo → NO_CONFORME.
- RSC-02 (P2): firmantes de contrato o NDA y apoderados de poder o acta, con su cita; el core coteja firmante y apoderado en cada evaluación (RN-03).

### Chat documental (P4, PRD §21.4)
Orden de decisión de un turno (`controllers/analisis_controller.py`):

1. `forzar_modelo` en la petición → directo al modelo.
2. **T0** (`respuestas_directas.py`, PLUS-07): preguntas factuales y sugeridas, con la ficha de la auditoría, solo si es la del dictamen vigente de ese binario (`dictamen_id` y SHA-256).
3. **T1** (`pasajes.py`, PLUS-08): cláusula nombrada o monto → el renglón literal con su página, si hay un ganador claro; varias cantidades empatadas → modelo.
4. **T2** (PLUS-09): una pregunta puntual recibe `fragmentos.seleccionar_enfocado` y el estado breve; una general, el contexto amplio y el estado completo. Historial acotado y tope de respuesta propio.
5. **T3** (`cache_chat.py`, PLUS-10): clave exacta y, en el primer turno, clave de la pregunta normalizada (todas sus palabras y cifras). El estado del sistema forma parte de la clave.
6. **T4** (`presupuesto_tokens.py`, PLUS-11): si el turno no cabe en `GROQ_TOKENS_POR_MINUTO`, se acota el contexto y esa respuesta no se guarda bajo las claves del contexto completo. Los criterios se conservan en memoria; el dictamen se lee en vivo en cada turno.
7. Modelo.

Salvaguardas:
- Una respuesta sin modelo **nunca afirma que un dato no aparece**: sin el dato o sin un renglón que lo respalde, responde el modelo.
- Las faltas se atribuyen a la verificación del motor, y el estado dice «no extraído por el motor», nunca «no declarado».
- Las preguntas interpretativas y las que preguntan por la otra parte van al modelo.
- Cada cita «…» se marca como verificada contra el documento o el sistema.
- `origen_respuesta` ∈ {`MODELO`, `CACHE`, `DATOS_DEL_DICTAMEN`, `PASAJE_DEL_DOCUMENTO`}.

### Nivel 5 — Gobernanza humana
Bandas del DOC-08 §6.2: ≥ 0.85 CONFORME; de 0.70 a 0.84 y por debajo de 0.70, revisión humana. Una confianza baja **nunca** rechaza: el rechazo se reserva a hechos del documento (vigencia expirada, RFC ajeno, opinión en sentido negativo). La ratificación (RN-05) conserva el `estatus_preliminar`.

---

## 5. Frontend (`frontend/`, React 19)

- Estilo «White & Warm Minimalist»: blanco y neutros cálidos, sin gradientes, neones ni desenfoques. `Inter` para el texto y `JetBrains Mono` con cifras tabulares para huellas, folios, RFC y fechas. Iconos de `lucide-react` con `strokeWidth` 1.5.
- Usar exclusivamente tokens semánticos del sistema de diseño, definidos en `src/index.css` (`var(--ok)`, `var(--warn-bg)`, `var(--text-primary)`, `var(--s-4)`…), nunca valores hexadecimales literales en componentes; el tema oscuro redefine los mismos tokens. El color solo comunica estado y siempre va acompañado de su etiqueta.
- Las vistas usan las primitivas de `src/components/ui/` (exportadas en `ui/index.js`), no las clases `btn`, `badge`, `tag` o `card` escritas a mano. Todo cambio de una primitiva lleva su caso en `scripts/equivalencia-ui.jsx`.
- **Lenguaje llano (RNF-08):** ningún texto visible cita RF-, RN-, RNF-, HU-, DOC-, niveles del pipeline, el proveedor de IA ni códigos internos, salvo el código de una regla donde la identifica. El core redacta motivos, alertas y reportes con `motor/redaccion.py`.
- Estructura: hojas de estilo por contexto en `src/styles/`, importadas en orden por `App.css` (una regla nueva va en la hoja de su contexto); panel de IA en `components/documento-ia/`; detalle del expediente en `components/expedientes/`; modal compartido `DetalleDocumentoModal.jsx`.
- Reglas fijas de producto (el detalle está en PRD §13):
  - la URL con hash (`hooks/useRuta.js`) es la fuente de verdad de la sección, con inicio en Expedientes;
  - las métricas van solo en Expedientes y Reportes;
  - la Bóveda entra con solo los documentos vigentes;
  - el éxito de una auditoría no se anuncia con un aviso flotante;
  - la meta de cada respuesta del chat indica su procedencia.
- El catálogo `#/ui` (`src/dev/`) solo existe en desarrollo: nunca importar `src/dev/` de forma estática.

---

## 6. Verificación

- **Core y rules:** `pytest tests/` desde `motor de validacion/` (requiere PostgreSQL con el seed). `tests/bd_pruebas.py` recrea `plurione_compliance_test`: **nunca correr pruebas contra `plurione_compliance`**, porque la bitácora y los dictámenes son inmutables. Las suites que cuentan eventos de bitácora cuentan solo los propios.
- **ai-service:** `cd services/ai-service && pytest tests/` (offline; con el servicio en marcha, agregar `--deselect tests/test_niveles_3_4.py::test_niveles_3_4` para no consumir tokens). `tests/conftest.py` da a cada prueba una SQLite temporal. `test_niveles_3_4.py` requiere el servicio en vivo y consume tokens de Groq (se omite si el servicio no está).
- **Frontend:** `npm run lint`, `npm run test:ui` (equivalencia de marcado) y `npm run build`.
- **Regresión visual** (servicios y `npm run dev` en marcha; Chrome): `python scripts/regresion_visual.py capturar base` antes del cambio, `capturar actual` después y `comparar`. Un cambio sin efecto visual da 0 capturas distintas (160 capturas). Unos cientos de píxeles en letras sueltas de una sola combinación de tamaño y tema son ruido de suavizado del navegador: se descartan repitiendo solo esa combinación (`TAMANOS` y `TEMAS` del módulo) y comparando contra la base. Comportamiento: `scripts/prueba_sondeo_colgado.py` y `scripts/prueba_carga_fallida.py`.
- **CI** (`.github/workflows/ci.yml`): PostgreSQL 17 con `setup_postgres.py`, pytest de los tres servicios, y lint, `test:ui` y build del frontend.
- **Validación cuantitativa** (`services/ai-service/evaluacion/`, `docs/VALIDACION_CUANTITATIVA.md`):
  - Gold Standard de 42 casos ficticios, más un contrato de 20 páginas, congelado por SHA-256 (`*.sha256`, `.gitattributes -text`). Un cambio de la anotación exige un commit propio.
  - `python -m evaluacion.medir_chat --etiqueta <nombre> [--bateria corta|extensa] [--modo grabar]`. En modo reproducir (el predeterminado) no consume tokens y aborta si falta una huella del casete; en modo grabar llama a Groq solo por lo que falte. Las baterías corren sin el presupuesto de T4; lo mide `python -m evaluacion.escenario_contencion`.
  - Las corridas con Groq se planean según 8,000 tokens por minuto y 200,000 por día. Resultados en `docs/resultados_validacion/`.

| Área | Pruebas |
|---|---|
| Nivel 1 e ingesta (P1) | `test_pipeline_nivel1`, `test_ingesta_robustez`, `test_ingesta_blindada` |
| Dictámenes, semáforo, alertas, reportes, índice | `test_dictamenes_semaforo`, `test_tipos_anexos_alertas`, `test_indice_cumplimiento` |
| Representación (P2) y custodia (P3) | `test_representacion_legal`, `test_cadena_custodia`; ai: `test_representacion` |
| Integridad permanente y excepciones (P5) | `test_integridad_permanente`, `test_dictamen_reproducible`, `test_excepciones_doc05`; ai: `test_excepciones_doc05` |
| Esquemas, errores y rules | `test_esquema_bd`, `test_esquema_rules`, `test_errores_core`, `test_errores_rules`, `test_rules_service`; ai: `test_errores_no_controlados` |
| Nivel 3 (ai) | `test_iluminacion`, `test_sellos`, `test_visor_documento`, `test_optimizaciones`, `test_cache_y_lectura` |
| Nivel 4 (ai) | `test_contenido_titularidad`, `test_vigencia_dictamen`, `test_opinion_cumplimiento`, `test_persistencia_dictamen` |
| Chat P4 (ai) | `test_respuestas_directas`, `test_pasajes`, `test_contexto_enfocado`, `test_contexto_chat`, `test_cache_chat`, `test_presupuesto_tokens` |
| Evaluación (ai) | `test_metricas`, `test_gold_standard`, `test_entorno_evaluacion`, `test_bateria_chat` |

---

## 7. Variables de entorno

| Variable | Valor por defecto | Uso |
|---|---|---|
| `GROQ_API_KEY` | — | Clave de Groq (`services/ai-service/.env`; en Docker, el `.env` de la raíz) |
| `GROQ_MODEL` / `GROQ_TEMPERATURE` | `qwen/qwen3.8-27b` / `0.0` | Modelo y temperatura (0.0: reproducible y cacheable) |
| `GROQ_TIMEOUT` / `GROQ_MAX_RETRIES` | `30` / `2` | Única capa de reintentos: la del SDK, con `Retry-After` |
| `GROQ_MAX_TOKENS` | `1000` | Tope de respuesta de la auditoría |
| `GROQ_CACHE_INFERENCIAS` | `true` | Reutiliza respuestas idénticas (auditoría y chat) |
| `GROQ_TOKENS_POR_MINUTO` | `8000` | Presupuesto de T4; `0` lo desactiva |
| `CHAT_MAX_TOKENS` | `600` | Tope de respuesta del chat |
| `CHAT_PRESUPUESTO_PUNTUAL` / `CHAT_FRAGMENTOS_PUNTUALES` | `3000` / `3` | Contexto enfocado de T2 |
| `CHAT_MENSAJES_HISTORIAL` / `CHAT_CARACTERES_TURNO_ASISTENTE` | `4` / `400` | Historial acotado de T2 |
| `CHAT_TTL_CRITERIOS_SEGUNDOS` | `300` | Criterios del catálogo en memoria (T4) |
| `OCR_LANG` / `OCR_DPI` / `OCR_WORKERS` | `spa` / `300` / hilos lógicos | OCR del Nivel 3 |
| `OCR_RELEER_SELLOS` | `false` | Sellos en tinta de color |
| `MAX_CARACTERES_CONTEXTO` / `MAX_CARACTERES_VERIFICACION` | `6500` / `9500` | Contexto de la auditoría y de la verificación |
| `MAX_PAGINAS_OCR` | `6` | Lectura parcial del chat sin auditoría |
| `UMBRAL_CONFIANZA_CONFORME` / `UMBRAL_CONFIANZA_HITL` | `0.85` / `0.70` | Bandas del Nivel 5 |
| `CORE_BASE_URL` / `RULES_BASE_URL` | `:8001` / `:8002` | Clientes del ai-service |
| `REEVALUACION_INTERVALO_HORAS` (core) | `24` | Reevaluación programada; `0` la desactiva |
| `BARRIDO_INTEGRIDAD` (core) | `true` | Barrido de integridad de la bóveda en cada reevaluación (PLUS-14) |
| `LEGIBILIDAD_MIN_CARACTERES` / `LEGIBILIDAD_MIN_CONFIANZA` | `50` / `0.40` | Umbral de «Documento ilegible» (P5) |
| `DIFERIDOS_INTERVALO_MINUTOS` / `DIFERIDOS_MAX_INTENTOS` | `15` / `6` | Ciclo de procesamiento diferido (P5); `0` lo desactiva |
| `AUTO_SEED` (rules) / `DB_ECHO` (core, rules) | `true` / `false` | Precarga idempotente del catálogo / imprimir SQL |
| `STORAGE_VAULT_PATH` | `storage_vault/` | Bóveda física |
| `VITE_CORE_URL` / `VITE_RULES_URL` / `VITE_AI_URL` | `:8001` / `:8002` / `:8003` | URLs del frontend |

---

## 8. Arranque

- Servicios: `cd services/<core|rules|ai>-service && python main.py`; frontend: `cd frontend && npm run dev`.
- Todo con Docker Compose: `docker compose up -d --build` (PostgreSQL 5432 y los puertos de §3).
- Base de datos (tablas de todos los servicios y seed): `python scripts/setup_postgres.py`; solo tablas: `python scripts/crear_tablas.py`; solo el catálogo: `python scripts/seed_reglas_validacion.py`.
- Salud: `GET :8001|:8002|:8003/api/v1/health` (el del ai-service incluye `motor_inferencia`); Swagger en `/docs` de cada servicio.
