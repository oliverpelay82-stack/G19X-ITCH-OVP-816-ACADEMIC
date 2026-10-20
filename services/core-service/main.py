"""
Core Service — Motor de Validación de Cumplimiento Documental.
Responsable de Titulares, Expedientes y Documentos (ingesta, magic bytes,
hash SHA-256 y almacenamiento físico en storage_vault), del semáforo con sus
alertas y recomendaciones, y de los reportes de auditoría exportables.
Puerto: 8001.
"""
import asyncio
import os
import re
import traceback
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from config import cifrado_boveda, observabilidad, seguridad
from config.database import SessionLocal, engine, init_db
from controllers.asignacion_controller import router as asignacion_router
from controllers.asignacion_controller import router_usuarios as asignacion_usuarios_router
from controllers.auth_controller import router as auth_router
from controllers.usuario_controller import router as usuario_router
from controllers.titular_controller import router as titular_router
from controllers.expediente_controller import router as expediente_router
from controllers.documento_controller import router as documento_router
from controllers.health_controller import router as health_router
from controllers.dictamen_controller import router as dictamen_router
from controllers.bitacora_controller import router as bitacora_router
from controllers.alerta_controller import router as alerta_router
from controllers.reporte_controller import router as reporte_router
from controllers.configuracion_controller import router as configuracion_router
from motor import reevaluacion_programada, usuarios_iniciales


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Módulo 7: sin un JWT_SECRET válido el servicio no arranca (no podría firmar sesiones).
    seguridad.verificar_configuracion()
    # RNF-04: una BOVEDA_LLAVE mal formada no deja arrancar (cifraría o leería mal la bóveda).
    cifrado_boveda.verificar_configuracion()
    print("[core-service] Sincronizando modelos con PostgreSQL...")
    init_db()
    with SessionLocal() as db:
        creados = usuarios_iniciales.crear(db)
        sin_cuentas = not usuarios_iniciales.hay_cuentas(db)
    if creados:
        print(f"[core-service] Cuentas creadas al arrancar: {', '.join(creados)}")
    if sin_cuentas:
        print("[core-service] AVISO: no hay cuentas de usuario. Defina ADMIN_INICIAL_EMAIL y "
              "ADMIN_INICIAL_CONTRASENA (o USUARIOS_DEMO=true) y reinicie el servicio.")
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


class _GZipSalvoBinarios(GZipMiddleware):
    """
    Comprime las respuestas JSON (la lista de expedientes con su evaluación es la
    más pesada). No toca los originales de la bóveda ni los reportes: un PDF ya va
    comprimido y un Excel es un ZIP, así que volver a comprimirlos (hasta 15 MB en
    cada auditoría del ai-service) gastaría CPU sin reducir su tamaño.
    """

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and _RUTA_BINARIA.search(scope.get("path", "")):
            await self.app(scope, receive, send)
            return
        await super().__call__(scope, receive, send)


_RUTA_BINARIA = re.compile(r"/documentos/[^/]+/contenido$|/reportes/")
# Primero en registrarse, la capa más interna: ve la respuesta completa con su tamaño y
# solo comprime la de más de 1 KB (por fuera, el cuerpo le llegaría por partes y comprimiría todo).
app.add_middleware(_GZipSalvoBinarios, minimum_size=1000, compresslevel=5)


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
    except cifrado_boveda.LlaveBovedaError as exc:
        # RNF-04: la llave no es la que cifró la bóveda. Es configuración, no una
        # alteración: el documento no se marca y el servicio lo dice (503).
        return JSONResponse(status_code=503, content={"detail": str(exc), "id_peticion": observabilidad.actual()})
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


# CORS: solo los orígenes de la interfaz (Módulo 7; el informe de ZAP pedía dejar el
# comodín al llegar la autenticación). El token viaja en Authorization, sin cookies.
# Por omisión, Vite en desarrollo (5173) y el puerto de las pruebas aisladas (5174).
_ORIGENES_PREDETERMINADOS = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in os.getenv("CORS_ORIGENES", _ORIGENES_PREDETERMINADOS).split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    # El frontend lee el nombre de los reportes descargados (RF-24) y la huella del binario.
    expose_headers=["Content-Disposition", "X-Hash-SHA256", "X-Request-ID"],
)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(usuario_router)
app.include_router(asignacion_usuarios_router)
app.include_router(titular_router)
# Antes que el de expedientes: /expedientes/asignados no es /expedientes/{expediente_id}.
app.include_router(asignacion_router)
app.include_router(expediente_router)
app.include_router(documento_router)
app.include_router(dictamen_router)
app.include_router(bitacora_router)
app.include_router(alerta_router)
app.include_router(reporte_router)
app.include_router(configuracion_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
