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
# Tope de tokens de salida por respuesta. También acota el consumo del límite de
# tokens por minuto del plan de Groq, que cuenta entrada y salida.
GROQ_MAX_TOKENS: int = int(os.getenv("GROQ_MAX_TOKENS", "1000"))
# Auditoría documental: temperatura 0.0 para respuestas deterministas y
# reproducibles ante un mismo documento (requisito de trazabilidad, DOC-05).
GROQ_TEMPERATURE: float = float(os.getenv("GROQ_TEMPERATURE", "0.0"))

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
OCR_LANG: str = os.getenv("OCR_LANG", "spa+eng")

# Los modelos de idioma se versionan dentro del propio servicio para que el
# despliegue no dependa de que el instalador de Tesseract haya incluido 'spa'.
_TESSDATA_LOCAL = os.path.join(os.path.dirname(os.path.dirname(__file__)), "tessdata")
TESSDATA_PREFIX: str = os.getenv("TESSDATA_PREFIX", _TESSDATA_LOCAL)
if os.path.isdir(TESSDATA_PREFIX):
    os.environ["TESSDATA_PREFIX"] = TESSDATA_PREFIX

# Resolución de rasterizado de las páginas PDF antes del OCR. 300 ppp es el
# mínimo recomendado para texto de 8-10 pt en documentos fiscales escaneados.
OCR_DPI: int = int(os.getenv("OCR_DPI", "300"))

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

# Recorte del contexto enviado al LLM (protege la ventana de contexto del modelo).
MAX_CARACTERES_CONTEXTO: int = int(os.getenv("MAX_CARACTERES_CONTEXTO", "12000"))

# ── Integración con el core-service (:8001) ─────────────────────────
CORE_BASE_URL: str = os.getenv("CORE_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
_DEFAULT_VAULT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "storage_vault"
)
STORAGE_VAULT_PATH: str = os.getenv("STORAGE_VAULT_PATH", _DEFAULT_VAULT)
