# Motor de Validación de Cumplimiento Documental — CLAUDE.md

Residencia profesional para **PluriOne S.A. de C.V.** (Develop Talent & Technology). El motor dictamina el cumplimiento de expedientes jurídicos, corporativos y regulatorios en cinco niveles (DOC-05): reglas deterministas más una IA que solo extrae, con evidencia citada y ratificación humana.

---

## 1. Fuentes de verdad (en orden de prioridad)

1. `docs/ESPECIFICACIONES_DOC01_A_DOC08.txt` — texto íntegro de DOC-01 a DOC-08 (entrevistas, requisitos, regulaciones, SRS, validación y reglas, propuesta, backlog, arquitectura y BD).
2. `docs/PRD.md` — requerimientos del producto, consolidados de los DOC (anteriores al desarrollo); `docs/MVP.md` — producto mínimo viable (DOC-07: motor de reglas sin IA, Sprints 1 y 2); `docs/ESTADO_DEL_DESARROLLO.md` — estado de cada requerimiento, resultados medidos, cambios y extensiones PLUS (§6).
3. `docs/ANALISIS_BRECHAS_MOTOR.md` — brechas vigentes; `docs/VALIDACION_CUANTITATIVA.md` — metodología y resultados de QA.
4. `docs/uml/` — diagramas PlantUML de cada requerimiento posterior al PRD 1.2 (índice en `docs/uml/README.md`).

**Prohibido inventar** tablas, nombres de producto, roles o categorías: toda decisión técnica se fundamenta en esos documentos.

---

## 2. Reglas del proyecto

- **No abrir, leer ni modificar `DOCUMENTO GENERAL.docx`** (entregable académico que gestiona el residente). La documentación se actualiza solo en los markdown del repositorio; los datos que parezcan requerir ese documento se toman de las fuentes de §1 o se piden al residente.
- **Documentar antes de implementar:** cada requerimiento nuevo lleva primero sus diagramas en `docs/uml/` y su trazabilidad en el PRD (lo que se pide) y en ESTADO_DEL_DESARROLLO (estado y, si es PLUS, su fundamento) (primer commit); después, la implementación con sus pruebas.
- **Alcance:** se implementa lo que pide la documentación (DOC-04: RF, RNF y HU; reglas del DOC-05; arquitectura del DOC-08), en su versión mínima que lo cumpla. No se proponen extensiones nuevas salvo que el residente las pida: la entrega es el repositorio dockerizado que los agentes de PluriOne levantan y prueban con datos ficticios, y cada extra es superficie que puede fallar en esa prueba (depuración del 02/10/2026, ESTADO_DEL_DESARROLLO §6.8). Antes de proponer algo, citar el DOC que lo pide.
- Si el residente pide algo que no proviene del DOC-04, se marca como **extensión PLUS** y cita la norma que la respalda (DOC-03: ISO/IEC 25010, 27001, 30301, NOM-151, CFF, LFPDPPP); nunca se presenta como requerimiento original.
- **Funciona con datos ficticios y reales:** ninguna función puede castigar un documento de prueba por serlo (un RFC ficticio se acepta con advertencia; un PDF hecho en un procesador de texto no es sospechoso por eso).
- **Módulo 7** (autenticación JWT y roles: RF-25, RF-26, HU-05, HU-06, HU-31, con el correo RF-20) implementado del 14 al 15/10/2026 por fases (F1 core, F2 rules y ai, F3 MFA, F4 frontend, F5 correo, F6 pruebas y entrega). Diseño y matriz de permisos: PRD §5.1 y §5.2; diagramas `m7-*` y `rf20-*` en `docs/uml/`.
- Ante una petición de análisis o de propuesta, **presentar la propuesta y esperar aprobación** antes de tocar código. Cada mejora trae su análisis de segundo orden: qué evidencia se pierde, qué requisitos toca, qué pasa con los dictámenes y cachés existentes y qué pruebas dependen del comportamiento actual.
- Un problema encontrado dentro del alcance se corrige en el mismo trabajo, con una prueba de regresión que falle sin la corrección.
- Los commits se registran con el usuario configurado en el entorno local (Oliver Villanueva) y llevan al final `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. Un commit por cambio real, en español: la documentación de un cambio va en su mismo commit. Formato *conventional commits*; el cuerpo explica el porqué, la evidencia y el resultado de las pruebas, y cita los requisitos (RF, HU, RN, reglas). No se versionan artefactos regenerados sin cambio real.
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
- Fechas en UTC: las columnas son `TIMESTAMP` sin zona y los engines del core y del rules fijan la sesión de PostgreSQL en UTC (`connect_args`); la API las devuelve sin zona, el frontend las lee con `aFecha` (`utils/format.js`) y los días del negocio salen de `ZONA_HORARIA`.
- SQLite del ai-service, indexada por SHA-256: `extracciones` y `palabras_ocr` (columna `version` = `version_lectura()`), `inferencias` (respuestas del modelo a temperatura 0.0; las del chat llevan el prefijo `chat:`) y `fichas_documento` (lo verificado en la última auditoría, ligado a su `dictamen_id`).
- **Módulo 7 (PRD §5.1 y §5.2):** `config/seguridad.py` (roles, JWT HS256, token SISTEMA, bcrypt) no depende de la base y es **idéntico en los tres servicios**: se edita una copia y se copia a las otras dos (`tests/test_seguridad_paridad.py`). Cada servicio declara el permiso de cada endpoint con su `config/autorizacion.py`:
  - core: confirma la cuenta en la base en cada petición y autoriza con el rol guardado; la bitácora registra `actor.email` (la cuenta en sesión o, con un token SISTEMA, la persona de `X-Usuario-Actor`);
  - rules: la misma confirmación sobre la tabla `usuarios` de la base compartida;
  - ai: confirma la cuenta con `GET /auth/me` del core (60 s en memoria por token). Su dependencia es `async` para fijar la persona en una variable de contexto que llega al endpoint síncrono; los clientes del core y del rules envían `autorizacion.cabeceras_servicio()` (folio, token SISTEMA y `X-Usuario-Actor`), y las tareas de fondo, sin persona.
  El segundo factor TOTP opcional (F3) vive solo en el core (`motor/segundo_factor.py`, pyotp): con MFA habilitado, `POST /auth/login` sin `codigo` responde `{requiere_codigo: true}` sin token.
  Un endpoint nuevo lleva su fila en la matriz del PRD §5.1 y en la prueba de matriz de su servicio (`tests/test_permisos_roles.py`, `tests/test_rules_autorizacion.py`, `services/ai-service/tests/test_autorizacion_ai.py`), que fallan si falta.
- **Folio de seguimiento (PLUS-21):** cada servicio registra `observabilidad.middleware` (acepta o crea `X-Request-ID`, lo devuelve y escribe una línea JSON por petición); los clientes entre servicios envían `headers=observabilidad.cabeceras()` y la bitácora guarda `id_peticion` en el detalle.
- **Estabilidad:** los clientes entre servicios usan `requests` síncrono con timeouts y excepciones traducidas (no migrar a async). Los contratos de API solo admiten campos opcionales nuevos; `GET /api/v1/health` lo consume `SystemHealth.jsx`. Cada `main.py` registra el middleware `errores_no_controlados` antes de CORS (un carácter nulo en los datos responde 422) y `cabeceras_seguridad` (`nosniff`, CORP `same-origin`, `Cache-Control: no-store` salvo que la ruta defina la suya; Q-c). Los `.env` nunca se versionan.
- Proveedor de inferencia: Groq Cloud, `qwen/qwen3.8-27b` (cambio respecto de Azure documentado en ESTADO_DEL_DESARROLLO §4). Al modelo solo viaja el texto extraído, nunca el documento. Plan gratuito: **8,000 tokens por minuto y 200,000 por día**.

---

## 4. Motor de validación (DOC-05)

### Nivel 1 — Integridad (core)
- Firma binaria (PDF, JPEG, PNG), 15 MB y huella SHA-256 (NOM-151).
- PLUS-01: una huella repetida en el mismo expediente responde 409 (`pg_advisory_xact_lock`). PLUS-02: un PDF con contraseña se custodia con un dictamen NO_CONFORME de origen `NIVEL_1`.
- RIE-03: toda lectura del binario recalcula la huella; si no coincide, el documento queda ALTERADO, con un dictamen NO_CONFORME y respuesta 409.
- RNF-04: la bóveda se escribe cifrada (`config/cifrado_boveda.py`, AES-256-GCM, `BOVEDA_LLAVE`) y se lee solo por `motor/integridad.py`, que descifra antes de recalcular la huella (siempre la del original). Un archivo cifrado que no supera la etiqueta GCM es una alteración (RIE-03); una llave distinta o ausente es `LlaveBovedaError` (503) y **nunca** marca un documento. Toda lectura nueva de la bóveda pasa por `integridad`; los archivos en claro anteriores se siguen leyendo (`scripts/cifrar_boveda.py` los cifra).

### Nivel 2 — Reglas deterministas (rules y core)
- Completitud contra los obligatorios del tipo de expediente que declara el rules-service (con respaldo DOC-02); los anexos RIE-02 se exigen solo si su documento principal está presente.
- Tipos de documento (RF-09): los 23 del catálogo base (21 tipos del DOC-02, cuyas Tablas 2 a 4 suman 22 filas porque el poder notarial aparece en la corporativa y en la jurídica, más la opinión de cumplimiento 32-D y la carátula bancaria que ya custodiaba el expediente B2B; `config/catalogo.py`) más los declarados por reglas RDS (`GET /reglas/tipos-documento`; `motor/tipos_documento.py` los admite en la carga si están activos y registra sus nombres). La CHECK de `documentos.tipo_documento` valida el formato del código; la existencia la valida la API. En el frontend, `registrarTiposDeclarados` (constants.js) los incorpora al catálogo al recibir las reglas.
- Vigencia RCV, recalculada en cada consulta (RN-02): RCV-01 (días para el vencimiento; alertas a 30, 15 y 5 días) y caducidad estricta desde la emisión: RCV-02 comprobante de domicilio (90 días), RCV-03 constancia fiscal (90), RCV-04 opinión 32-D (30).
- Semáforo: NO_CONFORME si falta un obligatorio crítico o un anexo exigido, o si un documento vigente es NO_CONFORME o venció; EN_REVISION si hay obligatorios no críticos faltantes, documentos sin auditar, pendientes de ratificación o próximos a vencer; CONFORME solo con todo presente y conforme. **Subir archivos nunca aprueba un expediente.**
- Índice de cumplimiento (C6, PRD §10.5): cumplidas / (cumplidas + incumplidas + pendientes); el bloqueo por criticidad no altera el porcentaje.
- Las alertas se derivan de la evaluación (sin tabla); bandeja en `GET /api/v1/alertas`. Los umbrales de anticipación de «Próximo a vencer» y del correo (HU-14, RF-17) salen de `motor/umbrales.py` en cada evaluación: los guarda el administrador desde el detalle de RCV-01 (`PUT /configuracion/umbrales-vencimiento`, tabla `parametros_sistema`) y, sin valor guardado, rige `UMBRALES_ALERTA_VENCIMIENTO`; la gráfica de vencimientos usa los mismos. La reevaluación programada (`REEVALUACION_INTERVALO_HORAS`) no ejecuta la IA.
- Correo (RF-20, `motor/notificaciones.py`, PRD §5.2): `cumplimiento.sincronizar` avisa el paso a NO_CONFORME (salvo la apertura) y la reevaluación programada, el umbral de vencimiento más cercano alcanzado (una vez por documento, umbral y fecha), a los VALIDADOR activos asignados. Cada aviso es un evento `NOTIFICACION_CORREO` (ENVIADO, FALLIDO, SIN_DESTINATARIOS, ENVIO_DESACTIVADO); el envío se encola al confirmar la transacción y lo hace un hilo propio. Sin `SMTP_HOST`, apagado.
- Bitácora: `motor/bitacora.registrar` es el único punto de escritura y sella cada evento en cadena (PLUS-04/05). Los triggers impiden modificar la bitácora y los dictámenes, salvo la ratificación, una sola vez.
- P5 (ESTADO_DEL_DESARROLLO §6.5): la reevaluación programada barre antes la integridad de toda la bóveda (`integridad.barrer`, PLUS-14, constancia VERIFICACION_INTEGRIDAD); cada reporte imprime el último sello de la cadena (PLUS-15); cada dictamen guarda `version_lectura` y `version_instrucciones`, protegidas por el trigger de RN-05.
- Excepciones del DOC-05, Tabla 1: sin texto suficiente (`pipelines/legibilidad.py`) el ai-service no llama al modelo y emite un dictamen de origen NIVEL_3_ILEGIBLE (no se ratifica como conforme); si Groq no responde, la auditoría entra en la cola de `pipelines/diferidos.py`, el core la marca (`/documentos/{id}/procesamiento-diferido`) y un ciclo la reintenta con espera de 15 min a 24 h.

### Nivel 3 — Extracción de texto (ai-service)
- Capa vectorial con PyMuPDF. Página escaneada: raster en grises a `OCR_DPI` (300), preprocesamiento OpenCV (normalización de la iluminación, filtro bilateral, Otsu con respaldo adaptativo) y Tesseract `spa`, en un pool único de `OCR_WORKERS` hilos (por defecto, los hilos lógicos; cada uno lanza su proceso de Tesseract). La lectura completa (auditoría) alimenta el pool en flujo continuo, con hasta 2 × `OCR_WORKERS` páginas en vuelo; la lectura parcial del chat va por tandas, porque su corte temprano depende del texto de cada tanda. Toda página pasa por `_ocr_sobre_imagen` (las pruebas que vigilan un OCR repetido parchean esa función). Topes por página: `OCR_TIMEOUT_PAGINA_SEGUNDOS` corta un Tesseract colgado (`TiempoOcrExcedidoError`, 400) y `OCR_MAX_MEGAPIXELES_PAGINA` baja la resolución de una página o imagen enorme; las de tamaño normal se leen igual.
- Lectura vigente: `VERSION_PIPELINE` 3.3. **Subir `VERSION_PIPELINE` al cambiar cualquier paso de la extracción**: la persistencia se invalida por versión.
- La auditoría (`/preparar` y `/analisis-semantico`) lee el documento completo de una vez, en flujo continuo. El chat de un documento sin auditar responde con la lectura parcial (`MAX_PAGINAS_OCR`) y programa la completa.
- Lectura anticipada (RNF-02): al custodiar, el frontend pide `POST /ai/documentos/{id}/anticipar` y el documento se lee de fondo, sin el modelo. El pool de OCR (`_PoolPrioritario`) atiende primero las páginas de primer plano (auditoría, chat, visor); una lectura de fondo lleva un `Turno` de prioridad `FONDO` que se promueve si alguien pide ese documento. Tesseract es el 95 % del tiempo de una página: no hay perilla del OCR que lo baje (VALIDACION §10.3).
- Una sola lectura como fuente de verdad: texto, confianza y palabras con recuadro salen de la misma llamada a Tesseract, así que el dictamen y el visor ven lo mismo.
- Sello Digital SAT (DOC-08): `pipelines/sellos.py` lo detecta en el texto. La lectura de sellos en tinta de color se retiró (ESTADO_DEL_DESARROLLO §6.8); la versión de lectura conserva «sin-sellos» para no invalidar las extracciones guardadas.
- Visor de evidencia (HU-20, RF-13): páginas renderizadas desde el binario verificado y localización de citas (`POST /api/v1/ai/documentos/{id}/localizar`).

### Nivel 4 — Análisis semántico (ai-service)
- Groq a temperatura 0.0 con JSON estricto. **El modelo solo extrae**; titularidad, vigencia y estatus preliminar los calculan reglas deterministas. Titularidad por RFC o por razón social normalizada, contra el titular del expediente que da el core en la ficha del documento (los de la petición solo valen para un texto suelto); sin RFC y con otra razón social → EN_REVISION; tipo incompatible con el registrado (`TIPOS_COMPATIBLES`) → EN_REVISION con el único motivo «Discrepancia de documento…», que precede a cualquier otro: al archivo no se le aplican la vigencia, los elementos RSC/RDS ni la representación del tipo esperado, y el dictamen persistido no lleva sus fechas (ESTADO_DEL_DESARROLLO §6.9). La respuesta trae `descripcion_coherente`, el motivo del estatus vigente que muestra el veredicto. Solo con discrepancia, una consulta breve aparte (`SYSTEM_PROMPT_NOMBRE`, ≈ 500 tokens) obtiene `nombre_documento_real`, que llega al motivo, a la interfaz, al chat y a `dictamenes_auditoria.nombre_documento_real`. **No agregar campos a la extracción principal:** cambiar su prompt invalida la caché de inferencias y las casetes del Gold Standard.
- Contexto: encabezado más fragmentos por BM25 (`pipelines/fragmentos.py`). BM25 léxico, sin embeddings: decisión documentada.
- Verificación de contenido RSC/RDS: las instrucciones exigen el elemento expreso (una mención de paso o una definición no lo prueban). `CUMPLE` solo con una cita literal anclada al texto (`cita_literal`, semejanza ≥ 0.93 para errores de OCR; **las cifras deben coincidir exactamente** y una paráfrasis no pasa) y sin una observación que declare una deducción (`declara_deduccion`: «implícitamente», «se infiere»… → NO_VERIFICABLE). `NO_LOCALIZADO` o `NO_VERIFICABLE` → EN_REVISION; las RDS siempre pasan a ratificación (RDS-03). El sentido de la opinión 32-D (RSC-OPIN-SENT) se lee sin modelo; negativo → NO_CONFORME.
- RSC-02 (P2): firmantes de contrato o NDA y apoderados de poder o acta, con su cita; el core coteja firmante y apoderado en cada evaluación (RN-03). Un apoderado sin cargo cuya cita verificada le confiere un poder recibe «Apoderado» (`representacion._cargo`).

### Chat documental (P4, ESTADO_DEL_DESARROLLO §6.4)
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

- Estilo «White & Warm Minimalist»: blanco y neutros cálidos, sin gradientes, neones ni desenfoques. La pantalla de acceso (`components/sesion/PantallaAcceso.jsx`, rediseñada el 15/10/2026 con la guía de Impeccable) hace una pregunta a la vez (correo, contraseña y, con MFA, el código; `InicioSesion.jsx`), a pantalla completa y sin caja, con la secuencia de pasos arriba; el correo no se valida por separado, para no revelar qué cuentas existen. Ni esa pantalla ni su indicador de servicios afirman nada que el sistema no haga: el indicador consulta la salud real y dice «Conexión cifrada» solo bajo HTTPS. `Inter` para el texto y `JetBrains Mono` con cifras tabulares para huellas, folios, RFC y fechas. Iconos de Phosphor en peso regular (duotone en la sección activa del menú) y solo tres tamaños: 12, 14 y 16 (única excepción comentada: el cargador de la perilla del interruptor de reglas). Se importan siempre de `components/iconos.js`, nunca de `@phosphor-icons/react`: lo genera `npm run iconos` (`scripts/generar-iconos.mjs`) con los iconos usados y solo los pesos que cada archivo escribe literalmente en `weight`, y `test:ui` falla si está desactualizado. Un icono sin `aria-label` sale con `aria-hidden`. La marca del sistema es `LogoMotor.jsx` (SealCheck relleno, la misma figura que `public/favicon.svg`).
- Usar exclusivamente tokens semánticos del sistema de diseño, definidos en `src/index.css` (`var(--ok)`, `var(--warn-bg)`, `var(--text-primary)`, `var(--s-4)`…), nunca valores hexadecimales literales en componentes; el tema oscuro redefine los mismos tokens. Los espaciados (`padding`, `margin`, `gap`) usan la escala `--s-1` a `--s-10`, con los medios pasos `--s-1-5` (6 px) y `--s-2-5` (10 px); solo los ajustes ópticos de 1 a 3 px y los 7 px de las etiquetas van escritos (`verificar-logica.mjs` lo comprueba). El color solo comunica estado y siempre va acompañado de su etiqueta.
- Las vistas usan las primitivas de `src/components/ui/` (exportadas en `ui/index.js`), no las clases `btn`, `badge`, `tag` o `card` escritas a mano. Todo cambio de una primitiva lleva su caso en `scripts/equivalencia-ui.jsx`.
- Sin código repetido entre vistas: la insignia de un estado del dominio es `EstadoBadge.jsx` (ESTADO_BADGE o ESTADO_DOCUMENTO); las iniciales del titular, `ui/Avatar`; todo buscador filtra con `utils/busqueda.js` (`normalizar` y `coincideEn`: sin acentos y con varias palabras, igual que Ctrl+K); la lista de alertas de varios expedientes sale de `utils/alertas.js`; `plural()` vive en `utils/format.js`.
- **Lenguaje llano (RNF-08):** ningún texto visible cita RF-, RN-, RNF-, HU-, DOC-, niveles del pipeline, el proveedor de IA ni códigos internos, salvo el código de una regla donde la identifica. El core redacta motivos, alertas y reportes con `motor/redaccion.py`.
- Estructura: hojas de estilo por contexto en `src/styles/`, importadas en orden por `App.css` (una regla nueva va en la hoja de su contexto); panel de IA en `components/documento-ia/`; detalle del expediente en `components/expedientes/`; modal compartido `DetalleDocumentoModal.jsx`.
- Reglas fijas de producto (el detalle está en PRD §13):
  - la URL con hash (`hooks/useRuta.js`) es la fuente de verdad de la sección, con inicio en Expedientes;
  - las métricas van solo en Expedientes; Reportes empieza con las gráficas;
  - ninguna vista repite otra ni un botón lleva a donde el usuario ya está (ESTADO_DEL_DESARROLLO §3, 04/10/2026); un filtro que una vista pide a otra viaja por `filtroPendiente` (App.jsx);
  - la Bóveda entra con solo los documentos vigentes;
  - con su servicio caído y sin datos que mostrar, una vista usa `sinRespuesta` (components/sinRespuesta.js), nunca el estado de lista vacía: Alertas no puede decir que todo cumple si el core no responde; mientras carga, su esqueleto; y una lista que no llegó conserva la anterior (`utils/carga.js`);
  - el éxito de una auditoría no se anuncia con un aviso flotante;
  - la meta de cada respuesta del chat indica su procedencia.
- **Sesión y roles (Módulo 7):**
  - `services/sesion.js` guarda el token y el perfil en `sessionStorage`; `api.js` envía `Authorization: Bearer` en toda petición y descarga, cierra la sesión ante un 401 y pide el cambio de contraseña ante el 403 de contraseña temporal.
  - `App.jsx` monta una puerta: inicio de sesión (`components/sesion/`), cambio obligatorio y luego el sistema del rol. Las secciones y la pantalla de inicio de cada rol, y la matriz de permisos, viven en `utils/permisos.js` (probados en `verificar-logica`).
  - Toda acción de escritura nueva se envuelve con `usePermiso('operar' | 'administrarReglas' | 'tipoDocumentoNuevo' | 'gestionarUsuarios')`: la interfaz oculta y el servicio responde 403 de todos modos. El hook va en el componente que pinta el control (oxlint no detecta un identificador no definido).
  - Una imagen que exige la sesión se pide con `useImagenAutenticada` (un `<img src>` no envía el token), como las páginas del visor.
  - Vistas nuevas: `usuarios/` (solo ADMIN) y `ConsultaTab.jsx` (CONSULTA, solo `GET /expedientes/asignados`). El QR del MFA usa `qrcode`, cargado solo al abrir su ventana.
- El catálogo `#/ui` (`src/dev/`) solo existe en desarrollo: nunca importar `src/dev/` de forma estática.
- Fase B: `PaletaComandos.jsx` (Ctrl+K, montada en `App.jsx`; búsqueda en `utils/busqueda.js`), `FolioExpediente.jsx` para todo folio mostrado fuera de su expediente (`enfocable={false}` dentro de un botón), `toast.*(titulo, detalle, { accion })` para un cambio reversible (nunca para la ratificación), `Destello` con su check al pasar a conforme y el anillo de `AuditarPendientes`.
- Movimiento (`utils/movimiento.js`, sin librerías; **única excepción, aprobada el 15/10/2026:** Motion (`motion/react`, con `LazyMotion` y `domAnimation`) solo en `components/sesion/` para la pantalla de acceso, con `MotionConfig reducedMotion="user"` y la curva `SALIDA_EXPONENCIAL`, sin rebotes): duraciones 150/240 ms con la curva del sistema y toda animación respeta «reducir movimiento». Un elemento que sale usa `animarSalida` (copia inerte; así cierra `Modal`) o `usePresencia` (sigue montado lo que dura su salida, como `expedientes/Desplegable.jsx`); el cambio de sección pasa por `conTransicion` (View Transitions, en `useRuta`). Una lista animable usa `useDesplazamiento` y marca cada elemento con `data-flip` (su id, nunca el índice) y `style={{ '--i': i }}` para la entrada escalonada de `styles/movimiento.css`, que va al final de `App.css`.
- Carga por vista: `App.jsx` importa con `React.lazy` todas las vistas salvo Expedientes (la de inicio). Recharts solo se importa desde `components/graficas/` (Reportes).
- Gráficas (`components/graficas/`): `comun.jsx` (tarjeta, leyenda, tooltip y «Ver datos»), `estilo.js` (ejes, retícula, separación, `animar()`) y la lógica sin React en archivos `.js`. Cada gráfica lleva leyenda con cifras, tooltip y tabla de datos. Sus colores son los tokens `--chart-*` de `index.css`, validados con un verificador de paletas; uno nuevo se valida antes de usarse. El texto nunca lleva el color de la serie. Los reportes PDF y Excel usan los mismos colores (`GRAFICA_ESTADO`, `GRAFICA_SEVERIDAD` en `motor/reportes.py`).

---

## 6. Verificación

- **Core y rules:** `pytest tests/` desde `motor de validacion/` (requiere PostgreSQL con el seed). `tests/bd_pruebas.py` recrea `plurione_compliance_test`: **nunca correr pruebas contra `plurione_compliance`**, porque la bitácora y los dictámenes son inmutables. Las suites que cuentan eventos de bitácora cuentan solo los propios.
- **ai-service:** `cd services/ai-service && pytest tests/` (offline; con el servicio en marcha, agregar `--deselect tests/test_niveles_3_4.py::test_niveles_3_4` para no consumir tokens). `tests/conftest.py` da a cada prueba una SQLite temporal. `test_niveles_3_4.py` requiere el servicio en vivo y consume tokens de Groq (se omite si el servicio no está).
- **Frontend:** `npm run lint`, `npm run test:ui` (equivalencia de marcado y lógica de `src/utils/` en `scripts/verificar-logica.mjs`) y `npm run build`.
- **Sesión en los scripts (Módulo 7, F6):** toda vista y toda ruta, salvo la salud y el inicio de sesión, exigen token. Los scripts lo obtienen solo de `scripts/sesion_api.py`: `ENTORNO_AISLADO` para los servicios que levantan (clave propia y `USUARIOS_DEMO=true`, aplicado por `e2e_api.levantar`), `sesion(core, rol)` por la API, `cabeceras_sistema()` para registrar un dictamen y `nueva_pagina()` para Playwright. Contra los servicios locales (base sin cuentas de demostración), `PRUEBAS_EMAIL` y `PRUEBAS_CONTRASENA`. Un selector de la interfaz que busque `[aria-expanded]` se limita a `.app-content`: el menú de usuario de la cabecera también lo tiene.
- **Sesión y roles en el navegador:** `python scripts/prueba_sesion_roles.py [etapa …] [--capturas CARPETA]` levanta los tres servicios (8101 a 8103) y Vite (5174) sobre `plurione_compliance_e2e` y recorre acceso, permisos por rol, MFA, usuarios y visor.
- **Regresión visual** (servicios y `npm run dev` en marcha; Chrome): `python scripts/regresion_visual.py capturar base` antes del cambio, `capturar actual` después y `comparar`. Un cambio sin efecto visual da 0 capturas distintas (160 capturas). Unos cientos de píxeles en letras sueltas de una sola combinación de tamaño y tema son ruido de suavizado del navegador: se descartan repitiendo solo esa combinación (`TAMANOS` y `TEMAS` del módulo) y comparando contra la base. Comportamiento: `scripts/prueba_sondeo_colgado.py`, `scripts/prueba_carga_fallida.py`, `scripts/prueba_error_422.py` (un 422 de FastAPI se muestra con su campo, no como «[object Object]»), `scripts/prueba_servicio_caido.py` (con el core caído, Empresas, Expedientes, Bóveda, Alertas y Reportes dicen que no responde, y Reportes no afirma nada mientras carga; solo requiere `npm run dev`) y `scripts/prueba_carga_lote.py` (RF-02; levanta core, rules y Vite aislados, en 8101, 8102 y 5174, sobre `plurione_compliance_e2e`).
- **Extremo a extremo (Q-b):** `python scripts/e2e_api.py` levanta core y rules en los puertos 8101 y 8102 sobre `plurione_compliance_e2e` (recreada en cada corrida) y recorre el flujo completo por HTTP con un RFC real y uno ficticio; código 0 si todo pasa.
- **Lectura anticipada (RNF-02):** `python scripts/prueba_lectura_anticipada.py` levanta core, rules y ai-service aislados (8101 a 8103, `plurione_compliance_e2e`, SQLite temporal) y comprueba por HTTP que `/anticipar` responde 202 al instante, que la auditoría encuentra después el texto en milisegundos y que una auditoría inmediata espera la lectura de fondo sin repetirla. Sin modelo ni tokens.
- **Entrega (RNF-11):** `python scripts/prueba_entrega_docker.py [--con-ia]` clona el último commit, lo levanta con `docker compose up --build` en un proyecto propio (`plurione_entrega`) y recorre el flujo con datos ficticios; sin `--con-ia` comprueba el 503 de IA no configurada, con él hace una auditoría y una pregunta reales. Siempre baja contenedores, volúmenes y clon. Correrla antes de entregar y tras cambiar dependencias, Dockerfiles o `docker-compose.yml` (los puertos 5433, 8001 a 8003 y 5173 deben estar libres).
- **Seguridad (Q-c):** `python scripts/zap_api.py` (Docker) corre OWASP ZAP sobre el OpenAPI de los tres servicios, levantados sobre `plurione_compliance_zap` y sin clave de Groq; un hallazgo alto sin justificar da código 1. Informe en `docs/resultados_validacion/seguridad_zap.md`.
- **Respaldo (RNF-10):** `python scripts/prueba_respaldo.py` (core y rules sobre `plurione_compliance_e2e` con bóveda propia; respalda en línea y comprueba que la verificación detecta un archivo alterado o ausente, una pieza fuera del manifiesto y un eslabón ausente, más la retención). La prueba de `pytest` no sirve aquí: su base comparte documentos de suites con bóvedas distintas.
- **CI** (`.github/workflows/ci.yml`): PostgreSQL 17 con `setup_postgres.py`, pytest de los tres servicios, los trabajos `e2e` y `zap`, y lint, `test:ui` y build del frontend.
- **Validación cuantitativa** (`services/ai-service/evaluacion/`, `docs/VALIDACION_CUANTITATIVA.md`):
  - Gold Standard de 42 casos ficticios, más un contrato de 20 páginas, congelado por SHA-256 (`*.sha256`, `.gitattributes -text`). Un cambio de la anotación exige un commit propio.
  - `python -m evaluacion.medir_chat --etiqueta <nombre> [--bateria corta|extensa] [--modo grabar]`. En modo reproducir (el predeterminado) no consume tokens y aborta si falta una huella del casete; en modo grabar llama a Groq solo por lo que falte. Las baterías corren sin el presupuesto de T4; lo mide `python -m evaluacion.escenario_contencion`.
  - Precisión: `python -m evaluacion.evaluar_precision [--modo grabar]` (42 casos, casete `casetes/precision.json`, reutiliza el del chat; en modo grabar guarda tras cada caso y continúa donde quedó).
  - Rendimiento: `python scripts/benchmark_rendimiento.py` (RNF-01 y RNF-03, base `plurione_compliance_bench`) y `python -m evaluacion.benchmark_extraccion [--actas RUTA] [--nivel4 N --sin-nivel3]` (RNF-02). Medir con nada más ejecutándose en el equipo.
  - Las corridas con Groq se planean según 8,000 tokens por minuto y 200,000 por día. Resultados en `docs/resultados_validacion/`.

| Área | Pruebas |
|---|---|
| Nivel 1 e ingesta (P1) | `test_pipeline_nivel1`, `test_ingesta_robustez`, `test_ingesta_blindada`, `test_cifrado_boveda` (RNF-04) |
| Dictámenes, semáforo, alertas, reportes, índice | `test_dictamenes_semaforo`, `test_tipos_anexos_alertas`, `test_indice_cumplimiento`, `test_sello_reporte` (PLUS-23) |
| Representación (P2) y custodia (P3) | `test_representacion_legal`, `test_cadena_custodia`; ai: `test_representacion` |
| Autenticidad y operación (P6) | `test_rfc_titular`, `test_senales_archivo`, `test_version_catalogo`, `test_rules_version_catalogo`, `test_antiguedad_pendientes`, `test_fechas_limite`, `test_rules_fechas_limite`; ai: `test_revision_por_senales`, `test_cuota_diaria` |
| Integridad permanente y excepciones (P5) | `test_integridad_permanente`, `test_dictamen_reproducible`, `test_excepciones_doc05`; ai: `test_excepciones_doc05` |
| Operación trazable (P7) | `test_folio_seguimiento`, `test_version_catalogo`; ai: `test_folio_seguimiento` |
| Módulo 7 (autenticación y roles) | `test_autenticacion`, `test_mfa`, `test_permisos_roles`, `test_notificaciones_correo` (RF-20, servidor SMTP en memoria de `tests/servidor_smtp.py`), `test_rules_autorizacion`, `test_seguridad_paridad`; ai: `test_autorizacion_ai`. Las suites del core piden sus tokens a `bd_pruebas.Autenticacion` (`auth.cliente(app)`, `auth.sistema()` para las llamadas del ai-service); las del rules, que leen la base de desarrollo sin modificarla, a `tests/sesiones_rules.py`; las del ai, a `services/ai-service/tests/sesion.py` (conftest toma la cuenta del token, salvo `@pytest.mark.cuenta_real`). La clave de pruebas la fija `tests/servicios.py` |
| Esquemas, errores y rules | `test_esquema_bd`, `test_esquema_rules`, `test_errores_core`, `test_errores_rules`, `test_rules_service`; ai: `test_errores_no_controlados` |
| Nivel 3 (ai) | `test_limites_ocr`, `test_iluminacion`, `test_sellos`, `test_visor_documento`, `test_optimizaciones`, `test_cache_y_lectura`, `test_ocr_continuo`, `test_lectura_anticipada` |
| Nivel 4 (ai) | `test_contenido_titularidad`, `test_titular_expediente`, `test_vigencia_dictamen`, `test_opinion_cumplimiento`, `test_persistencia_dictamen`, `test_discrepancia_tipo` |
| Chat P4 (ai) | `test_respuestas_directas`, `test_pasajes`, `test_contexto_enfocado`, `test_contexto_chat`, `test_cache_chat`, `test_presupuesto_tokens` |
| Evaluación (ai) | `test_metricas`, `test_gold_standard`, `test_entorno_evaluacion`, `test_bateria_chat`, `test_evaluar_precision` |

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
| `GROQ_TOKENS_POR_DIA` | `200000` | Cuota diaria que informa la salud (PLUS-19); estimación de esta instancia |
| `CHAT_MAX_TOKENS` | `600` | Tope de respuesta del chat |
| `CHAT_PRESUPUESTO_PUNTUAL` / `CHAT_FRAGMENTOS_PUNTUALES` | `3000` / `3` | Contexto enfocado de T2 |
| `CHAT_MENSAJES_HISTORIAL` / `CHAT_CARACTERES_TURNO_ASISTENTE` | `4` / `400` | Historial acotado de T2 |
| `CHAT_TTL_CRITERIOS_SEGUNDOS` | `300` | Criterios del catálogo en memoria (T4) |
| `OCR_LANG` / `OCR_DPI` / `OCR_WORKERS` | `spa` / `300` / hilos lógicos | OCR del Nivel 3 (300 dpi y 8 hilos medidos como óptimos, VALIDACION §10.3) |
| `OCR_TIMEOUT_PAGINA_SEGUNDOS` / `OCR_MAX_MEGAPIXELES_PAGINA` | `120` / `40` | Topes por página del OCR: un Tesseract colgado se corta (400) y una página o imagen mayor se lee a menos resolución |
| `LECTURA_ANTICIPADA` | `true` | Lectura de fondo al custodiar (RNF-02); con `false`, `/anticipar` no programa nada |
| `MAX_CARACTERES_CONTEXTO` / `MAX_CARACTERES_VERIFICACION` | `6500` / `9500` | Contexto de la auditoría y de la verificación |
| `MAX_PAGINAS_OCR` | `6` | Lectura parcial del chat sin auditoría |
| `UMBRAL_CONFIANZA_CONFORME` / `UMBRAL_CONFIANZA_HITL` | `0.85` / `0.70` | Bandas del Nivel 5 |
| `CORE_BASE_URL` / `RULES_BASE_URL` | `:8001` / `:8002` | Clientes del ai-service |
| `REEVALUACION_INTERVALO_HORAS` (core) | `24` | Reevaluación programada; `0` la desactiva |
| `UMBRALES_ALERTA_VENCIMIENTO` (core) | `30,15,5` | Días de anticipación de las alertas de vencimiento mientras el administrador no los cambie desde la interfaz (HU-14) |
| `ZONA_HORARIA` | `America/Mexico_City` | Día de referencia de las vigencias y de la antigüedad (Q-a); requiere `tzdata` |
| `RFC_DIGITO_ESTRICTO` (core) | `false` | M1: con `true`, un RFC cuyo dígito verificador no coincide se rechaza (hoy se acepta con advertencia) |
| `BARRIDO_INTEGRIDAD` (core) | `true` | Barrido de integridad de la bóveda en cada reevaluación (PLUS-14) |
| `LEGIBILIDAD_MIN_CARACTERES` / `LEGIBILIDAD_MIN_CONFIANZA` | `50` / `0.40` | Umbral de «Documento ilegible» (P5) |
| `DIFERIDOS_INTERVALO_MINUTOS` / `DIFERIDOS_MAX_INTENTOS` | `15` / `6` | Ciclo de procesamiento diferido (P5); `0` lo desactiva |
| `AUTO_SEED` (rules) / `DB_ECHO` (core, rules) | `true` / `false` | Precarga idempotente del catálogo / imprimir SQL |
| `BOVEDA_LLAVE` (core, `scripts/respaldo.py`) | vacía (la de demostración en el docker-compose) | Llave AES-256 de la bóveda (RNF-04), 64 caracteres hexadecimales; vacía, se guarda en claro; mal formada, el core no arranca. `/health` advierte la ausencia y la de demostración. Sin ella no se recuperan los documentos cifrados: se guarda fuera del equipo, nunca en el respaldo |
| `STORAGE_VAULT_PATH` (core) | `storage_vault/` | Bóveda física; el ai-service no la monta (lee por el core, RIE-03) |
| `RESPALDO_DIR` / `RESPALDO_SECUNDARIO` / `RESPALDO_RETENCION` | `../respaldos` / vacía / `14` | Destino de los respaldos (fuera del repositorio: contienen los originales), segunda copia dentro de la infraestructura (PRD §12.5) y paquetes verificados que se conservan (RNF-10) |
| `JWT_SECRET` (core, rules y ai) | — (obligatorio, ≥ 32 caracteres) | Clave HMAC de las sesiones y del token SISTEMA, **la misma en los tres servicios**; sin ella ninguno arranca. El docker-compose trae una de demostración que `/health` del core advierte |
| `JWT_EXPIRACION_MINUTOS` | `480` | Vigencia del token de sesión |
| `USUARIOS_DEMO` (core) | `false` (`true` en el docker-compose) | Crea, si faltan, `admin@`, `validador@`, `auditor@` y `consulta@example.com` (contraseñas en `motor/usuarios_iniciales.py`) |
| `ADMIN_INICIAL_EMAIL` / `ADMIN_INICIAL_CONTRASENA` (core) | vacías | Administrador que se crea si no hay ninguna cuenta; debe cambiar la contraseña en su primer acceso |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_STARTTLS` (core) | vacía / `587` / `true` | Servidor de correo de los avisos (RF-20); vacía, el envío está apagado y el aviso queda como ENVIO_DESACTIVADO |
| `SMTP_USUARIO` / `SMTP_CONTRASENA` / `SMTP_REMITENTE` / `SMTP_TIMEOUT_SEGUNDOS` (core) | vacías / vacía / `SMTP_USUARIO` / `15` | Credenciales, remitente y espera máxima del servidor |
| `FRONTEND_URL` (core) | `http://localhost:5173` | Base del enlace al expediente en los correos |
| `PRUEBAS_EMAIL` / `PRUEBAS_CONTRASENA` (scripts) | vacías | Cuenta con que los scripts de navegador entran a los servicios locales si no hay cuentas de demostración |
| `CORS_ORIGENES` (core, rules y ai) | `localhost` y `127.0.0.1` en 5173 y 5174 | Orígenes de la interfaz, separados por comas |
| `PG_BIN` | PATH o `C:/Program Files/PostgreSQL/*/bin` | Carpeta de `pg_dump` y `pg_restore` para `scripts/respaldo.py` |
| `VITE_CORE_URL` / `VITE_RULES_URL` / `VITE_AI_URL` | `:8001` / `:8002` / `:8003` | URLs del frontend |

---

## 8. Arranque

- Entorno local: `.venv` del proyecto con `pip install -r requirements-dev.txt` (las mismas versiones fijas que Docker más pytest, httpx, pyflakes y playwright). Las pruebas y los scripts se corren con ese Python; el Python global de la máquina puede tener otras versiones.
- Servicios: `cd services/<core|rules|ai>-service && python main.py` (con el `.venv` activado); frontend: `cd frontend && npm run dev`.
- Todo con Docker Compose: `docker compose up -d --build` (PostgreSQL publicado en el 5433 para no chocar con uno local; los demás puertos, los de §3).
- Base de datos (tablas de todos los servicios y seed): `python scripts/setup_postgres.py`; solo tablas: `python scripts/crear_tablas.py`; solo el catálogo: `python scripts/seed_reglas_validacion.py`. `db/base-de-datos.sql` (entrega: estructura y datos ficticios, importable con `psql` en una base vacía) se regenera con `python scripts/exportar_base_sql.py` cada vez que cambie el esquema, el catálogo o las cuentas de demostración.
- Respaldo (RNF-10): `python scripts/respaldo.py crear` (paquete en `RESPALDO_DIR` con su prueba de restauración; código 0 solo si quedó verificado), `verificar RUTA` y `programar [--hora 02:00] [--quitar]` (tarea diaria de Windows que también corre al encender el equipo si la hora pasó). Restaurar en producción: `pg_restore` de `base.dump` en la base, `boveda.zip` en `storage_vault/` y `extracciones.sqlite3` en `services/ai-service/data/`, con los servicios detenidos.
- Salud: `GET :8001|:8002|:8003/api/v1/health` (el del ai-service incluye `motor_inferencia`); Swagger en `/docs` de cada servicio.
