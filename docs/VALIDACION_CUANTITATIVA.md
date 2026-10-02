# Validación cuantitativa y benchmarking del motor

| Campo | Valor |
|---|---|
| Propósito | Demostrar con métricas reproducibles la exactitud de la IA (ISO/IEC 25010, Adecuación funcional › Exactitud) y el rendimiento del sistema (ISO/IEC 25010, Eficiencia de desempeño) frente a RNF-01, RNF-02 y RNF-03, y medir la eficiencia del chat documental antes y después de su optimización (PRD §21.4, P4) |
| Fase del cronograma | Fase 5 · QA (DOC-07, semanas 13 y 14: «pruebas de precisión de IA»; riesgo «baja precisión en la detección de cláusulas», 13 h de pruebas de precisión) |
| Fuentes | DOC-01 H12 y H15; DOC-03 (ISO/IEC 25010: «Gold Standard con precisión, exhaustividad y F1»); DOC-04 RNF-01 a RNF-03; DOC-05 (RSC-01, RSC-02, bandas del Nivel 5); DOC-08 §6.2; [PRD.md](PRD.md) §11, §15 y §21.4 |
| Estado | Diseño aprobado el 30/09/2026, junto con la configuración del OCR (§5) y la optimización del chat (§6). Chat (§10.1), precisión del Gold Standard (§10.2) y rendimiento (§10.3) medidos el 01/10/2026; pendiente la medición formal del RNF-02 completo sin el presupuesto del grabador |
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

La lectura de sellos en tinta de color se retiró del código el 02/10/2026 (PRD §21.8); la tabla registra la configuración medida.

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

#### Lectura 3.3 del Nivel 3 — hallazgo al diagnosticar el error de la mesa de ayuda

El error del documento extenso («¿tiempo de respuesta de la mesa de ayuda?») **no estaba en la búsqueda de fragmentos sino en el OCR**: en las páginas A.1 a A.6 del Anexo A se perdían el título del anexo, el nombre del servicio y su descripción, porque el escaneo tiene los bordes más oscuros que el centro y el corte global de Otsu pintaba de negro las esquinas (22.8 % de la página en negro, por debajo del 25 % que activa el camino adaptativo). La corrección (`_normalizar_iluminacion`, `VERSION_PIPELINE` 3.3) divide la página entre su fondo estimado antes de binarizar:

| Medición (sin modelo, texto impreso conocido) | Lectura 3.2 | Lectura 3.3 |
|---|---|---|
| Recall de palabras, 13 escaneos del Gold Standard | 94.3 % | **99.65 %** |
| Precisión de palabras | 98.6 % | **99.58 %** |
| Peor documento | 79.9 % (poder notarial) | 98.4 % |
| Tiempo de OCR de los 13 escaneos | 43.3 s | 40.5 s |
| Acta real de 14 páginas (sin referencia) | confianza 0.879 | 0.878; recupera el nombre del notario y el distrito en la página 1 |

Con la lectura 3.3 y sin cambiar la búsqueda, la batería del contrato de 20 páginas pasa de 7/8 a **8/8** ([`chat_n33_extensa.json`](resultados_validacion/chat_n33_extensa.json)): la mesa de ayuda se responde con «15 minutos». Tokens por turno con modelo: 2,951.

**Límite diario del proveedor.** La medición de la batería corta con la lectura 3.3 se detuvo porque el plan gratuito de Groq tiene, además del límite por minuto, **200,000 tokens por día** para `qwen/qwen3.8-27b`, que se agotaron el 30/09/2026. Las mediciones que requieren llamadas nuevas (batería corta con la lectura 3.3, T2 y T1) quedan pendientes de la cuota del día siguiente.

**Hallazgo del entorno de medición.** En modo grabar, la llamada real a Groq alimentaba el presupuesto de T4 y acotaba el turno siguiente del chat (en una corrida descartada, «¿hasta cuándo está vigente el contrato?» recibió 1,921 caracteres y el modelo respondió que la fecha no aparecía). Las mediciones de las baterías corren ahora sin presupuesto; solo el escenario de contención lo activa. Del mismo caso salió otra corrección: el estado del sistema decía «vencimiento no declarado» cuando la auditoría no lo extraía; ahora dice «no extraído por el motor».

#### T2 y T1 — medición con Groq (01/10/2026)

- **T2 (PLUS-09):** las preguntas puntuales reciben un contexto enfocado (3,000 caracteres en hasta 3 tramos, reordenados por cobertura de términos y por coincidencia en encabezados distintivos, y recortados al tramo relevante), el estado breve y el historial acotado; el chat tiene su propio tope de respuesta (600 tokens). Sin modelo, sobre el texto del contrato de 20 páginas: las seis preguntas puntuales de la batería extensa reciben su respuesta en 1,130 a 2,842 caracteres contra 6,442 de la selección general (`tests/test_contexto_enfocado.py`). No se compactaron las instrucciones de sistema.
- **T1 (PLUS-08):** cláusulas nombradas y montos se responden con el renglón literal y su página, sin modelo. Verificado sobre los textos del Gold Standard: 8 pasajes literales con el dato correcto (monto mensual, contraprestación, capital social, prima total, suma asegurada de una cobertura, precio de un servicio, cláusulas de confidencialidad y de subcontratación) y 5 casos que van al modelo (suma asegurada con tres coberturas, pregunta interpretativa, seguimiento de un solo término, pregunta sin monto ni cláusula, anexo sin tema) (`tests/test_pasajes.py`).
- **Interfaz:** la meta de cada respuesta del chat dice su procedencia («análisis con IA», «datos del dictamen», «texto del documento», «respuesta ya consultada»). Regresión visual: 158 de 158 capturas iguales y un escenario nuevo con una respuesta sin modelo.

Medición con Groq real en ambas baterías, con la cuota del 01/10/2026 y la lectura 3.3 del Nivel 3 (`n3-3.3`), que cubre también la batería corta pendiente del 30/09/2026. Las auditorías usan la lectura nueva: las 6 de la batería corta se grabaron de nuevo (19,283 tokens) y la del contrato de 20 páginas ya estaba grabada desde el 30/09/2026 (7,097). La reproducción desde el casete da las mismas respuestas, tokens y exactitud sin llamar a Groq. Detalle en [`chat_t2t1.json`](resultados_validacion/chat_t2t1.json) y [`chat_t2t1_extensa.json`](resultados_validacion/chat_t2t1_extensa.json).

| Batería | Sin modelo (T0 + T1) | Tokens/turno | Tokens/turno con modelo | Turnos/min | p50 | p95 | Exactitud | Citas verificadas |
|---|---|---|---|---|---|---|---|---|
| Documentos breves — base | 0/38 | 1,581 | 1,581 | 5.06 | 732 ms | 4,843 ms | 95 % (83–99 %) | 39/39 |
| Documentos breves — T0 | 15/38 | 959 | 1,585 | 8.34 | 515 ms | 2,028 ms | 97 % (87–100 %) | 42/42 |
| Documentos breves — T2 + T1 | **18/38** (16 + 2) | **646** | **1,228** | **12.38** | **428 ms** | **1,434 ms** | **97 % (87–100 %)** | 44/44 |
| Contrato de 20 páginas — base | 0/8 | 3,006 | 3,006 | 2.66 | 1,116 ms | 1,706 ms | 88 % (53–98 %) | 12/12 |
| Contrato de 20 páginas — lectura 3.3 | 3/8 | 1,844 | 2,951 | 4.34 | 907 ms | 4,220 ms | 100 % (68–100 %) | 10/10 |
| Contrato de 20 páginas — T2 + T1 | **4/8** (3 + 1) | **863** | **1,727** | **9.27** | **240 ms** | **2,103 ms** | **100 % (68–100 %)** | 9/9 |

- **Tokens:** contra la base, el turno promedio baja un **59 %** en los documentos breves (1,581 → 646) y un **71 %** en el contrato de 20 páginas (3,006 → 863). La cuota del plan gratuito pasa de 5.1 a 12.4 turnos por minuto en documentos breves y de 2.7 a 9.3 en el documento largo.
- **T2 es el que más ahorra en el documento largo:** las preguntas puntuales que llegan al modelo reciben de 2,359 a 2,584 caracteres de contexto, contra 6,349 a 6,486 antes; el turno con modelo baja de 2,951 a 1,727 tokens. La pregunta general («¿Hasta cuándo está vigente el contrato?») conserva el contexto amplio (6,428 caracteres), como está diseñado.
- **T1 respondió 3 turnos con el renglón literal y su página, sin modelo:** el monto mensual del contrato de 20 páginas (página 17), la contraprestación del contrato breve y el capital social del acta escaneada. Los tres son correctos.
- **La mesa de ayuda sigue resuelta con el contexto acotado:** «15 minutos», con su cita, en 2,584 caracteres de contexto. La causa era el OCR (lectura 3.3); T2 no la empeora.
- **Exactitud 37/38 en los documentos breves.** El único fallo es el falso negativo del calificador que ya estaba en la base: «¿El apoderado puede vender inmuebles?» se respondió «No… el poder se limita a pleitos y cobranzas y actos de administración… sin facultades especiales para enajenar bienes», sin la palabra esperada «dominio». El criterio se congeló antes de ejecutar y no se ajusta a posteriori. El otro falso negativo de la base («¿Cuándo vence?» de la constancia) ya se responde con la fecha desde T0.
- **Ninguna cita quedó sin verificar** (44/44 y 9/9). En la repetición sin acentos ni signos, las 38 preguntas sueltas se respondieron desde el caché, con 0 tokens.
- **La latencia de la cola mejora**, aunque sigue dependiendo de Groq: el p95 de los documentos breves baja de 4.8 s a 1.4 s; el del contrato de 20 páginas (2.1 s) lo fija la única pregunta general, que sigue con contexto amplio.
- **Pendiente de P4:** la compactación de las instrucciones de sistema (parte de PLUS-09) no se hizo; cambia el comportamiento del modelo y no se justifica con estas cifras.

#### Resumen de P4

| Paso | Qué cambia para el analista | Evidencia |
|---|---|---|
| T3 (PLUS-10) | Una pregunta ya respondida sobre el mismo documento y estado: ≈ 25 ms y cero tokens | 38/38 repeticiones desde el caché |
| T4 (PLUS-11) | Tras una auditoría de 20 páginas, la espera del chat baja un 44 % | 68.3 s → 38.5 s en 3 preguntas |
| T0 (PLUS-07) | Preguntas factuales y sugeridas: ≈ 20 ms, cero tokens, con cita del documento | 16/38 y 3/8 turnos |
| T1 (PLUS-08) | Montos y cláusulas nombradas: el renglón literal con su página, ≈ 30 ms | 2/38 y 1/8 turnos, 3/3 correctos |
| T2 (PLUS-09) | Preguntas puntuales con un contexto de ≈ 2,500 caracteres en lugar de ≈ 6,400 | −71 % de tokens por turno en el documento largo; exactitud 100 % |

### 10.2 Precisión (01/10/2026)

Corrida oficial de `python -m evaluacion.evaluar_precision` sobre los 42 casos (30 vectoriales y 12 escaneados), con Groq real: `qwen/qwen3.8-27b` a temperatura 0.0, lectura `n3-3.3` con 8 procesos y fecha de referencia fija (30/09/2026). Las 42 auditorías consumieron 126,019 tokens (1,700 a 4,470 por caso: los contratos y NDA hacen dos llamadas). La reproducción desde el casete (`evaluacion/casetes/precision.json`) da las mismas cifras sin llamar a Groq. Detalle por caso en [`resultados_validacion/precision.json`](resultados_validacion/precision.json).

**Incidente de la grabación.** En la primera pasada, la verificación de contenido de `GS-NDA-01-ESC` falló por el límite por minuto de Groq (`GroqNoDisponibleError`). El motor la trató como debía: dictamen EN_REVISION, con la observación «la verificación de contenido no pudo completarse». Esa inferencia se regrabó y es la que se reporta. El caso confirma que una falla del proveedor no aprueba nada.

#### PE-4 · Decisiones de los Niveles 4 y 5

| | Dictaminado CONFORME | Dictaminado EN_REVISION | Dictaminado NO_CONFORME |
|---|---|---|---|
| Esperado CONFORME (16) | **16** | 0 | 0 |
| Esperado EN_REVISION (18) | 0 | **18** | 0 |
| Esperado NO_CONFORME (8) | 0 | 0 | **8** |

| Métrica | Resultado | IC 95 % | Meta |
|---|---|---|---|
| Exactitud del estatus preliminar | **42/42 (100 %)** | 92–100 % | — |
| κ de Cohen · F1 macro | 1.000 · 1.000 | — | — |
| **Tasa de falsa conformidad** | **0/26 (0 %)** | 0–13 % | 0 % ✔ |
| **Tasa de rechazo indebido** | **0/34 (0 %)** | 0–10 % | 0 % ✔ |
| Derivación a revisión humana | 18/42; por estatus esperado: CONFORME 0/16, EN_REVISION 18/18, NO_CONFORME 0/8 | — | — |

- Cada caso que necesita analista llega al analista y ninguno de los que no lo necesitan lo hace. Los 8 NO_CONFORME se rechazan por hechos del documento (vencimiento, RFC ajeno, opinión negativa, póliza vencida), nunca por confianza baja.
- **Calibración:** los 42 casos se dictaminaron con confianza ≥ 0.85 y los 42 fueron correctos (IC 92–100 %). Las bandas 0.70–0.84 y < 0.70 quedaron vacías: con documentos sintéticos legibles la calibración de esas bandas **no se puede evaluar**; hace falta el subconjunto real (§2.4).
- Que el estatus sea perfecto no significa que todo lo extraído lo sea (ver PE-2): los contratos y NDA siempre pasan a revisión humana (RSC-02), y eso absorbió los dos errores de elementos.

#### PE-1 · Extracción de entidades

| Campo | n | Precisión | Exhaustividad | F1 (IC 95 %) | Alucinación |
|---|---|---|---|---|---|
| Tipo documental | 42 | 100 % | 100 % | 100 % | — |
| RFC | 42 | 96.8 % | 96.8 % | 96.8 % (90–100 %) | 0/11 |
| Razón social | 42 | 100 % | 100 % | 100 % | — |
| Fecha de emisión | 42 | 100 % | 97.6 % | 98.8 % (96–100 %) | — |
| Fecha de vencimiento | 42 | 100 % | 100 % | 100 % | 0/26 |
| **Micro** | 210 | **99.4 %** | **98.8 %** | **99.1 % (98–100 %)** | **0/37** |

- **Ninguna alucinación:** en los 37 campos que el documento no trae (11 RFC y 26 fechas de vencimiento), el modelo no inventó un valor. F1 macro 99.1 %; 40/42 documentos con todos sus campos correctos.
- **RFC de GS-CSF-03-ESC:** el OCR leyó «CBA120809QWA4» (una A de más) en el renglón del RFC y el modelo lo copió fielmente; la cadena original del mismo documento trae el RFC correcto. El dictamen no cambia (el RFC es ajeno en ambos casos: NO_CONFORME). Es el único error atribuible al OCR en los 12 escaneos.
- **Fecha de emisión de GS-CONT-06** (contrato sin apartado de firmas): la anotación la fija en el inicio de la vigencia (2 de marzo de 2026); el modelo devolvió vacío porque, sin firmas, el documento no declara la fecha en que se celebró. Es una **discrepancia defendible de la anotación**; la cifra oficial la cuenta como error y no se ajusta a posteriori (§2.1).

#### PE-2 · Elementos normativos RSC

101 pares (caso, regla anotada): 14 omisiones reales y 87 elementos presentes.

| Clase | VP | FP | FN | Precisión | Exhaustividad | F1 (IC 95 %) |
|---|---|---|---|---|---|---|
| Omisión (la métrica crítica) | 12 | 0 | **2** | 100 % | **85.7 %** | 92.3 % (78–100 %) |
| Presente | 87 | 2 | 0 | 97.8 % | 100 % | 98.9 % (97–100 %) |

- **Dos falsas conformidades de elemento, ambas por inferencia del modelo:**
  - `GS-CONT-05` (contrato sin objeto): RSC-01-CONT-OBJ se dio por cumplida con la cita «…prestar los servicios objeto de este contrato» de las declaraciones, y la observación «el objeto se define implícitamente».
  - `GS-NDA-02` (NDA sin obligación de no divulgación): RSC-01-NDA-NODIV se dio por cumplida con la definición de información confidencial, «estableciendo la base para la obligación».
- **Las citas son literales pero no prueban el elemento.** Las 89 citas de los elementos CUMPLE están ancladas al texto (89/89): el anclaje garantiza que la cita existe, no que sea pertinente. Es un límite del diseño actual.
- **Impacto:** ninguno en el estatus. Contratos y NDA siempre pasan a revisión humana por RSC-02, y el analista ve la cita y la observación «implícitamente». Pero el motivo que se muestra da el elemento por presente.
- **Por regla:** 15 de las 17 reglas evaluadas aciertan en todos sus pares; RSC-01-CONT-OBJ 9/10 y RSC-01-NDA-NODIV 3/4.
- **Abstenciones:** ninguna (0 NO_VERIFICABLE).
- **Corrección aplicada (aprobada el 01/10/2026): salvaguarda determinista.** Un CUMPLE con cita literal cuya observación declara una deducción («implícitamente», «se infiere», «la base para»…) queda NO_VERIFICABLE y pasa al analista (`verificacion_contenido.declara_deduccion`).
  - Las frases se tomaron de las 39 observaciones reales de los casetes; ninguna observación de un elemento presente las contiene.
  - Las instrucciones del modelo no cambian: no hay que regrabar y el resultado se mide desde el casete, sin tokens.

| Elementos RSC | Omisiones detectadas | Omisiones indebidas | Falsas conformidades |
|---|---|---|---|
| Antes de la salvaguarda | 12/14 (85.7 %) | 0 | 2 |
| **Con la salvaguarda** | **14/14 (100 %)** | **0** | **0** |

  - El estatus (42/42), las entidades y el chat (37/38 y 8/8, los mismos tokens) no cambian.
  - **Límite:** si el modelo deduce un elemento sin decirlo en su observación, la salvaguarda no lo detecta. Si vuelve a aparecer una falsa conformidad en documentos reales, el paso siguiente es exigir el elemento expreso en las instrucciones, lo que obliga a regrabar.

#### PE-3 · Firmantes y apoderados (RSC-02)

- **Nombres:** 46/46 personas encontradas, sin ninguna inventada (P = R = F1 = 100 %).
- **Cargo:** 41/46 (89 %, IC 77–95 %). Los 5 fallos son el mismo: en las 5 actas (3 vectoriales y 2 escaneadas), la apoderada se extrae sin cargo, porque el acta la nombra solo por su poder («Se otorga a María Elena Ruiz Soto poder general…») y no la llama «apoderada».
- **Impacto:** el cotejo RN-03 usa el nombre y el rol (APODERADOS), no el cargo, así que no se afecta. Lo que ve el analista es un cargo vacío.

#### OCR (CER sobre texto conocido)

| Escaneos | CER mediano | CER máximo | Peor documento |
|---|---|---|---|
| 12 | **0.24 %** | 0.96 % | Poder notarial |

Tres escaneos tienen CER de 0 %. La lectura 3.3 coincide con lo medido sin modelo en §10.1 (recall de palabras 99.65 %).

**Ablación vectorial / escaneado** (los 12 casos base que tienen escaneo, en sus dos rendiciones):

| Rendición | F1 micro de entidades | Documentos con todos los campos | Estatus correcto |
|---|---|---|---|
| Vectorial | 100 % | 12/12 | 12/12 |
| Escaneado | 98.0 % | 11/12 | 12/12 |

El OCR cuesta 2 puntos de F1 en las entidades (el RFC de GS-CSF-03-ESC) y nada en las decisiones ni en los elementos RSC.

#### Lectura para el residente

- **Lo que se puede afirmar con estas cifras:** en el Gold Standard, el motor no aprobó nada que debiera revisarse ni rechazó nada aprobable; no inventó datos; y cada cita que presenta existe en el documento.
- **Lo que no se puede afirmar:**
  - el comportamiento con documentos reales ni la calibración de las bandas bajas (§2.4 y §9);
  - que el motor detecte siempre la omisión de una cláusula: sin la salvaguarda, 2 de 14 omisiones se dieron por cumplidas, y con ella 14 de 14 se detectan en este conjunto. La salvaguarda depende de que el modelo declare su deducción.

### 10.3 Rendimiento (01/10/2026)

**Equipo:** AMD Ryzen 5 3500U (4 núcleos y 8 hilos), 5.9 GB de RAM y Windows 11. Python 3.12, PostgreSQL 17 local y Tesseract 5.4. Servicios locales, con un proceso de uvicorn por servicio. Las cifras valen para este equipo de desarrollo (§9), no para un servidor.

#### RNF-01 · Evaluación determinista (≤ 2 s) — **Cumple**

`python scripts/benchmark_rendimiento.py`, sobre `plurione_compliance_bench`. Expedientes jurídicos con tipos de documento distintos, cada uno con su dictamen, el anexo del contrato (RIE-02) y el cotejo RN-03 acreditado. 5 peticiones de calentamiento y 100 medidas, secuenciales. Detalle en [`rendimiento.json`](resultados_validacion/rendimiento.json).

| Expediente | `GET /expedientes/{id}` p50 / p95 / p99 | Con OCR de 20 páginas en curso, p95 | `reevaluar()` en proceso, p95 |
|---|---|---|---|
| 3 documentos | 47.5 / 65.6 / 73.1 ms | 54.6 ms | 47.8 ms |
| 8 documentos | 30.0 / 54.2 / 62.0 ms | 56.4 ms | 53.8 ms |
| 15 documentos | 51.2 / **72.5** / 80.4 ms | 58.5 ms | 55.6 ms |
| Listado de 30 expedientes (estrés) | 201.9 / 245.1 / 280.1 ms | — | — |

- El peor p95 es de 72.5 ms: **27 veces por debajo de la meta**.
- La lectura OCR en curso con 8 procesos no la degrada. El core es otro proceso y su trabajo es de base de datos, no de CPU.
- La evaluación en proceso cuesta de 30 a 55 ms; el resto del tiempo es red local y serialización.

#### RNF-02 · Extracción y análisis (≤ 25 s por documento de hasta 20 páginas) — **Cumple con documentos sintéticos; no con el acta real**

`python -m evaluacion.benchmark_extraccion` mide el Nivel 3 en frío (sin persistencia ni caché): 5 corridas por documento, con la configuración definitiva y con la anterior, cada una en su propio proceso. Detalle en [`rendimiento_extraccion.json`](resultados_validacion/rendimiento_extraccion.json).

| Documento | Páginas | Definitiva: mediana (rango) | Anterior: mediana | Cambio |
|---|---|---|---|---|
| Contrato vectorial | 20 | 0.02 s | 0.03 s | — |
| Contrato escaneado | 20 | **8.9 s** (8.6–9.0) | 15.5 s | −43 % |
| Contrato escaneado a color, con sellos en 5 páginas | 20 | 10.0 s (9.9–10.9) | 15.6 s | −36 % |
| Acta real escaneada (bóveda, no versionada) | 26 | **35.4 s** (31.0–36.8) | 71.5 s | −50 % |

- **Desglose por etapa** (tiempo acumulado en los 8 procesos, contrato escaneado): Tesseract 36.8 s, preprocesamiento 5.6 s y rasterizado 2.1 s. El OCR es ≈ 83 % del trabajo; con 8 procesos en paralelo, eso son 8.9 s de reloj.
- **Sellos:** con la configuración definitiva, el raster a color de un documento con sellos cuesta 1.1 s más. La relectura de sellos de la configuración anterior no cambió el tiempo, lo que confirma §5.1.

**RNF-02 completo, Nivel 3 en frío + Nivel 4:** 3 auditorías reales del contrato escaneado ([`rendimiento_rnf02.json`](resultados_validacion/rendimiento_rnf02.json)).

| Auditoría | Lectura del texto | Groq: extracción · verificación (en paralelo) | Total medido | Total sin la espera del grabador |
|---|---|---|---|---|
| 1 | 9.1 s | 3.0 s · 1.7 s | 70.9 s | ≈ 12.1 s |
| 2 | 9.0 s | 2.3 s · 2.1 s | 71.2 s | ≈ 11.3 s |
| 3 | 9.4 s | 1.3 s · 2.0 s | 71.5 s | ≈ 11.4 s |

- **El total medido no es el del servicio.** Unos 58 s de cada auditoría son la espera del presupuesto de 7,000 tokens por minuto del grabador (`evaluacion/entorno.py`), que existe para grabar casetes sin errores 429 y no forma parte del servicio.
- **La última columna es una reconstrucción:** lectura + la mayor de las dos latencias de Groq, porque las dos llamadas corren en paralelo. Su mediana es ≈ **11.4 s frente a la meta de 25 s**.
- **Pendiente:** el benchmark ya corre sin ese presupuesto y con 61 s entre auditorías (prueba `test_sin_limite_de_tokens_el_grabador_no_espera`). La medición formal se repite con la cuota diaria siguiente, porque la de hoy se agotó (≈ 21,000 tokens).
- **El acta real no cumple la meta.** Sus 26 páginas tardan 35.4 s solo en el Nivel 3, unos 27 s si se normaliza a 20 páginas (1.36 s por página). Con el Nivel 4, ≈ 30 s frente a 25 s.
  - Sus páginas son mucho más densas que las del contrato sintético (0.44 s por página): Tesseract acumula 207 s contra 37 s.
  - Para los escaneos reales densos, el RNF-02 **no se cumple en este equipo**. Las palancas de §5.2 ya están en su mejor valor.
  - Lo que queda fuera del alcance documentado: un equipo con más núcleos, OCR en la nube o reducir los ppp, que §5.1 descartó por pérdida de texto.

#### RNF-03 · Concurrencia (≥ 50 peticiones simultáneas) — **Cumple el criterio de §7.4, con degradación de latencia**

50 peticiones liberadas por una barrera, contra la misma serie en secuencia:

| Escenario | Secuencial p95 | Simultáneo p50 / p95 | Degradación del p95 | 5xx | Respuestas correctas |
|---|---|---|---|---|---|
| `GET /health` | 5.0 ms | 269 / 316 ms | ×63 | 0 | 50/50 |
| `GET /expedientes/{id}` (10 expedientes) | 64.2 ms | 831 / **1,070 ms** | ×17 | 0 | 50/50 |
| Cargas de documentos distintos (10 expedientes) | 98.2 ms | 1,542 / 2,200 ms | ×22 | 0 | 50/50 (201) |

| Pérdida de transacciones | Resultado |
|---|---|
| Cargas aceptadas (secuenciales + simultáneas) | 100 |
| Documentos en la base (versiones incluidas) | 100 |
| Eventos INGESTA_DOCUMENTO | 100 |
| Cadena de la bitácora | Íntegra y sellada (499 eventos) |

- **Sin errores ni pérdidas:** 0 respuestas 5xx, 0 transacciones perdidas, la cadena íntegra y un p95 de consulta simultánea de 1.07 s, por debajo de 2 s.
- **Sí hay degradación de latencia:** las 50 peticiones se atienden con un solo proceso de uvicorn, así que esperan turno.
- **Las cargas simultáneas suben a 2.2 s de p95.** El candado de la bitácora las serializa, como advierte el PRD §21.3. Es el precio de la cadena sellada: sin el candado, dos eventos podrían encadenarse al mismo eslabón.
- **«Sin degradación» se lee como «sin errores ni pérdidas y dentro de la meta de RNF-01»,** el criterio que fija §7.4. Un despliegue con varios procesos (`uvicorn --workers`) reduciría la espera de las consultas; las cargas seguirían serializadas por diseño.
- **Primera corrida descartada.** Cargaba tipos repetidos, que el core guarda como versiones, y contaba los documentos desde la evaluación, que solo lista los vigentes. El script ahora exige el tamaño evaluado y cuenta las filas en la base.

#### Conclusión por requisito

| Requisito | Resultado |
|---|---|
| RNF-01 (≤ 2 s) | **Cumple:** p95 ≤ 73 ms, incluso con OCR en curso |
| RNF-02 (≤ 25 s, 20 páginas) | **Cumple con el contrato escaneado sintético** (≈ 11.4 s, reconstrucción pendiente de la medición formal sin el presupuesto del grabador); **no cumple con el acta real densa** (≈ 30 s normalizado a 20 páginas) |
| RNF-03 (≥ 50 simultáneas) | **Cumple el criterio de §7.4** (0 errores, 0 pérdidas, p95 de consulta 1.07 s), con degradación de latencia por un solo proceso |
