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
GROQ_MAX_RETRIES=2
GROQ_CACHE_INFERENCIAS=true
GROQ_MAX_TOKENS=1000
```

En Docker Compose la variable `GROQ_API_KEY` se toma del `.env` de la raíz del
proyecto. Sin la API key el servicio arranca igual: el health check reporta que
Groq no está configurado y el Nivel 3 (OCR) sigue operando.

> **Límite de tokens por minuto.** El plan gratuito de Groq admite 8,000 tokens
> por minuto para este modelo, contando entrada y salida. Cada consulta envía
> hasta `MAX_CARACTERES_CONTEXTO` (6,500 por defecto) caracteres del documento
> más el historial del chat, así que varias consultas seguidas agotan el cupo y
> el SDK reintenta hasta `GROQ_MAX_RETRIES` veces respetando la cabecera
> `Retry-After` de Groq (la respuesta pasa de ~2 s a 10–18 s); agotados los
> reintentos, el servicio responde 503. Un plan de pago elimina esa espera.
>
> Cada dictamen y cada respuesta del chat informan los tokens consumidos en
> `contexto_llm.uso_tokens` (`prompt_tokens`, `completion_tokens`,
> `total_tokens` y `desde_cache`). Medido: una Constancia de Situación Fiscal
> consume 1,780 tokens por auditoría y un turno de chat, unos 500; una
> reauditoría servida por el caché, 0. El historial del chat admite hasta 20
> turnos (422 si se excede).

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
| `POST` | `/api/v1/ai/documentos/{id}/preparar` | 3 | Resuelve el texto de un documento de la bóveda (memoria, disco u OCR) sin llamar al modelo. |
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

**La vigencia la deciden las reglas del rules-service.** El dictamen no fija
plazos por su cuenta: envía las fechas que extrajo el modelo y el tipo registrado
del documento a `POST /api/v1/reglas/evaluar-vigencia` (`RULES_BASE_URL`), que
aplica las reglas RCV activas: RCV-01 (días para el vencimiento) y RCV-02
(comprobante de domicilio con máximo 90 días naturales desde su emisión). Un
resultado VENCIDO produce NO_CONFORME; INDETERMINADO (sin fecha de emisión) turna
el caso a revisión humana. Si el rules-service no responde, el dictamen tampoco
se aprueba en automático: pasa a revisión humana con el motivo registrado.

**La confianza del Nivel 4 se acota por la del Nivel 3.** Por sólida que sea la
lectura del modelo, no puede ser más fiable que el texto que se le entregó.

**Corte temprano del OCR.** Para responder rápido la primera vez, el OCR se
detiene al reunir `MAX_CARACTERES_CONTEXTO` caracteres o tras `MAX_PAGINAS_OCR`
(6) páginas escaneadas; el resto se lee en segundo plano cuando se usa el
chat (la auditoría solo necesita los datos de identificación). La traza
informa `paginas_omitidas_ocr` y `extraccion_parcial`, y el endpoint
`/ai/extraer-texto` acepta `texto_completo=true` para reconocer todas las
páginas.

**OCR en paralelo.** Las páginas escaneadas se reconocen en tandas de
`OCR_WORKERS` páginas simultáneas (por defecto, los procesadores lógicos: con un
hilo OpenMP por proceso, Tesseract sí gana con SMT; ver
`docs/VALIDACION_CUANTITATIVA.md` §5). La
rasterización ocurre en el hilo principal, porque PyMuPDF no es seguro entre
hilos. Cada Tesseract se limita a un hilo interno (`OMP_THREAD_LIMIT=1`) para no
sobresuscribir el CPU, y el corte temprano se evalúa al terminar cada tanda.
Mediciones en un Ryzen 5 3500U (4 núcleos) con un acta escaneada de 26 páginas:

| Escenario | Tiempo |
|---|---|
| Secuencial, sin corte temprano (26 páginas) | 224.8 s |
| Secuencial, con corte temprano (4 páginas) | 34.5 s |
| **4 workers, con corte temprano (4 páginas)** | **11.5 s** |
| 8 workers, con corte temprano (6 páginas) | 17.0 s |
| 4 workers, sin corte temprano (26 páginas) | 92.1 s |

Con 8 workers empeora: SMT no acelera a Tesseract, y una tanda mayor reconoce
páginas que no hacían falta.

**Fragmentos relevantes en lugar del inicio del documento.** Al modelo llegan
como máximo `MAX_CARACTERES_CONTEXTO` caracteres. Si el documento no cabe, se
envía su encabezado (`ENCABEZADO_CARACTERES`: fedatario, denominación y
otorgantes) más los fragmentos de `FRAGMENTO_CARACTERES` que mejor responden a
la consulta según BM25 (`pipelines/fragmentos.py`). La recuperación es léxica y
determinista: normaliza acentos, descarta palabras vacías, aplica un stemming
ligero en español, da un bono a las frases de dos palabras ("capital social") y
expande preguntas legales frecuentes ("¿quién…?" también busca "designa" o
"nombramiento"). La auditoría usa una consulta fija con los datos que extrae y
las cláusulas de un acta (capital social, acciones, comisario, facultades y
firmas). El chat usa la pregunta del analista con hasta `MAX_FRAGMENTOS_CHAT`
fragmentos. En un acta de 26 páginas (133,636 caracteres), el chat encuentra el
capital social (al 12 % del documento) y la designación del comisario (al 82 %).

**Persistencia del texto extraído.** Además del caché LRU en memoria, cada
extracción se guarda en SQLite (`EXTRACCIONES_DB_PATH`, por defecto
`data/extracciones.sqlite3`; en Docker, el volumen `plurione_ai_data`), indexada
por la huella SHA-256 del binario. Un documento ya leído no vuelve a pasar por
OCR aunque se reinicie el servicio: el acta de 26 páginas se sirve desde disco en
0.2 s en lugar de 89 s. Cuando el corte temprano deja páginas sin leer, la
lectura completa se hace en segundo plano (`COMPLETAR_LECTURA_EN_SEGUNDO_PLANO`)
al primer uso del chat —no en la auditoría— y reemplaza a la parcial al terminar.

**Caché de inferencias.** A temperatura 0.0 la respuesta del modelo se guarda en
la misma SQLite (tabla `inferencias`) por huella SHA-256 de la petición exacta
(modelo, parámetros, prompt, texto y titular). Reauditar el mismo documento no
consume tokens de Groq (medido: 0.8 s → 0.0 s de inferencia); cualquier cambio
en el texto, el titular o el prompt produce otra clave. `GROQ_CACHE_INFERENCIAS=false`
lo desactiva. El chat no se guarda.

**Preprocesamiento de fotos.** Las imágenes de menos de 1,800 px de ancho se
amplían antes del OCR. Si la binarización de Otsu deja más del 25 % de la página
en negro (una foto con sombra), se repite con corrección de contraste CLAHE y
umbral adaptativo. Sobre una foto sintética de recibo a 110 ppp con sombra, la
exactitud pasa de 0 % a 94-97 %; en escaneos con iluminación pareja el resultado
es idéntico al anterior (98.0 % en la constancia de prueba).

**Caché del texto extraído.** El texto de cada `documento_id` se guarda en un
caché LRU en memoria (`CACHE_MAX_DOCUMENTOS`, 64 por defecto). La auditoría y
los turnos del chat lo reutilizan sin repetir el OCR, y si dos peticiones piden
el mismo documento a la vez, la extracción corre una sola vez. Las respuestas
del Nivel 4 incluyen `fuente_texto` (`cliente`, `cache` o `extraccion`) y
`tiempos_ms` con el desglose de cada fase. El caché se vacía al reiniciar el
servicio.

---

## 5. Pruebas

```powershell
python tests/generar_fixtures.py     # genera los documentos de prueba
python tests/test_niveles_3_4.py     # suite contra el servicio levantado
python tests/test_optimizaciones.py  # fragmentos, persistencia, caché, corte temprano y preprocesamiento (sin servidor)
python tests/test_vigencia_dictamen.py  # dictamen con las reglas de vigencia RCV (sin red)
```

`generar_fixtures.py` produce dos versiones del mismo documento ficticio: una
vectorial, con capa de texto, y otra rasterizada y degradada para imitar un
escaneo de oficina. Los datos son ficticios y están rotulados como tales dentro
del propio documento.

La suite requiere el servicio en el puerto 8003 y `GROQ_API_KEY` configurada.
Deja su evidencia en `tests/fixtures/evidencia_niveles_3_4.json`.
