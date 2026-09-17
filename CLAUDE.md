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

### ⚙️ Agente Backend & Arquitectura de Datos (FastAPI + PostgreSQL)
* **Patrón:** Arquitectura en capas limpia, aislada dentro de `backend/`:
  * `backend/models/` → Entidades SQLAlchemy (tablas de PostgreSQL).
  * `backend/schemas/` → DTOs y validación con Pydantic v2.
  * `backend/controllers/` → Enrutadores REST (`APIRouter`) con versionado `/api/v1/`.
  * `backend/config/` → Conexión PostgreSQL (`plurione_compliance`) y variables `backend/.env`.
  * `storage_vault/` → Bóveda física desacoplada para almacenamiento de binarios (raíz del proyecto, referenciada por `backend/controllers/documento_controller.py` como `../storage_vault`).

---

## 2.1 Estructura de Carpetas

```
motor de validacion/
├── backend/            # API FastAPI + PostgreSQL (config/, controllers/, models/, schemas/, main.py, requirements.txt, .env)
├── frontend/           # Interfaz oficial React 19 (Vite)
├── scripts/            # Utilidades de BD: setup_postgres.py, crear_tablas.py, seed_reglas_validacion.py
├── tests/              # Pruebas: test_conexion.py, test_pipeline_nivel1.py
├── storage_vault/      # Bóveda física de binarios (desacoplada del backend)
├── docs/               # Fuente oficial de la verdad (DOC-01 a DOC-08)
└── CLAUDE.md
```

Los scripts de `scripts/` y las pruebas de `tests/` insertan `backend/` en `sys.path` al inicio del archivo para poder importar `config`, `models`, `schemas` y `main` sin necesidad de instalar el backend como paquete.

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

* **Backend:** `cd backend && python main.py` (o `uvicorn main:app --reload`) — Puerto `8000`, PostgreSQL `5432`.
* **Frontend:** `cd frontend && npm run dev` — Puerto `5173`.
* **Inicializar/sincronizar BD PostgreSQL:** `python scripts/setup_postgres.py` (desde la raíz del proyecto).
* **Sincronizar solo tablas:** `python scripts/crear_tablas.py`
* **Precargar catálogo de reglas (DOC-05):** `python scripts/seed_reglas_validacion.py`
* **Correr suite de pruebas de integridad:** `python tests/test_pipeline_nivel1.py`
* **Probar conexión a PostgreSQL:** `python tests/test_conexion.py`
* **Documentación interactiva Swagger:** `http://127.0.0.1:8000/docs`

---

## 5. Reglas de Colaboración
* Trabajar de manera modular y paso a paso.
* No alterar tablas existentes sin migración o confirmación.
* Todo código debe incluir manejo estricto de excepciones HTTP y tipado estático con anotaciones de Python.
