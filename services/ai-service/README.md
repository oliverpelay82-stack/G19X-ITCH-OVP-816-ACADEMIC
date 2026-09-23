# AI Service (:8003) — Niveles 3 y 4 del pipeline

Microservicio de análisis inteligente del Motor de Validación de Cumplimiento
Documental. Implementa el **Nivel 3** (extracción de texto con OCR) y el
**Nivel 4** (análisis semántico con un modelo de lenguaje) del pipeline definido
en el DOC-05.

La inferencia se resuelve contra **Groq Cloud** (modelo `qwen/qwen3.8-27b`,
servido sobre la LPU de Groq con una API compatible con OpenAI). Se mantiene el
principio de minimización de datos: al modelo solo viaja el texto que ya extrajo
el Nivel 3, nunca el documento original, cifrado en tránsito (TLS).

**Privacidad.** Por defecto Groq no retiene las entradas ni las salidas de
inferencia y no las usa para entrenar modelos. Puede registrarlas temporalmente,
hasta 30 días, solo para diagnosticar fallas de la plataforma o investigar
abuso. Ese registro se desactiva activando **Zero Data Retention** en *Data
Controls* de la consola de Groq, lo cual se recomienda para este proyecto.
Groq audita sus controles de seguridad con SOC 2 Type II. Fuente:
<https://console.groq.com/docs/your-data>.

---

## 1. Dependencias externas

El servicio necesita una API key de Groq y el binario de Tesseract, que no se instala con `pip`.

### Groq Cloud (motor de inferencia)

1. Cree una cuenta en <https://console.groq.com>.
2. En **API Keys → Create API Key**, genere una key (empieza con `gsk_`).
3. Configúrela en `services/ai-service/.env`:

```env
GROQ_API_KEY=gsk_...
GROQ_MODEL=qwen/qwen3.8-27b
GROQ_TEMPERATURE=0.0
GROQ_TIMEOUT=30
GROQ_MAX_TOKENS=1000
```

En Docker Compose la variable `GROQ_API_KEY` se toma del `.env` de la raíz del
proyecto. Sin la API key el servicio arranca igual: el health check reporta que
Groq no está configurado y el Nivel 3 (OCR) sigue operando.

> **Límite de tokens por minuto.** El plan gratuito de Groq admite 8,000 tokens
> por minuto para este modelo, contando entrada y salida. Cada consulta envía
> hasta `MAX_CARACTERES_CONTEXTO` (12,000) caracteres del documento, unos 4,000
> tokens, así que dos consultas seguidas agotan el cupo y la librería reintenta
> hasta que se libera (la respuesta pasa de ~1 s a 15–25 s). Un plan de pago
> elimina esa espera.

### Tesseract OCR (motor de reconocimiento óptico)

```powershell
winget install --id UB-Mannheim.TesseractOCR -e
```

El instalador de Windows solo incluye el idioma inglés. Los modelos de idioma
que usa el servicio se guardan en `tessdata/` (no versionados, por tamaño) y se
descargan así:

```powershell
$dir = "services/ai-service/tessdata"
New-Item -ItemType Directory -Force -Path $dir | Out-Null
foreach ($l in @("spa", "eng", "osd")) {
    Invoke-WebRequest -UseBasicParsing `
        -Uri "https://github.com/tesseract-ocr/tessdata_fast/raw/main/$l.traineddata" `
        -OutFile "$dir/$l.traineddata"
}
```

En Docker no hace falta: el `Dockerfile` instala `tesseract-ocr-spa` y
`tesseract-ocr-eng` desde los paquetes del sistema.

---

## 2. Puesta en marcha

```powershell
pip install -r requirements.txt
python main.py            # o: uvicorn main:app --reload --port 8003
```

Documentación interactiva: <http://127.0.0.1:8003/docs>

El health check informa del estado de ambas dependencias, de modo que sirve como
primer diagnóstico cuando algo no responde:

```powershell
Invoke-RestMethod http://127.0.0.1:8003/api/v1/health
```

---

## 3. Endpoints

| Método | Ruta | Nivel | Descripción |
|--------|------|-------|-------------|
| `GET`  | `/api/v1/health` | — | Estado del servicio, de Groq Cloud y del motor OCR. Responde 200 aunque falte una dependencia. |
| `POST` | `/api/v1/ai/extraer-texto` | 3 | Extracción híbrida: capa vectorial con PyMuPDF y OCR con preprocesamiento OpenCV. |
| `GET`  | `/api/v1/ai/configuracion-ocr` | 3 | Parámetros activos del motor OCR y umbrales vigentes. |
| `POST` | `/api/v1/ai/analisis-semantico` | 4 | Dictamen estructurado: tipo documental, RFC, vigencia y estatus preliminar. |
| `POST` | `/api/v1/ai/chat-documento` | 4 | Consulta en lenguaje natural sobre un documento concreto. |

Los dos endpoints del Nivel 4 aceptan el documento por `documento_id` —lo
recuperan del `core-service` y ejecutan antes el Nivel 3— o por `texto`, cuando
el contenido ya fue extraído.

---

## 4. Decisiones de diseño

**El modelo extrae; el servicio dictamina.** La inferencia corre a temperatura
0.0 con la salida restringida a JSON, y su única responsabilidad es localizar
datos en el texto. La coincidencia del RFC se resuelve con una comparación
exacta de caracteres y la vigencia comparando fechas, ambas en código
determinista. Así el dictamen es reproducible y auditable línea por línea.

**Bandas de confianza (DOC-08 §6.2).** Un puntaje de 0.85 o superior permite
dictaminar CONFORME; entre 0.70 y 0.84 el caso pasa al Nivel 5 de gobernanza
humana; por debajo de 0.70 la lectura no se considera fiable y también se
escala. Una confianza baja nunca produce un rechazo automático: el rechazo se
reserva a hechos del documento (vigencia expirada o RFC ajeno al expediente).

**La confianza del Nivel 4 se acota por la del Nivel 3.** Por sólida que sea la
lectura del modelo, no puede ser más fiable que el texto que se le entregó.

---

## 5. Pruebas

```powershell
python tests/generar_fixtures.py     # genera los documentos de prueba
python tests/test_niveles_3_4.py     # suite contra el servicio levantado
```

`generar_fixtures.py` produce dos versiones del mismo documento ficticio: una
vectorial, con capa de texto, y otra rasterizada y degradada para imitar un
escaneo de oficina. Los datos son ficticios y están rotulados como tales dentro
del propio documento.

La suite requiere el servicio en el puerto 8003 y `GROQ_API_KEY` configurada.
Deja su evidencia en `tests/fixtures/evidencia_niveles_3_4.json`.
