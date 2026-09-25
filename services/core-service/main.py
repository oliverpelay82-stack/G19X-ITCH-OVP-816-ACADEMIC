"""
Core Service — Motor de Validación de Cumplimiento Documental.
Responsable de Titulares, Expedientes y Documentos (ingesta, magic bytes,
hash SHA-256 y almacenamiento físico en storage_vault).
Puerto: 8001.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import engine, init_db
from controllers.titular_controller import router as titular_router
from controllers.expediente_controller import router as expediente_router
from controllers.documento_controller import router as documento_router
from controllers.health_controller import router as health_router
from controllers.dictamen_controller import router as dictamen_router
from controllers.bitacora_controller import router as bitacora_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[core-service] Sincronizando modelos con PostgreSQL...")
    init_db()
    yield
    engine.dispose()
    print("[core-service] Pool de conexiones a PostgreSQL cerrado.")


app = FastAPI(
    title="Core Service — Motor de Validación de Cumplimiento Documental",
    description="Microservicio responsable de Titulares, Expedientes y Documentos (API RESTful /api/v1).",
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
app.include_router(titular_router)
app.include_router(expediente_router)
app.include_router(documento_router)
app.include_router(dictamen_router)
app.include_router(bitacora_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
