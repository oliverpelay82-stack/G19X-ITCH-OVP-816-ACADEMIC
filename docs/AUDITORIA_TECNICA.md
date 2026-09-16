# Auditoría Técnica del Motor de Validación — Estado Actual vs. Documentación Oficial

> Fecha: 14 de septiembre de 2026  
> Modelo Auditor: Claude Opus 4.6  
> Archivos revisados: **DOC-01 a DOC-08**, **Anteproyecto (Ficha 045)**, **`motor de validacion/`** (código fuente completo)

---

## 1. ¿Qué dice la Documentación Oficial que debe existir?

Conforme al **DOC-04 (SRS)**, el sistema comprende **7 módulos funcionales**:

| Módulo | Nombre Oficial | Descripción |
|:---|:---|:---|
| **M1** | Gestión de Expedientes | Carga, organización, almacenamiento e integridad (SHA-256) |
| **M2** | Reglas de Validación Configurables | Obligatoriedad de documentos, anexos, niveles de severidad |
| **M3** | Análisis Inteligente de Documentos | OCR, extracción de texto, análisis semántico con IA |
| **M4** | Verificación de Vigencia | Cálculo de fecha de emisión vs. vigencia máxima, alertas de caducidad |
| **M5** | Alertas y Recomendaciones | Semáforos de riesgo, notificaciones de vencimiento |
| **M6** | Reportes y Panel de Control | Dashboard con indicadores, semáforos, exportación PDF/Excel |
| **M7** | Administración y Seguridad | Usuarios con roles (Admin, Validador, Auditor, Consulta), bitácora |

Conforme al **DOC-08 (Arquitectura)**, la base de datos necesita **7 tablas**:

| Tabla | Descripción |
|:---|:---|
| `usuarios` | Usuarios del sistema con roles y contraseñas hasheadas |
| `titulares_expediente` | Empresas, clientes o proveedores a evaluar |
| `expedientes` | Agrupador de documentos de un titular |
| `documentos` | Archivos cargados con hash SHA-256 y metadatos |
| `reglas_validacion` | Catálogo de reglas configurables por tipo de documento |
| `dictamenes_auditoria` | Resultados de evaluación (APROBADO/RECHAZADO) con score |
| `logs_auditoria_sistema` | Bitácora inmutable de eventos del sistema |

Conforme al **DOC-05 (Estrategia de Validación)**, el pipeline opera en **5 niveles**:

| Nivel | Nombre | Qué hace |
|:---|:---|:---|
| **1** | Validación Estructural y Criptográfica | MIME válido, no corrupto, cálculo SHA-256 |
| **2** | Validación Determinista (Reglas de Backend) | Vigencia, completitud, obligatoriedad |
| **3** | Extracción de Texto | OCR / parseo de PDF para obtener contenido |
| **4** | Análisis Semántico Asistido (IA) | Cruce de RFC, razón social, cláusulas con LLM |
| **5** | Gobernanza Humana (Human-in-the-Loop) | Revisión manual de dictámenes con baja confianza |

---

## 2. ¿Qué existe hoy en el código?

### Estructura actual del proyecto:

```
motor de validacion/
├── .env                          # ✅ Configuración MySQL
├── config/
│   └── database.py               # ✅ Conexión SQLAlchemy + MySQL
├── models/
│   ├── titular.py                # ✅ Tabla titulares_expediente
│   ├── expediente.py             # ✅ Tabla expedientes
│   └── documento.py              # ✅ Tabla documentos
├── controllers/
│   ├── titular_controller.py     # ✅ POST/GET /api/v1/titulares
│   ├── expediente_controller.py  # ✅ POST/GET /api/v1/expedientes
│   └── documento_controller.py   # ✅ POST/GET /api/v1/documentos
├── schemas/
│   ├── titular_schema.py         # ✅ DTOs Pydantic
│   ├── expediente_schema.py      # ✅ DTOs Pydantic
│   └── documento_schema.py       # ⚠️ Incompleto (solo Response, no hay Create)
├── views/
│   └── panel.html                # ⚠️ Panel provisional HTML (el final será React)
├── storage_vault/                # ✅ Bóveda física de archivos
├── main.py                       # ⚠️ Tiene errores de nomenclatura
├── requirements.txt              # ⚠️ Incompleto
└── test_conexion.py              # ✅ Script de prueba de conexión
```

---

## 3. Problemas Encontrados (Errores del Modelo Anterior)

### ❌ PROBLEMA 1: Nomenclatura incorrecta en `main.py`

El archivo [`main.py`](file:///c:/Users/HP/Desktop/RESIDENCIA%20PLURIONE/motor%20de%20validacion/main.py) línea 15 dice:

```python
title="PluriOne Sentinel - Motor de Cumplimiento",
```

**El nombre del proyecto NO es "PluriOne Sentinel".** El nombre oficial según la Ficha 045 y todos los documentos es: **"Motor de Validación de Cumplimiento Documental"**. PluriOne es la empresa receptora, no el nombre del producto.

También en línea 59:
```python
"service": "PluriOne Sentinel",
```

### ❌ PROBLEMA 2: Faltan 4 tablas de la base de datos (de 7 que pide el DOC-08)

Solo existen 3 modelos de las 7 tablas requeridas:

| Tabla del DOC-08 | ¿Existe en código? | Estado |
|:---|:---|:---|
| `usuarios` | ❌ **NO** | Falta completamente. No hay autenticación ni roles. |
| `titulares_expediente` | ✅ Sí | Funcional. |
| `expedientes` | ✅ Sí | Funcional. |
| `documentos` | ✅ Sí | Funcional. |
| `reglas_validacion` | ❌ **NO** | No existe. Sin esto no hay motor de reglas (M2). |
| `dictamenes_auditoria` | ❌ **NO** | No existe. Sin esto no hay dictámenes (M4/M5). |
| `logs_auditoria_sistema` | ❌ **NO** | No existe. Sin esto no hay bitácora forense (M7). |

### ❌ PROBLEMA 3: El cálculo de completitud es demasiado ingenuo

En [`documento_controller.py`](file:///c:/Users/HP/Desktop/RESIDENCIA%20PLURIONE/motor%20de%20validacion/controllers/documento_controller.py) línea 85-88:

```python
docs_totales = db.query(Documento).filter(...).count() + 1
progreso = min(100.0, round((docs_totales / 3.0) * 100, 1))
```

**Problema:** Solo cuenta cuántos documentos hay, sin verificar que sean de **tipos distintos**. Si subes 3 veces la misma Constancia Fiscal (CSF_SAT), el sistema marca 100% de completitud, cuando en realidad faltan el Comprobante de Domicilio y el Acta Constitutiva.

El **DOC-05 (Regla RIE)** dice claramente que se debe verificar la **presencia de cada tipo obligatorio**, no simplemente contar el total.

### ❌ PROBLEMA 4: No existe validación de tipos de documento admitidos

En [`documento_controller.py`](file:///c:/Users/HP/Desktop/RESIDENCIA%20PLURIONE/motor%20de%20validacion/controllers/documento_controller.py) línea 34, el parámetro `tipo_documento` acepta cualquier cadena de texto sin restricción:

```python
tipo_documento: str = Form("CSF_SAT", description="CSF_SAT, COMP_DOMICILIO, ACTA_CONSTITUTIVA"),
```

**Problema:** Alguien podría enviar `tipo_documento="HOLA_MUNDO"` y el sistema lo aceptaría sin error. Debería validarse contra un catálogo de tipos válidos (idealmente desde la tabla `reglas_validacion`).

### ❌ PROBLEMA 5: No hay validación de integridad del archivo (Nivel 1 del Pipeline)

El `DOC-05` establece que el **Nivel 1** del pipeline debe verificar:
- Que el archivo no esté corrupto
- Que el MIME type sea válido (PDF o imagen)
- Que no sea un PDF cifrado/protegido con contraseña
- Que el tamaño no exceda el límite

Actualmente solo se verifica que no esté vacío (0 bytes). **No se valida** el MIME type real del archivo ni su integridad.

### ❌ PROBLEMA 6: El `estado_cumplimiento` del expediente nunca se actualiza automáticamente

En [`expediente.py`](file:///c:/Users/HP/Desktop/RESIDENCIA%20PLURIONE/motor%20de%20validacion/models/expediente.py) existe el campo `estado_cumplimiento` con valores `EN_REVISION`, `CONFORME`, `NO_CONFORME`, `BLOQUEADO`. Sin embargo, **ningún controlador actualiza este campo automáticamente**. Siempre queda en `EN_REVISION` sin importar cuántos documentos tenga.

Según el **DOC-07 (HU-12)**: *"El sistema verifica automáticamente la completitud del expediente"* y cambia su estado conforme al resultado.

### ⚠️ PROBLEMA 7: El `models/__init__.py` importa modelos específicos de PluriOne

```python
# En __init__.py
```

Los modelos se importan manualmente. Funciona, pero debería ser más limpio.

### ⚠️ PROBLEMA 8: La categoría "EMPLEADO" no existe en la documentación

En [`titular_schema.py`](file:///c:/Users/HP/Desktop/RESIDENCIA%20PLURIONE/motor%20de%20validacion/schemas/titular_schema.py) línea 14:

```python
categoria: str = Field("PROVEEDOR", description="PROVEEDOR, CLIENTE o EMPLEADO")
```

El **DOC-08** solo define dos categorías para la tabla `titulares_expediente`: **CLIENTE** y **PROVEEDOR**. La categoría "EMPLEADO" fue inventada y no corresponde al alcance del motor (que evalúa **personas morales y proveedores**, no empleados individuales).

---

## 4. ¿Qué está BIEN hecho?

| Componente | Evaluación | Observación |
|:---|:---|:---|
| Estructura MVC | ✅ **Correcto** | Separación en `models/`, `controllers/`, `schemas/`, `views/` conforme al patrón |
| Conexión MySQL + SQLAlchemy | ✅ **Correcto** | Bien configurada con `.env`, `pymysql`, `pool_pre_ping` |
| Modelo `titulares_expediente` | ✅ **Correcto** | Coincide con el DOC-08 (UUID, RFC con UNIQUE, razón social, tipo, categoría) |
| Modelo `expedientes` | ✅ **Correcto** | FK con cascade, código legible, estado y porcentaje |
| Modelo `documentos` | ✅ **Correcto** | Hash SHA-256 de 64 chars, tamaño, MIME, ruta en vault |
| Cálculo SHA-256 en ingesta | ✅ **Correcto** | Se calcula antes de guardar, cumple principio NOM-151 |
| Almacenamiento en `storage_vault/` | ✅ **Correcto** | Persistencia desacoplada (metadatos en BD, binario en disco) |
| Prefijo de hash en nombre de archivo | ✅ **Correcto** | Evita colisiones de nombres duplicados |
| API RESTful con versionado `/api/v1/` | ✅ **Correcto** | Conforme al DOC-08 |
| Validación de RFC duplicado | ✅ **Correcto** | Retorna HTTP 409 si ya existe |
| Código de expediente legible | ✅ **Correcto** | `EXP-PLU0-202609131748` conforme al DOC-08 |

---

## 5. Mapa de Trabajo: Lo que falta por Sprint

### Sprint 1 (Semanas 5-6) — Cimientos del Sistema
> **Estado: 70% completado** (falta autenticación y validaciones)

- [x] Base de datos MySQL conectada
- [x] Modelo y CRUD de titulares
- [x] Modelo y CRUD de expedientes
- [x] Carga de documentos con SHA-256
- [x] Bóveda de almacenamiento
- [ ] **Modelo `usuarios`** (tabla, roles, login con JWT)
- [ ] **Validación de MIME type** en carga de archivos (Nivel 1)
- [ ] **Validación de tipos de documento** contra catálogo
- [ ] **Cálculo correcto de completitud** (por tipos distintos, no por conteo)
- [ ] **Actualización automática de `estado_cumplimiento`**

### Sprint 2 (Semanas 7-8) — Motor de Reglas y Vigencias
> **Estado: 0% completado**

- [ ] Modelo `reglas_validacion` (tabla con vigencia, campos obligatorios, severidad)
- [ ] CRUD de reglas (crear, listar, activar/desactivar)
- [ ] Motor de evaluación determinista (Nivel 2 del Pipeline)
- [ ] Verificación de vigencia (fecha emisión + días máximos)
- [ ] Modelo `dictamenes_auditoria` (tabla con score, estado, observaciones)
- [ ] Emisión automática de dictamen (APROBADO / RECHAZADO)
- [ ] Sistema de alertas (documentos faltantes, vencidos, próximos a vencer)

### Sprint 3 (Semanas 9-10) — Análisis Inteligente con IA
> **Estado: 0% completado**

- [ ] Extracción de texto de PDFs (OCR / parseo)
- [ ] Integración con modelo de lenguaje (análisis semántico)
- [ ] Cruce de RFC y razón social del PDF vs. titular
- [ ] Score de confianza y cita textual
- [ ] Flujo Human-in-the-Loop (Nivel 5)

### Sprint 4 (Semanas 11-12) — Reportes, Dashboard e Integración
> **Estado: 5% completado** (solo existe el panel HTML provisional)

- [ ] Frontend en **React.js** (no HTML estático)
- [ ] Dashboard con semáforos de cumplimiento
- [ ] Exportación de reportes PDF/Excel
- [ ] Bitácora de auditoría (`logs_auditoria_sistema`)
- [ ] Integración end-to-end de todos los módulos

---

## 6. Acciones Inmediatas Recomendadas

> [!IMPORTANT]
> Los siguientes 5 items deben corregirse **antes de avanzar** al Sprint 2.

1. **Corregir nomenclatura en `main.py`:** Cambiar "PluriOne Sentinel" por "Motor de Validación de Cumplimiento Documental".
2. **Eliminar categoría EMPLEADO** del schema y modelo de titulares.
3. **Corregir cálculo de completitud** para contar tipos DISTINTOS de documento, no cantidad total.
4. **Agregar validación de `tipo_documento`** contra un Enum de valores permitidos.
5. **Agregar validación básica de archivo** (MIME type, tamaño máximo) para cumplir el Nivel 1 del Pipeline.

---

## 7. Conclusión

El modelo anterior (Gemini 3.8) construyó los **cimientos básicos** del Sprint 1 correctamente (conexión MySQL, modelos base, API REST, SHA-256). Sin embargo, cometió los siguientes errores conceptuales:

1. **Confundió el producto con la empresa receptora** (nombró todo "PluriOne Sentinel" cuando el producto es genérico B2B).
2. **Inventó la categoría "EMPLEADO"** que no existe en ningún documento oficial.
3. **No implementó el cálculo de completitud correctamente** (cuenta documentos en vez de tipos distintos).
4. **No creó las tablas críticas del motor** (`reglas_validacion`, `dictamenes_auditoria`, `logs_auditoria_sistema`, `usuarios`).
5. **No implementó ninguna validación del Nivel 1 ni del Nivel 2** del Pipeline de 5 Niveles definido en el DOC-05.

El código que existe es funcional y correcto en su estructura, pero representa aproximadamente el **15-20%** del sistema completo que exige la documentación.
