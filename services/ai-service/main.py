"""
AI Service — Motor de Validación de Cumplimiento Documental.
Sprint 0 (Semana 4): esqueleto vivo con únicamente su health check.
A partir de la Semana 5 alojará el Nivel 3 (extracción de texto / OCR) y el
Nivel 4 (análisis semántico con IA) del pipeline de validación (DOC-05).
Puerto: 8003.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from controllers.health_controller import router as health_router

app = FastAPI(
    title="AI Service — Motor de Validación de Cumplimiento Documental",
    description="Microservicio de análisis inteligente de documentos (esqueleto, Sprint 0 / Semana 4).",
    version="0.1.0",
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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)
