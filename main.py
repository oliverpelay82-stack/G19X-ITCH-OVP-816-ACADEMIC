"""
Punto de entrada principal de la aplicación.
Equivalente a @SpringBootApplication en Spring Boot.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import init_db
from controllers.titular_controller import router as titular_router
from controllers.expediente_controller import router as expediente_router
from controllers.documento_controller import router as documento_router

# Inicializar la aplicación FastAPI
app = FastAPI(
    title="Motor de Validación de Cumplimiento Documental",
    description="API RESTful para el Motor de Validación de Cumplimiento Documental B2B (FastAPI + MySQL).",
    version="1.0.0",
)

# Permitir llamadas CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Sincronizar tablas al iniciar
@app.on_event("startup")
def on_startup():
    print("[Sistema] Sincronizando modelos con MySQL...")
    init_db()


# Registrar los Controladores
app.include_router(titular_router)
app.include_router(expediente_router)
app.include_router(documento_router)


from fastapi.responses import HTMLResponse
import os

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def panel_vista():
    """Vista básica (V de MVC) para visualizar y probar el sistema."""
    ruta_vista = os.path.join("views", "panel.html")
    if os.path.exists(ruta_vista):
        with open(ruta_vista, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Cargando vista...</h1>")


@app.get("/api/v1/status", tags=["General"])
def root():
    return {
        "status": "online",
        "service": "Motor de Validación de Cumplimiento Documental",
        "database": "MySQL 8.0 (plurione_compliance)",
        "docs": "http://127.0.0.1:8000/docs",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
