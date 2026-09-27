"""
Rules Service — Motor de Validación de Cumplimiento Documental.
Responsable del catálogo de Reglas de Negocio (DOC-05: familias RIE, RCV,
RSC, RDS) y su CRUD / activación-desactivación.
Puerto: 8002.
"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config.database import engine, init_db
from controllers.regla_controller import router as regla_router
from controllers.health_controller import router as health_router
from seed_reglas_validacion import precargar_reglas


@asynccontextmanager
async def lifespan(app: FastAPI):
    print("[rules-service] Sincronizando modelos con PostgreSQL...")
    init_db()
    # Catálogo base del DOC-05: se insertan solo las reglas que falten.
    if os.getenv("AUTO_SEED", "true").strip().lower() not in ("false", "0", "no"):
        insertadas = precargar_reglas(verboso=False, sincronizar=False)
        print(f"[rules-service] Catálogo de reglas verificado ({insertadas} reglas base agregadas).")
    yield
    engine.dispose()
    print("[rules-service] Pool de conexiones a PostgreSQL cerrado.")


app = FastAPI(
    title="Rules Service — Motor de Validación de Cumplimiento Documental",
    description="Microservicio responsable del catálogo de Reglas de Negocio (API RESTful /api/v1).",
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
app.include_router(regla_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
