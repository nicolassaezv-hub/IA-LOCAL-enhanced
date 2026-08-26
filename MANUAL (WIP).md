# ASTRA — Manual de Usuario
**Sistema AI Modular · Forex Intelligence · Despliegue Provider-Agnostic · v7.0.2-prod**

---

## GUÍA RÁPIDA — TUS PRIMEROS 10 MINUTOS

```bash
# 1. Dependencias (Python 3.11+)
pip install -r requirements.txt

# 2. API key de Groq para el chat AI
export GROQ_API_KEY=gsk_tu_key        # Windows: set GROQ_API_KEY=gsk_tu_key

# 3. Verificar que todo está en su sitio
python astra_doctor.py                # o dentro del CLI: astra doctor

# 4. Datos: genera CSVs reales (Yahoo) para probar
python main.py
> generar csvs forex H1 800

# 5. Primer ciclo completo sobre un par
> full forex CSVs/H1/EURUSD.csv       # entrena + predice + backtest
> predict forex CSVs/H1/EURUSD.csv    # señal con Decision Engine (Roadmap V)

# 6. Interfaz visual (opcional)
python workspace/server.py            # http://localhost:8000
```

Qué esperar de `predict forex`: además de la señal cruda del modelo verás el
bloque **Roadmap V** con régimen de mercado, coherencia multi-timeframe,
reliability score, circuit breaker y la **decisión final**, que puede ser
`NO_OPERAR` aunque el modelo diga BUY. Esa decisión final es la que manda para
el cálculo de SL/TP y el tamaño de posición.


## PARTE 0 — ASTRA WORKSPACE (interfaz visual)

El Workspace es la interfaz visual completa de ASTRA. Disponible en dos modos:

### En Replit
Se abre automáticamente en el panel Preview. El workflow **"artifacts/api-server: ASTRA Workspace"** lo lanza al iniciar el proyecto.

### En Windows (local)
```cmd
cd ruta\al\proyecto
pip install fastapi uvicorn python-multipart
python workspace\server.py
:: → Abre http://localhost:8000 en el navegador
```

### Paneles del Workspace

| Panel | Acceso | Qué hace |
|---|---|---|
| **Chat** | Barra lateral → Chat | Conversación con ASTRA (Llama-3.3-70B), historial de sesión, subida de archivos |
| **Forex Lab** | Barra lateral → Forex Lab | Selector de par/CSV, gráfico de velas OHLC interactivo, entrenamiento con barra de progreso visual |
| **Prediction Lab** | Barra lateral → Prediction Lab | Análisis ML de cualquier dataset |
| **Business Lab** | Barra lateral → Business Lab | KPIs + health score + forecast + scorecard PYME |
| **Cognitive Core** | Barra lateral → Cognitive Core | Memoria explorable: conversaciones, proyectos, modelos, timeline |
| **Evolution Engine** | Barra lateral → Evolution Engine | Ciclo evolutivo: propuestas, aprobación/rechazo manual, audit, rollback |
| **Activity Center** | Barra lateral → Activity Center | Feed unificado en vivo: alertas, señales, comandos, eventos |
| **Dashboard Activo** | Barra lateral → Dashboard Activo | Market Sentinel, Scheduler, señales activas, datasets |
| **Configuración** | Barra lateral → Configuración | Estado del sistema, API key, versión |

---

## PARTE 1 — INSTALACIÓN Y ARRANQUE

### Requisitos previos
- Python 3.11 o superior (3.12 recomendado)
- pip actualizado: `python -m pip install --upgrade pip`
- Una API key de **Groq** (gratis): https://console.groq.com → API Keys → Create API Key

### Variables de entorno

| Variable | Requerida | Descripción |
|---|---|---|
| `GROQ_API_KEY` | Sí (para chat AI) | API key de Groq — https://console.groq.com |
| `OPENAI_API_KEY` | No | Alternativa OpenAI |
| `MT5_ACCOUNT` / `MT5_PASSWORD` / `MT5_SERVER` | No (solo Windows+MT5) | Conexión MetaTrader 5 |
| `BINANCE_API_KEY` / `BINANCE_SECRET` | No | Datos Binance para cripto |
| `NEWS_API_KEY` | No | Noticias financieras |
| `ASTRA_LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` (por defecto: `INFO`) |
| `ASTRA_SCHEDULER_ENABLED` | No | `true` / `false` (por defecto: `true`) |

> ⚠️ **Nunca subas `.env` a git.** Está protegido en `.gitignore`.

### Instalación en Windows (entorno virtual)

```cmd
:: 1. Clonar / descargar el proyecto y entrar a la carpeta
cd ruta\al\proyecto

:: 2. Crear entorno virtual
python -m venv venv

:: 3. Activar el entorno virtual
venv\Scripts\activate.bat          (CMD)
.\venv\Scripts\Activate.ps1        (PowerShell)

:: 4. Instalar dependencias
pip install -r requirements.txt

:: 5. Configurar la API key de Groq
setx GROQ_API_KEY "gsk_tu_key_aqui"

:: 6a. Lanzar ASTRA CLI
python main.py

:: 6b. Lanzar ASTRA Workspace (interfaz web)
python workspace\server.py
```

### Instalación en Linux (cualquier VM)

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. La API key en Replit Secrets como GROQ_API_KEY

# 3a. Lanzar CLI
python main.py

# 3b. Lanzar Workspace
python workspace/server.py
```

### Diagnóstico

**Opción A — Diagnóstico rápido (check_startup.py)**
```bash
python check_startup.py
```
Resultado esperado: `No critical issues found`.

**Opción B — ASTRA Doctor (completo)**
```bash
python astra_doctor.py
```
Verifica 10 categorías completas y guarda resultado en `astra_doctor_report.json`.

---

## PARTE 2 — REFERENCIA COMPLETA DE COMANDOS (CLI)

Arranque del CLI: `python main.py`. Escribe `ayuda` en cualquier momento para ver
este mismo listado dentro del programa, y `salir` / `exit` / `quit` para terminar.
**Cualquier texto que no coincida con un comando se envía al chat libre
(Llama-3.3-70B vía Groq) con el contexto de la sesión.**

Convenciones: `<obligatorio>`, `[opcional]`, `|` separa alternativas.
Las rutas de CSV admiten varios archivos separados por comas en los comandos que lo indican.

### 2.1 Sistema y diagnóstico

| Comando | Qué hace |
|---|---|
| `ayuda` | Referencia de comandos dentro del CLI |
| `astra doctor` | Diagnóstico completo (10 categorías) + informe en `reports/` |
| `self-test` | Diagnóstico semáforo rápido (VI.2) |
| `analiza astra` | Reporte completo de autoanálisis del sistema |
| `estado pc` | CPU, RAM, disco y uptime |
| `fecha` | Fecha y hora actual del sistema |
| `json` | Demo de serialización JSON |
| `gui` | Lanza la mini GUI local |
| `imagen` | Demo de detección de bordes (scikit-image) |
| `barra progreso` | Demo de barra de progreso |
| `tabla <datos>` / `rich <texto>` | Salida formateada en tabla / Rich |
| `simular click` / `simular tecla <k>` | Automatización de escritorio |
| `monitor archivos <ruta>` | Vigila cambios en archivos |
| `monitor historial` | Historial de snapshots de rendimiento |
| `dev log` | Últimas entradas del historial de desarrollo |
| `dev log add [tipo] título \| detalle` | Añade entrada (`feature`, `bugfix`, `optimization`, `refactor`, `docs`, `release`) |
| `dev log release <versión>` | Release notes de una versión |
| `api start` / `api stop` / `api status` | API REST interna legada (`http://localhost:8766`) |

### 2.2 Forex Lab — flujo principal

| Comando (alias español) | Qué hace |
|---|---|
| `train forex <csv>` (`entrenar forex`) | Entrena el ensemble XGB + LGBM + RF |
| `tune forex <csv>` (`afinar forex`) | Búsqueda de hiperparámetros con Optuna (5-15 min) y entrena |
| `predict forex <csv>[,<csv2>...]` (`predecir forex`) | Señal BUY/SELL/HOLD; con varios CSV guarda un `.txt` por par en `reports/` |
| `multi forex <csv>` (`multihorizonte forex`) | Consenso a 3 horizontes (5/10/20 velas) |
| `backtest forex <csv>` | Backtest sobre datos retenidos |
| `full forex <csv>` (`completo forex`) | Train + Predict + Backtest en una pasada |
| `scan forex <carpeta\|csvs>` (`escanear forex`) | Escanea CSVs y rankea señales por fuerza |
| `analiza forex <csv> <símbolo>` | Informe técnico completo (RSI/MACD/EMA/ATR…) |
| `generar csvs forex [tf] [n]` | Genera CSVs en lote (Yahoo real → sintético como respaldo). Alias: `generate forex csvs`, `generar todos los csvs forex` |
| `lista mercados` | Pares y materias primas soportados |
| `mercados analizados` | Mercados analizados alguna vez |
| `historial forex <símbolo>` (`forex history`) | Historial de análisis guardados |
| `compara forex <símbolo>` | Compara los últimos 5 análisis del par |
| `mis modelos` / `info modelo <par>` | Modelos entrenados y detalle de uno |
| `schedule forex <csv> [min]` / `schedule run <par>` / `schedule stop [par]` | Análisis recurrente programado |

### 2.3 Watcher y señales (Fase 2)

| Comando | Qué hace |
|---|---|
| `watch forex <par> <csv> [seg]` | Monitoreo continuo del par en background |
| `watch check <par>` | Fuerza una evaluación inmediata |
| `watch status` | Pares en monitoreo |
| `watch stop <par>` / `watch stop all` | Detiene uno o todos los watchers |
| `señales [par]` (`signals`) | Historial de señales BUY/SELL/HOLD |
| `stats señales [par]` | Ratio y estadísticas de señales |

### 2.4 Roadmap V — motor de decisión avanzado

Todos estos módulos se ejecutan **también de forma automática** dentro de
`predict forex` / `full forex`: el pipeline construye el contexto (volatilidad,
régimen, coherencia MTF, circuit breaker, noticias, histórico real) y el
Decision Engine puede **vetar** la señal del modelo. Los comandos siguientes
permiten inspeccionar cada pieza por separado.

| Comando | Fase | Qué hace |
|---|---|---|
| `quality <csv> [par] [tf]` | V.5 | Gate de calidad del dataset |
| `regime <csv> [par] [tf]` | V.4 | Detección de régimen de mercado |
| `mtf <d1.csv> <h4.csv> <h1.csv>` | V.3 | Coherencia multi-timeframe D1→H4→H1 |
| `reliability <conf> [signal]` | V.8 | Reliability Score (7 factores, 0-100) |
| `decision <signal> <conf>` | V.1 | Motor de decisión final (BUY/SELL/HOLD/NO_OPERAR) |
| `risk <BUY\|SELL> <entry> <atr>` | V.2 | SL/TP + position sizing (Kelly) |
| `backtest <modelo> <csv> [par]` | V.9 | Backtesting con 20+ métricas y Walk-Forward |
| `feature_importance <modelo> <csv>` | V.6 | Importancia de features (SHAP) |
| `dataset_update <par> [tf]` | V.11 | Actualización incremental del CSV |
| `scheduler_status` | V.12 | Estado del scheduler inteligente |
| `retrain_check <par>` / `retrain_history` | V.13 | Reentrenamiento adaptativo |
| `sentinel_status` / `sentinel_signals [par] [n]` | V.10 | Market Sentinel y su historial |
| `outcome_stats [par]` / `outcome_history` | V.14 | Resultados reales de las predicciones |
| `notify_test <par> <signal> <r>` / `notify_log` | V.15 | Notificaciones multi-canal |
| `portfolio_ranking [signal] [min]` / `portfolio_export` | V.18 | Ranking multi-activo y exportación |
| `news <par>` / `noticias <par>` / `noticias predice <par>` | V.16 | Sentimiento de noticias financieras |

### 2.5 Roadmap VI — data intelligence y autonomía

| Comando | Qué hace |
|---|---|
| `descargar datos <par> [tf] [n]` | Descarga Forex/Cripto (Yahoo / Binance / MT5) |
| `migrar csv <ruta> [par] [tf]` | Migra un CSV al formato rolling |
| `escanear csvs` / `csvs activos` | Escanea e indexa los CSVs de `CSVs/` |
| `rolling info <par> [tf]` | Estado del RollingDataset |
| `candlestick <csv>` | Patrones de vela japonesa |
| `hparam cache` / `hparam invalidar <par>` | Caché de hiperparámetros |
| `model cache` | Estado del Model Cache Manager |
| `adaptive budget <par>` | Historial de budgets adaptativos |
| `quality history` | Precisión verificada por modelo |
| `opportunity ranking [n]` | Top N BUY/SELL por Opportunity Score |
| `scheduler start` / `scheduler stop` / `scheduler info` | Scheduler autónomo |
| `auto update` | Actualiza ahora todos los CSVs activos |

### 2.6 Gestión de riesgo

| Comando | Qué hace |
|---|---|
| `circuit status` / `circuit reset` | Circuit breaker (pérdida diaria/semanal/drawdown) |
| `position size <par> [balance]` (`sizing`) | Tamaño de posición con criterio Kelly |

### 2.7 Business Intelligence (PYME)

| Comando | Qué hace |
|---|---|
| `consulta negocio <csv>` (`consultar negocio`) | Consultoría completa: KPIs + forecast + recomendaciones |
| `analiza negocio <csv>` (`analizar negocio`) | KPIs + health score + alertas (sin ML) |
| `predice negocio <csv>` (`predecir negocio`) | Forecast ML: ¿crece o cae el próximo periodo? |
| `entrena negocio <csv>` (`entrenar negocio`) | Entrena modelo sobre tu dataset de negocio |
| `forecast negocio <csv> [meses]` | Proyección optimista / esperada / conservadora |
| `diagnóstico pyme <csv>` | Scorecard financiero + crecimiento + riesgo |
| `plan de accion <csv>` | 5 recomendaciones priorizadas (Llama) |
| `que pasa si <escenario> <csv>` | Simulación what-if con tabla antes/después |
| `si aumento ventas <csv> 20%` / `si reduzco costos <csv> 15%` | Simulaciones rápidas |

### 2.8 Prediction Lab (Fase 5)

| Comando | Qué hace |
|---|---|
| `lab analiza "<idea>"` | Extrae el ProblemSpec de una idea en lenguaje natural |
| `lab dataset <csv> [target]` | Calidad, señal y VIF del dataset |
| `lab viabilidad <csv> "<idea>"` | Índice de viabilidad 0-100 |
| `lab planea <csv> "<idea>"` | Plan de modelo: algoritmos, features, validación |
| `lab genera <csv> "<idea>"` | Genera el `Pipeline` sklearn ejecutable |
| `lab valida <csv> "<idea>"` | Entrena y valida (holdout / k-fold / WFV) |
| `lab reporte <csv> "<idea>"` | Corre 5.1→5.6 y guarda el informe |
| `lab info proyecto <nombre>` | Detalle de un proyecto del lab |

### 2.9 Proyectos y tareas (Fase 1)

| Comando | Qué hace |
|---|---|
| `mis proyectos` | Lista los proyectos registrados |
| `nuevo proyecto <nombre> <desc>` | Crea un proyecto |
| `cerrar proyecto <nombre>` / `pausar proyecto <nombre>` | Cambia el estado |
| `tareas [proyecto]` | Tareas pendientes |
| `nueva tarea <proyecto> \| <desc>` | Crea una tarea |
| `completar tarea <id>` | Marca la tarea como completada |

### 2.10 Evolution Engine, Constitution y feedback

| Comando | Qué hace |
|---|---|
| `reglas ver` | Reglas constitucionales activas |
| `evolucionar` / `evolucionar ciclo` / `evolucionar ciclo auto` | Genera y ejecuta ciclos evolutivos |
| `evolucion historial` | Historial de ciclos |
| `propuestas ver` | Propuestas pendientes |
| `propuesta validar\|aprobar\|rechazar\|aplicar <id>` | Flujo de aprobación manual |
| `audit ver` | Auditoría de cambios |
| `rollback ver` / `rollback aplicar <id>` | Puntos de rollback |
| `salud sistema` / `mejoras detectar` / `monitor snapshot` | Salud y oportunidades de mejora |
| `feedback ver <id>` / `feedback votar <id> <voto>` | Feedback sobre resultados |
| `feedback analisis` / `feedback dashboard` | Análisis y dashboard de feedback |
| `thresholds ver` / `contextual memoria` | Umbrales adaptativos y memoria contextual |

### 2.11 Despliegue y robustez

| Comando | Qué hace |
|---|---|
| `deploy check` | Pipeline + Deployment + Readiness en un paso |
| `deploy readiness` (`deploy readiness check`) | Solo Production Readiness Report |
| `deploy verify` / `deploy history` / `deploy reports` | Verificación, historial y listado de informes |
| `robustness check` (`robustez check`) | Dependencias Python / paquetes / sistema |
| `robustness data` | Integridad de CSVs (filas, huecos, duplicados) |
| `robustness models` | Carga, features y antigüedad de los modelos |
| `robustness recovery` | Historial de eventos de recuperación |
| `robustness provider` | Proveedor cloud detectado |
| `robustness benchmark` | Rendimiento del pipeline |
| `robustness wizard` | Asistente de primera ejecución |
| `robustness all` | Todos los checks |

> Todos los comandos `robustness *` tienen alias en español `robustez *`.

### 2.12 Documentos, web, audio y utilidades

| Comando | Qué hace |
|---|---|
| `lee pdf\|word\|excel\|csv <ruta>` | Lectura de documentos |
| `analiza csv <ruta>` | Estadísticas completas de un CSV |
| `escribe pdf\|word\|excel\|csv <ruta> <contenido>` | Creación de documentos |
| `crear pdf <ruta> <texto>` | PDF vía ReportLab |
| `grafica csv <ruta>` | Gráfico a partir de un CSV |
| `extrae web <url>` | Scraping de texto |
| `traducir <texto>` | Traducción al inglés |
| `youtube <url>` / `descargar audio youtube <url>` | Descarga de vídeo / audio |
| `httpx demo`, `aiohttp demo`, `socketio demo`, `fastapi demo`, `flask demo` | Demos de red |
| `voz a texto` / `texto a voz <texto>` | STT / TTS |
| `analiza audio <ruta>` / `reproducir audio <ruta>` / `convertir audio <ruta>` | Audio |
| `crea py <ruta>` / `analiza codigo [archivo…]` | Generación y análisis de código |
| `torch demo`, `tensorflow demo`, `keras demo`, `sklearn demo`, `integral` | Demos ML / simbólico |
| `memoria buscar <texto>` / `que hice con <tema>` / `historial <tema>` | Memoria y trazabilidad |
| `redis set\|get`, `sqlalchemy usuario`, `faiss add\|search`, `llama add\|query` | Demos de memoria/DB |
| `hash pass`, `verify pass`, `passlib hash\|verify`, `crear jwt`, `verificar jwt`, `cifra archivo`, `bloquear archivo`, `paramiko demo` | Seguridad |

---

## PARTE 3 — ESTRUCTURA DE ARCHIVOS DE DATOS

### CSV Forex

| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp` | datetime | Marca temporal de la vela (UTC sin tz) |
| `open` | float | Precio de apertura |
| `high` | float | Precio máximo |
| `low` | float | Precio mínimo |
| `close` | float | Precio de cierre |
| `volume` | float | Volumen (puede ser 0) |
| `pair` | string | Par de divisas (ej: `EURUSD`) |

Columnas técnicas (generadas por el pipeline):
`spread`, `returns`, `RSI_14`, `ATR_14`, `EMA20`, `EMA50`, `EMA200`, `MACD`, `MACD_signal`, `MACD_hist`, `BB_upper`, `BB_lower`, `session`, `h4_close`, `d1_close`

### Ubicación de CSVs

```
CSVs/
├── H1/    # Velas de 1 hora
│   ├── EURUSD.csv
│   ├── GBPUSD.csv
│   └── USDJPY.csv
├── H4/    # Velas de 4 horas
│   ├── EURUSD.csv
│   ├── GBPUSD.csv
│   └── USDJPY.csv
└── D1/    # Velas diarias (futuro)
```

---

## PARTE 4 — MOTOR AI Y MEMORIA

### Motor de lenguaje
ASTRA usa **Groq** con Llama-3.3-70B por defecto. Alternativa: OpenAI GPT-4.
La conexión se realiza via el SDK de OpenAI con `base_url="https://api.groq.com/openai/v1"`.

### Memoria
Base de datos SQLite con múltiples bases de datos:

| Archivo | Motor | Contenido |
|---|---|---|
| `memory_db/astra_autonomous.db` *(se crea en el primer arranque; ruta configurable con `ASTRA_DB_PATH`)* | SQLite | Scheduler autónomo (8 tablas: predictions, scheduler_runs, supported_symbols, dataset_registry, model_quality, outcomes, config, sqlite_sequence) |
| `memoria.db` | SQLite | Memoria conversacional, proyectos, modelos (gestionada por memory.py) |
| `dev_log.db` | SQLite | Development log (releases, bugfixes, features) |
| `analytics_memory.db` | SQLite | Cache de reportes de análisis (forex + business) |
| `astra_hparam_cache.db` | SQLite | Cache de hiperparámetros optimizados |
| `models/forex/` | Pickle/Joblib | Modelos XGBoost + LightGBM entrenados (generados en runtime) |
| `forex/data/` | CSV | Datasets rolling de velas OHLC |

---

## PARTE 5 — DESPLIEGUE EN VM LINUX (Provider-Agnostic)

ASTRA esta disenado para ejecutarse en cualquier VM Linux estandar. La capa de infraestructura es desacoplada del proveedor -- no hay codigo especifico de Oracle, GCP, AWS o Azure. El unico requerimiento es una VM con Ubuntu/Debian/RHEL y Python 3.11+.

> **Que es una VM y por que la necesito?**
> Una VM (Virtual Machine) es una computadora que vive en la nube. La contratas con un proveedor (Oracle, Google, Amazon, Microsoft) y la usas como si fuera tuya -- pero esta encendida 24/7 sin que tu la dejes prendida. ASTRA necesita esto para que el scheduler corra cada hora automaticamente sin que tu PC este encendido.

### Arquitectura (identica en cualquier proveedor)

```
VM Linux (Ubuntu / Debian / RHEL / Alpine)
+-- ASTRA Pipeline (Python 3.11+)
|   +-- forex/prediction/integrated_pipeline.py  (XGBoost+LightGBM ensemble)
|   +-- workspace/server.py (FastAPI SPA)
|   +-- scheduler/autonomous_scheduler.py        (CLI: --init, --timeframe, --status)
|   +-- memory_db/ (SQLite -- astra_autonomous.db, 8 tablas; creado en runtime)
+-- infra/
|   +-- deploy.sh          (despliegue en 1 comando)
|   +-- db/database.py     (abstraccion SQLite/PostgreSQL)
|   +-- monitor/supervisor.py (monitor + auto-restart)
|   +-- backup/backup.sh   (backup automatico diario)
|   +-- systemd/           (services + timers)
|   +-- logging/logrotate.conf
|   +-- config/astra.env   (configuracion del entorno)
+-- systemd timers (H1/H4/D1 -- sin dependencia de proveedor)
+-- Logs: /var/log/astra/  |  Backups: /var/backups/astra/
```

### Configuracion del proveedor

El proveedor de nube se selecciona solo mediante variables de entorno o el archivo `infra/config/astra.env`. No hay codigo que dependa del proveedor.

```bash
# infra/config/astra.env -- editar antes del despliegue
ASTRA_DB_ENGINE=sqlite          # sqlite (default) | postgresql (futuro)
ASTRA_API_HOST=0.0.0.0
ASTRA_API_PORT=8000
ASTRA_SCHEDULER_ENABLED=true
ASTRA_ROLLING_WINDOW_SIZE=2000
ASTRA_BACKUP_RETENTION_DAYS=7
ASTRA_MONITOR_INTERVAL_SECONDS=30
GROQ_API_KEY=
```

---

### 5.1 -- GUIA PASO A PASO: Oracle Cloud (RECOMENDADA)

> **Por que Oracle Cloud?** Porque su Free Tier es el mas generoso: te dan una VM Ampere A1 con 24 GB de RAM y 4 nucleos ARM -- gratis para siempre, 24/7. Es la mejor opcion para correr ASTRA sin pagar nada.

#### Paso 1: Crear cuenta en Oracle Cloud

1. Ve a **https://www.oracle.com/cloud/free/** y haz clic en **Start for free**
2. Llena el formulario con tu nombre, email y telefono
3. Necesitaras una tarjeta de credito para verificar identidad (no te cobraran nada mientras uses el Free Tier)
4. Elige tu region (recomendado: la mas cercana a ti para menor latencia)
5. Espera el email de confirmacion y haz clic en el enlace

#### Paso 2: Crear la VM (Instancia Compute)

1. Entra a **https://cloud.oracle.com** -> inicia sesion
2. En el menu izquierdo: **Compute** -> **Instances**
3. Haz clic en **Create instance**
4. Configura asi:
   - **Name**: `astra-server`
   - **Image**: **Canonical Ubuntu 22.04** (click en "Change image" si no es esa)
   - **Shape**: Click en **Change shape** -> **Ampere** -> **VM.Standard.A1.Flex**
     - Numero de OCPUs: **4** (gratis hasta 4)
     - Memoria: **24 GB** (gratis hasta 24)
   - **Networking**: Deja los defaults. Anota la IP publica que aparece
   - **Add SSH keys**:
     - Selecciona **"Save private key pair"** -> descarga el archivo `.key` (tu llave privada)
     - Tambien descarga la llave publica `.key.pub`
     - **Guarda estos archivos bien** -- sin la llave privada no puedes entrar a la VM
5. Haz clic en **Create**
6. Espera 2-5 minutos a que el estado cambie a **Running** (verde)
7. Anota la **IP publica** de la instancia (ej: `138.2.1.50`)

#### Paso 3: Abrir puertos en el firewall (VCN)

> ASTRA usa el puerto 8000 para el Workspace web. Hay que abrirlo en Oracle.

1. Menu izquierdo -> **Networking** -> **Virtual Cloud Networks**
2. Haz clic en tu VCN (se llama algo como `Default-VCN-...`)
3. Haz clic en **Security Lists** -> el default security list
4. Haz clic en **Add Ingress Rules**:
   - Source CIDR: `0.0.0.0/0`
   - IP Protocol: `TCP`
   - Destination Port Range: `8000`
   - Haz clic en **Add Ingress Rules**
5. Repite para el puerto `22` (SSH) si no esta ya abierto

#### Paso 4: Conectarse a la VM por primera vez

```bash
# En tu computadora (Linux/Mac) o usando Git Bash / WSL en Windows:

# Cambiar permisos de la llave privada (solo tu puedes leerla)
chmod 600 ~/Downloads/astra-server.key

# Conectarse por SSH (reemplaza la IP por la de tu VM)
ssh -i ~/Downloads/astra-server.key ubuntu@138.2.1.50

# La primera vez te pregunta "Are you sure you want to continue connecting?"
# Escribe: yes
# Ya estas dentro de la VM. Veras algo como: ubuntu@astra-server:~$
```

> **En Windows sin Git Bash/WSL**: Usa PuTTY. Convierte la llave con PuTTYgen (File -> Load private key -> Save private key), luego conecta con `ubuntu@<IP>` y la llave convertida.

#### Paso 5: Instalar Python y dependencias del sistema

```bash
# Una vez dentro de la VM por SSH:

# Actualizar paquetes del sistema
sudo apt update && sudo apt upgrade -y

# Instalar Python 3.11+ y herramientas de build
sudo apt install -y python3 python3-pip python3-venv git unzip curl

# Verificar version de Python (debe ser 3.11 o mayor)
python3 --version
# Si sale Python 3.10.x, instalar Python 3.11:
# sudo add-apt-repository ppa:deadsnakes/ppa
# sudo apt update && sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

#### Paso 6: Subir el proyecto a la VM

```bash
# Opcion A: Subir el ZIP desde tu computadora (en otra terminal, NO en la VM)
scp -i ~/Downloads/astra-server.key ~/Downloads/ASTRA_v702_FINAL.zip ubuntu@138.2.1.50:~/

# Opcion B: Clonar desde git (si tienes el proyecto en GitHub)
# git clone https://github.com/tu-usuario/astra.git ~/astra
```

#### Paso 7: Descomprimir e instalar

```bash
# De vuelta en la VM (por SSH):

# Descomprimir
cd ~
unzip ASTRA_v702_FINAL.zip -d astra
cd astra/IA-LOCAL-enhanced-main

# Crear entorno virtual
python3 -m venv venv

# Activar entorno virtual
source venv/bin/activate

# Instalar dependencias de ASTRA
pip install --upgrade pip
pip install -r requirements.txt
```

> Esto tarda 5-10 minutos (descarga XGBoost, LightGBM, scikit-learn, etc.)

#### Paso 8: Configurar la API key de Groq

```bash
# Editar el archivo de configuracion
cp infra/config/astra.env.example infra/config/astra.env
nano infra/config/astra.env
# Buscar la linea GROQ_API_KEY= y poner tu key:
#   GROQ_API_KEY=gsk_tu_key_aqui
# Guardar: Ctrl+O, Enter, Ctrl+X

# Tambien exportar como variable de entorno para la sesion actual
export GROQ_API_KEY="gsk_tu_key_aqui"
```

> **No tienes API key?** Ve a https://console.groq.com -> API Keys -> Create API Key -> copia el valor que empieza con `gsk_`

#### Paso 9: Inicializar el sistema

```bash
# Generar datasets iniciales (descarga ~1500 velas por par desde Yahoo Finance)
python scheduler/autonomous_scheduler.py --init

# Verificar que todo funciona
python check_startup.py
# Debe decir: "No critical issues found"

# Probar el pipeline
python test_complete_pipeline.py
# Debe decir: "All tests passed!"

# Lanzar el workspace para probarlo
python workspace/server.py
# Abre en tu navegador: http://138.2.1.50:8000
# (reemplaza por la IP de tu VM)
# Deberias ver el dashboard de ASTRA. Ctrl+C para detener.
```

#### Paso 10: Despliegue automatico (systemd + timers)

```bash
# Desplegar todo con un comando
bash infra/deploy.sh
```

> Esto hace todo automaticamente:
> - Copia servicios systemd a `/etc/systemd/system/`
> - Habilita y arranca el workspace (puerto 8000)
> - Programa los timers del scheduler (H1, H4, D1)
> - Configura logrotate para que los logs no llenen el disco
> - Configura el monitor de auto-recuperacion
> - Programa backups diarios a las 02:00

#### Paso 11: Verificar que todo corre

```bash
# Ver servicios activos
sudo systemctl status astra-api.service
sudo systemctl list-timers astra-*

# Ver logs en vivo
sudo journalctl -u astra-api.service -f
# (Ctrl+C para salir)

# Ver estado del scheduler
python scheduler/autonomous_scheduler.py --status

# Abrir el workspace desde tu navegador
# http://TU_IP_PUBLICA:8000
```

#### Paso 12: Mantenimiento

```bash
# Reiniciar el workspace manualmente
sudo systemctl restart astra-api.service

# Ver backups disponibles
ls -la /var/backups/astra/

# Restaurar un backup
sudo tar xzf /var/backups/astra/astra_backup_20260804_020000.tar.gz -C ~/astra/IA-LOCAL-enhanced-main/

# Ver logs del scheduler
sudo journalctl -u astra-scheduler-h1.service --since today

# Detener todo (mantenimiento)
sudo systemctl stop astra-*

# Arrancar todo de nuevo
sudo systemctl start astra-api.service
sudo systemctl start astra-scheduler-h1.timer astra-scheduler-h4.timer astra-scheduler-d1.timer
```

---

### 5.2 -- GUIA PASO A PASO: Google Cloud Platform (GCP)

> GCP te da una VM `e2-micro` gratis para siempre (1 GB RAM, 30 GB disco). Es mas pequena que Oracle pero suficiente para ASTRA.

#### Paso 1: Crear cuenta y proyecto

1. Ve a **https://cloud.google.com/free** -> **Get started for free**
2. Llena el formulario (tarjeta requerida, no cobran en Free Tier)
3. Crea un proyecto: ve a **https://console.cloud.google.com** -> barra superior -> selecciona/crea proyecto llamado `astra`

#### Paso 2: Crear la VM

1. En la consola: **Compute Engine** -> **VM Instances** -> **Create**
2. Configura:
   - **Name**: `astra-server`
   - **Machine configuration**: Series `E2` -> Machine type `e2-micro` (2 vCPU, 1 GB RAM)
   - **Boot disk**: Click "Change" -> **Ubuntu 22.04 LTS** -> 30 GB
   - **Firewall**: Marca **Allow HTTP traffic** y **Allow HTTPS traffic**
   - **SSH**: GCP usa SSH sin llave manual -- veras un boton "Connect" mas adelante
3. Click **Create** -> espera 1-2 minutos
4. Anota la **IP externa** (ej: `35.1.2.3`)

#### Paso 3: Abrir puerto 8000

1. **VPC network** -> **Firewall** -> **Create firewall rule**
2. Configura:
   - Name: `astra-allow-8000`
   - Direction: Ingress
   - Target tags: `http-server` (o el tag de tu VM)
   - Source IP ranges: `0.0.0.0/0`
   - Protocols and ports: TCP `8000`
3. Click **Create**

#### Paso 4: Conectarse por SSH

```bash
# Opcion A: Boton "SSH" en la consola de GCP (mas facil, abre terminal en el navegador)
# Opcion B: Desde tu terminal:
gcloud compute ssh astra-server --zone=us-central1-a
```

#### Paso 5 en adelante: Identico a Oracle

```bash
# Los pasos 5-12 son exactamente iguales a Oracle Cloud:
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git unzip curl

# Subir el ZIP o clonar, descomprimir, crear venv, instalar...
# Seguir desde el Paso 6 de la guia de Oracle
```

---

### 5.3 -- GUIA PASO A PASO: Amazon Web Services (AWS)

> AWS te da una VM `t2.micro` gratis por 12 meses (1 GB RAM, 30 GB EBS). Despues de eso hay que pagar.

#### Paso 1: Crear cuenta

1. Ve a **https://aws.amazon.com/free** -> **Create a Free Account**
2. Llena todo (tarjeta requerida). Elige la region mas cercana

#### Paso 2: Crear la VM (EC2)

1. Entra a **https://console.aws.amazon.com** -> **EC2** -> **Launch Instance**
2. Configura:
   - **Name**: `astra-server`
   - **AMI**: **Ubuntu 22.04 LTS** (busca "Ubuntu" y selecciona la 64-bit x86)
   - **Instance type**: `t2.micro` (1 vCPU, 1 GB -- Free Tier)
   - **Key pair**: Click "Create new key pair" -> Name: `astra-key` -> RSA -> .pem -> Create. **Descarga el archivo .pem**
   - **Network**: Allow SSH traffic from internet. Allow HTTP/HTTPS
3. Click **Launch instance**
4. Espera a que el estado sea **Running**
5. Anota la **Public IPv4** (ej: `54.1.2.3`)

#### Paso 3: Abrir puerto 8000

1. En la consola EC2: selecciona tu instancia -> **Security** -> click en el **security group**
2. **Inbound rules** -> **Edit inbound rules** -> **Add rule**:
   - Type: Custom TCP
   - Port range: `8000`
   - Source: `0.0.0.0/0`
   - Click **Save rules**

#### Paso 4: Conectarse por SSH

```bash
# Cambiar permisos de la llave
chmod 600 ~/Downloads/astra-key.pem

# Conectarse (reemplaza IP)
ssh -i ~/Downloads/astra-key.pem ubuntu@54.1.2.3
# Escribe: yes la primera vez
```

#### Paso 5 en adelante: Identico a Oracle

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git unzip curl
# Seguir desde el Paso 6 de la guia de Oracle
```

---

### 5.4 -- GUIA PASO A PASO: Microsoft Azure

> Azure te da una VM `B1s` gratis por 12 meses (1 vCPU, 1 GB RAM, 64 GB disco).

#### Paso 1: Crear cuenta

1. Ve a **https://azure.microsoft.com/free** -> **Start free**
2. Llena el formulario (tarjeta requerida)

#### Paso 2: Crear la VM

1. Entra a **https://portal.azure.com** -> **Virtual machines** -> **Create** -> **Azure virtual machine**
2. Configura:
   - **Resource group**: Click "Create new" -> `astra-rg`
   - **Virtual machine name**: `astra-server`
   - **Image**: **Ubuntu Server 22.04 LTS** (x64 Gen2)
   - **Size**: Click "See all sizes" -> busca `B1s` (1 vCPU, 1 GB RAM, Free Tier)
   - **Authentication type**: **SSH public key**
   - **Username**: `azureuser`
   - **SSH key name**: Click "Generate new key pair" -> `astra-ssh`
   - **Inbound port rules**: Marca **Allow HTTP (80)** y deja SSH (22) ya marcado
3. Click **Review + create** -> **Create**
4. Se abre una ventana para descargar la llave privada `.pem` -- **DESCARGALA AHORA** (no puedes recuperarla despues)
5. Espera a que el deployment termine (3-5 minutos)
6. Anota la **IP publica** (ej: `20.1.2.3`)

#### Paso 3: Abrir puerto 8000

1. En el portal: ve a tu VM -> **Networking** -> **Add inbound port rule**
2. Configura:
   - Destination port: `8000`
   - Source: `0.0.0.0/0`
   - Protocol: TCP
   - Name: `astra-8000`
3. Click **Add**

#### Paso 4: Conectarse por SSH

```bash
chmod 600 ~/Downloads/astra-ssh.pem
ssh -i ~/Downloads/astra-ssh.pem azureuser@20.1.2.3
# Escribe: yes la primera vez
```

#### Paso 5 en adelante: Identico a Oracle

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv git unzip curl
# Seguir desde el Paso 6 de la guia de Oracle
```

---

### 5.5 -- Tabla comparativa de proveedores

| Proveedor | VM | RAM | Free Tier | 24/7 gratis | Discos | Notas |
|---|---|---|---|---|---|---|
| **Oracle Cloud** (RECOMENDADO) | Ampere A1 | 24 GB | Siempre | Si | 200 GB | Mejor opcion. Mas RAM y gratis para siempre |
| GCP | e2-micro | 1 GB | Siempre | Si | 30 GB | Suficiente para ASTRA. SSH en navegador |
| AWS | t2.micro | 1 GB | 12 meses | Si | 30 GB | Despues de 12 meses hay que pagar |
| Azure | B1s | 1 GB | 12 meses | Si | 64 GB | Despues de 12 meses hay que pagar |
| Local | Tu PC | Variable | -- | No (si apagas) | Variable | Para desarrollo y pruebas |

> **Recomendacion:** Usa **Oracle Cloud** si puedes. 24 GB de RAM gratis para siempre es una oferta que ningun otro proveedor iguala. Si Oracle no esta disponible en tu region o tienes problemas, **GCP** es la segunda mejor opcion (gratis para siempre, SSH directo desde el navegador sin configurar llaves).

---

### 5.6 -- Comandos del scheduler autonomo (CLI)

```bash
# Generar datasets iniciales (primera vez)
python scheduler/autonomous_scheduler.py --init

# Ejecutar un ciclo manual
python scheduler/autonomous_scheduler.py --timeframe H1

# Ver estado del sistema (JSON)
python scheduler/autonomous_scheduler.py --status

# Anadir un simbolo nuevo
python scheduler/autonomous_scheduler.py --add-symbol NZDUSD
```

---

### 5.7 -- Capa de persistencia desacoplada

```python
from infra.db.database import get_database

db = get_database()  # SQLite por defecto
# Cambiar a PostgreSQL: set ASTRA_DB_ENGINE=postgresql

# La interfaz es la misma sin importar el motor:
symbols = db.get_supported_symbols()
db.save_prediction({"symbol": "EURUSD", "direction": "buy", ...})
health = db.get_system_health()
```

---

### 5.8 -- Monitor y auto-recuperacion

El supervisor (`infra/monitor/supervisor.py`):
- Verifica cada 30s: API, base de datos, frescura del scheduler
- Si la API cae: `systemctl restart astra-api`
- Si la DB esta corrupta: log critico + restart
- Si el scheduler no ha corrido en tiempo: warning
- Logs estructurados en `/var/log/astra/monitor.log`

---

### 5.9 -- Backups automaticos

El script `infra/backup/backup.sh` (corre diario a 02:00):
- Crea `astra_backup_YYYYMMDD_HHMMSS.tar.gz`
- Incluye: memory_db/, forex/data/, models/forex/, config, scheduler
- Guarda en `/var/backups/astra/`
- Retencion: 7 dias (configurable via `ASTRA_BACKUP_RETENTION_DAYS`)

---
# CHANGE

### 5.10 -- Servicios systemd

| Servicio | Funcion | Frecuencia |
|---|---|---|
| `astra-api.service` | FastAPI workspace (puerto 8000) | Siempre activo, restart=always | 
| `astra-scheduler-h1.timer` | Ciclo H1 (update + predict) | Cada hora a :02 |
| `astra-scheduler-h4.timer` | Ciclo H4 (update + predict) | Cada 4h a :05 |
| `astra-scheduler-d1.timer` | Ciclo D1 (update + predict) | Diario a 00:10 |
| `astra-monitor.service` | Supervisor de procesos | Siempre activo, cada 30s |
| `astra-backup.timer` | Backup completo | Diario a 02:00 |

---

### 5.11 -- Despliegue en 1 comando (cualquier proveedor)

```bash
# Resumen de todos los pasos (ya con SSH dentro de la VM):
cd ~/astra/IA-LOCAL-enhanced-main
cp infra/config/astra.env.example infra/config/astra.env
nano infra/config/astra.env   # <- poner GROQ_API_KEY
bash infra/deploy.sh          # <- hace todo el resto
```

> **Importante:** ASTRA no depende del proveedor. La seleccion se hace al crear la VM y abrir el firewall -- el despliegue (`deploy.sh`), el scheduler, el pipeline, la API y la base de datos son identicos en todos los casos.

---

## PARTE 6 — SUBSISTEMAS INTERNOS

### Constitution Engine (Phase 8)
Sistema de reglas constitucionales que valida propuestas de evolución antes de aplicarlas.
- `constitution/constitution_rules.py` — Catálogo de reglas inmutables
- `constitution/constitution_validator.py` — Validador de propuestas
- `constitution/approval_flow.py` — Flujo de aprobación/rechazo
- `constitution/rollback_manager.py` — Puntos de rollback y restauración
- `constitution/audit_log.py` — Log de auditoría inmutable

### Evolution Engine (Phase 7)
Motor evolutivo que detecta mejoras, genera propuestas y las aplica con validación constitucional.
- `evolution/improvement_detector.py` — Detector de oportunidades de mejora
- `evolution/evolution_proposal.py` — Generador de propuestas
- `evolution/proposal_store.py` — Persistencia de propuestas (SQLite)
- `evolution/performance_monitor.py` — Monitor de rendimiento

### Feedback System (Phase 6)
Sistema de feedback adaptativo que ajusta umbrales según votación de usuario.
- `feedback/feedback_collector.py` — Recolección de feedback
- `feedback/feedback_analyzer.py` — Análisis de patrones
- `feedback/adaptive_thresholds.py` — Umbrales adaptativos por par
- `feedback/contextual_memory.py` — Memoria contextual de condiciones
- `feedback/evolution_memory.py` — Log de eventos evolutivos
- `feedback/feedback_dashboard.py` — Dashboard visual

### Prediction Lab
Laboratorio de ML genérico para cualquier dataset.
- `prediction_lab/prompt_analyzer.py` — Análisis del prompt del usuario
- `prediction_lab/dataset_analyzer.py` — Análisis del dataset
- `prediction_lab/feasibility_engine.py` — Evaluación de viabilidad
- `prediction_lab/model_planner.py` — Planificación de modelos
- `prediction_lab/pipeline_generator.py` — Generación de pipeline
- `prediction_lab/validation_engine.py` — Validación cruzada
- `prediction_lab/report_generator.py` — Generación de reportes

### Market Intelligence
- `forex/market_sentinel.py` — Sentinel 24/7 de monitoreo multi-activo
- `forex/market_universe.py` — Universo de 92 instrumentos (Forex, Commodities, Crypto)
- `news_intelligence.py` — Noticias financieras con web scraping
- `signal_tracker.py` — Tracking de señales activas

### SME / PYME Consultant
- `sme_consultant.py` — Consultor automatizado para PYMEs
- `bi_analytics.py` — Business Intelligence adapter
- `forex/business/` — Pipeline de business analytics (KPIs, health score, forecast)

---

## PARTE 7 — BASE44 CLOUD INTEGRATION (v7.0)

### Arquitectura Base44 ↔ Pipeline

```
[Cron dispara workflow] 
  → [invoke_superagent_step: recibe mensaje]
    → [Crea SchedulerRun(status=running)]
    → [Por cada símbolo activo:]
      → [bash: astra_bridge.py update <symbol> <tf>]  (rolling update)
      → [bash: astra_bridge.py predict <symbol> <tf>] (predicción)
      → [Crea Prediction entity con resultado]
      → [Actualiza DatasetRegistry]
    → [Actualiza SchedulerRun(status=completed, counts)]
    → [Reporta resumen al owner]
```

### Reglas Operativas

Las reglas operativas viven en el módulo `constitution/` (`constitution_rules.py`, validadas por `constitution_validator.py` y aplicadas vía `approval_flow.py`):

1. **Pipeline Integrity** — Nunca modificar el código Python. Los 175 módulos se ejecutan as-is.
2. **Error Handling** — Todo ciclo crea SchedulerRun. Errores se capturan con stderr completo.
3. **Model Quality Gates** — AUC < 0.55 bloquea retrain. retrain_count >= 3 → degraded.
4. **Dataset Management** — Verificar DatasetRegistry antes de regenerar. Skip si ya existe.
5. **API Rules** — Confianza < 0.60 se almacena pero se excluye del ranking.
6. **Symbol Management** — Validar formato (6 letras), verificar duplicados.

### API Reference (Backend Functions)

**URL base**: `https://velo-9c44d510.base44.app/functions/<name>`

#### GET getSystemHealth
```json
// Response 200
{
  "ok": true,
  "data": {
    "symbols_total": 5,
    "symbols_active": 5,
    "datasets_total": 12,
    "datasets_ready": 12,
    "datasets_error": 0,
    "latest_prediction": { "symbol": "EURUSD", "direction": "hold", "confidence": 0.52 },
    "recent_runs": [],
    "degraded_models": 0,
    "healthy": true
  }
}
```

#### POST getDatasetStatus
```json
// Body: { "symbol": "EURUSD" }  // opcional
// Response 200
{ "ok": true, "data": [{ "symbol": "EURUSD", "timeframe": "H1", "candle_count": 1523, "status": "ready" }] }
```

#### POST getLatestPrediction
```json
// Body: { "symbol": "EURUSD", "ranked_only": true }
// Response 200
{ "ok": true, "data": [{ "symbol": "EURUSD", "direction": "buy", "confidence": 0.72 }] }
```

#### POST addSupportedSymbol
```json
// Body: { "symbol_code": "NZDUSD", "display_name": "NZD/USD", "pip_value": 0.0001 }
// Response 200
{ "ok": true, "data": { "id": "...", "symbol_code": "NZDUSD", "message": "Symbol NZDUSD added." } }
// Response 400 si ya existe o formato inválido
```

#### POST triggerManualRun
```json
// Body: { "symbol": "EURUSD", "timeframe": "H1" }
// Response 200
{ "ok": true, "data": { "run_id": "...", "message": "Manual run triggered for EURUSD H1." } }
```

---

## PARTE 8 — ROADMAP Y ESTADO

### Estado actual (v7.0.2-prod)

| Componente | Estado | Notas |
|---|---|---|
| Pipeline ML (175 módulos Python) | ✅ Producción | XGBoost+LightGBM, Walk-Forward Validation |
| Base44 Entities | ✅ Activo | 6 entidades, 5 símbolos, 12+ datasets |
| Base44 Backend Functions | ✅ Activo | 9 endpoints HTTP respondiendo 200 |
| Base44 Workflows | ✅ Activo | 3 ciclos programados (H1/H4/D1) |
| Bridge Script | ✅ Activo | 8 comandos, JSON output |
| Yahoo Finance data | ✅ Activo | ~1500 velas por dataset |
| Rolling update | ✅ Activo | Detecta velas nuevas, mantiene ventana 2000 |
| Model quality gates | ✅ Activo | AUC < 0.55 bloquea, retrain_count >= 3 degrade |
| Outcome validation | ✅ Estructurado | Pendiente datos reales para validar |
| Constitution Engine | ✅ Activo | Reglas, validador, approval flow, rollback |
| Evolution Engine | ✅ Activo | Propuestas, performance monitor, detector |
| Feedback System | ✅ Activo | Umbrales adaptativos, feedback collector |
| Prediction Lab | ✅ Activo | Análisis ML de datasets genéricos |
| Market Sentinel | ✅ Activo | Monitoreo 24/7 multi-activo |
| Workspace Dashboard | ✅ Activo | 12 endpoints /api/roadmap6/* |
| SME Consultant | ✅ Activo | KPIs, health score, forecast PYME |

### Pendiente (verificación en entorno real)

| Item | Descripción |
|---|---|
| GROQ_API_KEY | Configurar en entorno de producción para chat AI |
| MetaTrader 5 | Conexión real en Windows para datos en vivo |
| Binance | Conexión para datos cripto (IP whitelist) |
| VM Linux 24/7 | Despliegue provider-agnostic (Oracle/GCP/AWS/Azure) |
| Paper Trading | Validación de predicciones con broker demo |

---

## PARTE 9 — SOLUCIÓN DE PROBLEMAS

| Problema | Solución |
|---|---|
| `ModuleNotFoundError: yfinance` | `pip install yfinance` |
| `ModuleNotFoundError: yaml` | `pip install PyYAML` |
| `ModuleNotFoundError: imblearn` | `pip install imbalanced-learn` |
| `ModuleNotFoundError: shap` | `pip install shap` |
| `ModuleNotFoundError: nltk` | `pip install nltk` |
| `GROQ_API_KEY not set` | Configurar en `.env` o variables de entorno |
| Dataset vacío | Ejecutar `python scheduler/autonomous_scheduler.py --init` |
| Modelo no encontrado | El pipeline auto-entrena si no hay modelo |
| Confianza baja (HOLD) | Normal — HOLD cuando las señales no son claras |
| Backend function 500 | Verificar `createClientFromRequest(req)` y headers |
| Workflow no dispara | Verificar CRON expression y timezone (America/Santiago) |
| `forex_backup/` errores | Directorio obsoleto — usar `forex/` y `forex/prediction/` |
| `future_phases_draft/` | Directorio obsoleto — subsistemas ya en producción |

---

## PARTE 10 — ESTRUCTURA DE ARCHIVOS

```
IA-LOCAL-enhanced-main/
├── main.py                           # CLI entry point (101 KB)
├── astra.py                          # Utilidades legacy (DB, PDF, GUI adapters)
├── astra_agent.py                    # Capa de agente inteligente
├── ai_models.py                       # Motor AI (Groq/OpenAI)
├── requirements.txt                   # Dependencias Python
├── MANUAL.md                          # Este manual
│
├── forex/                             # Pipeline Forex completo
│   ├── __init__.py                    # Lazy loading del paquete
│   ├── prediction/                    # Núcleo de predicción (33 módulos)
│   │   ├── integrated_pipeline.py     # Pipeline principal XGBoost+LightGBM
│   │   ├── predictor.py               # Predictor con WFV
│   │   ├── xgb_trainer.py             # Entrenador ensemble
│   │   ├── decision_engine.py         # Motor de decisiones
│   │   ├── risk_engine.py             # Motor de riesgo
│   │   ├── regime_detector.py         # Detector de régimen
│   │   ├── mtf_coherence.py           # Coherencia multi-timeframe
│   │   ├── backtester.py              # Backtesting
│   │   ├── circuit_breaker.py         # Circuit breaker
│   │   └── ... (23 módulos más)
│   ├── data/                          # Proveedores de datos
│   │   ├── yahoo_provider.py          # Yahoo Finance
│   │   ├── mt5_provider.py            # MetaTrader 5 (Windows)
│   │   ├── binance_provider.py        # Binance (crypto)
│   │   ├── data_router.py             # Router de proveedores
│   │   ├── dataset_updater.py         # Rolling update
│   │   └── rolling_dataset.py         # Ventana rolling
│   ├── business/                      # Business Intelligence
│   │   ├── business_predictor.py      # Predictor de negocio
│   │   ├── business_pipeline.py       # Pipeline BI
│   │   ├── kpi_engine.py              # Motor de KPIs
│   │   └── business_csv_adapter.py    # Adaptador CSV business
│   ├── portfolio/                     # Gestión de portafolio
│   │   ├── portfolio_ranker.py        # Ranking de oportunidades
│   │   └── opportunity_score.py      # Score de oportunidad
│   ├── scheduler/                     # Scheduler Forex
│   │   ├── autonomous_scheduler.py   # Scheduler autónomo
│   │   ├── auto_updater.py            # Auto-actualización
│   │   └── task_manager.py            # Gestión de tareas
│   ├── indicators.py                  # Indicadores técnicos (RSI, MACD, ATR, etc.)
│   ├── market_sentinel.py             # Sentinel 24/7
│   ├── market_universe.py             # 92 instrumentos
│   └── forex_report.py                # Reportes estructurados
│
├── constitution/                      # Constitution Engine (Phase 8)
│   ├── constitution_rules.py
│   ├── constitution_validator.py
│   ├── approval_flow.py
│   ├── rollback_manager.py
│   └── audit_log.py
│
├── evolution/                         # Evolution Engine (Phase 7)
│   ├── evolution_proposal.py
│   ├── improvement_detector.py
│   ├── performance_monitor.py
│   └── proposal_store.py
│
├── feedback/                          # Feedback System (Phase 6)
│   ├── feedback_collector.py
│   ├── feedback_analyzer.py
│   ├── adaptive_thresholds.py
│   ├── contextual_memory.py
│   ├── evolution_memory.py
│   └── feedback_dashboard.py
│
├── prediction_lab/                    # Prediction Lab genérico
│   ├── prompt_analyzer.py
│   ├── dataset_analyzer.py
│   ├── feasibility_engine.py
│   ├── model_planner.py
│   ├── pipeline_generator.py
│   ├── validation_engine.py
│   └── report_generator.py
│
├── workspace/
│   └── server.py                      # FastAPI SPA server (puerto 8000)
│
├── infra/                             # Capa de infraestructura
│   ├── deploy.sh                      # Despliegue en 1 comando
│   ├── db/database.py                # Abstracción SQLite/PostgreSQL
│   ├── monitor/supervisor.py          # Monitor + auto-restart
│   ├── backup/backup.sh               # Backup automático
│   ├── systemd/                       # Servicios y timers
│   ├── logging/logrotate.conf        # Rotación de logs
│   └── config/astra.env.example       # Configuración de entorno
│
├── scheduler/                         # Scheduler autónomo (CLI)
│   └── autonomous_scheduler.py
│
├── notifications/                     # Centro de notificaciones
│   └── notifier.py
│
├── memoria.db / dev_log.db / astra_hparam_cache.db   # Bases SQLite en la raíz
├── models/forex/                      # Modelos entrenados (.pkl) por par
│
├── tests/                             # Tests de infraestructura
│   └── test_infrastructure.py         # 10 tests end-to-end
│
├── docs/                              # Documentación técnica
│   ├── FLUJO_PREDICCION.md            # Diagramas del pipeline
│   ├── FOREX_COMMANDS_FULL.md         # Referencia completa de comandos
│   ├── GUIA_CSV.md                    # Guía de formato CSV
│   └── ...
│
├── CSVs/                              # Datos CSV de entrada
│   ├── H1/                            # Velas de 1 hora
│   ├── H4/                            # Velas de 4 horas
│   └── D1/                            # Velas diarias (futuro)
│
├── legacy/                            # Código legacy (referencia)
│   └── astra_legacy_v1.py
│
├── forex_backup/                      # ⚠️ OBSOLETO — safe to delete
├── future_phases_draft/                # ⚠️ OBSOLETO — subsistemas ya en producción
│
└── constitution/                      # Reglas, validador, aprobación y rollback
    ├── rules/
    │   └── astra_ops_policy.md        # Reglas operativas
    └── skills/
        └── astra_bridge.py            # Puente Base44 ↔ Pipeline
```

### Tests de infraestructura

```bash
python tests/test_infrastructure.py
```

10 tests que validan:
1. Capa de abstracción de base de datos (7 tablas, CRUD, thread-safety)
2. Detección de primera ejecución (init genera datasets)
3. Rolling update mantiene tamaño de ventana (2000 velas)
4. Auto-detección de símbolos nuevos
5. Init idempotente (no regenera datasets existentes)
6. Endpoint de health de la API
7. Monitor detecta y reporta estado
8. Backup script crea tar.gz válido
9. Ciclo end-to-end (init → update → predict → log)
10. Persistencia desacoplada (SQLite/PostgreSQL interface)

---

*ASTRA v7.0.2-prod · 2026-08-04 · Nicolas Saez*
