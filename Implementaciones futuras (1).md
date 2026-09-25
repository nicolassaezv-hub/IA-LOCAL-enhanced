# Implementaciones futuras del proyecto ASTRA

> **Estado del documento:** borrador técnico de implementaciones futuras. Las propuestas de este archivo están definidas y aprobadas, pero **todavía no se consideran implementadas**. Quedan listas para pasar a Work cuando el usuario lo decida.

## Simbología

- ✅ Propuesta hecha con una base.
- ✅✅ Propuesta creada y aprobada por IA.
- ■ Propuesta en proceso de desarrollo.

> **Principio general de integración:** las nuevas implementaciones deben ampliar ASTRA sin romper los flujos que ya están en producción. En especial, mientras Forex se encuentre en calificación Shadow, cualquier mejora de esa rama debe ser de visualización, operación o infraestructura y no modificar modelos, thresholds, targets ni la lógica BUY/SELL/HOLD sin una autorización explícita.

# ESTÉTICA:

## ✅✅ Shadow Monitor ampliado — Analytics y navegación de predicciones

### Objetivo

Ampliar el Shadow Monitor para visualizar y explorar el rendimiento real de las predicciones Forex sin alterar la lógica que las genera, su calificación ni el funcionamiento productivo de Forex Shadow.

### Fuente y flujo de datos

- La API del monitor debe entregar la información completa disponible para el período solicitado.
- Los filtros de visualización se aplicarán localmente en el Shadow Monitor.
- La interfaz debe poder trabajar con el histórico completo recibido sin ocultar predicciones.
- Si el volumen aumenta, la tabla podrá usar paginación, virtualización o carga progresiva de renderizado, siempre que el usuario conserve acceso a todas las predicciones disponibles y que estas optimizaciones no cambien las métricas.
- La integración será de lectura y visualización. No debe modificar registros Shadow ni intervenir en la generación de señales.

Flujo esperado:

```text
Shadow data store (read-only)
        ↓
Monitor API — dataset completo
        ↓
Shadow Monitor
        ├── métricas
        ├── filtros locales
        ├── gráfica interactiva
        └── tabla filtrable y ordenable
```

### Universo válido para win rate

El win rate se calculará únicamente con predicciones que cumplan ambas condiciones:

```text
dirección ∈ {BUY, SELL}
AND
resultado confirmado/maduro
```

No participarán en wins, losses ni en el denominador del win rate:

- `HOLD`;
- `pending`;
- `observation_hold_only`;
- predicciones cuyo horizonte todavía no haya madurado;
- registros sin resultado confirmado.

Los registros excluidos del cálculo podrán seguir apareciendo en la tabla completa con su estado real. La interfaz debe diferenciar con claridad entre el total de registros mostrado y el subconjunto elegible para W/L.

### Métricas obligatorias

El monitor debe ofrecer métricas:

- globales;
- por cohorte —incluidas Restricted, Expansion v1 y futuras cohortes—;
- por símbolo, por ejemplo `EURUSD`, `USDJPY`, `AUDUSD` o `GBPUSD`;
- acumuladas por símbolo hasta la fecha o punto temporal seleccionado.

Para cada nivel se deben poder consultar, como mínimo:

- win rate;
- wins;
- losses;
- número de predicciones elegibles;
- pending como conteo informativo separado, sin incorporarlo al win rate;
- confidence agregada, con la regla de agregación identificada;
- evolución histórica.

### Gráfica interactiva

- Debe permitir alternar entre las vistas global, por cohorte y por símbolo.
- Debe mostrar la evolución temporal de la métrica seleccionada.
- Al pasar el cursor por una fecha, debe mostrar un resumen contextual, por ejemplo:

```text
23/09/2026
Win rate: 61,4 %
Wins: 8
Losses: 5
Signals elegibles: 13
```

- Al hacer clic en una fecha, la tabla debe filtrarse a las señales o predicciones de ese día **dentro de la misma pantalla**; no debe redirigir a otra vista.
- Cuando exista un símbolo seleccionado, la gráfica debe permitir consultar su histórico acumulado hasta la fecha seleccionada.
- Los filtros activos deben quedar visibles para evitar interpretar una vista parcial como una métrica global.

### Tabla de predicciones

- Debe contener todas las predicciones disponibles recibidas desde la API, incluidas las no elegibles para W/L, conservando su estado.
- Debe sincronizarse con los filtros de la gráfica en la misma pantalla.
- Debe permitir quitar el filtro temporal y volver a la tabla completa.
- Debe permitir ordenar, como mínimo, por:
  - símbolo en orden alfabético;
  - win rate;
  - confidence.
- La tabla debe mostrar suficientes campos de identificación para auditar el origen de cada métrica: símbolo, cohorte, dirección, timestamp, horizonte/madurez, estado, resultado y confidence cuando estén disponibles.

### Criterios de aceptación

- Un registro `HOLD`, `pending`, `observation_hold_only` o no maduro nunca altera wins, losses ni win rate.
- La suma de wins y losses coincide con el total de predicciones elegibles en cada filtro.
- La vista por símbolo permite obtener, por ejemplo, el win rate acumulado de `USDJPY` hasta una fecha seleccionada.
- El clic en un punto temporal filtra la tabla sin abandonar la pantalla.
- Quitar los filtros restaura el conjunto completo entregado por la API.
- La implementación no modifica modelos, thresholds, targets ni la lógica BUY/SELL/HOLD.

# FUNCIONAL:

## ✅✅ Model Registry — Hasta 8 motores IA personalizados

### Objetivo

Permitir que ASTRA registre y use hasta ocho motores o modelos IA distintos, incluso de proveedores y APIs independientes, y que el usuario pueda cambiar manualmente de modelo desde el chat.

### Alcance funcional

- Admitir un máximo de **8 configuraciones activas** de motores/modelos.
- Una configuración representa una combinación concreta de proveedor, modelo y endpoint. El mismo proveedor puede aparecer más de una vez si utiliza modelos o endpoints diferentes.
- Mostrar en el chat un selector de modelos similar a los selectores habituales de motores IA.
- Permitir selección manual por turno o conversación, según lo que defina la interfaz.
- Antes del uso inicial, consultar al usuario qué configuración desea establecer como modelo `default`.
- Permitir cambiar posteriormente el modelo default de forma explícita.
- Si el modelo elegido no está disponible, informar el fallo y solicitar o aplicar una alternativa definida por política; nunca cambiar silenciosamente de proveedor o modelo.

### Registro canónico de modelos

Cada configuración debe registrar, como mínimo:

```text
model_registry_entry
├── id
├── display_name
├── provider
├── model
├── endpoint
├── credential_ref
├── context_window
├── capabilities
├── enabled
└── is_default
```

- `provider`: proveedor o familia de API.
- `model`: identificador exacto del modelo solicitado al proveedor.
- `endpoint`: endpoint base o referencia de conexión correspondiente.
- `credential_ref`: referencia al secreto necesario para autenticar la solicitud.
- `context_window`: ventana de contexto declarada para ese motor y usada por el Context Budget Manager.

### Seguridad de credenciales

- Las API keys, tokens y secretos **nunca se guardarán en texto plano** dentro del registro, logs, memoria de chat, archivos de configuración versionables ni interfaz.
- `credential_ref` debe apuntar a un mecanismo de secretos autorizado —por ejemplo, almacén de credenciales o variable secreta administrada— sin revelar el valor.
- Los mensajes de error y auditoría deben ocultar credenciales, cabeceras de autenticación y parámetros sensibles.

### Memoria y contexto

- La memoria compartida de ASTRA será la fuente canónica común a los motores.
- Cambiar de motor no crea memorias contradictorias ni duplica automáticamente el historial.
- Cada motor recibirá únicamente el contexto relevante para la solicitud actual, recuperado desde esa memoria canónica y limitado por su propia ventana de contexto.
- Las instrucciones críticas y permisos de ASTRA deben aplicarse de forma consistente sin depender del proveedor seleccionado.

### Observabilidad por turno

Cada turno debe registrar, como mínimo:

```text
provider
model
timestamp
token_usage
latency
status
```

Cuando el proveedor lo permita, `token_usage` distinguirá entrada, salida y total. Si la medición no es exacta, deberá marcarse como estimada. Los logs no deben incluir secretos.

### Criterios de aceptación

- El usuario puede registrar hasta ocho motores con APIs independientes y distinguirlos por nombre visible.
- El selector del chat muestra únicamente configuraciones habilitadas.
- El modelo default fue elegido previamente por el usuario y queda identificado sin ambigüedad.
- Cada solicitud usa el `provider`, `model`, `endpoint` y `credential_ref` correctos.
- Ningún secreto aparece en texto plano en configuración, memoria, interfaz o logs.
- Cada turno deja trazabilidad del motor usado, timestamp, tokens, latencia y estado.

## ✅✅ Context Budget Manager — Presupuesto preventivo de contexto

### Objetivo

Calcular el payload completo antes de enviarlo al motor para evitar cortes por límites de contexto y adaptar la política al tamaño de ventana de cada modelo registrado.

### Componentes incluidos en el conteo

El contador preventivo debe considerar **todo** lo que se envía o se reserva para la petición:

- system prompt;
- instrucciones de operación y seguridad;
- contexto ASTRA;
- memoria recuperada;
- historial conversacional incluido;
- archivos, adjuntos o fragmentos incorporados;
- definiciones y resultados de herramientas;
- mensaje actual del usuario;
- metadatos que formen parte del payload;
- reserva de tokens para la salida.

La comprobación debe ocurrir después de ensamblar el payload efectivo y antes de enviarlo al proveedor.

### Tokenización y declaración de precisión

- Se usará el tokenizer exacto del motor cuando esté disponible.
- Si no existe un tokenizer exacto accesible, se empleará una estimación conservadora.
- El resultado debe declarar si el conteo es `exact` o `estimated`, junto con el modelo y la ventana usados.
- El cálculo debe soportar ventanas de contexto distintas para cada entrada del Model Registry.

### Política inicial de thresholds

Los thresholds serán configurables. La política inicial será:

```text
uso < 80 %       → NORMAL
80 % a < 90 %    → WARNING
90 % a 95 %      → COMPACT_OR_REDUCE
uso > 95 %       → BLOCK_SEND
```

- **NORMAL:** enviar normalmente.
- **WARNING:** advertir el uso elevado y registrar el evento; la solicitud puede continuar.
- **COMPACT_OR_REDUCE:** reducir preventivamente el payload, volver a contar y enviar solo si vuelve a existir margen suficiente.
- **BLOCK_SEND:** no enviar al proveedor hasta recuperar margen y superar una nueva validación preventiva.

El porcentaje debe calcularse contra la ventana del motor seleccionado e incluir la reserva de salida.

### Reglas de reducción o compactación

- Preservar instrucciones de sistema, seguridad, permisos, objetivo actual, decisiones vigentes y contexto crítico.
- Priorizar la eliminación de duplicados, resultados de herramientas obsoletos, detalle histórico no relevante y contenido recuperable.
- No resumir de forma que se cambie una decisión del usuario, una restricción o un dato requerido para la tarea.
- Identificar que hubo compactación y conservar provenance suficiente para auditar qué fuentes fueron reducidas.
- Volver a contar el payload resultante antes del envío.
- Si no se puede recuperar margen sin perder contexto crítico, bloquear el envío y explicar la causa.

### Salida mínima del contador

```text
model
context_window
input_tokens
reserved_output_tokens
projected_total_tokens
usage_percent
count_method: exact | estimated
status: NORMAL | WARNING | COMPACT_OR_REDUCE | BLOCK_SEND
```

### Criterios de aceptación

- Ninguna petición sale sin una comprobación preventiva del payload final.
- Cambiar de motor recalcula el presupuesto con su ventana y tokenizer correspondientes.
- Una petición por encima del 95 % queda bloqueada hasta recuperar margen.
- Tras compactar, el sistema conserva instrucciones y contexto crítico y realiza un conteo nuevo.
- La interfaz o trazabilidad distingue con claridad entre conteo exacto y estimado.

## ✅✅ Business Dataset Intelligence v1 — Análisis adaptativo de CSV

### Objetivo

Inspeccionar archivos CSV heterogéneos, diagnosticar su estructura y calidad y, cuando exista aprobación explícita, producir una versión normalizada sin sobrescribir silenciosamente el original.

### Alcance de v1

- La primera versión se limita a archivos **CSV**.
- Otros formatos quedan fuera de alcance hasta una propuesta posterior.
- El módulo ofrecerá exactamente dos modos operativos:
  - `inspect_only`;
  - `normalize_with_approval`.

### Modo `inspect_only`

- Lee y perfila el CSV sin modificar el archivo original.
- Detecta problemas y propone transformaciones.
- Genera un perfil de calidad, inferencias por columna y confidence de esas inferencias.
- No produce cambios destructivos ni reemplaza datos.

### Modo `normalize_with_approval`

- Requiere aprobación explícita antes de aplicar correcciones o normalizaciones.
- Puede corregir automáticamente problemas aprobados de encoding, parsing, tipos o representación.
- Genera un archivo derivado; nunca sobrescribe silenciosamente el CSV original.
- Registra cada transformación aplicada, su motivo y su resultado.

### Detección estructural

Antes de procesar valores, debe detectar o inferir:

- encoding;
- delimitador;
- reglas de quoting y escape;
- cabecera y número esperado de columnas;
- inconsistencias de filas o parseo.

Cuando una inferencia sea ambigua, debe presentar alternativas y confidence en vez de asumir certeza.

### Inferencia por columna

Debe poder diferenciar, como mínimo:

- fechas;
- timestamps;
- campos JSON;
- strings;
- valores `NaN`;
- enteros;
- floats, incluida notación científica;
- campos vacíos;
- listas;
- diccionarios;
- booleanos;
- columnas mixtas.

La detección de separadores forma parte de la estructura del archivo y también debe considerar separadores internos cuando sean relevantes para listas, números o campos compuestos, sin dividir contenido citado incorrectamente.

### Perfil de calidad

El reporte debe incluir, como mínimo:

- tipo inferido por columna y confidence;
- porcentaje y conteo de vacíos/nulos;
- valores que no coinciden con el tipo dominante;
- duplicados relevantes;
- errores de parseo;
- formatos de fecha o booleanos incompatibles;
- columnas mixtas y ejemplos representativos;
- acciones propuestas;
- riesgos de pérdida o cambio semántico.

### Manifest y provenance

Cada salida normalizada debe estar vinculada al original mediante un manifest que registre, como mínimo:

```text
source_file
source_fingerprint
normalized_file
normalized_fingerprint
mode
timestamp
detected_encoding
detected_delimiter
schema_before
schema_after
approved_transformations
warnings
```

El original debe conservarse intacto. El manifest debe permitir reconstruir qué cambió y por qué.

### Criterios de aceptación

- Un CSV puede analizarse en `inspect_only` sin crear cambios en el original.
- La normalización no comienza sin aprobación explícita.
- El sistema identifica encoding, delimitador y quoting antes de inferir tipos.
- Las columnas mixtas no se fuerzan silenciosamente a un tipo incompatible.
- Cada inferencia relevante incluye confidence.
- El archivo normalizado y su manifest conservan provenance verificable hacia el original.

## ✅✅ Prediction Lab — Dataset Mix Gate

### Objetivo

Permitir integración o entrenamiento conjunto entre datasets únicamente cuando exista compatibilidad demostrable y evidencia suficiente para obtener rendimiento real, evitando técnicas que fabriquen métricas o introduzcan leakage.

Principio rector:

```text
REAL DATA IN → REAL EVALUATION → REAL PERFORMANCE
```

### Regla base

- Deben existir al menos **4 variables predictoras comunes y persistentes** entre los datasets.
- Esas variables deben conservar significado, tipo, unidad y comportamiento comparables.
- Deben existir relaciones lineales o estables evaluables entre las variables comunes, y su estabilidad debe comprobarse en distintos períodos relevantes.
- Entrenar modelos separados por dataset **no** será la estrategia principal de este módulo; el gate existe para decidir si los datos pueden integrarse de manera válida.
- El target utilizado para entrenamiento conjunto debe ser semánticamente idéntico entre datasets. Compartir únicamente el nombre de columna no es suficiente.

### Prácticas no permitidas dentro del módulo

No se permitirá:

- SMOTE;
- oversampling;
- synthetic balancing o generación de muestras sintéticas para balancear;
- stratified sampling dentro de este módulo;
- leakage de cualquier tipo, incluido temporal, de target, de features, de entidades o de preprocessing;
- alteraciones destinadas a fabricar rendimiento;
- ignorar sesgos conocidos o detectados;
- ignorar diferencias de escala, unidades o escalabilidad operativa;
- usar el test intacto para selección, ajuste de hiperparámetros o decisiones del gate.

### Gate obligatorio

Antes de mezclar datos o iniciar entrenamiento, el gate debe evaluar y documentar:

1. **Provenance:** origen, versión, licencias/restricciones, período, transformaciones y trazabilidad de cada dataset.
2. **Schema compatibility:** correspondencia explícita de columnas y significado.
3. **Common predictors:** existencia de al menos cuatro variables predictoras comunes y persistentes.
4. **Type/unit compatibility:** compatibilidad de tipos, escalas, unidades y convenciones.
5. **Temporal compatibility:** frecuencias, ventanas, zonas horarias, cortes temporales y disponibilidad histórica compatibles.
6. **Entity/granularity match:** entidades observadas y nivel de granularidad comparables o reconciliables sin fabricar observaciones.
7. **Target compatibility:** target semánticamente idéntico, con la misma definición, horizonte y momento de disponibilidad.
8. **Linear relationship test:** evaluación estadística de las relaciones lineales pertinentes entre variables comunes.
9. **Stability across periods:** estabilidad de relaciones, distribuciones y efectos entre períodos.
10. **Bias analysis:** sesgos de cobertura, selección, medición, supervivencia, representatividad y otros riesgos relevantes.
11. **Scaling analysis:** unidades, rangos, transformaciones permitidas, escalabilidad computacional y comportamiento al crecer el volumen.
12. **Leakage audit:** revisión explícita del pipeline completo antes de entrenar.
13. **Research evidence:** respaldo externo documentado para la lógica de relación e integración.

Cada control debe producir estado, evidencia, hallazgos, limitaciones y decisión. Si falla un requisito crítico, el resultado será:

```text
PAUSED_REQUIRES_EVIDENCE
```

En ese estado no se mezclan datasets ni se inicia entrenamiento. El usuario podrá aportar evidencia adicional o decidir abandonar la integración.

### Investigación y respaldo

- Se permiten como máximo **3 rondas de investigación** para respaldar la relación propuesta.
- Cada ronda debe registrar:
  - pregunta investigada;
  - reporte;
  - fuentes principales;
  - hallazgos;
  - limitaciones;
  - nivel de respaldo.
- Deben priorizarse fuentes principales y trazables.
- La investigación puede justificar hipótesis y contexto, pero **no reemplaza** los tests estadísticos, la auditoría de leakage ni la validación empírica.
- Si después de tres rondas no existe respaldo suficiente, el gate permanece en `PAUSED_REQUIRES_EVIDENCE` hasta que el usuario aporte fuentes fidedignas o se reformule la propuesta.

### Estrategias de integración permitidas

Según el resultado del gate, el plan puede autorizar una de estas estrategias:

- **Row concatenation:** filas compatibles bajo un schema y target equivalentes.
- **Temporal/relational join:** unión por tiempo o entidad cuando claves, granularidad, causalidad y disponibilidad eviten leakage.
- **Feature-level integration:** combinación de variables compatibles para una misma unidad de observación.

La estrategia seleccionada debe justificarse en el reporte del gate. No se debe forzar una unión cuando la compatibilidad solo sea aparente.

### Evaluación final obligatoria

Todo entrenamiento aprobado debe terminar con:

```text
temporal OOS validation
        +
untouched test
        +
final report
```

- La validación OOS debe respetar el orden temporal y simular disponibilidad real de los datos.
- El test debe permanecer intacto hasta la evaluación final.
- El reporte final debe describir datasets, provenance, particiones, transformaciones, features, target, métricas, incertidumbre, sesgos, limitaciones, fallos del gate y evidencia utilizada.
- El rendimiento debe reportarse tal como se obtiene; no se permite ocultar resultados negativos ni seleccionar únicamente segmentos favorables.

### Resultado mínimo del gate

```text
decision: APPROVED | REJECTED | PAUSED_REQUIRES_EVIDENCE
approved_integration_strategy
common_predictors
target_compatibility
checks
research_rounds
leakage_audit
bias_analysis
scaling_analysis
required_actions
```

### Criterios de aceptación

- No existe aprobación con menos de cuatro predictores comunes válidos.
- Un target solo se considera compatible si su semántica, horizonte y disponibilidad coinciden.
- Cualquier requisito crítico fallido produce `PAUSED_REQUIRES_EVIDENCE` y detiene mezcla y entrenamiento.
- La investigación queda limitada a tres rondas y no sustituye las pruebas estadísticas.
- No se usan SMOTE, oversampling, synthetic balancing, stratified sampling ni leakage dentro del módulo.
- La evaluación utiliza temporal OOS validation, un test intacto y un reporte reproducible.
- La decisión final preserva el principio `REAL DATA IN → REAL EVALUATION → REAL PERFORMANCE`.

# Estado del borrador

- ✅✅ Shadow Monitor ampliado — Analytics y navegación de predicciones.
- ✅✅ Model Registry — Hasta 8 motores IA personalizados.
- ✅✅ Context Budget Manager — Presupuesto preventivo de contexto.
- ✅✅ Business Dataset Intelligence v1 — Análisis adaptativo de CSV.
- ✅✅ Prediction Lab — Dataset Mix Gate.

Las cinco propuestas son implementaciones futuras, ya definidas y aprobadas como borradores técnicos. Están listas para pasar a Work cuando el usuario lo decida; este documento no afirma que hayan sido desarrolladas, desplegadas ni integradas todavía.
