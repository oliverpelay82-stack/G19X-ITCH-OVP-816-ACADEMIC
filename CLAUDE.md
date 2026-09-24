# Motor de Validación de Cumplimiento Documental — Configuración de Agentes (CLAUDE.md)

Este repositorio contiene el backend y la arquitectura del **Motor de Validación de Cumplimiento Documental**, desarrollado como proyecto de residencia profesional para **PluriOne S.A. de C.V.** (Develop Talent & Technology).

---

## 1. Misión del Agente

Operar como **Ingeniero de Software Senior y Especialista en Arquitectura de Compliance & UI/UX**. Tu objetivo es construir un sistema de validación documental automatizado de nivel bancario/corporativo conforme a los documentos oficiales del proyecto (`DOC-01` a `DOC-08`).

### 📚 Fuente Oficial de la Verdad (En la carpeta `docs/`)
Antes de implementar cualquier módulo, tabla o regla, debes consultar:
* **`docs/ESPECIFICACIONES_DOC01_A_DOC08.txt`:** Contiene el texto íntegro de los 8 documentos aprobados (DOC-01 Entrevistas, DOC-02 Requisitos, DOC-03 Regulaciones, DOC-04 SRS Requerimientos, DOC-05 Estrategia de Validación en 5 Niveles y Reglas, DOC-06 Propuesta, DOC-07 Backlog de Sprints, DOC-08 Arquitectura y BD).
* **`docs/AUDITORIA_TECNICA.md`:** La auditoría detallada de lo que ya existe y lo que falta por Sprint.
* **Regla de Oro:** **PROHIBIDO inventar** tablas, nombres de producto, roles o categorías (como inventar categorías que no existan). Toda decisión técnica debe estar fundamentada en estos documentos oficiales.

---

## 2. Roles y Agentes Especializados

### 🎨 Agente de Diseño y Experiencia de Usuario (UI/UX Specialist)
* **Estándar Visual:** Prohibido usar interfaces genéricas o diseños tipo plantilla básica. La interfaz debe transmitir calidad corporativa de grado enterprise (estilo Stripe, Linear, Vercel).
* **Tipografía:** Utilizar fuentes modernas como `Inter` para texto base y `JetBrains Mono` para hashes criptográficos, códigos de folio y RFCs.
* **Design system minimalista (tokens en `frontend/src/index.css`):**
  * Tema oscuro por defecto: fondo `#09090B`, superficies `#111113` / `#18181B`, borde `rgba(255,255,255,0.06)` (hover `0.12`), texto `#FAFAFA` / `#A1A1AA` / `#71717A`.
  * Tema claro: fondo `#FAFAFA`, superficies `#FFFFFF` / `#F4F4F5`, borde `#E4E4E7` (hover `#D4D4D8`), texto `#09090B` / `#52525B` / `#A1A1AA`.
  * Acento primario: `#3B82F6`.
  * Estados de Auditoría:
    * `CONFORME`: `#059669`, fondo `rgba(5,150,105,0.1)`.
    * `EN_REVISION`: `#D97706`, fondo `rgba(217,119,6,0.1)`.
    * `NO_CONFORME` / `RECHAZADO`: `#DC2626`, fondo `rgba(220,38,38,0.1)`.
    * Criptografía / Bóveda: `#7C3AED`, fondo `rgba(124,58,237,0.1)`.
  * Espaciado en rejilla de 4 px; radios 6 px (botones, inputs), 8 px (cards), 12 px (modales).
* **Micro-interacciones:** Transiciones de 150 ms ease-out, sin rebotes ni escalados. Sombras solo en modales, dropdowns y tooltips; las cards ganan profundidad por contraste de superficie. Status dots de 6 px sin pulso, tablas sin zebra-striping y copiado de hashes al portapapeles.
* **Interfaz Oficial:** La interfaz oficial del sistema es el proyecto **React 19** ubicado en `frontend/`. La vista legacy `views/panel.html` fue retirada.

### ⚙️ Agente Backend & Arquitectura de Datos (FastAPI + PostgreSQL + Microservicios)
* **Patrón (desde Sprint 0 / Semana 4):** Arquitectura de **microservicios desacoplados**, orquestados con Docker Compose, dentro de `services/`. Cada microservicio replica internamente la misma capa limpia que antes vivía en `backend/`:
  * `services/core-service/` (**puerto 8001**) → Titulares, Expedientes y Documentos (ingesta, magic bytes, hash SHA-256, bóveda física).
  * `services/rules-service/` (**puerto 8002**) → Catálogo de Reglas de Validación (DOC-05: familias RIE, RCV, RSC, RDS). Evalúa además la vigencia de forma determinista en `POST /api/v1/reglas/evaluar-vigencia` (`motor/vigencia.py`): RCV-01 mide los días hasta el vencimiento y RCV-02 aplica la caducidad estricta del comprobante de domicilio fiscal (`COMP_DOMICILIO`, máximo 90 días naturales desde la emisión, DOC-02/DOC-08). El dictamen del ai-service consulta este endpoint en cada auditoría (`clients/rules_client.py`, `RULES_BASE_URL`) con el tipo registrado del documento; si el rules-service no responde, el dictamen pasa a revisión humana en lugar de aprobarse.
  * `services/ai-service/` (**puerto 8003**) → Nivel 3 (extracción de texto híbrida: capa vectorial con PyMuPDF + OCR con Tesseract y preprocesamiento OpenCV) y Nivel 4 (análisis semántico con un modelo de lenguaje servido por Groq Cloud sobre su LPU, `qwen/qwen3.8-27b`, API compatible con OpenAI en `https://api.groq.com/openai/v1`). No usa la base de datos PostgreSQL de los otros servicios: persiste el texto extraído en su propio SQLite (`services/ai-service/data/`, indexado por SHA-256) para no repetir el OCR. Sus dependencias externas son Groq Cloud (requiere `GROQ_API_KEY`, prefijo `gsk_`) y el binario de Tesseract. Al modelo solo viaja el texto extraído por el Nivel 3, nunca el documento original. Por defecto Groq no retiene entradas ni salidas de inferencia ni entrena con ellas; puede registrarlas hasta 30 días para diagnóstico o abuso, salvo que se active Zero Data Retention en Data Controls. El plan gratuito limita a 8,000 tokens por minuto. Ver `services/ai-service/README.md`.
  * Cada servicio mantiene su propia carpeta `schemas/`, `controllers/`, `main.py`, `requirements.txt`, `Dockerfile` y `.env`. Los dos servicios con base de datos (`core` y `rules`) añaden `models/` y `config/database.py`, y comparten la misma PostgreSQL física `plurione_compliance` (cada uno gestiona su propio subconjunto de tablas vía `Base.metadata` independiente). El `ai-service` no usa PostgreSQL: en lugar de `models/` tiene `clients/` (integraciones salientes) y `pipelines/` (los algoritmos de los Niveles 3 y 4), y solo persiste el texto extraído en su SQLite local.
  * Todo controlador expone `GET /api/v1/health` (status, servicio, puerto, y `conexion_bd` cuando aplica) para health checks de Docker Compose y del frontend.
  * `storage_vault/` → Bóveda física desacoplada, en la raíz del proyecto. En local la referencia `core-service/controllers/documento_controller.py` por ruta relativa; en Docker se monta como volumen y se apunta vía la variable `STORAGE_VAULT_PATH`.

---

## 2.1 Estructura de Carpetas

```
motor de validacion/
├── services/
│   ├── core-service/     # API FastAPI :8001 — Titulares, Expedientes, Documentos
│   │   ├── config/ controllers/ models/ schemas/ main.py requirements.txt Dockerfile .env
│   ├── rules-service/    # API FastAPI :8002 — Reglas de Validación (DOC-05)
│   │   ├── config/ controllers/ models/ schemas/ main.py requirements.txt Dockerfile .env
│   └── ai-service/       # API FastAPI :8003 — Niveles 3 y 4 del pipeline
│       ├── config/settings.py      # Groq Cloud, Tesseract y umbrales del pipeline
│       ├── clients/                # groq_client.py, core_client.py
│       ├── pipelines/              # extraccion_pipeline.py, analisis_semantico.py
│       ├── controllers/ schemas/ tests/ tessdata/
│       ├── main.py requirements.txt Dockerfile .env README.md
├── docker-compose.yml   # Orquesta plurione-db, plurione-core, plurione-rules, plurione-ai, plurione-frontend
├── frontend/            # Interfaz oficial React 19 (Vite), apunta a los 3 microservicios
├── scripts/             # Utilidades de BD: setup_postgres.py, crear_tablas.py, seed_reglas_validacion.py
│                        # (orquestan subprocesos por servicio; ver comentarios en cada script)
├── tests/               # Pruebas: test_conexion.py, test_pipeline_nivel1.py (contra core-service)
├── storage_vault/       # Bóveda física de binarios (desacoplada de los servicios)
├── docs/                # Fuente oficial de la verdad (DOC-01 a DOC-08)
└── CLAUDE.md
```

`core-service` y `rules-service` definen cada uno su propio módulo `config.database` con nombre idéntico pero contenido distinto (una Base de SQLAlchemy por servicio); por eso **no se importan en el mismo proceso de Python**. Los scripts de `scripts/` que necesitan tocar ambos servicios (p. ej. `crear_tablas.py`, `setup_postgres.py`) invocan cada servicio en un subproceso aislado con su propio directorio como `cwd`. Los scripts/pruebas que solo tocan un servicio (`seed_reglas_validacion.py` de rules-service, `tests/test_pipeline_nivel1.py` y `tests/test_conexion.py` contra core-service) insertan la carpeta de ese servicio en `sys.path` igual que antes.

---

## 3. Pipeline de Validación Normativa (DOC-05)

El motor opera en un pipeline estricto de 5 niveles:
1. **Nivel 1 - Integridad Estructural y Criptográfica:** Validación de Magic Bytes (PDF `%PDF-`, JPEG, PNG), límite de 15 MB y generación inmutable de hash SHA-256 (NOM-151-SCFI-2016).
2. **Nivel 2 - Reglas Deterministas en BD:** Consulta contra la tabla `reglas_validacion` para verificar vigencia temporal (días máximos) y completitud obligatoria.
3. **Nivel 3 - Extracción de Texto:** Lectura directa de la capa vectorial del PDF con PyMuPDF y, para páginas escaneadas, OCR con Tesseract (`spa+eng`) previo preprocesamiento con OpenCV (escala de grises, filtro bilateral y binarización de Otsu). Devuelve el texto y un *confidence score* en [0.0, 1.0]. Las páginas escaneadas se reconocen en paralelo en tandas de `OCR_WORKERS` (núcleos físicos por defecto). El OCR se corta al reunir `MAX_CARACTERES_CONTEXTO` caracteres o tras `MAX_PAGINAS_OCR` páginas escaneadas, y el texto de cada `documento_id` queda en un caché LRU en memoria (`pipelines/cache_extracciones.py`), respaldado por SQLite, de modo que la auditoría y el chat nunca repiten el OCR sobre el mismo documento, ni tras reiniciar. Al LLM se le envía el encabezado más los fragmentos relevantes por BM25 (`pipelines/fragmentos.py`), no solo el inicio del documento.
4. **Nivel 4 - Análisis Semántico con IA:** Inferencia vía Groq Cloud (`qwen/qwen3.8-27b`) a temperatura 0.0 con salida JSON estricta (`response_format={"type": "json_object"}`). Solo se envía el texto extraído (minimización de datos). **El modelo solo extrae**; el dictamen (coincidencia de RFC, vigencia y estatus preliminar) lo calculan reglas deterministas del servicio, de modo que sea reproducible y auditable.
5. **Nivel 5 - Gobernanza Humana (Human-in-the-Loop):** Bandas de confianza del DOC-08 §6.2 — `>= 0.85` CONFORME, `0.70 a 0.84` revisión humana, `< 0.70` revisión humana por lectura no fiable. Una confianza baja **nunca** produce rechazo automático: el rechazo se reserva a hechos del documento (vigencia expirada o RFC ajeno).

---

## 4. Comandos de Referencia

* **Core Service:** `cd services/core-service && python main.py` (o `uvicorn main:app --reload --port 8001`) — Puerto `8001`.
* **Rules Service:** `cd services/rules-service && python main.py` (o `uvicorn main:app --reload --port 8002`) — Puerto `8002`.
* **AI Service:** `cd services/ai-service && python main.py` (o `uvicorn main:app --reload --port 8003`) — Puerto `8003`.
* **Frontend:** `cd frontend && npm run dev` — Puerto `5173`.
* **Levantar todo con Docker Compose:** `docker compose up -d --build` (desde la raíz del proyecto) — PostgreSQL `5432`, Core `8001`, Rules `8002`, AI `8003`, Frontend `5173`.
* **Inicializar/sincronizar BD PostgreSQL (todos los servicios + seed):** `python scripts/setup_postgres.py` (desde la raíz del proyecto).
* **Sincronizar solo tablas (todos los servicios):** `python scripts/crear_tablas.py`
* **Precargar catálogo de reglas (DOC-05):** `python scripts/seed_reglas_validacion.py`
* **Correr suite de pruebas de integridad (core-service):** `python tests/test_pipeline_nivel1.py` — trabaja sobre un titular y un expediente temporales (`EXP-TEST-TMP`, RFC `TMP010101AAA`) que crea y elimina ella misma; no toca los expedientes reales.
* **Pruebas del rules-service (solo lectura):** `python tests/test_rules_service.py` (incluye el motor de vigencia con fechas fijas y el endpoint `evaluar-vigencia`; requiere RCV-02 precargada con `python scripts/seed_reglas_validacion.py`)
* **Pruebas offline de optimización del ai-service:** `cd services/ai-service && python tests/test_optimizaciones.py`
* **Pruebas offline del dictamen con las reglas de vigencia (RCV):** `cd services/ai-service && python tests/test_vigencia_dictamen.py`
* **Generar los documentos de prueba del ai-service:** `cd services/ai-service && python tests/generar_fixtures.py`
* **Correr la suite de los Niveles 3 y 4:** `cd services/ai-service && python tests/test_niveles_3_4.py` (requiere el servicio en :8003 y `GROQ_API_KEY` configurada)
* **Verificar el motor de inferencia (Groq Cloud):** `GET http://127.0.0.1:8003/api/v1/health` → bloque `motor_inferencia`.
* **Variables del ai-service (`services/ai-service/.env`):** `GROQ_API_KEY` (generarla en https://console.groq.com/keys), `GROQ_MODEL=qwen/qwen3.8-27b`, `GROQ_TEMPERATURE=0.0`, `GROQ_TIMEOUT=30`, `GROQ_MAX_TOKENS=1000`, más `TESSERACT_CMD`, `OCR_LANG`, `OCR_DPI`, umbrales del pipeline, `CORE_BASE_URL` y `RULES_BASE_URL`. En Docker Compose, `GROQ_API_KEY` se toma del `.env` de la raíz del proyecto.
* **Probar conexión a PostgreSQL:** `python tests/test_conexion.py`
* **Documentación interactiva Swagger:** `http://127.0.0.1:8001/docs` (Core), `http://127.0.0.1:8002/docs` (Rules), `http://127.0.0.1:8003/docs` (AI).
* **Health checks:** `GET http://127.0.0.1:8001/api/v1/health`, `:8002/api/v1/health`, `:8003/api/v1/health`.

---

## 5. Reglas de Colaboración
* Trabajar de manera modular y paso a paso.
* No alterar tablas existentes sin migración o confirmación.
* Todo código debe incluir manejo estricto de excepciones HTTP y tipado estático con anotaciones de Python.
