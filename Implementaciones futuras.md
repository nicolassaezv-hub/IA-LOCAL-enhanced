# Implementaciones futuras del proyecto ASTRA

## Simbología

- ✅ Propuesta hecha con una base.
- ✅✅ Propuesta creada y aprobada por IA.
- ■ Propuesta en proceso de desarrollo.

> **Principio general de integración:** las nuevas implementaciones deben ampliar ASTRA sin romper los flujos que ya están en producción. En especial, mientras Forex se encuentre en calificación Shadow, cualquier mejora de esa rama debe ser de visualización, operación o infraestructura y no modificar modelos, thresholds, targets ni la lógica BUY/SELL/HOLD sin una autorización explícita.

# ESTÉTICA

## ✅ Rama Forex con vista gráfica

La rama Forex debe incluir una vista detallada con gráfico y puntero/crosshair para cada timeframe, incluyendo la vista multiframe (MTF), con una experiencia visual cercana a MetaTrader 5.

### Funciones esperadas

- Gráfico de línea y/o velas.
- Tooltips al pasar el mouse sobre las velas.
- Crosshair y lectura de OHLC/fecha/hora.
- Cambio entre H1, H4 y D1.
- Vista MTF con contexto H4/D1 y señal H1.
- Indicadores opcionales mediante casillas (máximo 30 disponibles).
- Dark/Light Mode.
- Zoom y desplazamiento temporal.

### Adaptación recomendada

Usar una librería ligera de gráficos financieros, preferentemente **TradingView Lightweight Charts** o una alternativa equivalente, alimentada exclusivamente desde las APIs/datos canónicos de ASTRA.

Flujo recomendado:

```text
RemoteMT5Provider / datos canónicos
            ↓
       API Forex ASTRA
            ↓
     gráfico Workspace
       ├─ H1/H4/D1
       ├─ velas
       ├─ tooltips
       └─ indicadores seleccionados
```

Los indicadores deben calcularse/renderizarse solo cuando el usuario los active. La vista gráfica será **read-only respecto del pipeline predictivo**: nunca debe modificar datasets, modelos ni señales.

---

## ✅ Manejo de procesos múltiples simultáneos en la ejecución (Workspace y CLI)

ASTRA debe poder conocer el rendimiento del sistema donde se está ejecutando y decidir cuántas tareas puede aceptar simultáneamente. Por ejemplo, determinar si puede ejecutar Forex y procesar un PDF al mismo tiempo sin degradar el sistema.

### Adaptación recomendada

Crear un **Resource Manager / Admission Controller** central apoyado en `psutil` y en primitivas como `asyncio`, `ThreadPoolExecutor` y `ProcessPoolExecutor` según el tipo de tarea.

Debe observar al menos:

- RAM disponible y utilizada.
- CPU disponible y carga actual.
- Cantidad de tareas activas.
- Tipo/peso estimado de cada tarea.
- Historial de consumo de tareas similares cuando exista.
- Margen de seguridad configurable.

En vez de declarar siempre un número fijo como “máximo 5 procesos”, ASTRA debe calcular una capacidad aproximada y decidir:

```text
ACCEPT  → ejecutar ahora
QUEUE   → dejar en espera
REJECT  → no aceptar hasta liberar recursos
```

Ejemplo visual:

```text
3 tareas activas
RAM: 6.2 / 11 GB
CPU: 47 %
Capacidad estimada: +2 tareas ligeras
```

Cuando se alcance el límite, ASTRA debe informar claramente al usuario y no iniciar nuevas tareas pesadas hasta liberar recursos.

---

## ✅ Barra de Personalización

La personalización debe integrarse dentro de la barra de **Configuración/Settings** del Workspace, no como un módulo aislado.

### Adaptación recomendada

Usar variables CSS y persistencia de preferencias del usuario.

Estructura sugerida:

```text
Settings
└─ Appearance
   ├─ Dark / Light
   ├─ Accent Color
   ├─ Glow
   ├─ Interface Style
   └─ Animations
```

Variables visuales sugeridas:

```css
--astra-accent
--astra-bg
--astra-glow
--astra-border
```

Los cambios deben afectar solo a la presentación, nunca al estado lógico de ASTRA.

---

## ■ Resaltar código, comandos y rutas de archivo con estilos distintos

ASTRA debe distinguir visualmente entre texto normal, código, comandos de terminal y rutas de archivo.

### Adaptación recomendada

Usar **Prism.js**, `highlight.js` o una alternativa ligera para bloques de código y añadir una capa propia de ASTRA para detectar comandos/rutas.

Ejemplos:

```text
python main.py                  → COMMAND
/etc/astra/astra.env           → PATH
C:\ASTRA\mt5-bridge            → PATH
def predict():                 → CODE
```

Esto debe funcionar tanto en respuestas del Workspace como en paneles técnicos y documentación interna.

---

## ■ Pantalla de inicio con animación

La pantalla de inicio debe ser breve, opcional y útil, no una animación decorativa que retrase el acceso al Workspace.

### Adaptación recomendada

Implementar con HTML/CSS/JS nativo, evitando dependencias pesadas. Puede mostrar el estado real de componentes durante el arranque:

```text
ASTRA

Oracle Core          ✓
Database             ✓
Workspace            ✓
Forex                SHADOW
MT5 Worker           ONLINE
Prediction Lab       READY
```

Recomendaciones:

- Duración aproximada: 0.8–1.5 segundos cuando todo está sano.
- Botón/acción para omitir.
- Soporte para `prefers-reduced-motion`.
- Si un servicio tarda, mostrar estado real en vez de bloquear indefinidamente.

# FUNCIONAL

## ✅ Kernel Lab dentro del Prediction Lab

Prediction Lab debe validar primero el prompt, target y dataset. Kernel Lab **no debe ejecutarse automáticamente para todo sistema predictivo válido**: solo cuando el problema sea compatible, principalmente clasificación binaria.

### Adaptación recomendada

Integrar sobre `scikit-learn`, aprovechando el flujo ya existente de:

```text
Prompt
  ↓
Dataset
  ↓
Feasibility
  ↓
¿Clasificación binaria y Kernel Lab aplicable?
  ↓ SÍ
Kernel Lab
  ├─ Linear
  ├─ Polynomial
  ├─ RBF
  └─ Sigmoid
  ↓
Comparación y validación
```

Mostrar al menos:

- Matriz de confusión.
- Precision.
- Recall.
- F1.
- ROC-AUC cuando corresponda.
- Cross-validation adecuada al problema.
- Calibración/fiabilidad cuando sea aplicable.
- Visualizaciones de kernels cuando la dimensionalidad permita una representación razonable.

No forzar kernelización para regresión, forecasting temporal u otros problemas donde no sea metodológicamente apropiada.

---

## ✅ Seccionar los casos viables del Prediction Lab

Los proyectos que hayan superado el flujo de viabilidad deben tener una sección propia dentro del Prediction Lab.

### Adaptación recomendada

Crear un registro persistente de casos y una navegación similar a:

```text
Prediction Lab
├─ Experiments
├─ Viable Systems
├─ Rejected / Insufficient Data
└─ Archived
```

Cada caso viable debería conservar, cuando exista:

- Problem specification.
- Dataset/hash o referencia de procedencia.
- Target.
- Features seleccionadas.
- Pipeline/modelo.
- Estrategia de validación.
- Métricas.
- Fecha de creación.
- Última evaluación.
- Estado actual.

Reutilizar `FeasibilityEngine` y los componentes actuales del Prediction Lab en vez de crear un segundo sistema de viabilidad paralelo.

---

## ✅✅ Regla de ASTRA como proyecto de producción

Prediction Lab y Forex deben tratar con **datos reales** cuando se evalúe capacidad productiva o predictiva.

### Regla refinada

> Todo resultado utilizado como evidencia de rendimiento, validación productiva, E2E, Shadow, backtesting real o calificación de un modelo debe provenir de datos reales y tener procedencia identificable.

Los datos sintéticos siguen permitidos únicamente como **fixtures de ingeniería** en unit tests, edge-case tests, failure tests y pruebas similares. Nunca deben presentarse como evidencia de rendimiento real.

### Adaptación recomendada

Añadir metadatos de procedencia, por ejemplo:

```text
dataset_origin:
  REAL_MT5
  REAL_UPLOAD
  REAL_API
  SYNTHETIC_TEST_FIXTURE
```

En production/E2E/model evidence:

```text
SYNTHETIC_TEST_FIXTURE → FORBIDDEN
```

---

## ✅✅ Evolution Engine aplicado a selección (Forex, Business, Prediction Lab o General)

Evolution Engine es un sistema general de ASTRA y no debe estar limitado a Forex.

### Adaptación recomendada

Reutilizar la infraestructura ya existente de `evolution/`, `constitution/`, approval flow, audit y rollback, agregando selección de scope.

Scopes iniciales sugeridos:

```text
Evolution target
○ General
○ Chat
○ Forex
○ Prediction Lab
○ Workspace
○ Personalization
○ Business (cuando la rama esté integrada)
```

Flujo obligatorio:

```text
OBSERVE
   ↓
PROPOSE
   ↓
VALIDATE
   ↓
HUMAN APPROVAL
   ↓
SNAPSHOT
   ↓
APPLY
   ↓
VERIFY
   ↓
ROLLBACK available
```

No permitir auto-modificación irrestricta. En Forex, especialmente durante Shadow, cualquier cambio que afecte al predictor debe permanecer bloqueado hasta autorización explícita.

---

## ✅ Interruptor Modo Automatización de Forex y Modo Manual

Forex debe disponer de dos modos de operación claramente separados, pero **el cambio de modo no debe mover físicamente datasets o modelos canónicos**.

### Adaptación recomendada

Implementar la selección en la capa Provider/Data Router:

```text
ForexDataMode
├─ AUTOMATED
│   └─ RemoteMT5Provider / rolling data
│
└─ MANUAL
    └─ UserDatasetProvider / imported snapshot
```

### Modo Automatizado

- Obtiene datos desde el proveedor remoto/canónico.
- Mantiene rolling datasets.
- Usa el pipeline Forex normal.
- Puede alimentar Shadow cuando corresponda.

### Modo Manual

- Permite importar un dataset elegido por el usuario.
- Ejecuta el pipeline de manera explícita y controlada.
- No modifica el dataset rolling canónico.

Si el usuario desea trabajar con los datos actuales en forma de CSV, usar una acción explícita:

```text
Export current snapshot
        ↓
CSVs/
EURUSD_H1_<timestamp>.csv
EURUSD_H4_<timestamp>.csv
EURUSD_D1_<timestamp>.csv
...
```

Esto debe ser una **copia/exportación**, no una migración destructiva de los originales ni de los modelos/cache.

---

## ✅✅ Límites y asignación de RAM + modalidad de rendimiento

ASTRA debe permitir controlar el consumo de recursos, pero la interfaz no debe prometer una reserva o límite que el runtime no pueda hacer cumplir.

### Adaptación recomendada

Compartir el mismo **Resource Manager** definido para procesos simultáneos y añadir perfiles de rendimiento:

```text
Performance Mode
├─ ECO
├─ BALANCED
├─ PERFORMANCE
└─ CUSTOM
```

Ejemplo CUSTOM:

```text
Soft RAM target: 6 GB
Hard RAM limit: 8 GB
Max concurrent heavy tasks: 2
CPU workers: 4
```

Comportamiento esperado:

```text
psutil / métricas del sistema
          ↓
Resource Manager
          ↓
Admission Controller
          ↓
Queue / Execute / Reject
```

Opciones conceptuales:

- **Sin límites:** ASTRA usa recursos dinámicamente respetando siempre un margen de seguridad del SO.
- **Límite asignado:** el usuario configura un objetivo y/o límite máximo realista.
- **Rendimiento básico/ECO:** reduce concurrencia y tareas pesadas.
- **Balanced:** comportamiento recomendado por defecto.
- **Performance:** mayor paralelismo dentro de límites seguros.
- **Custom:** parámetros manuales avanzados.

A futuro, si se requiere enforcement fuerte:

- Linux: `cgroups` / límites `systemd`.
- Windows: Job Objects u otros límites de proceso apropiados.

No tratar “RAM mínima” como una reserva física obligatoria si el sistema no la necesita.

# ORDEN RECOMENDADO DE IMPLEMENTACIÓN

Mientras Shadow Forex siga acumulando evidencia, priorizar cambios de bajo riesgo y desacoplados del predictor:

```text
1. Resaltado de código/comandos/rutas
2. Personalización + Dark/Light
3. Pantalla de inicio
4. Casos viables de Prediction Lab
5. Vista gráfica Forex
6. Resource Manager / procesos simultáneos
7. Modos RAM/rendimiento
8. Forex Auto/Manual
9. Kernel Lab
10. Evolution Engine por scope
```

`Manejo de procesos múltiples` y `RAM + modalidad de rendimiento` deben compartir un único Resource Manager central y no convertirse en dos subsistemas incompatibles.

# REGLA DE ESTABILIDAD DURANTE SHADOW

Mientras `ASTRA FOREX SHADOW` esté en calificación:

- Permitido: visualización, observabilidad, UX, documentación, resource management y mejoras fail-safe que no cambien la predicción.
- Bloqueado salvo autorización explícita: nuevos pares, modelos, targets, Optuna, retraining, cambios de thresholds o modificaciones de la lógica BUY/SELL/HOLD.

La prioridad del experimento actual es conservar comparabilidad y obtener evidencia out-of-sample real.