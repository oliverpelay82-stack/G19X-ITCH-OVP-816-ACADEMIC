"""
Configuración central del AI Service (:8003).

El motor de inferencia del Nivel 4 es Groq Cloud (API OpenAI-compatible servida
sobre la LPU de Groq). Se mantiene el principio de minimización de datos
(DOC-03): al modelo solo viaja el texto que ya extrajo el Nivel 3, nunca el
documento original, cifrado en tránsito (TLS). Por defecto Groq no retiene las
entradas ni las salidas de inferencia y no las usa para entrenar modelos.
"""
import os
import shutil

from dotenv import load_dotenv

# Cargar variables del archivo .env del servicio, resuelto de forma independiente
# al directorio de trabajo actual. En Docker las variables llegan del entorno y
# tienen precedencia, porque load_dotenv no sobreescribe lo ya definido.
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

# ── Motor de inferencia: Groq Cloud (LPU) ───────────────────────────
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
GROQ_BASE_URL: str = os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_TIMEOUT: int = int(os.getenv("GROQ_TIMEOUT", "30"))
# Reintentos ante 429, 5xx y fallos de red. Los hace el SDK de OpenAI con backoff
# exponencial que respeta la cabecera Retry-After de Groq; no hay otra capa.
GROQ_MAX_RETRIES: int = int(os.getenv("GROQ_MAX_RETRIES", "2"))
# Tope de tokens de salida por respuesta. También acota el consumo del límite de
# tokens por minuto del plan de Groq, que cuenta entrada y salida.
GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "1000"))
# Auditoría documental: temperatura 0.0 para respuestas deterministas y
# reproducibles ante un mismo documento (requisito de trazabilidad, DOC-05).
GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.0"))
# Reutiliza la respuesta del modelo ante una petición idéntica (mismo texto,
# titular, prompt, modelo y parámetros). Solo aplica a temperatura 0.0, donde la
# respuesta es reproducible; una reauditoría del mismo documento no consume
# tokens. Desactívelo para obligar a consultar de nuevo al modelo.
GROQ_CACHE_INFERENCIAS: bool = os.getenv("GROQ_CACHE_INFERENCIAS", "true").strip().lower() in (
    "1", "true", "si", "sí", "yes",
)
# Límite de tokens por minuto del plan de Groq (8,000 en el gratuito). El chat
# acota su contexto si su petición no cabe en lo que el proceso gastó en el último
# minuto (T4, PLUS-11; pipelines/presupuesto_tokens.py). 0 lo desactiva.
GROQ_TOKENS_POR_MINUTO: int = int(os.getenv("GROQ_TOKENS_POR_MINUTO", "8000"))
# Segundos que el chat conserva en memoria los criterios de contenido de un tipo de
# documento (el catálogo cambia rara vez). El dictamen se lee en vivo en cada turno.
CHAT_TTL_CRITERIOS_SEGUNDOS: int = int(os.getenv("CHAT_TTL_CRITERIOS_SEGUNDOS", "300"))

# ── Motor OCR (Tesseract) ───────────────────────────────────────────
def _resolver_tesseract() -> str:
    """Localiza el binario de Tesseract en PATH o en su ruta típica de Windows."""
    explicito = os.getenv("TESSERACT_CMD")
    if explicito:
        return explicito
    en_path = shutil.which("tesseract")
    if en_path:
        return en_path
    return r"C:\Program Files\Tesseract-OCR\tesseract.exe"


TESSERACT_CMD: str = _resolver_tesseract()
# Solo español: los documentos del DOC-02 son mexicanos. Añadir "eng" hacía que
# Tesseract evaluara dos modelos por renglón (≈ 30 % más lento, medido en un acta
# de 14 páginas) sin mejorar la lectura de RFC, fechas ni razón social
# (docs/VALIDACION_CUANTITATIVA.md §5).
OCR_LANG: str = os.getenv("OCR_LANG", "spa")

# Los modelos de idioma se versionan dentro del propio servicio para que el
# despliegue no dependa de que el instalador de Tesseract haya incluido 'spa'.
_TESSDATA_LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tessdata")
TESSDATA_PREFIX: str = os.getenv("TESSDATA_PREFIX", _TESSDATA_LOCAL)
if os.path.isdir(TESSDATA_PREFIX):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_PREFIX

# Resolución de rasterizado de las páginas PDF antes del OCR. 300 ppp es el
# mínimo recomendado para texto de 8-10 pt en documentos fiscales escaneados.
OCR_DPI: int = int(os.getenv("OCR_DPI", "300"))

# Segunda lectura de las zonas con sellos en tinta de color (pipelines/sellos.py):
# recupera el texto impreso que un sello tapa y registra la presencia de los
# sellos. Rasteriza las páginas escaneadas a color (el triple de memoria por
# hoja). Apagada por defecto: ningún DOC exige detectar sellos en tinta de color
# (el DOC-08 pide el Sello Digital SAT, que se detecta en el texto) y en el acta
# real medida la relectura no se activó en ninguna página. Se decide su retiro
# con el Gold Standard escaneado (docs/VALIDACION_CUANTITATIVA.md §5).
OCR_RELEER_SELLOS: bool = os.getenv("OCR_RELEER_SELLOS", "false").strip().lower() in ("1", "true", "si", "sí", "yes")

# ── Umbrales del pipeline (DOC-05 y DOC-08) ─────────────────────────
# Si una página vectorial rinde menos caracteres que esto, se asume que es una
# imagen escaneada embebida y se deriva a la ruta de OCR.
UMBRAL_CARACTERES_PAGINA: int = int(os.getenv("UMBRAL_CARACTERES_PAGINA", "120"))

# Bandas de clasificación del dictamen, tomadas literalmente del DOC-08 §6.2:
#   score >= 0.85            → CONFORME, si además se cumplen todas las reglas.
#   0.70 <= score <= 0.84    → REQUIERE REVISIÓN HUMANA (Nivel 5).
#   score <  0.70            → la lectura no es fiable; tampoco se resuelve en
#                              automático, se turna igualmente al Nivel 5.
# El rechazo nunca se deriva de una confianza baja: se reserva a hechos del
# documento (vigencia expirada o RFC ajeno al expediente).
UMBRAL_CONFIANZA_CONFORME: float = float(os.getenv("UMBRAL_CONFIANZA_CONFORME", "0.85"))
UMBRAL_CONFIANZA_HITL: float = float(os.getenv("UMBRAL_CONFIANZA_HITL", "0.70"))

# Límite de carga alineado con el Nivel 1 del core-service.
MAX_FILE_SIZE_BYTES: int = 15 * 1024 * 1024

# Recorte del contexto enviado al LLM (protege la ventana de contexto y los límites de Groq).
MAX_CARACTERES_CONTEXTO: int = int(os.getenv("MAX_CARACTERES_CONTEXTO", "6500"))

# Corte temprano del OCR. El texto que excede MAX_CARACTERES_CONTEXTO se trunca
# antes de llegar al LLM, así que rasterizar y reconocer las páginas siguientes
# es cómputo desperdiciado: el OCR se detiene al alcanzar ese volumen de texto
# o tras MAX_PAGINAS_OCR páginas escaneadas, lo que ocurra primero. Las páginas
# con capa vectorial se siguen leyendo porque su costo es despreciable.
MAX_PAGINAS_OCR: int = int(os.getenv("MAX_PAGINAS_OCR", "6"))

# Páginas escaneadas que se reconocen en paralelo. Por defecto, los procesadores
# lógicos: con un hilo OpenMP por proceso, Tesseract sí gana con SMT (acta de 14
# páginas en un Ryzen 5 3500U de 4 núcleos y 8 hilos: 25.2 s con 4 procesos,
# 15.9 s con 8; docs/VALIDACION_CUANTITATIVA.md §5).
OCR_WORKERS: int = max(1, int(os.getenv("OCR_WORKERS", str(os.cpu_count() or 2))))

# Cada proceso de Tesseract abriría por defecto varios hilos OpenMP; con varias
# páginas en paralelo eso sobresuscribe el CPU y lo vuelve más lento. Un hilo
# por proceso deja que el paralelismo lo aporten los workers.
if OCR_WORKERS > 1:
    os.environ.setdefault("OMP_THREAD_LIMIT", "1")

# Documentos cuyo texto extraído se conserva en memoria (caché LRU) para que la
# auditoría y los turnos del chat no repitan el Nivel 3 sobre el mismo archivo.
CACHE_MAX_DOCUMENTOS: int = int(os.getenv("CACHE_MAX_DOCUMENTOS", "64"))

# Persistencia permanente del texto extraído (SQLite), indexada por la huella
# SHA-256 del binario: un documento ya leído no vuelve a pasar por OCR aunque se
# reinicie el servicio. En Docker el archivo vive en un volumen.
EXTRACCIONES_DB_PATH: str = os.getenv(
    "EXTRACCIONES_DB_PATH",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "extracciones.sqlite3"),
)

# Cuando el corte temprano deja páginas sin leer, el documento completo se
# reconoce en segundo plano; al terminar, la búsqueda de fragmentos abarca todas
# las páginas. La respuesta inicial no espera a esa lectura completa.
COMPLETAR_LECTURA_EN_SEGUNDO_PLANO: bool = os.getenv("COMPLETAR_LECTURA_EN_SEGUNDO_PLANO", "true").lower() in (
    "1", "true", "si", "sí", "yes",
)

# Búsqueda de fragmentos relevantes (Nivel 4). En lugar de enviar solo el inicio
# del documento, se envía su encabezado y los fragmentos que mejor responden a la
# consulta, dentro del mismo presupuesto de MAX_CARACTERES_CONTEXTO.
FRAGMENTO_CARACTERES: int = int(os.getenv("FRAGMENTO_CARACTERES", "1200"))
# El encabezado cubre la identidad del documento: en un acta, el fedatario, la
# denominación y los otorgantes que comparecen (≈1,300 caracteres en la prueba).
ENCABEZADO_CARACTERES: int = int(os.getenv("ENCABEZADO_CARACTERES", "1500"))
MAX_FRAGMENTOS_CHAT: int = int(os.getenv("MAX_FRAGMENTOS_CHAT", "4"))
# Contexto de la verificación de contenido (reglas RSC/RDS): los mejores
# fragmentos de cada criterio. Con la extracción de la misma auditoría (~3,300
# tokens) debe quedar por debajo del límite de 8,000 tokens por minuto de Groq.
MAX_CARACTERES_VERIFICACION: int = int(os.getenv("MAX_CARACTERES_VERIFICACION", "9500"))

# ── Integración con el core-service (:8001) ─────────────────────────
CORE_BASE_URL: str = os.getenv("CORE_BASE_URL", "http://127.0.0.1:8001").rstrip("/")

# ── Integración con el rules-service (:8002) ────────────────────────
# El dictamen del Nivel 4 consulta ahí las reglas de vigencia (familia RCV):
# RCV-01 (días para el vencimiento) y RCV-02 (antigüedad máxima del comprobante
# de domicilio fiscal, 90 días naturales desde su emisión).
RULES_BASE_URL: str = os.getenv("RULES_BASE_URL", "http://127.0.0.1:8002").rstrip("/")
_DEFAULT_VAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage_vault"
)
STORAGE_VAULT_PATH: str = os.getenv("STORAGE_VAULT_PATH", _DEFAULT_VAULT)
