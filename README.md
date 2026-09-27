# Motor de Validación de Cumplimiento Documental

Sistema de validación documental automatizada para **PluriOne S.A. de C.V.**, desarrollado como proyecto de residencia profesional. Recibe los expedientes de una empresa, custodia cada documento con su huella SHA-256, lo lee (capa vectorial u OCR), extrae sus datos con un modelo de lenguaje y emite un **dictamen determinista y auditable** con semáforo, alertas y recomendaciones. Un analista ratifica los casos dudosos (Human-in-the-Loop).

La especificación oficial está en [`docs/ESPECIFICACIONES_DOC01_A_DOC08.txt`](docs/ESPECIFICACIONES_DOC01_A_DOC08.txt) (DOC-01 a DOC-08).

## Arquitectura

| Servicio | Puerto | Responsabilidad |
|---|---|---|
| `services/core-service` | 8001 | Titulares, expedientes y documentos (magic bytes, límite de 15 MB, SHA-256, bóveda), dictámenes, bitácora inmutable, semáforo, alertas, reportes PDF/Excel y la reevaluación programada |
| `services/rules-service` | 8002 | Catálogo de reglas del DOC-05 (familias RIE, RCV, RSC, RDS) y evaluación determinista de la vigencia |
| `services/ai-service` | 8003 | Nivel 3 (PyMuPDF + Tesseract con OpenCV) y Nivel 4 (Groq Cloud, `qwen/qwen3.8-27b`), verificación de contenido y chat documental |
| `frontend` | 5173 | Interfaz React 19 + Vite |
| PostgreSQL 17 | 5432 | Base `plurione_compliance`, compartida por core y rules (cada uno con sus tablas) |

### Pipeline de validación (DOC-05)

1. **Integridad estructural y criptográfica:** magic bytes (PDF, JPEG, PNG), 15 MB como máximo y huella SHA-256 (NOM-151-SCFI-2016). Cada lectura del binario la recalcula (RIE-03).
2. **Reglas deterministas:** inventario obligatorio según el tipo de expediente (RIE-01), anexos (RIE-02) y vigencia (RCV-01, RCV-02 y RCV-03).
3. **Extracción de texto:** capa vectorial y, para páginas escaneadas, OCR `spa+eng`.
4. **Análisis semántico:** el modelo **solo extrae** datos; el dictamen lo calculan reglas del servicio. La titularidad se acredita con el RFC o, si el documento no lo trae, con la razón social. Un tipo documental distinto al registrado pasa a revisión. Los elementos que el catálogo exige a cada tipo (reglas RSC/RDS) se verifican con una **cita literal** que se contrasta con el texto; un elemento no localizado deja el documento en revisión con la recomendación del catálogo, nunca lo rechaza (RSC-01).
5. **Gobernanza humana:** con confianza ≥ 0.85 el dictamen es CONFORME, y por debajo pasa a revisión humana. Una confianza baja nunca rechaza un documento: solo lo rechazan una vigencia vencida o un RFC ajeno.

El motor se ejecuta de dos formas, **manual o programada** (DOC-02): por documento o con «Auditar pendientes» en el expediente (HU-32), y con una reevaluación periódica del semáforo (`REEVALUACION_INTERVALO_HORAS`, 24 h por defecto). Subir un archivo nunca lo aprueba ni lo analiza por sí solo.

## Puesta en marcha

### Con Docker Compose

```bash
# .env en la raíz con la clave de Groq Cloud (https://console.groq.com/keys)
echo "GROQ_API_KEY=gsk_..." > .env
docker compose up -d --build
```

El rules-service carga el catálogo de reglas al arrancar (`AUTO_SEED=true`). La precarga es idempotente: solo inserta las reglas que faltan y no toca las editadas.

### En local

Se necesitan Python 3.12, Node 20.19 o superior, PostgreSQL 17 y Tesseract (con los idiomas `spa` y `eng`). Cada servicio lee su propio `.env` (`DB_*` en core y rules; `GROQ_API_KEY`, `TESSERACT_CMD`, `CORE_BASE_URL` y `RULES_BASE_URL` en el ai-service; ver [`services/ai-service/README.md`](services/ai-service/README.md)).

```bash
pip install -r services/core-service/requirements.txt -r services/rules-service/requirements.txt -r services/ai-service/requirements.txt
python scripts/setup_postgres.py          # base, tablas, catálogo de reglas y un expediente de demostración

cd services/core-service  && python main.py   # :8001
cd services/rules-service && python main.py   # :8002
cd services/ai-service    && python main.py   # :8003
cd frontend && npm install && npm run dev     # :5173
```

La documentación interactiva de cada API está en `/docs` (por ejemplo, `http://127.0.0.1:8001/docs`), y el estado de cada servicio en `GET /api/v1/health`.

## Pruebas

```bash
pytest tests/ -v                                # core y rules (usa la base plurione_compliance_test)
cd services/ai-service && pytest tests/ -v      # ai-service, sin red (Groq, core y rules simulados)
cd frontend && npm run lint && npm run build
```

Las pruebas del core-service recrean `plurione_compliance_test` y una bóveda temporal: nunca escriben en la base de trabajo, porque ahí la bitácora y los dictámenes son inmutables. La suite `test_niveles_3_4.py` del ai-service se omite si el servicio no está corriendo en :8003 con una `GROQ_API_KEY` válida. El workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) ejecuta todo lo anterior en cada push.

## Estructura

```
services/            core-service, rules-service y ai-service (FastAPI)
frontend/            interfaz React 19 (Vite)
scripts/             setup_postgres.py, crear_tablas.py, seed_reglas_validacion.py
tests/               pruebas de core y rules
storage_vault/       bóveda física de binarios (no versionada)
docs/                especificación oficial (DOC-01 a DOC-08) y auditoría técnica
docker-compose.yml   plurione-db, plurione-core, plurione-rules, plurione-ai, plurione-frontend
```
