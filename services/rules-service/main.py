"""
Rules Service — Motor de Validación de Cumplimiento Documental.
Responsable del catálogo de Reglas de Negocio (DOC-05: familias RIE, RCV,
RSC, RDS) y su CRUD / activación-desactivación.
Puerto: 8002.
"""
import os
import traceback
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import observabilidad
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

# Compresión de las respuestas JSON de más de 1 KB (el catálogo de reglas). Primero en
# registrarse, la capa más interna: ve la respuesta completa y su tamaño real.
app.add_middleware(GZipMiddleware, minimum_size=1000, compresslevel=5)


# Un error no controlado se responde aquí, dentro de la pila y antes de CORS
# (que se registra después y la envuelve). Sin esto, Starlette lo resuelve en
# su capa más externa, sin cabeceras CORS, y el navegador oculta la respuesta:
# el frontend decía «¿el microservicio está corriendo?» aunque estuviera en línea.
@app.middleware("http")
async def errores_no_controlados(request: Request, call_next):
    try:
        return await call_next(request)
    except ValueError as exc:
        # Q-c (OWASP ZAP): PostgreSQL no admite el carácter nulo en un texto. Llegaba
        # desde un filtro (?expediente_id=%00) o un campo del cuerpo y respondía 500.
        if "NUL (0x00)" not in str(exc):
            traceback.print_exc()
            return _error_interno()
        return JSONResponse(
            status_code=422,
            content={"detail": "La petición contiene un carácter nulo (0x00), que no se admite en los datos.",
                     "id_peticion": observabilidad.actual()},
        )
    except Exception:
        traceback.print_exc()  # el detalle queda en el registro del servidor
        return _error_interno()


def _error_interno() -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content={"detail": "Error interno del rules-service; el detalle quedó en el registro del servidor.",
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
app.include_router(regla_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
