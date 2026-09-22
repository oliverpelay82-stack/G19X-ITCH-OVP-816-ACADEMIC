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
* **Paleta de Color de Compliance:**
  * Fondo/Superficie: Slate neutro (`#F8FAFC`, `#FFFFFF`), bordes sutiles (`#E2E8F0`).
  * Primario Corporativo: Azul profundo / Índigo (`#2563EB`, `#1D4ED8`).
  * Estados de Auditoría:
    * `CONFORME`: Verde esmeralda (`#059669`, fondo `#ECFDF5`).
    * `EN_REVISION`: Ámbar preventivo (`#D97706`, fondo `#FFFBEB`).
    * `NO_CONFORME` / `RECHAZADO`: Rojo carmesí (`#DC2626`, fondo `#FEF2F2`).
    * Criptografía / Bóveda: Púrpura auditor (`#7C3AED`, fondo `#FAF5FF`).
* **Micro-interacciones:** Indicadores de estado en vivo (*status dots* animados), modales limpios, barras de progreso dinámicas y tablas responsivas con copiado de hashes al portapapeles.
* **Interfaz Oficial:** La interfaz oficial del sistema es el proyecto **React 19** ubicado en `frontend/`. La vista legacy `views/panel.html` fue retirada.

### ⚙️ Agente Backend & Arquitectura de Datos (FastAPI + PostgreSQL + Microservicios)
* **Patrón (desde Sprint 0 / Semana 4):** Arquitectura de **microservicios desacoplados**, orquestados con Docker Compose, dentro de `services/`. Cada microservicio replica internamente la misma capa limpia que antes vivía en `backend/`:
  * `services/core-service/` (**puerto 8001**) → Titulares, Expedientes y Documentos (ingesta, magic bytes, hash SHA-256, bóveda física).
  * `services/rules-service/` (**puerto 8002**) → Catálogo de Reglas de Validación (DOC-05: familias RIE, RCV, RSC, RDS).
  * `services/ai-service/` (**puerto 8003**) → Esqueleto vivo (solo health check); alojará desde la Semana 5 el Nivel 3 (extracción de texto) y Nivel 4 (análisis semántico con IA) del pipeline.
  * Cada servicio mantiene su propia carpeta `models/`, `schemas/`, `controllers/`, `config/database.py`, `main.py`, `requirements.txt`, `Dockerfile` y `.env`. Todos los servicios con base de datos comparten la misma PostgreSQL física `plurione_compliance` (cada uno gestiona su propio subconjunto de tablas vía `Base.metadata` independiente).
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
│   └── ai-service/       # API FastAPI :8003 — Esqueleto (Semana 5)
│       ├── controllers/ main.py requirements.txt Dockerfile
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
3. **Nivel 3 - Extracción de Texto:** Parseo y extracción OCR de contenido documental.
4. **Nivel 4 - Análisis Semántico con IA:** Cruce semántico asistido por LLM (RFC y Razón Social contra el titular).
5. **Nivel 5 - Gobernanza Humana (Human-in-the-Loop):** Flujo de revisión manual para casos de baja confianza.

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
* **Correr suite de pruebas de integridad (core-service):** `python tests/test_pipeline_nivel1.py`
* **Probar conexión a PostgreSQL:** `python tests/test_conexion.py`
* **Documentación interactiva Swagger:** `http://127.0.0.1:8001/docs` (Core), `http://127.0.0.1:8002/docs` (Rules), `http://127.0.0.1:8003/docs` (AI).
* **Health checks:** `GET http://127.0.0.1:8001/api/v1/health`, `:8002/api/v1/health`, `:8003/api/v1/health`.

---

## 5. Reglas de Colaboración
* Trabajar de manera modular y paso a paso.
* No alterar tablas existentes sin migración o confirmación.
* Todo código debe incluir manejo estricto de excepciones HTTP y tipado estático con anotaciones de Python.
