"""
Rules Service — Motor de Validación de Cumplimiento Documental.
Responsable del catálogo de Reglas de Negocio (DOC-05: familias RIE, RCV,
RSC, RDS) y su CRUD / activación-desactivación.
Puerto: 8002.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import init_db
from controllers.regla_controller import router as regla_router
from controllers.health_controller import router as health_router

app = FastAPI(
    title="Rules Service — Motor de Validación de Cumplimiento Documental",
    description="Microservicio responsable del catálogo de Reglas de Negocio (API RESTful /api/v1).",
    version="1.0.0",
)

# Permitir llamadas CORS desde el frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    print("[rules-service] Sincronizando modelos con PostgreSQL...")
    init_db()


app.include_router(health_router)
app.include_router(regla_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
