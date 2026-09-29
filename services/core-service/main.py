"""
Core Service — Motor de Validación de Cumplimiento Documental.
Responsable de Titulares, Expedientes y Documentos (ingesta, magic bytes,
hash SHA-256 y almacenamiento físico en storage_vault), del semáforo con sus
alertas y recomendaciones, y de los reportes de auditoría exportables.
Puerto: 8001.
"""
import asyncio
import traceback
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from config.database import engine, init_db
from controllers.titular_controller import router as titular_router
from controllers.expediente_controller import router as expediente_router
from controllers.documento_controller import router as documento_router
from controllers.health_controller import router as health_router
from controllers.dictamen_controller import router as dictamen_router
from controllers.bitacora_controller import router as bitacora_router
from controllers.alerta_controller import router as alerta_router
from controllers.reporte_controller import router as reporte_router
from motor import reevaluacion_programada


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[core-service] Sincronizando modelos con PostgreSQL...")
    init_db()
    horas = reevaluacion_programada.intervalo_horas()
    tarea = asyncio.create_task(reevaluacion_programada.ciclo(horas)) if horas else None
    yield
    if tarea:
        tarea.cancel()
        with suppress(asyncio.CancelledError):
            await tarea
    engine.dispose()
    print("[core-service] Pool de conexiones a PostgreSQL cerrado.")


app = FastAPI(
    title="Core Service — Motor de Validación de Cumplimiento Documental",
    description="Microservicio responsable de Titulares, Expedientes y Documentos (API RESTful /api/v1).",
    version="1.0.0",
    lifespan=lifespan,
)


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
            content={"detail": "Error interno del core-service; el detalle quedó en el registro del servidor."},
        )


# Permitir llamadas CORS desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    # El frontend lee el nombre de los reportes descargados (RF-24) y la huella del binario.
    expose_headers=["Content-Disposition", "X-Hash-SHA256"],
)

app.include_router(health_router)
app.include_router(titular_router)
app.include_router(expediente_router)
app.include_router(documento_router)
app.include_router(dictamen_router)
app.include_router(bitacora_router)
app.include_router(alerta_router)
app.include_router(reporte_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
