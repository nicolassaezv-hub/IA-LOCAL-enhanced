# ASTRA — Manual de Usuario
**Sistema AI Modular · Consultor PYME · Forex Intelligence · Workspace Web · v7.0**

---

## PARTE 0 — ASTRA WORKSPACE (interfaz visual)

El Workspace es la interfaz visual completa de ASTRA. Disponible en dos modos:

### En Replit
Se abre automáticamente en el panel Preview. El workflow **"artifacts/api-server: ASTRA Workspace"** lo lanza al iniciar el proyecto.

### En Windows (local)
```cmd
cd artifacts\astra
pip install fastapi uvicorn python-multipart
python workspace\server.py
:: → Abre http://localhost:8000 en el navegador
```

### Paneles del Workspace

| Panel | Acceso | Qué hace |
|---|---|---|
| **Chat** | Barra lateral → Chat | Conversación con ASTRA (Llama-3.3-70B), historial de sesión, subida de archivos |
| **Forex Lab** | Barra lateral → Forex Lab | Selector de par/CSV, gráfico de velas OHLC interactivo, entrenamiento con barra de progreso visual por etapa |
| **Prediction Lab** | Barra lateral → Prediction Lab | Análisis ML de cualquier dataset: describe el problema, ASTRA genera pipeline, valida y guarda el reporte |
| **Business Lab** | Barra lateral → Business Lab | KPIs + health score + forecast + scorecard PYME + plan de acción sobre CSV de negocio |
| **Cognitive Core** | Barra lateral → Cognitive Core | Memoria explorable: conversaciones, proyectos, modelos, timeline, knowledge graph, búsqueda natural |
| **Evolution Engine** | Barra lateral → Evolution Engine | Ciclo evolutivo: propuestas, aprobación/rechazo manual, reglas constitucionales, audit, rollback |
| **Activity Center** | Barra lateral → Activity Center | Feed unificado en vivo: alertas, señales, comandos, eventos |
| **Dashboard Activo** | Barra lateral → Dashboard Activo | Market Sentinel (vigilancia de pares), Scheduler (estado de tareas), señales activas, datasets |
| **Configuración** | Barra lateral → Configuración | Estado del sistema, API key, versión |

### Funciones globales del Workspace

**Barra superior**: modelo AI activo · proyecto activo · tools cargados · reloj · notificaciones push

**Live Thinking**: franja visual que aparece durante tareas largas (entrenamiento Forex, Prediction Lab). Muestra en qué etapa está ASTRA en tiempo real.

**Barra de telemetría inferior**: CPU · RAM · Active Engine (watchers/jobs) · Cognitive Core (memorias totales, turnos de sesión) · Evolution Engine (eventos/propuestas pendientes) · peticiones API · tiempo promedio de respuesta.

**Subida de archivos**: el botón 📎 en el Chat permite subir CSV, PDF, Word, Excel. Se guardan en `workspace/uploads/` y quedan disponibles para todos los paneles.

### Notificaciones push
El sistema envía notificaciones automáticas para: entrenamiento completado · predicción lista · problema detectado · propuesta de evolución. Se acumulan en el botón 🔔 de la barra superior.

---

## PARTE 1 — INSTALACIÓN Y ARRANQUE

### Requisitos previos
- Python 3.10 o superior
- pip actualizado: `python -m pip install --upgrade pip`
- Una API key de **Groq** (gratis): https://console.groq.com → API Keys → Create API Key

---

### Instalación en Windows (recomendado: entorno virtual)

```cmd
:: 1. Clonar / descargar el proyecto y entrar a la carpeta
cd ruta\al\proyecto

:: 2. Crear entorno virtual
python -m venv venv

:: 3. Activar el entorno virtual
venv\Scripts\activate.bat          (CMD)
.\venv\Scripts\Activate.ps1        (PowerShell)

:: 4. Instalar dependencias
pip install -r artifacts\astra\requirements.txt
pip install fastapi uvicorn python-multipart

:: 5. Configurar la API key de Groq (una sola vez)
setx GROQ_API_KEY "gsk_tu_key_aqui"
:: Cierra y vuelve a abrir el terminal para que tome efecto

:: 6a. Lanzar ASTRA CLI
cd artifacts\astra
python main.py

:: 6b. Lanzar ASTRA Workspace (interfaz web)
cd artifacts\astra
python workspace\server.py
:: → Abre http://localhost:8000
```

> **Alternativa a setx**: crea un archivo `.env` dentro de `artifacts\astra\` con:
> ```
> GROQ_API_KEY=gsk_tu_key_aqui
> ```

---

### Instalación en Linux / Replit

```bash
# 1. Instalar dependencias
pip install -r artifacts/astra/requirements.txt
pip install fastapi uvicorn python-multipart

# 2. La API key ya está en Replit Secrets como GROQ_API_KEY

# 3a. Lanzar CLI
cd artifacts/astra && python main.py

# 3b. Lanzar Workspace
cd artifacts/astra && python workspace/server.py
```

En Replit los workflows **"ASTRA AI"** y **"artifacts/api-server: ASTRA Workspace"** hacen todo esto automáticamente.

---

### Diagnóstico antes de arrancar

**Opción A — Diagnóstico rápido (check_startup.py)**
```bash
cd artifacts/astra
python check_startup.py
```
Resultado esperado: `No critical issues found`. Los WARN (torch, redis, librosa…) son opcionales.

**Opción B — ASTRA Doctor (completo, recomendado)**
```bash
cd artifacts/astra
python astra_doctor.py
```
Verifica 10 categorías completas y guarda el resultado en `astra_doctor_report.json`.
También disponible desde el CLI con: `astra doctor`

---

### Instalar paquetes opcionales

```bash
pip install fastapi uvicorn python-multipart  # Workspace web (requerido para server.py)
pip install yfinance         # Yahoo Finance — datos Forex en tiempo real
pip install torch            # PyTorch — deep learning
pip install tensorflow       # TensorFlow
pip install redis            # cliente Redis
pip install scikit-image     # procesamiento de imagen
pip install librosa          # análisis de audio
pip install python-dotenv    # carga .env automáticamente
```

---

## PARTE 2 — COMANDOS DISPONIBLES (CLI)

Una vez dentro del asistente (prompt `Tú:`), escribe en lenguaje natural.
El archivo CSV/Excel puede estar en cualquier ruta relativa a `artifacts/astra/`.

> La mayor parte de estos comandos también están disponibles desde el **Workspace web** de forma visual.

---

### Diagnóstico y Sistema

| Comando | Qué hace |
|---|---|
| `astra doctor` | Diagnóstico completo: dependencias, APIs, modelos, DBs, scheduler, datasets (10 categorías) |
| `self-test` | Diagnóstico semáforo rápido del sistema |
| `analiza astra` | Genera reporte completo del sistema (REPORT DD-MM.md) |
| `self analysis` | Alias en inglés de analiza astra |
| `ayuda` | Lista todos los comandos disponibles |
| `estado pc` | CPU, RAM, disco y uptime |

---

### API REST Interna (legacy CLI)

> En el Workspace web el servidor FastAPI corre automáticamente y no necesitas `api start`.

| Comando | Qué hace |
|---|---|
| `api start` | Inicia el servidor REST legado en `http://localhost:8766` |
| `api stop` | Detiene el servidor REST legado |
| `api status` | Muestra si la API legada está activa y en qué puerto |

---

### Development Log

| Comando | Qué hace |
|---|---|
| `dev log` | Ver las últimas 20 entradas del historial |
| `dev log add [tipo] título \| detalle` | Añadir entrada al log |
| `dev log bugfix título` | Registrar una corrección |
| `dev log feature título` | Registrar una nueva función |
| `dev log release <versión>` | Ver Release Notes de una versión |
| `dev log versions` | Listar versiones disponibles |

**Tipos válidos**: `feature`, `bugfix`, `optimization`, `refactor`, `docs`, `release`

---

### Branch 1 — Núcleo: Documentos, Seguridad y Sistema

#### Lectura de archivos
| Comando | Qué hace |
|---|---|
| `lee pdf informe.pdf` | Lee y extrae texto de un PDF |
| `lee word documento.docx` | Lee un documento Word |
| `lee excel tabla.xlsx` | Lee un Excel |
| `lee csv datos.csv` | Lee un CSV |

#### Web y traducción
| Comando | Qué hace |
|---|---|
| `traduce Hola mundo al inglés` | Traduce texto al idioma indicado |
| `extrae web https://ejemplo.com` | Scraping y extracción de texto de una URL |

#### Seguridad
| Comando | Qué hace |
|---|---|
| `hash password mipassword` | Genera hash bcrypt seguro |
| `cifrar archivo secreto.txt` | Cifra un archivo con clave AES |
| `crear jwt` | Genera un token JWT firmado |

---

### Branch 2 — Análisis Forex (Básico)

El sistema reconoce 41 pares: EUR/USD, GBP/USD, USD/JPY, BTC/USD, commodities, etc.

| Comando | Qué hace |
|---|---|
| `analiza forex eurusd datos.csv` | Análisis técnico completo: RSI, MACD, EMA, CCI, MFI, ROC, volatilidad, señal ML |
| `forex eurusd` | Reconoce el par y muestra estado del mercado |
| `history eurusd` | Historial de análisis guardados para ese par |
| `compare history eurusd` | Compara los últimos reportes guardados |
| `list markets` | Lista todos los mercados analizados hasta ahora |

#### Indicadores técnicos incluidos

| Grupo | Indicadores |
|---|---|
| Momentum | RSI-14, Williams %R, Estocástico (14,3) |
| Tendencia | MACD (12/26/9), EMA 20/50/150, ADX-14, cruce EMA |
| Volatilidad | ATR-14, Bollinger Bands (20), ATR relativo |
| Ciclo / extremos | CCI-20 |
| Volumen | OBV, MFI-14 |
| Momentum % | ROC-10 |
| Patrones vela | Doji, Hammer, Shooting Star, Engulfing alcista/bajista |

---

### Branch 3 — Business Intelligence (BI Engine)

| Comando | Qué hace |
|---|---|
| `analiza negocio ventas.csv` | KPIs financieros + health score + alertas automáticas |
| `kpis reporte.xlsx` | Análisis de KPIs sobre un Excel |
| `analisis completo negocio.csv` | Diagnóstico completo: KPIs + señal ML + recomendaciones |
| `consulta empresa datos.xlsx` | Modo consultor PYME básico |
| `entrena negocio historico.csv` | Entrena modelo ML sobre datos históricos de negocio |

---

### Branch 4 — Consultor PYME Avanzado

Los cuatro módulos del consultor estratégico. Todos generan narración automática de **Llama-3.3-70B** al finalizar.
También disponibles en el panel **Business Lab** del Workspace.

#### `diagnóstico pyme`
```
diagnóstico pyme ventas.csv
```
Scorecard Multidimensional:
- **Salud Financiera** (40%): márgenes bruto/neto, ratio gastos, saldo mínimo
- **Salud de Crecimiento** (35%): CAGR, tendencia MoM, YoY
- **Nivel de Riesgo** (25%): volatilidad, concentración, estabilidad

#### `forecast negocio`
```
forecast negocio ventas.csv
forecast negocio ventas.csv 12
```
Proyección con tres bandas: Optimista (+1σ), Esperado (lineal), Conservador (−1σ).

#### `plan de accion`
```
plan de accion ventas.csv
```
Llama-3.3-70B genera 5 recomendaciones estratégicas priorizadas (acción + impacto + plazo).

#### `simular escenario`
```
que pasa si reduzco costos 15% ventas.csv
si aumento ventas ventas.csv 20%
que ocurre si mejoro margen 10% datos.csv
```
Simulación What-If: tabla Antes/Después con delta de KPIs y scorecard completo.

---

### Roadmap V — Forex Intelligence Avanzada

#### Pipeline ML completo

| Comando | Qué hace |
|---|---|
| `full forex eurusd datos.csv` | Pipeline completo: entrena modelo + Quality Gate + backtest + predicción |
| `predice eurusd datos.csv` | Predicción con Decision Engine (señal + SL/TP + posición) |
| `quality eurusd datos.csv` | Evaluación con Quality Gate (métricas de validación) |
| `generar csvs forex [tf] [n]` | Genera en lote todos los CSVs Forex en `CSVs/<TF>/<PAIR>.csv` (Yahoo real → sintético fallback). Ej: `generar csvs forex H1,H4 800`. Alias: `generate forex csvs`. |

#### Análisis técnico avanzado

| Comando | Qué hace |
|---|---|
| `regime eurusd datos.csv` | Detecta régimen de mercado (trending/ranging/breakout/high_vol) |
| `mtf eurusd datos.csv` | Coherencia multi-timeframe D1/H4/H1 |
| `reliability eurusd datos.csv` | Reliability Score 0–100 (7 componentes) |
| `decision eurusd datos.csv` | Decision Engine: BUY/SELL/HOLD/NO OPERAR |
| `risk BUY 1.0850 0.0020` | Risk Engine: SL/TP + position sizing Kelly |
| `backtest eurusd datos.csv` | Backtesting con Walk-Forward (20+ métricas) |
| `feature_importance eurusd datos.csv` | Importancia de features (SHAP) |

#### Seguimiento de predicciones

| Comando | Qué hace |
|---|---|
| `outcome_stats eurusd` | Estadísticas de predicciones reales (acierto %) |
| `retrain_check eurusd` | Check de reentrenamiento adaptativo |
| `portfolio_ranking BUY 0.7` | Ranking multi-activo por señal y confianza mínima |

---

### Roadmap VI — Autonomización & Data Intelligence

#### Gestión de datos

| Comando | Qué hace |
|---|---|
| `descargar datos EURUSD H1` | Descarga datos de Yahoo Finance/Binance (500 velas) |
| `descargar datos EURUSD H1 1000` | Descarga N velas |
| `migrar csv datos.csv EURUSD H1` | Migra un CSV existente al formato rolling |
| `escanear csvs` | Escanea el directorio CSVs/ y registra todos los pares |
| `csvs activos` | Lista el índice de CSVs registrados |

#### Scheduler Autónomo

| Comando | Qué hace |
|---|---|
| `scheduler start` | Inicia el scheduler en background (H1/H4/D1) |
| `scheduler stop` | Detiene el scheduler |
| `scheduler info` | Estado, tareas registradas y próxima ejecución |
| `auto update` | Actualiza todos los CSVs activos ahora mismo |

#### Ranking de oportunidades

| Comando | Qué hace |
|---|---|
| `opportunity ranking` | Top 10 BUY/SELL por Opportunity Score compuesto |
| `opportunity ranking 20` | Top 20 BUY/SELL |

Fórmula: `Reliability × 0.35 + WinRate × 0.30 + Régimen × 0.20 + MTF × 0.15`

---

## PARTE 3 — ESTRUCTURA DE ARCHIVOS DE DATOS

### CSV Forex (Branches 2, V, VI)

| Columna | Obligatoria | Descripción |
|---|---|---|
| `timestamp` | ✅ | Fecha y hora (cualquier formato ISO 8601) |
| `open` | ✅ | Precio de apertura |
| `high` | ✅ | Precio máximo |
| `low` | ✅ | Precio mínimo |
| `close` | ✅ | Precio de cierre |
| `volume` | ✅ | Volumen (necesario para MFI y OBV) |
| `rsi_14` | ☑ Opcional | Se recalcula automáticamente si NaN |
| `macd` / `macd_signal` | ☑ Opcional | Se recalcula si NaN |
| `atr_14` | ☑ Opcional | Se recalcula si NaN o = 0 |
| `ema_20` / `ema_50` / `ema_150` | ☑ Opcional | Se recalcula si NaN |

> Los pares se detectan automáticamente desde el nombre del archivo (ej: `aud_usd_dataset.csv` → AUDUSD).

### CSV Negocio / PYME (Branches 3 y 4)

| Columna | Alias aceptados | Tipo |
|---|---|---|
| Fecha | `date`, `fecha`, `periodo`, `mes` | fecha o texto |
| Ingresos | `revenue`, `ingresos`, `ventas`, `sales` | numérico |
| Gastos | `expenses`, `gastos`, `costos`, `costs` | numérico |
| Ganancia bruta | `gross_profit`, `ganancia_bruta` | numérico (opcional) |
| Ingreso neto | `net_income`, `ingreso_neto`, `beneficio` | numérico (opcional) |
| Saldo | `balance`, `saldo`, `cash` | numérico (opcional) |

Mínimo viable: `date` + `revenue` + `expenses`.

---

## PARTE 4 — MOTOR AI Y MEMORIA

### Motor de lenguaje
ASTRA usa **Llama-3.3-70B** (vía Groq). Si `GROQ_API_KEY` no está configurada, intenta con `OPENAI_API_KEY` (GPT-3.5-turbo) como fallback.

### Memoria
- **Sesión activa**: ASTRA recuerda los últimos 20 turnos en RAM.
- **Persistencia**: Los turnos se guardan en `memoria.db` (SQLite). Al reiniciar, carga los últimos 6 intercambios.

### Bases de datos internas

| Archivo | Contenido |
|---|---|
| `memoria.db` | Memoria principal: conversaciones, predicciones, outcomes, señales |
| `astra_hparam_cache.db` | Caché de hiperparámetros por par/horizonte (TTL 7 días) |
| `astra_model_quality.db` | Historial de precisión verificada por modelo |
| `dev_log.db` | Development Log: features, bugfixes, releases |
| `astra_csv_index.json` | Índice de datasets activos (par, timeframe, ruta, filas) |
| `project_memory.db` | Proyectos y tareas (Cognitive Core) |

---

## PARTE 5 — ORACLE CLOUD (Despliegue 24/7)

ASTRA está preparado para correr como servicio permanente en **Oracle Cloud Always Free** (VM ARM, 4 OCPUs, 24 GB RAM).

Consulta la guía completa en: `docs/ORACLE_CLOUD.md`

### Arquitectura resumida

```
Oracle Cloud VM
├── astra-scheduler.service  (systemd)   → scheduler_service.py
│     ├── AutonomousScheduler (H1/H4/D1)
│     └── AutoUpdater (descarga datos automáticamente)
│
├── astra-workspace.service  (systemd)   → workspace/server.py (FastAPI, puerto 8000)
│     └── Sirve la SPA completa + todos los endpoints /api/*
│
└── nginx                                → proxy HTTPS
      └── /* → localhost:8000
```

### Punto de entrada del Workspace en producción
```bash
cd /path/to/artifacts/astra
python workspace/server.py
```

---

## PARTE 6 — ROADMAP

| Versión | Nombre | Estado |
|---|---|---|
| v1–v4 | Core, Forex básico, BI Engine, PYME Consultant | ✅ Completo |
| v5.x | Roadmap V — Quality Gate, Decision Engine, Risk Engine, Outcome Tracker | ✅ Completo |
| v6.0 | Roadmap VI — Autonomización, Data Intelligence, Scheduler 24/7 | ✅ Completo |
| v6.1 | Integración & Validación — Doctor, API REST, Dev Log, Oracle Cloud | ✅ Completo |
| **v7.0** | **Roadmap IV — Workspace SPA completa** (Chat, Forex Lab, Prediction Lab, Business Lab, Cognitive Core, Evolution Engine, Activity Center, Dashboard Activo) | **✅ Completo** |
| v8.x | Industry Packs (Retail, Restaurante, E-Commerce, Manufactura) | Próximo |
| v9.x | Multi-Agent ASTRA | Futuro |
| v10.x | Executive Copilot | Futuro |

> A partir de v6.1, los cambios se registran directamente con `dev log add` en lugar de crear nuevos documentos de Roadmap.

---

## PARTE 7 — SOLUCIÓN DE PROBLEMAS

| Síntoma | Causa probable | Solución |
|---|---|---|
| `GROQ_API_KEY not found` | Key no configurada | Sigue los pasos de la Parte 1 |
| `ModuleNotFoundError: openai` | Falta el paquete | `pip install openai` |
| `ModuleNotFoundError: fastapi` | Falta el paquete | `pip install fastapi uvicorn python-multipart` |
| `lightgbm` crash en Linux | Falta libgomp | El workflow lo configura automáticamente vía `LD_LIBRARY_PATH` |
| Torch / TensorFlow WARN | Son opcionales | Ignóralos o instala con `pip install torch` |
| `redis` WARN | Es opcional | Ignóralo o instala con `pip install redis` |
| `yfinance` no disponible | No instalado | `pip install yfinance` (necesario para `descargar datos`) |
| Sin audio/TTS en Linux | pyttsx3 silenciado | Solo disponible en Windows con dispositivo de audio |
| CSV no reconocido | Columnas con nombres distintos | Renombra a `date`, `revenue`, `expenses` (ver Parte 3) |
| Workspace no carga en Replit | Puerto 8080 ocupado | `lsof -i :8080 -t \| xargs kill -9`, luego reinicia el workflow |
| Chat del Workspace sin respuesta | API key no configurada | Verifica `GROQ_API_KEY` en Replit Secrets |
| Binance 451 | Restricción geográfica | Usar Yahoo Finance como fuente alternativa |
| `astra doctor` muestra FAIL | Dependencia crítica faltante | Sigue la recomendación que muestra el doctor |
| Forex Lab — CSV no aparece | CSV fuera de `CSVs/H1/` o `workspace/uploads/` | Mueve el CSV a `CSVs/H1/EURUSD.csv` o súbelo desde el Workspace |

---

*ASTRA v7.0 — Workspace Edition — Julio 2026*
