# Prueba de seguridad del API con OWASP ZAP (P7, Q-c)

**Fecha:** 01/10/2026 · **Herramienta:** OWASP ZAP, imagen oficial `zaproxy/zap-stable`, `zap-api-scan.py` · **Requerimiento:** PRD §21.7 (Q-c), HU-61 · **Fundamento:** Ficha 045, actividad 6 (pruebas de seguridad); ISO/IEC 27001.

## Método

- `python scripts/zap_api.py` levanta el core-service (8201), el rules-service (8202) y el ai-service (8203) y corre ZAP en modo API contra el OpenAPI de cada uno. ZAP explora todas las operaciones declaradas y lanza el escaneo pasivo y el activo: inyección SQL (incluida la de PostgreSQL por tiempo), XSS reflejado y persistente, inclusión del lado del servidor, recorrido de rutas, inyección de comandos, divulgación de información, cabeceras y CORS. El escaneo activo tiene un tope de 10 minutos por servicio.
- **Aislamiento:** el escaneo activo envía miles de peticiones de ataque. Si llegaran a la base real, dejarían titulares y eventos basura para siempre, porque la bitácora es inmutable. Por eso los servicios corren sobre la base `plurione_compliance_zap` (recreada en cada corrida), con una bóveda temporal y una SQLite temporal del ai-service, y **sin clave de Groq**: no se consume ningún token.
- **Criterio:** un hallazgo alto sin justificación escrita hace fallar la corrida (código 1). Los medios y bajos se corrigen o se justifican aquí. El mismo script corre en el trabajo `zap` del CI, que guarda los informes como artefacto.
- **Cobertura:** 99 rutas del core-service, 45 del rules-service y 24 del ai-service. En los tres servicios se aprobaron 354 verificaciones.

## Resultados

| Pasada | Altos | Medios | Bajos | Informativos |
|---|---|---|---|---|
| 1. Línea base | 0 | 0 | 8 | 9 |
| 2. Tras corregir las cabeceras y los errores 500 | 0 | 0 | 4 | 6 |
| 3. Final, con CORP `same-origin` | **0** | **0** | **1** (justificado) | 6 |

Los informes completos de la pasada final están en `docs/resultados_validacion/zap/`: un HTML y un JSON por servicio, y `resumen.json`.

## Hallazgos corregidos

| Hallazgo (regla de ZAP) | Servicio | Causa | Corrección |
|---|---|---|---|
| Error del servidor (100000): `GET /bitacora?expediente_id=%00` y `GET /dictamenes?documento_id=%00` respondían 500 | core | PostgreSQL no admite el carácter nulo en un texto y psycopg2 lanzaba `ValueError`. Podía llegar desde un filtro o desde un campo del cuerpo. | El manejo de errores no controlados del core y del rules-service lo responde como 422 «La petición contiene un carácter nulo», con su folio. Prueba: `test_errores_core`, que falla sin la corrección, y `test_errores_rules`. |
| Error del servidor (100000): `POST /ai/analisis-semantico` respondía 500 con `OverflowError` | ai | La espera de la cola de reintentos (`15 min × 2^(intentos−1)`) desbordaba `timedelta` cuando un documento acumulaba unos 30 fallos. Puede pasar en producción si un analista reintenta muchas veces con el proveedor de IA caído. | El exponente se acota antes de multiplicar (commit `1736211`). Prueba: `test_excepciones_doc05`, que falla sin la corrección. |
| X-Content-Type-Options ausente (10021) | los tres | Las respuestas no declaraban `nosniff`. | Middleware `cabeceras_seguridad` en cada servicio. |
| Cross-Origin-Resource-Policy ausente o inválida (90004) | los tres | No se declaraba. En la segunda pasada `same-site` también se marcó, porque ZAP la considera insuficiente. | `Cross-Origin-Resource-Policy: same-origin` en toda respuesta. No afecta las llamadas `fetch` de la interfaz, que usan CORS. La imagen de página del visor, que la interfaz muestra con `<img>` desde otro puerto, declara `cross-origin` explícitamente. |
| Contenido almacenable en caché (10049) | los tres | Las respuestas con datos de cumplimiento podían guardarse en cachés intermedias. | `Cache-Control: no-store`, salvo donde la ruta define su propia política (la imagen del visor: `private, max-age=3600`). |

## Hallazgos justificados

| Hallazgo | Riesgo | Justificación |
|---|---|---|
| Error del servidor (100000) en `POST /ai/analisis-semantico` y `/ai/chat-documento` | Bajo | Son respuestas **503**, no 500. Es la respuesta prevista cuando el proveedor de IA no está disponible: la prueba corre sin clave de Groq a propósito, la auditoría entra en la cola de reintentos y el core la marca como diferida (DOC-05, Tabla 1). |
| Error del cliente (100000) | Informativo | Son respuestas 4xx (404, 409 y 422) a las entradas de ataque: es la validación funcionando. |
| Contenido no almacenable (10049) | Informativo | Es el efecto buscado de `Cache-Control: no-store`. |

## Riesgos que ZAP no reporta y que se declaran

- **Sin autenticación ni autorización.** Todos los endpoints son públicos para quien alcance la red de los servicios. Es una decisión de alcance: el Módulo 7 (RF-25, RF-26, HU-05, HU-06 y HU-31) está congelado hasta que el residente lo indique. ZAP no lo marca porque el escaneo de API no tiene un contexto de sesión contra el cual comparar. Mientras tanto, el despliegue debe mantener los puertos 8001 a 8003 dentro de la red interna de PluriOne (RNF-05).
- **CORS abierto (`allow_origins=["*"]`).** Hoy no expone credenciales porque no hay sesión ni cookies. Al llegar el Módulo 7, los orígenes deben quedar en una lista configurable del dominio de la interfaz.

## Cómo repetirla

```bash
python scripts/zap_api.py --minutos 10                 # requiere Docker y PostgreSQL
python scripts/zap_api.py --servicios core-service     # un solo servicio (los tres se levantan igual)
```
