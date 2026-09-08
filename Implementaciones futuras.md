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
○ Business
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

# BUSINESS

## ✅ Rama Business — Sistema de asistencia IA para PyMEs chilenas (PROTOTIPO)

Integrar dentro de la rama `Business` una sección `PyMEs` destinada inicialmente a representar de forma estructurada la operación de una pequeña o mediana empresa chilena. Este prototipo será la base de un futuro **ASTRA PyME Export Advisor**, capaz de analizar producción, costos, ventas, capacidad disponible y mercados de exportación.

La primera etapa **no consiste en entrenar una IA nueva**. Primero ASTRA debe disponer de datos internos consistentes y auditables sobre la empresa para que posteriormente las capas de analytics, predicción y asesoría puedan trabajar sobre información real.

### Arquitectura propuesta

```text
ASTRA
└─ Business
   └─ PyMEs
      ├─ Company Setup
      ├─ Products
      ├─ Materials / Resources
      ├─ Production
      ├─ Sales
      ├─ Costs
      ├─ Promotions
      ├─ Export Markets
      ├─ Analytics
      └─ AI Advisor (fase posterior)
```

### Configuración inicial de la PyME

Registrar como mínimo:

- Nombre de empresa.
- País base (Chile en el prototipo inicial).
- Moneda base (`CLP`).
- Industria/rubro.
- Región cuando corresponda.
- Tipo de producción.

Menú inicial sugerido:

```text
ASTRA BUSINESS — PyME Setup

[1] Buscar producto
[2] Modificar producto
[3] Lista completa de productos
[4] Registrar producto
[5] Confirmar catálogo/productos
[6] Seleccionar mercado objetivo
[7] Configurar producción
[8] Salir
```

La interfaz inicial puede implementarse primero en Python/CLI y posteriormente exponerse en Workspace sin cambiar el modelo de datos.

### Productos

Cada producto debe tener una representación estructurada similar a:

```text
Product
├─ id
├─ name
├─ abbreviation
├─ unit_price
├─ currency
├─ active
├─ created_at
└─ updated_at
```

Tipos recomendados en Python:

```text
name          → str
abbreviation  → str
quantity      → int / Decimal según caso
price         → Decimal
unit          → str normalizado
timestamp     → datetime
```

Usar `Decimal` para dinero; evitar `float` en precios, costos y totales.

### Abreviaciones

La abreviación se genera automáticamente a partir del nombre:

```text
Trufa               → Tr
Bombón               → Bo
Bombón Chocolate     → BoCh
Bombón Coco          → BoCo
```

Si una abreviación ya existe, ASTRA debe detectar la colisión y generar una alternativa o pedir confirmación; nunca sobrescribir silenciosamente otro producto.

La abreviación es una referencia útil, pero el `product_id` será la identidad canónica.

### Materiales, recursos y gasto productivo

Cada producto puede requerir X ingredientes/recursos de forma unitaria.

ASTRA debe aceptar entradas flexibles:

```text
50gr
50 gr
50 GR
0.5 kg
2 litros
```

pero normalizarlas internamente:

```text
50 GR    → quantity=50, unit=g
0.5 kg   → quantity=500, unit=g
2 litros → quantity=2000, unit=ml
```

Modelo recomendado:

```text
Material
├─ id
├─ name
├─ canonical_unit
└─ unit_cost

ProductMaterial
├─ product_id
├─ material_id
├─ quantity
└─ unit
```

Esto debe permitir calcular posteriormente:

```text
Costo unitario estimado
= Σ(costo material × cantidad requerida)
```

### Precios y promociones

Cada producto tendrá precio base y podrá asociar descuentos/promociones.

Tipos iniciales:

```text
Promotion
├─ percentage
├─ fixed_amount
├─ 2x1
├─ NxM
└─ custom
```

Con:

- fecha/hora de inicio;
- fecha/hora de término;
- productos aplicables;
- estado activo/inactivo.

Las promociones por temporada deben conservar explícitamente su rango temporal.

### Persistencia: SQLite canónico, CSV como interoperabilidad

Para el prototipo, **SQLite será la fuente canónica de datos**.

No usar CSV como base de datos principal porque las relaciones entre productos, materiales, ventas, promociones y producción requieren integridad y consultas estructuradas.

Los CSV se mantienen como:

- exportación;
- importación controlada;
- reportes;
- respaldo interoperable;
- análisis externo.

Arquitectura:

```text
SQLite / Business DB
       ↓
Business Services
       ↓
CLI / Workspace / Analytics
       ↓
CSV / TXT export when requested
```

### Producción

No mantener cuatro bases separadas para diario/semanal/mensual/anual. Guardar eventos productivos con timestamps y calcular las agregaciones después.

Modelo sugerido:

```text
ProductionRecord
├─ id
├─ timestamp
├─ product_id
├─ produced_quantity
├─ production_cost
├─ calculated_priority
├─ producer_priority
└─ notes
```

ASTRA puede presentar/filtrar:

- Diario.
- Semanal.
- Mensual.
- Anual.

CSV de exportación sugerido:

```csv
date,product,quantity,production_cost,calculated_priority,producer_priority
2026-09-08,Trufa,120,38400,2,1
2026-09-08,Bombon,75,27000,1,2
```

No se necesitan filas `NULL` para representar días sin registro. La ausencia de evento significa que no existe un registro para ese período; si se necesita diferenciar `0 producido` de `dato desconocido`, guardarlo explícitamente.

### Ventas / ganancias

No guardar internamente una venta como un string compuesto del tipo:

```text
Bomb.C(3),Truf.C(5)
```

Ese formato puede existir como representación de salida, pero el almacenamiento debe ser relacional:

```text
Sale
├─ id
├─ datetime
├─ status
├─ total
└─ currency

SaleItem
├─ sale_id
├─ product_id
├─ quantity
├─ unit_price
├─ discount
└─ subtotal
```

Estados iniciales:

```text
PENDING_PAYMENT
PAID
CANCELLED (si posteriormente se requiere)
```

Esto permitirá calcular posteriormente:

- revenue diario/semanal/mensual;
- producto más vendido;
- margen;
- ticket promedio;
- estacionalidad;
- demanda;
- capacidad ociosa.

### Diccionario TXT de referencia

Mantener un archivo exportable de referencia:

```text
Trufa:Tr
Bombón:Bo
Bombón Chocolate:BoCh
```

pero generarlo desde SQLite. El TXT no es la fuente canónica.

Ejemplo de archivo:

`product_dictionary.txt`

### Búsqueda y eficiencia

No es necesario implementar una tabla hash manual desde cero. Python ya ofrece hash tables mediante `dict`.

Se pueden mantener índices temporales en memoria:

```text
products_by_id
products_by_name
products_by_abbreviation
```

SQLite debe incluir índices adecuados para las consultas persistentes más frecuentes.

### UTF-8, tildes y Ñ

Todo el módulo Business debe usar UTF-8.

Los nombres reales deben conservar acentos y `ñ`:

```text
Piñón Orgánico
```

Para búsqueda se puede crear una forma normalizada adicional:

```text
Piñón Orgánico → pinon organico
```

De este modo búsquedas como:

```text
pinon
PIÑÓN
Piñón
```

pueden resolver el mismo producto sin alterar el nombre mostrado al usuario.

### Mercados objetivo

Crear una entidad/configuración `SupportedExportMarkets` en vez de incrustar la lista directamente en la lógica del programa.

El prototipo comienza con mercados sudamericanos y debe permitir ampliar la lista posteriormente sin modificar el esquema central.

La selección de país no implica aún recomendar exportación; solo define uno o más mercados a evaluar.

Modelo conceptual:

```text
ExportMarket
├─ country_code
├─ country_name
├─ enabled
├─ currency
└─ metadata/provenance
```

### Analytics Business

Una vez que exista información interna suficiente, ASTRA Business podrá calcular de manera determinística antes de involucrar un modelo IA:

- costo unitario;
- margen bruto;
- ventas por período;
- capacidad productiva;
- capacidad ociosa;
- producción vs demanda;
- estacionalidad;
- rendimiento por producto;
- impacto de promociones.

### Fase futura: ASTRA PyME Export Advisor

La asesoría de exportación se construirá **encima del Operational Core**, no mezclada con él.

Flujo objetivo:

```text
DATOS INTERNOS PyME
        │
        ├─ productos
        ├─ ventas
        ├─ costos
        ├─ producción
        ├─ promociones
        └─ capacidad
        │
        ▼
Business Analytics
        │
        ▼
Export Feasibility Engine
        │
        ├─ mercado objetivo
        ├─ tipo de cambio
        ├─ logística
        ├─ requisitos/regulación
        ├─ demanda
        └─ riesgo
        │
        ▼
Ranking / Viabilidad
        │
        ▼
AI Advisor
```

Ejemplo de salida futura:

```text
ASTRA BUSINESS

Producto: Trufa Chocolate
Mercado evaluado: Perú
Capacidad exportable estimada: 420 unidades/mes
Margen doméstico: 54.7 %
Margen exportación estimado: 41.2 %
Principal riesgo: costo logístico
Recomendación: VIABLE PARA PRUEBA PILOTO
```

Las cifras mostradas por el sistema deben proceder de datos reales o de cálculos trazables; nunca inventarse para presentarlas como análisis productivo real.

### Integración futura con fuentes externas

En fases posteriores el `Export Feasibility Engine` podrá consumir fuentes reales para:

- tipos de cambio;
- costos logísticos;
- requisitos de entrada;
- aranceles;
- datos de mercado/demanda;
- indicadores económicos;
- riesgo cambiario.

Cada dato externo debe guardar fuente, fecha y procedencia.

### Fases de implementación

```text
PHASE 1
Company + Product Registry
             ↓
PHASE 2
Materials + Production + Sales
             ↓
PHASE 3
Costs + Promotions + Business Analytics
             ↓
PHASE 4
Country / Export Market selection
             ↓
PHASE 5
Export Feasibility Engine
             ↓
PHASE 6
AI Advisor
             ↓
PHASE 7
Prediction / recommendations avanzadas
```

### Alcance del prototipo inicial

El primer prototipo se considera terminado cuando pueda:

- registrar una PyME;
- registrar/modificar/buscar productos;
- generar abreviaciones sin colisiones silenciosas;
- registrar materiales y costos unitarios;
- registrar producción;
- registrar ventas y estados de pago;
- registrar promociones;
- seleccionar mercado objetivo;
- persistir todo en SQLite;
- exportar producción/ventas a CSV;
- exportar diccionario de abreviaciones a TXT;
- realizar métricas Business básicas;
- funcionar correctamente con UTF-8, tildes y `ñ`.

El prototipo **no requiere todavía un modelo ML ni una recomendación automática de exportación**.

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
11. Business / PyMEs Operational Core (prototipo)
```

`Manejo de procesos múltiples` y `RAM + modalidad de rendimiento` deben compartir un único Resource Manager central y no convertirse en dos subsistemas incompatibles.

La rama Business/PyMEs puede desarrollarse de forma paralela al período Shadow siempre que no modifique ni consuma recursos críticos del pipeline Forex desplegado. Su primera implementación debe centrarse en el **Operational Core**, no en entrenar un nuevo modelo predictivo.

# REGLA DE ESTABILIDAD DURANTE SHADOW

Mientras `ASTRA FOREX SHADOW` esté en calificación:

- Permitido: visualización, observabilidad, UX, documentación, resource management y mejoras fail-safe que no cambien la predicción.
- Bloqueado salvo autorización explícita: nuevos pares, modelos, targets, Optuna, retraining, cambios de thresholds o modificaciones de la lógica BUY/SELL/HOLD.

La prioridad del experimento actual es conservar comparabilidad y obtener evidencia out-of-sample real.