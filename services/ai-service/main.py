"""
AI Service — Motor de Validación de Cumplimiento Documental.

Aloja los Niveles 3 y 4 del pipeline de validación (DOC-05):

  * **Nivel 3 — Extracción de texto.** Pipeline híbrido que lee la capa
    vectorial del PDF con PyMuPDF y deriva a OCR (Tesseract, con
    preprocesamiento OpenCV) únicamente las páginas escaneadas.
  * **Nivel 4 — Análisis semántico.** Inferencia contra un modelo de lenguaje
    servido por Groq Cloud (qwen/qwen3.8-27b, sobre la LPU de Groq). Se
    conserva la minimización de datos: solo viaja el texto que extrajo el
    Nivel 3, nunca el documento original, y Groq no retiene por defecto las
    entradas ni las salidas de inferencia.

Puerto: 8003.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from pipelines import extraccion_pipeline
from controllers.health_controller import precargar as precargar_salud
from controllers.health_controller import router as health_router
from controllers.extraccion_controller import router as extraccion_router
from controllers.analisis_controller import router as analisis_router
from controllers.visor_controller import router as visor_router


def _diagnostico_arranque() -> None:
    """
    Diagnóstico y precarga de arranque.

    El servicio levanta aunque sus dependencias externas no estén listas: de esa
    forma el operador puede consultar `/api/v1/health` y ver exactamente qué
    falta, en lugar de enfrentarse a un contenedor que no arranca.

    Groq y Tesseract se consultan una sola vez y su estado queda en el caché del
    health check (``precargar``): el primer sondeo del frontend responde de
    inmediato y la primera inferencia reutiliza la conexión HTTPS ya abierta.
    """
    print(f"[ai-service] Motor de inferencia: Groq Cloud ({settings.GROQ_BASE_URL})")
    estado, diagnostico = precargar_salud()
    if estado["modelo_disponible"]:
        print(f"[ai-service] Modelo '{settings.GROQ_MODEL}' disponible y listo para inferencia.")
    else:
        print(f"[ai-service] AVISO: {estado['detalle']}")

    if diagnostico.get("disponible"):
        print(
            f"[ai-service] Tesseract {diagnostico['version']} activo "
            f"(idiomas: {', '.join(diagnostico['idiomas_disponibles'])})."
        )
    else:
        print(f"[ai-service] AVISO: {diagnostico.get('detalle')}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    _diagnostico_arranque()
    yield
    extraccion_pipeline.cerrar()
    print("[ai-service] Pool de OCR cerrado; servicio detenido.")


app = FastAPI(
    title="AI Service — Motor de Validación de Cumplimiento Documental",
    description=(
        "Microservicio de análisis inteligente de documentos (API RESTful /api/v1). "
        "Implementa el Nivel 3 (extracción de texto con OCR) y el Nivel 4 (análisis "
        "semántico con LLM vía Groq Cloud) del pipeline de validación del DOC-05."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

# Permitir llamadas CORS desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(extraccion_router)
app.include_router(analisis_router)
app.include_router(visor_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
