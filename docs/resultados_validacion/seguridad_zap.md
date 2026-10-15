# Prueba de seguridad del API con OWASP ZAP (P7, Q-c)

**Fecha:** 01/10/2026; pasada con autenticación del Módulo 7, 15/10/2026 · **Herramienta:** OWASP ZAP, imagen oficial `zaproxy/zap-stable`, `zap-api-scan.py` · **Requerimiento:** PRD §21.7 (Q-c), HU-61 · **Fundamento:** Ficha 045, actividad 6 (pruebas de seguridad); ISO/IEC 27001.

## Método

- `python scripts/zap_api.py` levanta el core-service (8201), el rules-service (8202) y el ai-service (8203) y corre ZAP en modo API contra el OpenAPI de cada uno. ZAP explora todas las operaciones declaradas y lanza el escaneo pasivo y el activo: inyección SQL (incluida la de PostgreSQL por tiempo), XSS reflejado y persistente, inclusión del lado del servidor, recorrido de rutas, inyección de comandos, divulgación de información, cabeceras y CORS. El escaneo activo tiene un tope de 10 minutos por servicio.
- **Aislamiento:** el escaneo activo envía miles de peticiones de ataque. Si llegaran a la base real, dejarían titulares y eventos basura para siempre, porque la bitácora es inmutable. Por eso los servicios corren sobre la base `plurione_compliance_zap` (recreada en cada corrida), con una bóveda temporal y una SQLite temporal del ai-service, y **sin clave de Groq**: no se consume ningún token.
- **Sesión (desde el 15/10/2026):** desde el Módulo 7 cada ruta exige un token Bearer. Sin token, el escaneo activo solo vería respuestas 401 y no llegaría a la lógica. ZAP envía en cada petición el token del administrador de demostración (`ZAP_AUTH_HEADER_VALUE`), el rol que alcanza todas las rutas de persona. Los servicios aislados crean las cuentas de demostración con `USUARIOS_DEMO=true` (`scripts/sesion_api.py`).
- **Criterio:** un hallazgo alto sin justificación escrita hace fallar la corrida (código 1). Los medios y bajos se corrigen o se justifican aquí. El mismo script corre en el trabajo `zap` del CI, que guarda los informes como artefacto.
- **Cobertura:** el 01/10, 99 URL del core-service, 45 del rules-service y 24 del ai-service. El 15/10, con las rutas del Módulo 7 (sesión, usuarios, asignaciones, MFA), 122, 46 y 61. En cada pasada se aprobaron 354 verificaciones (118 por servicio).

## Resultados

| Pasada | Altos | Medios | Bajos | Informativos |
|---|---|---|---|---|
| 1. Línea base | 0 | 0 | 8 | 9 |
| 2. Tras corregir las cabeceras y los errores 500 | 0 | 0 | 4 | 6 |
| 3. Con CORP `same-origin` (01/10) | 0 | 0 | 1 (justificado) | 6 |
| 4. **Vigente:** con autenticación y token de administrador (15/10) | **0** | **0** | **1** (justificado, el mismo) | 6 |

**Qué respondió el core con el token del administrador (pasada 4)**, según el registro de peticiones del servicio:

- **422, 404, 409 y 400:** las entradas de ataque llegaron a la validación de cada operación, es decir, el token se aceptó y el escaneo alcanzó la lógica.
- **403 (2,302):** todos en las rutas reservadas al token SISTEMA del ai-service: `POST /dictamenes` (1,822), `POST /documentos/{id}/procesamiento-diferido` (474) y `GET /documentos/{id}/contenido` (6). Ni siquiera un administrador puede registrar un dictamen ni leer el binario por esa ruta (PRD §5.1).
- **401 (118) y 429 (129):** solo en `POST /auth/login`. Son las credenciales que ZAP prueba: el mismo 401 para un correo inexistente que para una contraseña incorrecta y, tras cinco fallos seguidos, el bloqueo de 15 minutos.
- **Ningún 500** en los tres servicios.

Los informes completos de la pasada vigente están en `docs/resultados_validacion/zap/`: un HTML y un JSON por servicio, y `resumen.json`.

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

Los dos riesgos que esta sección declaraba el 01/10 quedaron resueltos con el Módulo 7 (PRD §5.1 y §5.2):

- **Autenticación y autorización:** toda ruta, salvo la salud y el inicio de sesión, exige un JWT, y cada servicio autoriza con la matriz de permisos. Una prueba por servicio recorre la matriz completa (`test_permisos_roles`, `test_rules_autorizacion`, `test_autorizacion_ai`).
- **CORS:** `allow_origins=["*"]` se sustituyó por la lista de `CORS_ORIGENES`.

Siguen vigentes:

- **ZAP escanea con un solo rol.** El token del administrador no cubre las rutas reservadas al SISTEMA, que respondieron 403. Tampoco prueba la escalada entre roles; eso lo comprueban las pruebas de matriz anteriores, no ZAP.
- **Sin TLS en los servicios (RNF-05).** El token viaja en claro dentro de la red. El despliegue debe poner los servicios detrás de un proxy con HTTPS o mantener los puertos 8001 a 8003 en la red interna de PluriOne.
- **Secreto de demostración.** El `docker-compose.yml` trae un `JWT_SECRET` y cuentas de demostración para que la entrega levante con un solo comando, y `/health` del core lo advierte. En producción se reemplazan (README, «Acceso y roles»).

## Cómo repetirla

```bash
python scripts/zap_api.py --minutos 10                 # requiere Docker y PostgreSQL
python scripts/zap_api.py --servicios core-service     # un solo servicio (los tres se levantan igual)
```
