# Validación cuantitativa y benchmarking del motor

| Campo | Valor |
|---|---|
| Propósito | Demostrar con métricas reproducibles la exactitud de la IA (ISO/IEC 25010, Adecuación funcional › Exactitud) y el rendimiento del sistema (ISO/IEC 25010, Eficiencia de desempeño) frente a RNF-01, RNF-02 y RNF-03, y medir la eficiencia del chat documental antes y después de su optimización (PRD §21.4, P4) |
| Fase del cronograma | Fase 5 · QA (DOC-07, semanas 13 y 14: «pruebas de precisión de IA»; riesgo «baja precisión en la detección de cláusulas», 13 h de pruebas de precisión) |
| Fuentes | DOC-01 H12 y H15; DOC-03 (ISO/IEC 25010: «Gold Standard con precisión, exhaustividad y F1»); DOC-04 RNF-01 a RNF-03; DOC-05 (RSC-01, RSC-02, bandas del Nivel 5); DOC-08 §6.2; [PRD.md](PRD.md) §11, §15 y §21.4 |
| Estado | Diseño aprobado el 30/09/2026, junto con la configuración del OCR (§5) y la optimización del chat (§6). Medición base del chat y pasos T3, T4 y T0 de P4 ejecutados (§10.1); precisión y rendimiento pendientes |
| Restricciones | Sin cambios de arquitectura ni de contratos de API; sin tocar el Módulo 7; ningún dato real de terceros en el repositorio; la suite de precisión corre sin consumir tokens una vez grabada |

---

## 1. Preguntas de evaluación

| Id | Pregunta | Eje | Requisito |
|---|---|---|---|
| PE-1 | ¿Con qué exactitud extrae el Nivel 4 las entidades clave (tipo, RFC, razón social, fechas, firmantes y apoderados)? | Precisión | DOC-03, H12, RF-10 |
| PE-2 | ¿Con qué exactitud detecta la presencia u omisión de los elementos exigidos por las reglas RSC-01 (y RSC por tipo)? | Precisión | DOC-05 RSC-01, riesgo del DOC-07 |
| PE-3 | ¿Con qué exactitud extrae los datos del firmante que RSC-02 presenta al analista? | Precisión | DOC-05 RSC-02, HU-23 |
| PE-4 | ¿Coincide el dictamen preliminar (Nivel 4) y su enrutamiento a revisión humana (Nivel 5) con el que emitiría un analista? | Precisión | DOC-08 §6.2, RN-05 |
| PE-5 | ¿Cuánto tarda la evaluación determinista de un expediente completo? | Rendimiento | RNF-01 (≤ 2 s) |
| PE-6 | ¿Cuánto tardan la extracción (Nivel 3) y el análisis (Nivel 4) de un documento de hasta 20 páginas, y cuánto aportaba la detección de sellos (Nivel 3, versión 3.2)? | Rendimiento | RNF-02 (≤ 25 s) |
| PE-7 | ¿Soporta la API 50 peticiones simultáneas sin degradación ni pérdida de transacciones? | Rendimiento | RNF-03 (≥ 50) |
| PE-8 | ¿Cuántos tokens y cuánto tiempo cuesta cada turno del chat documental, con qué exactitud responde y cuánto mejora con T0 a T4? | Eficiencia y exactitud | RF-13, HU-20, RNF-02; PRD §21.4 |

**Alcance del RNF-02.** El DOC-04 define el RNF-02 como «extracción OCR **y** análisis semántico» de un documento de hasta 20 páginas. Se reportan por separado el Nivel 3 (OCR) y el Nivel 4 (inferencia), y la meta se contrasta contra la suma.

**Alcance del RNF-01.** El RNF-01 mide la «evaluación determinista de reglas sobre un expediente completo». Se mide en `GET /api/v1/expedientes/{id}` (el semáforo consolidado que consume la interfaz) y, aparte, dentro del proceso (`motor/cumplimiento.reevaluar`), para separar el costo de red.

---

## 2. Gold Standard

### 2.1 Principios

1. **Datos ficticios y rotulados como tales.** Igual que `tests/generar_fixtures.py`: cada documento lleva «DOCUMENTO DE PRUEBA — DATOS FICTICIOS». Ningún documento real de la bóveda entra al repositorio.
2. **Generación determinista.** Fechas absolutas (no relativas al día) y **fecha de referencia fija** (`FECHA_REFERENCIA = 2026-09-30`) que se pasa a `analizar(fecha_referencia=…)`. Así el texto de cada documento, y con él la huella de cada petición al modelo, no cambia entre corridas.
3. **Verdad fundamental anotada antes de ejecutar el sistema.** La anotación (`gold_standard.json`) se escribe a partir de la especificación de cada caso, se congela con su SHA-256 y solo después se corre la suite. Esto evita la circularidad de «anotar lo que el sistema respondió». Toda corrección posterior de la anotación queda en un commit propio con su justificación.
4. **Estatus esperado derivado de las reglas documentadas, no del código.** El estatus esperado de cada caso se razona con DOC-05 y DOC-08 §6.2 y se escribe con su motivo (p. ej. «falta la cláusula de penalización → RSC-01 → EN_REVISION»).
5. **Dos renditions por documento seleccionado.** Vectorial (capa de texto) y escaneado degradado (rasterizado, ruido, inclinación, JPEG). La diferencia entre ambos mide el efecto del OCR sobre la exactitud (ablación). Como el texto de cada escaneo se conoce, el OCR se evalúa además por su tasa de error de caracteres (CER) sin llamar al modelo.

### 2.2 Composición (42 casos)

| Grupo (DOC-02) | Tipo registrado | Casos | Variaciones que cubre | Escaneados |
|---|---|---|---|---|
| Corporativo | `CSF_SAT` | 4 | vigente; emisión > 90 días (RCV-03); RFC ajeno; sin RFC con razón social igual | 2 |
| Corporativo | `OPINION_CUMPLIMIENTO` | 4 | positiva vigente; negativa (RSC-OPIN-SENT); vencida > 30 días (RCV-04); de otro RFC | 1 |
| Corporativo | `COMP_DOMICILIO` | 2 | vigente; > 90 días (RCV-02) | 1 |
| Corporativo | `ACTA_CONSTITUTIVA` | 4 | completa (escritura, RPC, administración, apoderados); sin inscripción en el RPC; inscripción al final del documento; tipo incompatible (se registró como acta y es un poder) | 2 |
| Jurídico | `PODER_NOTARIAL` | 3 | completo; sin facultades; con dos apoderados | 1 |
| Jurídico | `CONTRATO_SERVICIOS` | 7 | completo; falta confidencialidad; falta penalización; falta vigencia y terminación; falta objeto; sin firmas; dos firmantes con cargo | 3 |
| Jurídico | `ACUERDO_CONFIDENCIALIDAD` | 3 | completo; sin obligación de no divulgación; sin vigencia | 1 |
| Regulatorio | `POLIZA_SEGURO`, `LICENCIA_OPERACION` | 3 | póliza vigente con cobertura; póliza vencida; licencia sin giro | 1 |
| **Total** | | **30 base** | | **12 escaneados → 42 casos** |

Unidades evaluadas (estimación): ≈ 230 campos de entidad, ≈ 130 elementos RSC y ≈ 25 personas (firmantes y apoderados).

### 2.3 Esquema de la anotación

```json
{
  "id": "GS-CONT-03",
  "archivo": "gs_contrato_sin_penalizacion.pdf",
  "rendicion": "VECTORIAL",
  "tipo_registrado": "CONTRATO_SERVICIOS",
  "titular": {"rfc": "PLU180514AB3", "razon_social": "PLURIONE S.A. DE C.V."},
  "esperado": {
    "tipo_documento": "CONTRATO_SERVICIOS",
    "rfc": "PLU180514AB3",
    "razon_social": "PLURIONE S.A. DE C.V.",
    "fecha_emision": "2026-03-02",
    "fecha_vencimiento": "2027-03-01",
    "personas": [{"nombre": "María Elena Ruiz Soto", "cargo": "Apoderada legal"}],
    "elementos": {"RSC-01-CONT-OBJ": true, "RSC-01-CONT-CONF": true, "RSC-01-CONT-PEN": false,
                  "RSC-01-CONT-VIG": true, "RSC-01-CONT-FIRM": true},
    "estatus": "EN_REVISION",
    "motivo": "Falta la penalización por incumplimiento: omisión contractual relevante (RSC-01)."
  }
}
```

Los criterios RSC que recibe `analizar()` se toman de una **instantánea** del seed del rules-service guardada junto al Gold Standard (con su huella), para que un cambio del catálogo no altere en silencio la evaluación.

### 2.4 Subconjunto real (opcional, validez externa)

Las dos actas constitutivas escaneadas reales de la bóveda (14 y 26 páginas) pueden anotarse a mano por el residente. Por contener datos de terceros, su anotación y sus resultados **no se versionan**: solo se reportan cifras agregadas.

---

## 3. Ejecución offline: el casete de inferencias

Las suites llaman a las funciones y endpoints reales del ai-service (`analizar()`, `POST /ai/analisis-semantico`, `POST /ai/chat-documento`) y al Nivel 3 real. Solo se sustituyen los transportes externos:

| Dependencia | Modo `grabar` | Modo `reproducir` (por defecto) |
|---|---|---|
| Groq (`groq_client.generar_json` y `groq_client.conversar`) | Llama a Groq y guarda en el casete la respuesta, los tokens y la latencia bajo una huella SHA-256 de la petición exacta (modelo, temperatura, `max_tokens` y mensajes) | Lee la respuesta por huella. **Una huella ausente aborta la corrida** (garantía de cero tokens) |
| core-service (`core_client`: metadatos, binario, integridad, registro y último dictamen) | Almacén en memoria con los binarios del Gold Standard; el dictamen registrado se guarda con la misma forma que devuelve el core (`reglas_aplicadas`, `vigencia_resultado`, `representacion_legal`) | Igual |
| Vigencia RCV (`rules_client.evaluar_vigencia`) | `rules-service/motor/vigencia.py` (puro, sin base de datos) con las reglas RCV de la instantánea del seed | Igual |
| Criterios RSC (`rules_client.criterios_contenido`) | Instantánea del seed | Igual |
| Texto extraído (SQLite del servicio) | Base temporal por corrida; el caché de inferencias del servicio se desactiva para medir latencias reales | Igual |

Consecuencias:

- A temperatura 0.0 y con la misma huella, la corrida es **reproducible** en cualquier equipo, incluida la CI, sin `GROQ_API_KEY`.
- Si cambia el prompt, el modelo, la configuración del Nivel 3 o el catálogo RSC, la huella cambia y la corrida aborta: **los resultados quedan atados a una versión del motor**. Cada reporte registra modelo, `version_lectura()`, huella del Gold Standard y huella del casete.
- Costo de la grabación de precisión: ≈ 6,200 tokens por caso × 42 ≈ **260,000 tokens**, una sola vez y ya con la configuración definitiva del OCR (§5). El grabador respeta el límite de 8,000 tokens por minuto con un presupuesto propio en lugar de depender de los reintentos del SDK.

---

## 4. Catálogo de métricas de precisión

### 4.1 Extracción de entidades (PE-1)

Por campo y por caso, tras normalizar con las mismas funciones del motor (`normalizar_rfc`, `normalizar_fecha`, `normalizar_razon_social`):

| Resultado | Condición |
|---|---|
| VP | Hay valor esperado y el extraído coincide |
| FP | Se extrajo un valor que no coincide, o se extrajo algo donde no hay valor (**alucinación**) |
| FN | Hay valor esperado y no se extrajo, o el extraído no coincide |
| VN | No hay valor esperado y no se extrajo nada |

Un valor equivocado cuenta como FP y como FN a la vez (convención de *slot filling*).

- **Precisión** = VP / (VP + FP) · **Exhaustividad** = VP / (VP + FN) · **F1** = 2PR / (P + R).
- Por campo y agregadas: **micro** (suma de conteos) y **macro** (promedio de campos).
- **Tasa de alucinación** = FP con valor esperado nulo / casos con valor esperado nulo.
- **Tipo documental:** exactitud y F1 macro sobre las clases.
- **Exactitud por documento:** proporción de casos con todos los campos correctos.

### 4.2 Verificación de elementos normativos RSC-01 (PE-2)

Cada par (caso, regla RSC) es una decisión binaria: **positiva** («presente») = `CUMPLE` con cita anclada; **negativa** («omisión») = `NO_LOCALIZADO`; `NO_VERIFICABLE` es una **abstención** que se reporta aparte y, para P/R/F1, cuenta como omisión (así la trata el dictamen).

| Métrica | Lectura de cumplimiento |
|---|---|
| Exhaustividad de la clase «omisión» | Cuántas cláusulas faltantes detecta el motor. **Un FN aquí es una falsa conformidad: la métrica crítica** |
| Precisión de la clase «omisión» | Cuántas alertas de omisión son reales (carga de revisión innecesaria) |
| P/R/F1 de la clase «presente» | Exactitud al confirmar cláusulas |
| Tasa de citas ancladas | `CUMPLE` cuya cita aparece literalmente en el texto (debe ser 100 % por diseño) |

Se desglosa por regla y por rendición (vectorial / escaneada).

### 4.3 Datos del firmante RSC-02 (PE-3)

Nivel de entidad sobre el conjunto de personas de cada caso: una persona extraída es VP si su nombre coincide con uno esperado tras la normalización del cotejo RN-03 (sin acentos, títulos ni partículas). P/R/F1 de nombres y, sobre los VP, exactitud del cargo.

### 4.4 Decisiones de los Niveles 4 y 5 (PE-4)

- **Matriz de confusión 3 × 3** del estatus preliminar (filas: esperado; columnas: dictaminado).
- Exactitud global, F1 macro y **κ de Cohen**.

| Métrica | Definición | Meta de diseño |
|---|---|---|
| **Tasa de falsa conformidad** | Esperados EN_REVISION o NO_CONFORME dictaminados CONFORME / esperados no conformes | 0 % |
| **Tasa de rechazo indebido** | Esperados CONFORME o EN_REVISION dictaminados NO_CONFORME / esos casos | 0 % |

- **Nivel 5:** matriz 2 × 2 de `requiere_revision_humana` contra «el caso necesita analista» y tasa de derivación a revisión humana.
- **Calibración:** exactitud observada en cada banda del DOC-08 §6.2 (≥ 0.85, 0.70–0.84, < 0.70).

### 4.5 Incertidumbre

Las proporciones llevan **intervalo de Wilson al 95 %** y los F1, intervalo por *bootstrap* (1,000 remuestreos por caso, semilla fija). El reporte dice cuántas unidades respaldan cada cifra y no presenta un 100 % sin su intervalo.

---

## 5. Configuración definitiva del OCR (Nivel A, aprobada el 30/09/2026)

### 5.1 Hallazgo

La hipótesis inicial («la detección de sellos a color triplicó el tiempo del OCR») **no se sostuvo**. Medición de solo lectura sobre el acta real escaneada de 14 páginas (Ryzen 5 3500U, 4 núcleos / 8 hilos, Tesseract 5 con modelos `tessdata_fast`):

| Medición | Resultado |
|---|---|
| OCR secuencial con sellos / sin sellos | 6.4 / 7.2 s por página (diferencia dentro del ruido; la relectura atenuada no se activó en ninguna página) |
| Costo del raster a color | +0.06 s por página |
| Reparto del tiempo por página | Tesseract ≈ 95 %; preprocesamiento OpenCV ≈ 0.1 s |
| Rasterizar a 200 ppp en vez de 300 | Ahorro marginal y similitud del texto de 0.45 a 0.94 contra 300 ppp: **descartado** |

La causa real del salto de ≈ 13 s (PRD §15.2, 26 páginas) a 24.3 s (14 páginas) es que **la auditoría pasó a leer el documento completo** en lugar de las primeras 6 páginas escaneadas (`MAX_PAGINAS_OCR`): 6 páginas × ≈ 1.9 s ≈ 11.5 s, la cifra que reportaba el PRD. Leer todo el documento es correcto para el cumplimiento (la inscripción en el RPC y las firmas suelen ir al final) y se conserva.

### 5.2 Palancas medidas (mismas 14 páginas, OCR en paralelo)

| Procesos de Tesseract | `spa+eng` | `spa` |
|---|---|---|
| 4 (valor anterior: núcleos físicos) | 25.2 s | 16.6 s |
| 6 | 18.2 s | 14.6 s |
| **8 (hilos lógicos)** | 15.9 s | **11.1 s (−56 %)** |

- El supuesto documentado en `settings.py` («Tesseract no gana con SMT») **no se cumple** en este equipo: con un hilo OpenMP por proceso, 8 procesos rinden 37 % más que 4.
- Exactitud de `spa` frente a `spa+eng` en la constancia escaneada de prueba (texto conocido): CER de 1.60 % contra 1.23 % (≈ 5 caracteres de 1,350), **sin diferencias en RFC, fechas ni razón social**. La comparación definitiva la da el CER del Gold Standard escaneado (§2.1).

### 5.3 Configuración adoptada

| Variable | Antes | Ahora | Efecto secundario |
|---|---|---|---|
| `OCR_WORKERS` | núcleos físicos (`cpu_count // 2`) | **hilos lógicos (`cpu_count`)** | 8 procesos saturan la CPU durante una auditoría; RNF-01 se mide también con una auditoría en curso (§7.2) |
| `OCR_LANG` | `spa+eng` | **`spa`** | Palabras en inglés (nombres comerciales) pueden leerse con más errores; se vigila con el CER |
| `OCR_RELEER_SELLOS` | `true` | **`false`** | Raster en grises (un tercio de memoria por página con 8 procesos). La presencia de sellos en tinta de color deja de registrarse; ningún DOC la exige (el DOC-08 pide la del **Sello Digital SAT**, que se sigue detectando en el texto) |

Las tres cambian `version_lectura()`: los textos persistidos con la configuración anterior se ignoran y se releen una vez. Los dictámenes guardados no se tocan (son inmutables). El código de sellos queda inactivo, no se borra: su retiro (Nivel B) se decide con el Gold Standard escaneado.

**Proyección para el RNF-02:** 11.1 s / 14 páginas → ≈ 16 s para 20 páginas, más 2 a 4 s del Nivel 4: **≈ 19–20 s frente a la meta de 25 s**, pendiente de la medición formal (§7.3).

---

## 6. Batería de pruebas del chat documental (PE-8)

### 6.1 Objetivo y estrategia medida

El chat es la herramienta con la que el auditor consulta el documento; su optimización (PRD §21.4, P4) sigue este orden, y cada paso se compara contra la **medición base** de la implementación actual:

| Paso | Estrategia | Qué debe mejorar |
|---|---|---|
| Base | Implementación actual (un turno = prompt de sistema + estado + hasta 6,500 caracteres del documento + historial) | Referencia |
| T3 + T4 | Caché exacto de respuestas del primer turno; estado del sistema en memoria y consultado en paralelo; presupuesto local de tokens por minuto | Tokens en preguntas repetidas; latencia |
| T0 | Ficha del documento guardada al auditar y enrutador de intención: respuestas con las citas del dictamen, **sin modelo** | Tokens y latencia de las preguntas factuales y sugeridas |
| T2 | Presupuesto de contexto adaptativo, reordenamiento léxico local, estado condicional, historial acotado, instrucciones compactas, `max_tokens` propio | Tokens por turno con modelo |
| T1 | Pasaje literal del documento para preguntas sobre una cláusula nombrada (y los montos, que no se extraen en la auditoría) | Tokens de preguntas de localización |

### 6.2 Documentos y preguntas

- **6 documentos del Gold Standard**, auditados antes del chat (el estado del sistema necesita su dictamen): contrato completo, contrato sin penalización, acta constitutiva completa (escaneada), poder notarial, constancia de situación fiscal y opinión 32-D positiva.
- **30 preguntas** (5 por documento), escritas con su respuesta esperada **antes** de ejecutar:

| Categoría | Preguntas | Ejemplos | Ruta prevista tras P4 |
|---|---|---|---|
| Sugeridas por la interfaz | 8 | «¿Qué le falta a este documento?», «¿Cuándo vence este documento?», «Resume los datos clave de este archivo» | T0 |
| Factuales del dictamen | 10 | RFC, razón social, fecha de emisión, firmantes, apoderados, sentido de la opinión | T0 |
| Localización de cláusulas y montos | 6 | «¿Qué dice la cláusula de penalización?», «¿Cuál es el monto de la contraprestación?» | T1 |
| Interpretativas | 4 | «¿El apoderado puede firmar contratos de servicios?» | Modelo |
| Dato ausente | 2 | Un dato que el documento no contiene | Modelo (T0 nunca afirma una ausencia) |

- Además, **2 conversaciones de 4 turnos** con seguimientos cortos («¿y quién lo firma?») para medir el crecimiento del historial.

### 6.3 Métricas

| Métrica | Definición |
|---|---|
| Tokens por turno | `prompt_tokens`, `completion_tokens` y total que reporta Groq (`contexto_llm.uso_tokens`); 0 en respuestas sin modelo o desde caché |
| Capacidad bajo el límite | Turnos por minuto posibles = 8,000 / tokens medios por turno |
| Latencia | p50 y p95 del endpoint completo y de la inferencia (`tiempos_ms`) |
| Exactitud factual | Proporción de respuestas que contienen el dato esperado (normalizado: sin acentos; fechas en ISO o en palabras) |
| Afirmación de ausencia correcta | En las preguntas de dato ausente, que la respuesta diga que no aparece y no invente |
| Citas verificadas | Proporción de citas «…» marcadas como verificadas en el documento o en el sistema (las que abre el visor) |
| Respuestas sin modelo | Proporción de turnos resueltos por T0, T1 o caché |

### 6.4 Protocolo y criterios de aceptación

- **Tokens y latencia** se miden con Groq real (modo `grabar`), sin contención de cuota; la corrida base consumió 79,076 tokens (19,015 de auditorías y 60,061 de chat; se estimaban ≈ 170,000, §10.1).
- **Exactitud** se recalcula en modo `reproducir` sin tokens.
- Cada paso de P4 se acepta solo si: la exactitud factual y las citas verificadas **no bajan** respecto a la base; ninguna respuesta sin modelo afirma una ausencia; y el contrato de `POST /ai/chat-documento` y las pruebas existentes se mantienen.

---

## 7. Protocolo de rendimiento

### 7.1 Entorno controlado

Se registra en cada corrida: CPU, RAM, sistema operativo, versiones de Python, Tesseract y PostgreSQL, `OCR_WORKERS`, `OCR_LANG`, `OCR_DPI`, `version_lectura()` y si los servicios corren locales o en Docker. Nada más ejecutándose en el equipo.

**Base de datos dedicada.** La consulta de un expediente reevalúa y puede escribir en la bitácora, que es inmutable. El benchmark levanta core y rules contra `plurione_compliance_bench`, nunca contra `plurione_compliance`.

### 7.2 RNF-01 · Evaluación determinista (≤ 2 s)

- Expedientes sintéticos de 3, 8 y 15 documentos con dictámenes, anexos y un contrato con cotejo RN-03.
- 5 peticiones de calentamiento y 100 medidas por expediente, secuenciales; y la misma serie con una auditoría escaneada en curso (8 procesos de OCR).
- p50, p95, p99 y máximo de `GET /api/v1/expedientes/{id}` y de `reevaluar` en proceso; `GET /api/v1/expedientes` con 30 expedientes como estrés.
- **Criterio:** p95 ≤ 2.0 s.

### 7.3 RNF-02 · Extracción y análisis (≤ 25 s por documento de hasta 20 páginas)

| Documento | Páginas | Tipo |
|---|---|---|
| Contrato sintético vectorial | 20 | Capa de texto |
| Contrato sintético escaneado | 20 | OCR |
| Contrato sintético escaneado con sello en tinta de color en 1 de cada 4 páginas | 20 | OCR |
| Acta real escaneada (bóveda, no versionada) | 14 | OCR |
| Acta real escaneada (bóveda, no versionada) | 26 | OCR (fuera de la meta; se normaliza a 20 páginas) |

- Nivel 3 en frío (SQLite temporal y caché vacío), 5 corridas, mediana y rango; desglose por etapa (rasterizado, preprocesamiento, Tesseract).
- Comparación de la configuración anterior (4 procesos, `spa+eng`, sellos) contra la definitiva (§5.3).
- Nivel 4: 3 auditorías reales del documento de 20 páginas, sin contención de cuota.
- **Criterio:** mediana de (Nivel 3 en frío + Nivel 4) ≤ 25 s para 20 páginas.

### 7.4 RNF-03 · Concurrencia (≥ 50 peticiones simultáneas)

- `concurrent.futures` con `requests`, 50 peticiones liberadas a la vez por una barrera, en tres escenarios: 50 `GET /health`; 50 `GET /expedientes/{id}` sobre 10 expedientes; 50 cargas de documento distintas en 10 expedientes.
- **Degradación** = p95 concurrente / p95 secuencial.
- **Pérdida de transacciones:** documentos creados = cargas con respuesta 201; eventos `INGESTA_DOCUMENTO` = cargas aceptadas; `GET /api/v1/bitacora/verificar-cadena` íntegra.
- **Criterio:** 0 respuestas 5xx, 0 transacciones perdidas, cadena íntegra y p95 de consulta ≤ 2 s. El PRD §21.3 advierte que el candado de la bitácora serializa las cargas; esta prueba lo cuantifica.

---

## 8. Artefactos y orden de ejecución

| Artefacto | Ubicación |
|---|---|
| Esta metodología y los resultados | `docs/VALIDACION_CUANTITATIVA.md` |
| Diagramas | `docs/uml/qa-actividad-evaluacion.puml`, `docs/uml/p4-actividad-chat-documental.puml` |
| Métricas (funciones puras) y sus pruebas con valores calculados a mano | `services/ai-service/evaluacion/metricas.py`, `services/ai-service/tests/test_metricas.py` |
| Especificación y generador del Gold Standard, anotación e instantánea del catálogo | `services/ai-service/evaluacion/gold_standard.py`, `evaluacion/gold_standard/` |
| Entorno offline (casete, core y rules simulados) | `services/ai-service/evaluacion/entorno.py`, `evaluacion/casetes/` |
| Batería y medición del chat | `services/ai-service/evaluacion/bateria_chat.py`, `evaluacion/medir_chat.py` |
| Suite de precisión y benchmark del Nivel 3 | `services/ai-service/evaluacion/evaluar_precision.py`, `evaluacion/benchmark_extraccion.py` |
| Benchmark del core (RNF-01, RNF-03) | `scripts/benchmark_rendimiento.py` |
| Resultados de las corridas oficiales | `docs/resultados_validacion/` |

Orden: (1) documentación; (2) configuración del OCR; (3) métricas, Gold Standard y entorno offline; (4) **medición base del chat**; (5) P4 en el orden T3+T4, T0, T2, T1, cada paso con su nueva medición; (6) grabación y suite de precisión; (7) benchmarks de rendimiento; (8) resultados en §9 y §10 y en el PRD.

---

## 9. Amenazas a la validez

- **Validez externa:** el Gold Standard es sintético; los escaneos simulan degradación, no la reproducen. El subconjunto real (§2.4) acota esta amenaza.
- **Sesgo del anotador:** el mismo residente diseña el sistema y anota. Mitigación: anotación congelada antes de ejecutar y, si es posible, revisión de una muestra por el asesor externo.
- **Tamaño de muestra:** ≈ 42 casos y 38 turnos de chat; por eso los intervalos de §4.5.
- **Dependencia del proveedor:** los resultados valen para `qwen/qwen3.8-27b` en Groq a temperatura 0.0; otro modelo exige regrabar los casetes. Las latencias de Groq varían con la carga del proveedor: se reportan p50 y p95, no un valor único.
- **Hardware:** el rendimiento se mide en el equipo de desarrollo, no en un servidor de producción.

---

## 10. Resultados

### 10.1 Chat documental — medición base (30/09/2026)

Implementación previa a P4, con la configuración definitiva del OCR (`n3-3.2|tesseract-5.4.0|spa|300dpi|sin-sellos`, 8 procesos), `qwen/qwen3.8-27b` en Groq a temperatura 0.0, sin contención de cuota. Corrida grabada con Groq real: 6 auditorías (19,015 tokens) y 38 turnos de chat (60,061 tokens). La reproducción desde el casete (`evaluacion/casetes/chat.json`) da las mismas respuestas y los mismos tokens sin llamar a Groq. Detalle por turno: [`resultados_validacion/chat_base.json`](resultados_validacion/chat_base.json).

| Grupo | Turnos | Tokens/turno | Turnos/min (8,000 TPM) | Sin modelo | p50 ms | p95 ms | Exactitud (IC 95 %) | Citas verificadas |
|---|---|---|---|---|---|---|---|---|
| **Total** | 38 | 1,581 | 5.06 | 0 | 732 | 4,843 | 95 % (83–99 %) | 39/39 |
| Sugeridas por la interfaz | 8 | 1,614 | 4.96 | 0 | 866 | 8,261 | 88 % (53–98 %) | 4/4 |
| Factuales | 17 | 1,586 | 5.04 | 0 | 715 | 3,619 | 100 % (82–100 %) | 20/20 |
| Localización | 7 | 1,587 | 5.04 | 0 | 532 | 1,216 | 100 % (65–100 %) | 7/7 |
| Interpretativas | 4 | 1,499 | 5.34 | 0 | 620 | 1,278 | 75 % (30–95 %) | 6/6 |
| Dato ausente | 2 | 1,546 | 5.18 | 0 | 630 | 744 | 100 % (34–100 %) | 2/2 |
| Conversaciones (4 turnos) | 8 | 1,893 | 4.23 | 0 | 596 | 1,840 | 100 % (68–100 %) | 9/9 |

(Las categorías suman 17 factuales y 7 de localización porque incluyen los turnos de las conversaciones.)

**Lectura de la medición base:**

- **La estimación previa de ≈ 3,200–4,000 tokens por turno era alta.** El prompt real va de 1,046 a 2,154 tokens y la respuesta de 39 a 175: los documentos del Gold Standard son de 1 a 3 páginas y BM25 envía solo 800 a 2,700 caracteres de contexto, lejos del tope de 6,500. En documentos largos (actas reales de 14 a 26 páginas) el contexto llega al tope y el turno se acerca a la estimación; la batería no los cubre todavía.
- **La latencia típica ya es baja** (p50 ≈ 0.7 s); el problema es la **cola**: p95 de 4.8 s y un máximo de 10.6 s, variaciones del proveedor que no dependen del prompt. Las respuestas sin modelo (T0 y T1) eliminan esa cola en las preguntas que cubren.
- **Exactitud 36/38.** Los dos fallos son **falsos negativos del calificador**, no errores del chat: «¿El apoderado puede vender inmuebles?» se respondió correctamente («No… las facultades se limitan a pleitos y cobranzas y actos de administración… excluye la enajenación») sin usar la palabra esperada «dominio», y «¿Cuándo vence?» de la constancia respondió «no declara fecha de vencimiento… VIGENTE con 70 días restantes según RCV-03» (70 días = 9 de diciembre de 2026) sin escribir la fecha. La regla de la batería se congeló antes de ejecutar y no se ajusta a posteriori; la cifra oficial es 95 %.
- **Todas las citas (39/39) quedaron verificadas** en el documento o en el sistema.
- **Auditorías:** 1,743 a 4,421 tokens (las de contrato y NDA hacen dos llamadas: extracción y verificación); la latencia de Groq tuvo dos valores atípicos (10.2 s y 16.2 s) frente a 0.6–3.8 s del resto.

**Documento extenso (contrato marco escaneado de 20 páginas, `evaluacion/documento_extenso.py`).** 1 auditoría y 8 turnos, misma configuración; detalle en [`resultados_validacion/chat_base_extensa.json`](resultados_validacion/chat_base_extensa.json).

| Grupo | Turnos | Tokens/turno | Turnos/min (8,000 TPM) | Sin modelo | p50 ms | p95 ms | Exactitud (IC 95 %) | Citas verificadas |
|---|---|---|---|---|---|---|---|---|
| **Total** | 8 | 3,006 | 2.66 | 0 | 1,116 | 1,706 | 88 % (53–98 %) | 12/12 |
| Sugeridas | 2 | 3,070 | 2.61 | 0 | 1,417 | 1,775 | 100 % | 1/1 |
| Factuales | 2 | 2,898 | 2.76 | 0 | 1,027 | 1,455 | 100 % | 3/3 |
| Localización | 3 | 3,046 | 2.63 | 0 | 1,213 | 1,427 | 67 % (21–94 %) | 6/6 |
| Interpretativa | 1 | 2,976 | 2.69 | 0 | 796 | 796 | 100 % | 2/2 |

- **En un documento largo el turno cuesta el doble** (3,006 tokens contra 1,581): el contexto llega a su tope (5,600 a 6,500 caracteres en todos los turnos) y solo caben 2.7 turnos por minuto. Aquí es donde T2 (PLUS-09) puede ahorrar.
- **Un error real de recuperación:** a «¿Cuál es el tiempo de respuesta de la mesa de ayuda para un incidente de prioridad crítica?» el chat respondió «1 hora» y «30 minutos» (valores de otros servicios del Anexo A) en lugar de 15 minutos. Las siete páginas de niveles de servicio tienen el mismo texto salvo el nombre del servicio, y BM25 no favoreció el fragmento con el encabezado «MESA DE AYUDA». El reordenamiento léxico de T2 debe resolver este caso y se medirá contra él.
- **La auditoría del documento** consumió 6,995 tokens (6,127 de prompt) y tardó 16.9 s de principio a fin: lectura OCR en frío de las 20 páginas más dos llamadas a Groq (3.5 s y 1.8 s, en paralelo). Es una primera lectura del RNF-02 (≤ 25 s) con la configuración definitiva del OCR, no la medición formal de §7.3.

#### T3 — Caché de respuestas (PLUS-10)

Medición en modo reproducir (sin tokens), con una fase de repetición: cada pregunta suelta se vuelve a hacer como la teclearía otro analista (sin acentos, mayúsculas ni signos de interrogación). Detalle en [`chat_t3.json`](resultados_validacion/chat_t3.json) y [`chat_t3_extensa.json`](resultados_validacion/chat_t3_extensa.json).

| Batería | Turnos nuevos: tokens/turno, p50, exactitud | Repetición: sin modelo | Repetición: tokens/turno | Repetición: p50 / p95 | Repetición: exactitud y citas |
|---|---|---|---|---|---|
| Documentos breves | 1,581 · 747 ms · 95 % (sin cambio) | 30/30 | 0 | 22 ms / 30 ms | 93 % · 30/30 verificadas |
| Contrato de 20 páginas | 3,006 · 1,142 ms · 88 % (sin cambio) | 8/8 | 0 | 25 ms / 32 ms | 88 % · 12/12 verificadas |

- Una pregunta ya respondida sobre el mismo documento y el mismo estado **no vuelve a consumir tokens** y baja de ≈ 0.75–1.1 s a ≈ 25 ms. La exactitud y las citas son las mismas que en la primera respuesta, porque es la misma respuesta (93 % = 28/30: los dos falsos negativos del calificador de la base están entre las preguntas sueltas).
- T3 no cambia el costo de una pregunta nueva: su ahorro depende de cuánto se repitan las preguntas entre analistas (las sugeridas por la interfaz son las candidatas naturales).

#### T4 — Presupuesto de tokens y estado del chat (PLUS-11)

**Sin cuota compartida** (modo reproducir, ambas baterías; [`chat_t4.json`](resultados_validacion/chat_t4.json), [`chat_t4_extensa.json`](resultados_validacion/chat_t4_extensa.json)): los mismos tokens, respuestas y exactitud que T3. Ninguna huella faltó en el casete, lo que prueba que el refactor envía al modelo exactamente los mismos mensajes. En el entorno offline el core y el rules-service son simulados, así que el ahorro de consultarlos en paralelo y de conservar los criterios en memoria no se refleja en estas latencias.

**Contención con la auditoría** (Groq real; [`chat_t4_contencion.json`](resultados_validacion/chat_t4_contencion.json); `evaluacion/escenario_contencion.py`): se audita el contrato escaneado de 20 páginas (≈ 7,000 tokens) y enseguida se hacen 3 preguntas (monto del Anexo B, deductiva del Anexo D y subcontratación), primero con T4 desactivado y, tras 65 s, activado. Casete y SQLite nuevos en cada variante.

| Variante | Auditoría | Pregunta 1 | Pregunta 2 | Pregunta 3 | Espera total del chat | Tokens/turno | Aciertos |
|---|---|---|---|---|---|---|---|
| Sin T4 (contexto completo; el SDK espera y reintenta) | 23.5 s · 6,995 | 25.1 s | 17.3 s | 25.9 s | 68.3 s | ≈ 3,020 | 3/3 |
| Con T4 (contexto acotado a ≈ 1,950 caracteres) | 21.2 s · 7,003 | 9.9 s | 22.4 s | 6.2 s | 38.5 s | ≈ 1,850 | 3/3 |

- T4 **reduce la espera del chat un 44 %** y sus tokens un 39 % sin perder aciertos en estas tres preguntas (el pasaje correcto quedó dentro del contexto acotado).
- **No la elimina:** la auditoría gasta ≈ 7,000 de los 8,000 tokens del minuto, así que ni el turno acotado (≈ 1,900) cabe y Groq todavía hace esperar. La espera solo desaparece si la pregunta no llega al modelo: es el objetivo de T0 (PLUS-07) y T1 (PLUS-08).
- Es una corrida por variante (n = 3 preguntas): la tendencia es clara, pero las latencias individuales dependen de cuándo libera Groq la cuota.
- La auditoría de este escenario tardó 21 a 24 s contra 16.9 s en la línea base: su extracción y su verificación corren en paralelo y comparten la misma cuota del minuto.

#### T0 — Respuestas desde los datos del dictamen (PLUS-07)

Medición con ambas baterías; solo hizo falta 1 llamada nueva a Groq (2,195 tokens): un turno de conversación cuyo historial cambió porque T0 respondió el turno anterior. Detalle en [`chat_t0.json`](resultados_validacion/chat_t0.json) y [`chat_t0_extensa.json`](resultados_validacion/chat_t0_extensa.json).

| Batería | Turnos sin modelo | Tokens/turno | Turnos/min | p50 | p95 | Exactitud | Citas verificadas |
|---|---|---|---|---|---|---|---|
| Documentos breves — base | 0/38 | 1,581 | 5.06 | 732 ms | 4,843 ms | 95 % (83–99 %) | 39/39 |
| Documentos breves — T0 | **15/38** | **959** | **8.34** | **515 ms** | **2,028 ms** | **97 % (87–100 %)** | 42/42 |
| Contrato de 20 páginas — base | 0/8 | 3,006 | 2.66 | 1,116 ms | 1,706 ms | 88 % (53–98 %) | 12/12 |
| Contrato de 20 páginas — T0 | **3/8** | **1,888** | **4.24** | **824 ms** | **1,531 ms** | 88 % (53–98 %) | 12/12 |

Por categoría (documentos breves): 7 de las 8 preguntas **sugeridas por la interfaz** y 8 de las 17 **factuales** se responden sin modelo, en ≈ 20 ms; las de localización, interpretativas y de dato ausente siguen yendo al modelo, como estaba previsto (T1 y modelo).

- **Tokens:** −39 % por turno en ambas baterías; la cuota del plan gratuito alcanza para 8.3 turnos por minuto (antes 5.1) en documentos breves y 4.2 (antes 2.7) en el contrato de 20 páginas.
- **Latencia:** el p95 de los documentos breves baja de 4.8 s a 2.0 s. El p95 de las sugeridas (7.0 s) lo fija la única que sigue en el modelo («¿Cuándo vence?» de un poder sin fecha de vencimiento), por una latencia atípica de Groq.
- **Exactitud:** sube de 95 % a 97 % en los documentos breves. «¿Cuándo vence?» de la constancia fiscal, que en la base el modelo respondió sin la fecha, ahora se responde con la regla de caducidad del dictamen: «vale hasta el 9 de diciembre de 2026». En el contrato de 20 páginas se mantiene en 88 % (el error de la mesa de ayuda es de localización, T2).
- **Ninguna respuesta sin modelo afirma que un dato no aparece.** Cuando la ficha no tiene el dato, responde el modelo: en el contrato de 20 páginas la auditoría no extrajo la fecha de vencimiento, y «¿Hasta cuándo está vigente?» fue al modelo, que la localizó con su cita.
- **Hallazgos corregidos durante la medición** (con sus pruebas de regresión): el nombre de una regla escrito entre «…» se marcaba como cita no verificada; el resumen de un contrato omitía a la contraparte; la redacción de las faltas se atribuye ahora de forma explícita a la verificación del motor.

#### Resumen de P4 hasta T0

| Paso | Qué cambia para el analista | Evidencia |
|---|---|---|
| T3 (PLUS-10) | Una pregunta ya respondida sobre el mismo documento y estado: ≈ 25 ms y cero tokens | 38/38 repeticiones desde el caché |
| T4 (PLUS-11) | Tras una auditoría de 20 páginas, la espera del chat baja un 44 % | 68.3 s → 38.5 s en 3 preguntas |
| T0 (PLUS-07) | Las preguntas factuales y sugeridas: ≈ 20 ms, cero tokens, con cita del documento | 15/38 y 3/8 turnos sin modelo; −39 % de tokens; exactitud igual o mayor |

Pendientes de P4: T2 (PLUS-09, contexto acotado; debe resolver el error de localización de la mesa de ayuda) y T1 (PLUS-08, pasaje literal para cláusulas nombradas y montos).

### 10.2 Precisión y 10.3 Rendimiento

*Pendiente de ejecución.* Tablas previstas:

- **10.2 Precisión:** extracción por campo (P, R, F1, IC 95 %, n); elementos RSC por regla y por rendición; RSC-02; matriz de confusión 3 × 3, κ, falsa conformidad y rechazo indebido; calibración por banda; CER del OCR.
- **10.3 Rendimiento:** RNF-01 (p50/p95/p99 por tamaño de expediente, con y sin auditoría en curso); RNF-02 por documento y etapa, configuración anterior contra definitiva; RNF-03 por escenario; conclusión por RNF (Cumple / No cumple).
