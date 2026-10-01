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

from config import observabilidad
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
        content={"detail": "Error interno del core-service; el detalle quedó en el registro del servidor.",
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
    # El frontend lee el nombre de los reportes descargados (RF-24) y la huella del binario.
    expose_headers=["Content-Disposition", "X-Hash-SHA256", "X-Request-ID"],
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
