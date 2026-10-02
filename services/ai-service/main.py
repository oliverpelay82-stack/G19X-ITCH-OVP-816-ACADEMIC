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
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from clients.groq_client import IaNoConfiguradaError
from config import observabilidad
from config import settings
from pipelines import diferidos, extraccion_pipeline
from controllers import analisis_controller
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
    # P5 (DOC-05, Tabla 1): reintento automático de las auditorías diferidas.
    detener_diferidos = diferidos.iniciar_ciclo(analisis_controller.procesar_diferidos)
    yield
    if detener_diferidos:
        detener_diferidos.set()
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


# Sin la clave del proveedor de IA, la auditoría y el chat con el modelo no
# pueden ejecutarse: 503 con la instrucción para configurarla, no un error interno.
@app.exception_handler(IaNoConfiguradaError)
async def ia_no_configurada(request: Request, exc: IaNoConfiguradaError):
    return JSONResponse(status_code=503, content={"detail": str(exc), "id_peticion": observabilidad.actual()})


# Un error no controlado se responde aquí, dentro de la pila y antes de CORS
# (que se registra después y la envuelve). Sin esto, Starlette lo resuelve en
# su capa más externa, sin cabeceras CORS, y el navegador oculta la respuesta:
# el frontend decía «¿el microservicio está corriendo?» aunque estuviera en línea.
@app.middleware("http")
async def errores_no_controlados(request: Request, call_next):
    try:
        return await call_next(request)
    except Exception:
        traceback.print_exc()  # el detalle queda en el registro del servidor
        return JSONResponse(
            status_code=500,
            content={"detail": "Error interno del ai-service; el detalle quedó en el registro del servidor.",
                     "id_peticion": observabilidad.actual()},
        )


# PLUS-21: folio de seguimiento (X-Request-ID) y una línea de registro por petición.
# Va por fuera del manejo de errores, para que un 500 también lleve su folio, y
# por dentro de CORS, que lo expone al navegador.
app.middleware("http")(observabilidad.middleware)


# Q-c (OWASP ZAP): cabeceras de seguridad en toda respuesta, por dentro de CORS.
# CORP same-origin no afecta las llamadas fetch de la interfaz (usan CORS); un
# recurso hecho para incrustarse desde otro origen declara el suyo.
@app.middleware("http")
async def cabeceras_seguridad(request: Request, call_next):
    respuesta = await call_next(request)
    respuesta.headers.setdefault("X-Content-Type-Options", "nosniff")
    respuesta.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
    # Datos de cumplimiento: ningún intermediario los guarda, salvo que la ruta indique otra cosa.
    respuesta.headers.setdefault("Cache-Control", "no-store")
    return respuesta


# Permitir llamadas CORS desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)

app.include_router(health_router)
app.include_router(extraccion_router)
app.include_router(analisis_router)
app.include_router(visor_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
