# Frontend — Motor de Validación de Cumplimiento Documental

Interfaz oficial del sistema (PluriOne S.A. de C.V.), en React 19 con Vite. Consume los tres microservicios del backend: core-service (`:8001`), rules-service (`:8002`) y ai-service (`:8003`). La guía técnica completa del proyecto está en [`../CLAUDE.md`](../CLAUDE.md) y la descripción general en [`../README.md`](../README.md).

## Comandos

Desde esta carpeta, con Node 22:

| Comando | Qué hace |
|---|---|
| `npm install` | Instala las dependencias. |
| `npm run dev` | Servidor de desarrollo en `http://127.0.0.1:5173`. |
| `npm run build` | Build de producción en `dist/`. |
| `npm run lint` | oxlint (`.oxlintrc.json`: reglas de hooks, dependencias de efectos y variables sin usar). |
| `npm run test:ui` | Equivalencia de marcado de los componentes del sistema de diseño (`scripts/verificar-ui.mjs`). |

La CI (`../.github/workflows/ci.yml`) ejecuta `lint`, `test:ui` y `build` en cada push y pull request.

## Configuración

Las URL de los servicios se fijan en el build con `VITE_CORE_URL`, `VITE_RULES_URL` y `VITE_AI_URL`; por defecto apuntan a `http://127.0.0.1:8001/api/v1`, `:8002/api/v1` y `:8003/api/v1`.

## Estructura

| Carpeta | Contenido |
|---|---|
| `src/components/` | Vistas (Empresas, Expedientes, Bóveda, Alertas, Reportes, Reglas) y sus piezas. |
| `src/components/ui/` | Biblioteca del sistema de diseño «White & Warm Minimalist», exportada desde `index.js`. |
| `src/index.css` | Tokens maestros (color, tipografía, espaciado, radios, alturas de control) y temas claro y oscuro. |
| `src/App.css` | Estilos de los componentes; solo consumen tokens. |
| `src/services/api.js` | Cliente HTTP de los tres microservicios. |
| `src/dev/` | Catálogo del sistema de diseño en `#/ui`, solo con `npm run dev`; no llega al build de producción. |
| `scripts/` | Prueba `test:ui`. |

## Pruebas en el navegador

Requieren `npm run dev`, los servicios en marcha y Playwright para Python con Chrome. Se ejecutan desde la raíz del proyecto:

- `python scripts/regresion_visual.py capturar base|actual` y `comparar`: regresión visual de 138 capturas en 1366x768 y 1920x1080, en ambos temas.
- `python scripts/prueba_sondeo_colgado.py`: el sondeo no apila peticiones sobre un servicio que no responde.
- `python scripts/prueba_carga_fallida.py`: una carga rechazada no deja promesas sin capturar y conserva el archivo.

Ninguna escribe en la base de datos ni consume Groq.
