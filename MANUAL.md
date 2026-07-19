# ASTRA — Manual de Usuario
**Sistema AI Modular · Consultor PYME · Análisis Forex · v3.0 — Roadmap V**

---

## ÍNDICE

**CLI — Fases 1–9**
1. [Instalación y Arranque](#parte-1--instalación-y-arranque)
2. [Generación de CSVs Forex (creando.py)](#parte-2--generación-de-csvs-forex-creandopy)
3. [Análisis y Predicción Forex](#parte-3--análisis-y-predicción-forex)
4. [Documentos, Web y Utilidades](#parte-4--documentos-web-y-utilidades)
5. [Consultor PYME Avanzado](#parte-5--consultor-pyme-avanzado)
6. [Business Intelligence (BI Engine)](#parte-6--business-intelligence-bi-engine)
7. [Sistema y Auto-Análisis](#parte-7--sistema-y-auto-análisis)
8. [Formato de Archivos CSV](#parte-8--formato-de-archivos-csv)
9. [Gestión de Riesgo — Circuit Breaker y Position Sizing](#parte-9--gestión-de-riesgo)
10. [Watcher, Señales y Scheduler](#parte-10--watcher-señales-y-scheduler)
11. [News Intelligence](#parte-11--news-intelligence)
12. [Memoria de Proyectos](#parte-12--memoria-de-proyectos)

**Guías Operativas**
13. [Guía de Trading Real (paso a paso)](#parte-13--guía-de-trading-real)
14. [Prediction Lab — Fase 5 (Laboratorio de Predicción)](#parte-14--prediction-lab)
15. [Feedback System — Fase 6](#parte-15--feedback-system)
16. [Evolution Engine — Fase 7](#parte-16--evolution-engine)
17. [Constitution Engine — Fase 8](#parte-17--constitution-engine)
18. [Ciclo Evolutivo Completo — Fase 9](#parte-18--ciclo-evolutivo)

**Workspace — Roadmap IV (Secciones 1–12)**
19. [Workspace — Instalación y Secciones 1–3 (Chat Center, Forex Lab)](#parte-19--workspace-secciones-1-3)
20. [Predicción multi-CSV y reportes de texto](#parte-20--predicción-multi-csv)
21. [Prediction Lab Workspace (Sección 5)](#parte-21--prediction-lab-workspace)
22. [Business Lab Workspace (Sección 6)](#parte-22--business-lab-workspace)
23. [Cognitive Center Workspace (Sección 7)](#parte-23--cognitive-center)
24. [Evolution Center Workspace (Sección 8)](#parte-24--evolution-center-workspace)
25. [Activity Center Workspace (Sección 9)](#parte-25--activity-center)
26. [Notification Center (Sección 10)](#parte-26--notification-center)
27. [Live Thinking (Sección 11)](#parte-27--live-thinking)
28. [Identidad Visual (Sección 12)](#parte-28--identidad-visual)
29. [Revisión Operativa Final — Post-cierre Roadmap IV](#parte-29--revisión-operativa-final)

**Roadmap V — Sistema Autónomo**
30. [Roadmap V — Dashboard Activo y Sistema Autónomo (Sección 13)](#parte-30--roadmap-v-dashboard-activo)

---

## PARTE 1 — Instalación y Arranque

### Requisitos previos
- Python **3.10 o superior**
- pip actualizado: `python -m pip install --upgrade pip`
- API key de **Groq** (gratuita): https://console.groq.com — API Keys — Create

---

### Instalación en Windows

```cmd
:: 1. Entrar a la carpeta del proyecto
cd ruta\al\proyecto

:: 2. Crear entorno virtual
python -m venv venv

:: 3. Activar entorno virtual
venv\Scripts\activate.bat          :: CMD
.\venv\Scripts\Activate.ps1        :: PowerShell

:: 4. Instalar dependencias
pip install -r requirements.txt

:: 5. Configurar API key (una sola vez)
setx GROQ_API_KEY "gsk_tu_key_aqui"
:: Cierra y vuelve a abrir el terminal

:: 6. Lanzar ASTRA
python main.py
```

> **Alternativa .env:** crea un archivo `.env` en la raíz con:
> ```
> GROQ_API_KEY=gsk_tu_key_aqui
> ```
> Luego instala `pip install python-dotenv` y añade al inicio de `main.py`:
> ```python
> from dotenv import load_dotenv; load_dotenv()
> ```

---

### Instalación en Linux / macOS

```bash
# 1. Instalar dependencias
pip install -r requirements.txt

# 2. Exportar API key
export GROQ_API_KEY="gsk_tu_key_aqui"
# Para que persista, añádela a ~/.bashrc o ~/.zshrc

# 3. Lanzar ASTRA
python main.py
```

---

### Diagnóstico de instalación (opcional)

```bash
python check_startup.py
```

Resultado esperado: `No critical issues found`. Los `WARN` de torch, tensorflow,
redis y librosa son paquetes **opcionales** y no bloquean el funcionamiento.

---

## PARTE 2 — Generación de CSVs Forex (`creando.py`)

`creando.py` descarga datos OHLCV reales para todos los pares, commodities y
cryptos definidos en `forex/market_universe.py` y genera CSVs listos para
entrenar y predecir — con todos los indicadores técnicos ya calculados.

**Modos disponibles:**

| Modo | Requiere | Sistema |
|---|---|---|
| `yfinance` | Solo Python + internet | Cualquier OS — |
| `mt5` | MetaTrader5 terminal corriendo | Solo Windows |

**Timeframes generados:**

| Timeframe | Datos | Velas aprox. | Carpeta |
|---|---|---|---|
| H1 | H1 real desde Yahoo Finance | ~17 000 | `CSVs/H1/` |
| H4 | H1 resampleado a 4h | ~4 300 | `CSVs/H4/` |
| D1 | D1 real desde Yahoo Finance | ~3 600 | `CSVs/D1/` |

---

### Comandos `creando.py`

#### Generar todos los pares — todos los timeframes (modo yfinance)
```bash
python creando.py --modo yfinance --timeframe H1,H4,D1
```
Descarga EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD y todos los demás soportados.

---

#### Generar pares específicos — un timeframe
```bash
python creando.py --modo yfinance --timeframe H1 --pares EURUSD GBPUSD XAUUSD
```

---

#### Generar pares específicos — todos los timeframes
```bash
python creando.py --modo yfinance --timeframe H1,H4,D1 --pares EURUSD USDJPY BTCUSD
```

**Ejemplo de salida:**
```
=== yfinance H1 (2 años) — CSVs/H1 ===
  [ok] CSVs/H1/EURUSD.csv  (17201 filas)
  [ok] CSVs/H1/GBPUSD.csv  (17203 filas)

=== yfinance H4 simulado desde H1 — CSVs/H4 ===
  [ok] CSVs/H4/EURUSD.csv  (4338 filas)

=== yfinance D1 (10 años) — CSVs/D1 ===
  [ok] CSVs/D1/EURUSD.csv  (3626 filas)

— yfinance completo: 6 CSVs generados, 0 omitidos.
```

---

#### Usar MetaTrader5 (solo Windows)
```bash
# Asegúrate de tener el terminal MT5 abierto antes de ejecutar
python creando.py --modo mt5 --timeframe H1,H4,D1
```

---

#### Auto-detectar modo
```bash
# Si MT5 está disponible lo usa; si no, usa yfinance automáticamente
python creando.py --timeframe H1,H4,D1
```

---

### Pares soportados en yfinance

| Categoría | Ejemplos | Ticker Yahoo |
|---|---|---|
| Forex majors | EUR/USD, GBP/USD, USD/JPY, AUD/USD | `EURUSD=X`, `GBPUSD=X` |
| Forex crosses | EUR/JPY, GBP/JPY, AUD/JPY, EUR/GBP | `EURJPY=X`, `GBPJPY=X` |
| Metales | XAU/USD (Gold), XAG/USD (Silver) | `GC=F`, `SI=F` |
| Energía | WTI Crude Oil, Brent Crude Oil, Natural Gas | `CL=F`, `BZ=F`, `NG=F` |
| Granos | Corn, Wheat, Soybean, Sugar, Cotton | `ZC=F`, `ZW=F`, `ZS=F` |
| Crypto | BTC/USD, ETH/USD, XRP/USD, ADA/USD, SOL/USD | `BTC-USD`, `ETH-USD` |

> El mapeo completo display — ticker está en `YFINANCE_TICKER_MAP` dentro de
> `forex/market_universe.py`. Si necesitas añadir un par nuevo, solo agrega
> una línea ahí.

---

## PARTE 3 — Análisis y Predicción Forex

Una vez tienes los CSVs generados (ver Parte 2), puedes analizar y predecir
directamente desde el chat de ASTRA o desde código Python.

### Desde el chat de ASTRA (`main.py`)

#### Analizar un par con su CSV
```
analiza forex eurusd CSVs/H1/EURUSD.csv
```
Ejecuta análisis técnico completo + señal ML sobre la última vela.

---

#### Analizar solo mencionando el par (sin CSV)
```
forex eurusd
analiza forex XAUUSD
```
ASTRA busca automáticamente el CSV en `CSVs/H1/<SYMBOL>.csv`.

---

#### Ver historial de análisis guardados
```
history eurusd
history xauusd
```
Muestra los últimos reportes almacenados en memoria para ese par.

---

#### Comparar reportes históricos
```
compare history eurusd
compare history gbpusd
```
Compara los dos últimos reportes del par para detectar cambios de tendencia.

---

#### Ver todos los mercados analizados
```
list markets
```
Lista todos los pares con análisis guardado en la sesión actual.

---

### Desde código Python (pipeline directo)

#### Flujo completo: generar CSV — entrenar — predecir

```python
import sys
sys.path.insert(0, '.')  # ejecutar desde la raíz del proyecto

from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

pipeline = ForexIntegratedPipeline(
    horizon=10,          # velas hacia adelante para el target
    rr_ratio=1.5,        # ratio TP/SL para el label BUY/SELL
    min_confidence=0.62, # confianza mínima para dar señal (vs HOLD)
    min_adx=22.0,        # ADX mínimo — filtra mercados ranging
)

# 1. Entrenar el ensemble (XGBoost + LightGBM + RandomForest)
resultado = pipeline.train("CSVs/H1/EURUSD.csv", pair="EURUSD")
print(resultado)
# {'accuracy': 0.66, 'precision': 0.41, 'rows': 17201, ...}

# 2. Predecir señal de la última vela
señal = pipeline.predict("CSVs/H1/EURUSD.csv", pair="EURUSD")
print(señal)
# {'action': 'BUY', 'direction': 'bullish', 'confidence': 0.68, 'adx': 28.4, ...}

# 3. Backtest sobre datos retenidos
bt = pipeline.backtest("CSVs/H1/EURUSD.csv")
print(bt)
# {'win_rate': 0.51, 'profit_factor': 1.03, 'final_balance': 10001.64, ...}

# 4. Modo full (train + predict + backtest en un solo paso)
full = pipeline.run("CSVs/H1/EURUSD.csv", mode="full", pair="EURUSD")

# 5. Multi-horizonte (consenso H5 / H10 / H20)
multi = pipeline.predict_multi_horizon("CSVs/H1/EURUSD.csv", pair="EURUSD")
print(multi)
# {'action': 'BUY', 'bullish_votes': 3, 'bearish_votes': 0, 'avg_confidence': 0.71, ...}
```

---

#### Parámetros del pipeline

| Parámetro | Valor por defecto | Descripción |
|---|---|---|
| `horizon` | `10` | NÂº de velas futuras para calcular el target TP/SL |
| `rr_ratio` | `1.5` | Ratio Riesgo/Beneficio para clasificar BUY vs SELL |
| `min_confidence` | `0.62` | Confianza mínima del ensemble para no dar HOLD |
| `min_adx` | `22.0` | ADX mínimo (mercado trending vs ranging) |

---

#### Modos del pipeline (`pipeline.run(..., mode=...)`)

| Modo | Descripción |
|---|---|
| `"train"` | Solo entrenar y guardar el modelo |
| `"predict"` | Solo predecir (requiere modelo ya entrenado) |
| `"backtest"` | Solo backtest sobre datos retenidos |
| `"multi_horizon"` | Consenso entre horizontes 5, 10 y 20 velas |
| `"full"` | Train + predict + backtest en un solo paso |

---

#### Estructura de la señal devuelta

```python
{
  "action":           "BUY" | "SELL" | "HOLD",
  "direction":        "bullish" | "bearish",
  "confidence":       0.68,          # probabilidad calibrada del ensemble
  "signal_strength":  62.3,          # score 0–100 (confianza 65% + ADX 35%)
  "adx":              28.4,          # ADX de la última vela
  "regime":           "moderate trend" | "ranging" | "strong trend",
  "hold_reason":      None,          # descripción si action=HOLD
  "interpretation":   "Señal BUY de alta calidad — setup favorable detectado."
}
```

---

### Indicadores técnicos incluidos en el análisis

| Grupo | Indicadores calculados |
|---|---|
| Momentum | RSI-14, Williams %R, Estocástico (14,3), Stoch Cross |
| Tendencia | MACD 12/26/9, EMA 20/50/150/200, ADX-14, cruce EMAs |
| Volatilidad | ATR-14, Bollinger Bands (20), volatilidad rolling |
| Ciclo | CCI-20 |
| Volumen | OBV, OBV-EMA, MFI-14 |
| Momentum % | ROC-10, return_5 |
| Patrones vela | Doji, Hammer, Shooting Star, Engulfing alcista/bajista |
| Régimen | volatility_regime, trend_strength, ema_crossovers |

---

## PARTE 4 — Documentos, Web y Utilidades

### Lectura de archivos

```
lee pdf informe.pdf
```
Lee y extrae texto completo de un PDF.

```
lee word contrato.docx
```
Lee un documento Word (.docx o .doc).

```
lee excel ventas.xlsx
```
Lee un archivo Excel y muestra su contenido.

```
lee csv datos.csv
```
Lee un CSV y muestra las primeras filas con estadísticas.

---

### Resumen de documentos

```
resume pdf informe.pdf
```
Genera un resumen del PDF usando el modelo de lenguaje.

---

### Traducción

```
traduce Hola, Â¿cómo estás? al inglés
traduce Hello world al español
translate Good morning to French
```
Traduce texto libre al idioma indicado. Soporta cualquier idioma.

---

### Web

```
extrae web https://ejemplo.com
busca informacion https://docs.python.org
```
Hace scraping de la URL y extrae el texto principal.

---

### Seguridad

```
hash password mipassword123
```
Genera un hash bcrypt seguro.

```
cifrar archivo secreto.txt
```
Cifra un archivo con clave AES.

```
crear jwt
```
Genera un token JWT firmado.

---

### Sistema

```
estado pc
```
Muestra CPU, RAM, disco y uptime del sistema.

```
ayuda
```
Lista todos los comandos disponibles en el asistente.

---

## PARTE 5 — Consultor PYME Avanzado

Todos los módulos generan narración automática con **Llama-3.3-70B** al finalizar.
El archivo de entrada puede ser `.csv` o `.xlsx` con columnas de ingresos/gastos/fecha.

---

### Diagnóstico PYME

```
diagnóstico pyme ventas.csv
```
Genera un Scorecard Multidimensional con tres dimensiones:
- **Salud Financiera** (40%): márgenes bruto/neto, ratio de gastos
- **Salud de Crecimiento** (35%): CAGR, tendencia MoM y YoY
- **Nivel de Riesgo** (25%): volatilidad, concentración, estabilidad

**Resultado:** puntuación 0–100 por dimensión + score global + KPI table + alertas.

---

### Proyección / Forecast

```
forecast negocio ventas.csv
```
Proyección de ingresos a 6 meses (por defecto) con tres bandas:
- **Optimista**: tendencia + 1σ
- **Esperado**: extrapolación lineal (RÂ² como confianza)
- **Conservador**: tendencia — 1σ

```
forecast negocio ventas.csv 12
```
Proyección a 12 meses (añade el número de meses al final).

---

### Plan de Acción

```
plan de accion ventas.csv
recomienda para ventas.csv
```
Llama-3.3-70B analiza el diagnóstico y genera un **Plan Estratégico** con
5 recomendaciones priorizadas — cada una con acción concreta, impacto esperado
y plazo (corto / medio / largo).

---

### Simulación What-If

```
simula que pasa si reduzco costos 15% ventas.csv
que pasa si aumento ventas 20% datos.xlsx
si mejoro margen 10% reporte.csv
```
Aplica el cambio sobre los datos reales y muestra tabla **Antes / Después**
con todas las dimensiones del scorecard y sus deltas.

---

## PARTE 6 — Business Intelligence (BI Engine)

```
analiza negocio ventas.csv
```
KPIs financieros + health score + alertas automáticas.

```
kpis reporte.xlsx
```
Análisis de KPIs sobre un Excel.

```
analisis completo negocio ventas.csv
```
Diagnóstico completo: KPIs + señal ML + recomendaciones narrativas.

```
consulta empresa datos.xlsx
```
Modo consultor PYME básico.

```
entrena negocio historico.csv
```
Entrena un modelo ML sobre datos históricos del negocio.

---

## PARTE 7 — Sistema y Auto-Análisis

```
analiza astra
self analysis
reporte sistema
reporte astra
```
Genera un reporte completo del estado del sistema: motor AI activo,
herramientas registradas, módulos opcionales, roadmap.
El reporte se guarda como `REPORT DD-MM.md` en la raíz del proyecto.

---

### Audio

```
analiza audio entrevista.mp3
```
Analiza un archivo de audio (.mp3, .wav, .ogg, .m4a).

```
voz a texto grabacion.mp3
transcribir audio nota.wav
```
Transcribe audio a texto.

```
texto a voz Hola mundo
```
Convierte texto a audio.

---

### Matemáticas y ML

```
integral x^2
derivada sin(x)
```
Cálculo simbólico con SymPy.

```
entrena modelo datos.csv
```
Entrena un modelo sklearn genérico sobre un CSV.

---

### Memoria

```
recuerda esto: reunión el lunes a las 10
muestra memoria
```
Guarda y recupera notas en la memoria de sesión.

---

## PARTE 8 — Formato de Archivos CSV

### CSV Forex (generado por `creando.py`)

Columnas presentes en todos los CSVs de `CSVs/H1/`, `CSVs/H4/`, `CSVs/D1/`:

| Columna | Tipo | Descripción |
|---|---|---|
| `timestamp` | datetime | Fecha y hora de la vela |
| `open` | float | Precio de apertura |
| `high` | float | Precio máximo |
| `low` | float | Precio mínimo |
| `close` | float | Precio de cierre |
| `volume` | float | Volumen (0 en forex spot) |
| `rsi_14` | float | RSI de 14 períodos |
| `macd` | float | Línea MACD (EMA12 — EMA26) |
| `macd_signal` | float | Señal MACD (EMA9 del MACD) |
| `macd_histogram` | float | Histograma MACD |
| `atr_14` | float | ATR de 14 períodos |
| `ema_20` | float | EMA de 20 períodos |
| `ema_50` | float | EMA de 50 períodos |
| `ema_150` | float | EMA de 150 períodos |
| `bollinger_upper_20` | float | Banda superior Bollinger (20, 2σ) |
| `bollinger_lower_20` | float | Banda inferior Bollinger (20, 2σ) |
| `return_5` | float | Retorno a 5 velas (%) |
| `volatility_20` | float | Volatilidad rolling 20 velas |
| `session` | str | Sesión de mercado: Tokyo / London / NewYork |

### CSV PYME / Negocio

El sistema acepta cualquier CSV con al menos estas columnas
(nombres en español o inglés, indistinto):

| Columna ES | Columna EN | Descripción |
|---|---|---|
| `fecha` | `date` | Fecha del período |
| `ingresos` | `revenue` | Ingresos del período |
| `gastos` | `expenses` | Gastos del período |
| `beneficio` | `profit` | Opcional (se calcula como ingresos — gastos) |

-

---

## PARTE 9 — Memoria de Proyectos y Modelos (Fase 1)

`project_memory.py` extiende la base de datos SQLite con tres tablas nuevas:
`models`, `projects` y `tasks`. Al arrancar ASTRA se muestra automáticamente
un resumen de modelos entrenados, proyectos activos y tareas pendientes.

### Resumen de sesión automático

Al ejecutar `python main.py` verás:
```
  📋  ASTRA — Resumen de sesión
  ────────────────────────────────────────────
  🤖  Modelos entrenados (2):
     EURUSD        precision=71.00%  acc=68.00%      2026-06-30
     XAUUSD        precision=75.00%  acc=72.00%      2026-06-30
  📁  Proyectos activos (1):
     Forex_Prod    Pipeline activo EURUSD/XAUUSD
  ✅  Tareas pendientes (3):
     [1] Forex_Prod  Actualizar CSV julio
```

### Comandos de modelos

```
mis modelos
```
Lista todos los modelos entrenados con precision, accuracy, filas y fecha.

```
info modelo EURUSD
```
Detalle de un modelo específico.

> Los modelos se registran **automáticamente** después de cada `train forex <csv>`.
> No es necesario registrarlos a mano.

---

### Comandos de proyectos

```
mis proyectos
nuevo proyecto Forex_Prod Pipeline EURUSD activo
cerrar proyecto Forex_Prod
pausar proyecto Forex_Prod
```

Status disponibles: `active` → `paused` → `done`.

---

### Comandos de tareas

```
tareas
tareas Forex_Prod
nueva tarea Forex_Prod | Actualizar CSV con datos de julio
completar tarea 3
```

El id de la tarea aparece entre corchetes en el listado.

---

## PARTE 10 — Watcher y Señales Forex (Fase 2)

`forex_watcher.py` monitorea un CSV en background (thread daemon).
`signal_tracker.py` persiste cada señal BUY/SELL/HOLD generada en SQLite.

### Iniciar monitoreo de un par

```
watch forex EURUSD CSVs/H1/EURUSD.csv 60
```
Monitorea `EURUSD.csv` cada **60 segundos**. Si el CSV cambia (nuevo dato de MT5
o yfinance), re-entrena automáticamente el modelo antes de predecir.

Intervalo mínimo: 10 segundos. Sin especificar: 60 segundos por defecto.

```
watch forex XAUUSD CSVs/H1/XAUUSD.csv 120
```
Puedes tener múltiples pares activos simultáneamente.

---

### Control del watcher

```
watch status
```
Ver qué pares están siendo monitoreados y con qué intervalo.

```
watch check EURUSD
```
Forzar una evaluación inmediata sin esperar el intervalo.

```
watch stop EURUSD
watch stop all
```

---

### Historial de señales

```
señales EURUSD
señales
```
Muestra las últimas 10 señales del par (o de todos los pares).
Incluye barra de fuerza visual, confidence, ADX, régimen y razón de HOLD.

```
stats señales EURUSD
stats señales
```
Ratio BUY/SELL/HOLD, confidence promedio y strength promedio.

> Las señales también se guardan automáticamente al ejecutar `predict forex` y `full forex`.

---

## PARTE 11 — Active Engine Scheduler (Fase 3)

`active_engine.py` usa la librería `schedule` en un thread daemon para ejecutar
evaluaciones Forex de forma periódica sin necesidad de cron ni servicios externos.
100% compatible con Windows.

### Programar evaluación periódica

```
schedule forex EURUSD CSVs/H1/EURUSD.csv 60
```
Evalúa señal EURUSD cada 60 minutos. La señal se guarda en `signal_tracker`
automáticamente. Notificación en consola solo si la señal es BUY o SELL.

El engine se **auto-inicia** al registrar el primer trabajo. No hace falta
llamar a ningún comando de arranque.

---

### Control del scheduler

```
schedule status
```
Ver trabajos activos con nombre, intervalo y próxima ejecución.

```
schedule run forex_EURUSD
```
Forzar ejecución inmediata de un trabajo por nombre.

```
schedule stop forex_EURUSD
schedule stop all
```

> Los nombres de trabajos Forex siguen el patrón `forex_<PAR>`, ej. `forex_EURUSD`.

---

## PARTE 12 — News Intelligence (Fase 4)

`news_intelligence.py` obtiene noticias de Yahoo Finance y FXStreet,
analiza el sentimiento con **Llama-3.3-70B** (Groq) y combina la señal
técnica con el sentimiento para generar una recomendación final ponderada.

**Ponderación:** `70% señal técnica + 30% sentimiento noticias`

Si técnico y noticias coinciden en dirección → señal **REFORZADA**.
Si discrepan → señal reducida o HOLD.

### Solo noticias + sentimiento

```
noticias EURUSD
noticias XAUUSD
```
Muestra los últimos artículos de Yahoo Finance y FXStreet, y el score
de sentimiento generado por Llama (-1.0 muy bearish → +1.0 muy bullish).

Ejemplo de salida:
```
  NOTICIAS — EURUSD  (8 artículos)
  ────────────────────────────────────────────────────────────────
  [Yahoo Finance] EUR rallies as ECB signals rate hike
  [FXStreet     ] Euro holds gains ahead of US CPI data
  ...
  SENTIMIENTO  : BULLISH  score=+0.62  confianza=80%
  Análisis     : Las noticias reflejan expectativas alcistas en EUR...
```

---

### Señal combinada (técnico + noticias)

```
noticias predice EURUSD CSVs/H1/EURUSD.csv
```
Ejecuta el predictor técnico + scraping de noticias + análisis Llama.
Devuelve la decisión final con desglose de ambos componentes:

```
  ▲  ANÁLISIS COMBINADO — EURUSD
  ══════════════════════════════════════════════════════════════
  SEÑAL TÉCNICA   : BUY    conf=72.00%  adx=28.3  (moderate trend)
  SENTIMIENTO     : BULLISH   score=+0.62  confianza=80%
  SCORE COMBINADO : +0.6934  (70% técnico + 30% noticias)

  DECISIÓN: BUY
  Señal BUY REFORZADA — técnico y noticias alineados. Score: +0.6934
```

---

### Pares soportados en News Intelligence

| Par | Fuente Yahoo Finance |
|---|---|
| EURUSD | EURUSD=X |
| GBPUSD | GBPUSD=X |
| USDJPY | USDJPY=X |
| XAUUSD | GC=F (Gold Futures) |
| XAGUSD | SI=F (Silver Futures) |
| USOIL  | CL=F (WTI Crude) |
| UKOIL  | BZ=F (Brent Crude) |

> Si Llama no está disponible (sin API key), el análisis usa un fallback
> heurístico por keywords (bullish/bearish) con confianza reducida (40%).

---

## APÉNDICE — Referencia rápida de comandos
## APÁNDICE — Referencia rápida de comandos

| Comando | Ejemplo |
|---|---|
| Generar CSVs (yfinance) | `python creando.py --modo yfinance --timeframe H1,H4,D1` |
| Generar CSVs (pares específicos) | `python creando.py --modo yfinance --timeframe H1 --pares EURUSD XAUUSD` |
| Generar CSVs (MT5, Windows) | `python creando.py --modo mt5 --timeframe H1,H4,D1` |
| Análisis forex (chat) | `analiza forex eurusd CSVs/H1/EURUSD.csv` |
| Historial análisis | `history eurusd` |
| Comparar reportes | `compare history eurusd` |
| Ver mercados analizados | `list markets` |
| Diagnóstico PYME | `diagnóstico pyme ventas.csv` |
| Forecast | `forecast negocio ventas.csv 12` |
| Plan de acción | `plan de accion ventas.csv` |
| Simulación | `simula que pasa si reduzco costos 15% ventas.csv` |
| BI análisis | `analiza negocio ventas.csv` |
| Leer PDF | `lee pdf informe.pdf` |
| Traducir | `traduce Hola mundo al inglés` |
| Extraer web | `extrae web https://ejemplo.com` |
| Hash password | `hash password mipassword` |
| Estado PC | `estado pc` |
| Auto-análisis ASTRA | `analiza astra` |
| Diagnóstico instalación | `python check_startup.py` |
| Mis modelos | `mis modelos` |
| Info de un modelo | `info modelo EURUSD` |
| Nuevo proyecto | `nuevo proyecto Forex_Prod Pipeline activo` |
| Listar tareas | `tareas Forex_Prod` |
| Nueva tarea | `nueva tarea Forex_Prod | Actualizar CSV julio` |
| Completar tarea | `completar tarea 3` |
| Watcher Forex | `watch forex EURUSD CSVs/H1/EURUSD.csv 60` |
| Ver pares activos | `watch status` |
| Historial señales | `señales EURUSD` |
| Stats señales | `stats señales EURUSD` |
| Scheduler Forex | `schedule forex EURUSD CSVs/H1/EURUSD.csv 60` |
| Estado scheduler | `schedule status` |
| Noticias + sentimiento | `noticias EURUSD` |
| Señal combinada | `noticias predice EURUSD CSVs/H1/EURUSD.csv` |

---

## PARTE 13 — Predicción Forex para Inversión Real (Guía Paso a Paso)

> Esta sección cubre el flujo completo recomendado para usar ASTRA en trading real,
> incluyendo todos los controles de riesgo. Sigue los pasos en orden y no saltes ninguno.

---

### 9.1 Qué necesitas antes de empezar

Antes de ejecutar el primer comando, verifica que tienes:

| Requisito | Dónde obtenerlo |
|-----------|----------------|
| Archivo CSV del par en H1 | MetaTrader 5 → Historia → exportar |
| Mismo par en H4 y D1 | Misma carpeta raíz, subcarpetas H4/ y D1/ |
| Al menos 5.000 filas H1 (≈ 2 años) | Sin este mínimo el modelo no generaliza |
| Python con dependencias instaladas | `python setup_windows.py verify` |

**Estructura de carpetas obligatoria:**

```
CSVs/
├── H1/
│   └── EURUSD.csv       ← archivo principal
├── H4/
│   └── EURUSD.csv       ← mismo par, timeframe H4
└── D1/
    └── EURUSD.csv        ← mismo par, timeframe D1
```

> **Por qué importa:** El sistema detecta automáticamente H4 y D1 buscando en las
> carpetas hermanas. Si la estructura no es esta, el pipeline corre solo con H1 y la
> precisión cae entre 5–10%.

---

### 9.2 Paso 1 — Verificar el CSV antes de entrenar

Antes de entrenar, comprueba que tu CSV no tiene problemas que contaminen el modelo.

```
Tú: analiza forex EURUSD CSVs/H1/EURUSD.csv
```

ASTRA mostrará un resumen del par. Lo que debes verificar:

- **Filas cargadas:** mínimo 5.000 (idealmente 10.000+)
- **NaN < 5%:** si hay más, el CSV tiene datos faltantes
- **Gaps de fin de semana:** el sistema los filtra automáticamente — verás algo como
  `[CSV ADAPTER] Gap filter: 438 velas post-gap eliminadas` (esto es normal y correcto)

**Ejemplo de salida correcta:**

```
[CSV ADAPTER] Gap filter: 438 velas post-gap eliminadas
[CSV ADAPTER] MTF H4 merged: 9 cols
[CSV ADAPTER] MTF D1 merged: 9 cols
[CSV ADAPTER] Rows: 16877 | Pair: EURUSD | Columns: 39
```

**Si ves `MTF H4 merged: 0 cols`** → no encuentra el H4. Verifica la estructura de carpetas.

---

### 9.3 Paso 2 — Ejecutar el pipeline completo (full forex)

El comando `full forex` hace en un solo paso:
1. Tuneo de hiperparámetros con Optuna (75 trials)
2. Entrenamiento con Walk-Forward Validation (5 folds)
3. Señal sobre la última vela disponible
4. Backtesting sobre datos históricos

```
Tú: full forex CSVs/H1/EURUSD.csv
```

**Qué mirar en la salida:**

```
[WFV] avg_prec=68.21%  median_prec=67.50%  avg_acc=64.10%
[WFV] ✓ APROBADO — avg=68.21%  median=67.50%
```

El modelo se aprueba si `avg_prec >= 65%`. Si ves `✗ NO APROBADO`, el modelo
no está listo — ver sección 9.5 (solución de problemas).

**Métricas del backtesting:**

```
Trades: 1079  |  Win Rate: 57.5%  |  PF: 2.23  |  E[R]: 0.0000
```

Para trading real necesitas:
- **Win Rate ≥ 52%** con RR=1.0, o ≥ 45% con RR=2.0
- **Profit Factor ≥ 1.5** (cuánto ganas por cada dólar perdido)
- **Sharpe > 0.5** (más es mejor; > 1.0 es bueno)

---

### 9.4 Paso 3 — Interpretar la señal generada

```
╔══ ASTRA FOREX SIGNAL ══╗
  Signal     : ▼ SELL
  Pair       : EURUSD
  Confidence : 0.84
  Strength   : [███████░░░] 77.9/100
  ADX        : 24.2
  Regime     : weak trend
  Rows       : 16877
```

**Qué significa cada campo:**

| Campo | Qué indica | Umbral para operar |
|-------|-----------|-------------------|
| `Signal` | Dirección: BUY / SELL / HOLD | Solo operar en BUY o SELL |
| `Confidence` | Probabilidad calibrada del modelo (0–1) | ≥ 0.62 para operar |
| `Strength` | Combina confianza + ADX en escala 0–100 | ≥ 50 para considerar |
| `ADX` | Fuerza de tendencia del mercado | ≥ 22 (mercado con tendencia) |
| `Regime` | Clasificación del mercado actual | Preferir "moderate/strong trend" |

> **Regla de oro:** Si el modelo dice HOLD, no operes. El sistema usa ADX como filtro
> de régimen — en mercados laterales (ranging) las señales son ruido.

---

### 9.5 Paso 4 — Verificar el circuit breaker antes de cada operación

El circuit breaker protege tu capital deteniendo el trading automáticamente si las
pérdidas superan los límites configurados.

```
Tú: circuit status
```

**Salida cuando todo está bien:**

```
══════════════════════════════════════════════════════
  CIRCUIT BREAKER — 🟢 ABIERTO
──────────────────────────────────────────────────────
  Balance actual   :  $10,000.00
  Peak histórico   :  $10,250.00
  Pérdida diaria   :   1.20%  (límite: 3%)
  Pérdida semanal  :   2.10%  (límite: 6%)
  Drawdown         :   2.44%  (límite: 10%)
══════════════════════════════════════════════════════
```

**Salida cuando está bloqueado (no debes operar):**

```
══════════════════════════════════════════════════════
  CIRCUIT BREAKER — 🔴 BLOQUEADO
──────────────────────────────────────────────────────
  🚨 Motivo bloqueo : Pérdida diaria 3.30% ≥ límite 3.00%
  ⏱  Cooldown resto : 22.5h
══════════════════════════════════════════════════════
```

Los límites que activan el bloqueo son:

| Límite | Valor | Cooldown tras activación |
|--------|-------|--------------------------|
| Pérdida diaria | 3% del balance del día | 24 horas |
| Pérdida semanal | 6% del balance semanal | 24 horas |
| Drawdown máximo | 10% desde el pico histórico | 24 horas |

> **No resetees el circuit breaker manualmente salvo que hayas identificado y
> corregido la causa de las pérdidas.** Usar `circuit reset` para evitar el cooldown
> es la forma más rápida de perder el capital.

---

### 9.6 Paso 5 — Calcular el tamaño de posición (position sizing)

Una vez que tienes señal válida (BUY o SELL) y el circuit breaker está abierto,
calcula cuánto arriesgar en la operación.

```
Tú: position size EURUSD 10000
```

**Salida:**

```
══════════════════════════════════════════════════════
  POSITION SIZING — EURUSD
──────────────────────────────────────────────────────
  Balance       : $10,000.00
  Señal         : BUY  (conf=80.00%)
  Método        : Kelly Fraccionado (x0.25)
  Kelly raw     : 0.3200
  Riesgo        : 1.600%  →  $160.00
  Unidades      : 8,000.00
  Trades hist.  : 47
══════════════════════════════════════════════════════
```

**Cómo leer el resultado:**

- **Kelly raw:** el Kelly teórico puro calculado del historial de trades
- **Riesgo %:** el Kelly ya fraccionado (x0.25) y clampeado entre 0.5%–2.0%
- **Riesgo USD:** el dinero máximo que puedes perder en esta operación
- **Unidades:** tamaño aproximado de posición (ajusta según el apalancamiento de tu broker)
- **Método "conservative":** si tienes menos de 20 trades en historial, se usa 0.5% fijo

> **Regla crítica:** El riesgo máximo por operación está clampeado al 2% del balance.
> Nunca aumentes este límite aunque el modelo tenga alta confianza.

---

### 9.7 Paso 6 — Monitoreo continuo con el scheduler

Para que ASTRA evalúe el par automáticamente cada hora sin que tengas que escribir
comandos manualmente:

```
Tú: schedule forex EURUSD CSVs/H1/EURUSD.csv 60
```

Cada 60 minutos ASTRA:
1. Verifica el circuit breaker (si está bloqueado, no evalúa)
2. Carga el CSV actualizado y genera la señal
3. Guarda la señal en historial
4. Muestra el position sizing si la señal es BUY o SELL
5. Notifica en pantalla solo si hay acción (no spam con HOLDs)

**Para ver el historial de señales generadas:**

```
Tú: señales EURUSD
```

**Para detener el monitoreo:**

```
Tú: schedule stop EURUSD
```

---

### 9.8 Paso 7 — Validar el modelo con múltiples pares (scan)

Antes de operar con dinero real, escanea todos tus pares a la vez para tener
una visión global de las oportunidades:

```
Tú: scan forex CSVs/H1/
```

ASTRA procesará todos los CSV en esa carpeta y mostrará un ranking:

```
╔══ MULTI-PAIR SCANNER — 8 pairs ══╗
  BUY Signals (2):
    ▲  EURUSD  conf=0.81  strength=74.2  ADX=26.1
    ▲  GBPJPY  conf=0.76  strength=68.0  ADX=23.8

  SELL Signals (1):
    ▼  USDJPY  conf=0.79  strength=71.0  ADX=28.4

  HOLD (5):
    AUDCAD, NZDUSD, EURCAD, GBPUSD, XAUUSD
```

Cada señal generada por el scanner queda registrada automáticamente en el
historial. Puedes verla con `señales <par>`.

---

### 9.9 Checklist completo antes de cada operación real

Usa esta lista antes de abrir cualquier posición con dinero real:

```
[ ] 1. El modelo del par está entrenado y aprobado (WFV avg ≥ 65%)
[ ] 2. La señal es BUY o SELL (no HOLD)
[ ] 3. Confidence ≥ 0.62
[ ] 4. ADX ≥ 22 (mercado con tendencia)
[ ] 5. Circuit breaker está ABIERTO (verde)
[ ] 6. Position sizing calculado (riesgo ≤ 2% del balance)
[ ] 7. Stop loss definido antes de abrir la posición
[ ] 8. Take profit definido (TP = SL × RR, donde RR ≥ 1.0)
[ ] 9. No hay noticias de alto impacto en las próximas 2 horas
         (verificar en https://www.forexfactory.com/calendar)
[ ] 10. Has esperado al menos 3 meses de paper trading con este par
```

> **Si algún punto del checklist está en rojo → no operes.** El modelo puede
> generar señales técnicamente correctas y aun así perder dinero si el contexto
> macroeconómico va en contra. Las noticias de banco central (FOMC, BCE, BOJ)
> anulan cualquier señal técnica.

---

### 9.10 Solución de problemas comunes

#### El WFV no se aprueba (avg_prec < 65%)

**Causa más frecuente:** datos insuficientes o el par tiene mucha variabilidad entre períodos.

**Solución paso a paso:**
1. Verificar que tienes al menos 5.000 filas H1: `analiza forex EURUSD CSVs/H1/EURUSD.csv`
2. Añadir H4 y D1 en la estructura correcta
3. Re-ejecutar con tuneo explícito primero:
   ```
   Tú: tune forex CSVs/H1/EURUSD.csv
   Tú: train forex CSVs/H1/EURUSD.csv
   ```
4. Si sigue sin aprobar, el par no es predecible con los datos actuales —
   busca otro par o espera a tener más datos históricos.

#### La señal siempre es HOLD

**Causa:** ADX < 22 (mercado lateral) o confidence < 0.62 (modelo inseguro).

**Esto es correcto.** El sistema está diseñado para no operar en condiciones desfavorables.
Espera a que el mercado entre en tendencia. Puedes verificar el ADX actual con:
```
Tú: analiza forex EURUSD CSVs/H1/EURUSD.csv
```

#### El circuit breaker está bloqueado inesperadamente

**Causa:** pérdidas acumuladas del día/semana superaron el límite.

**No resetees de inmediato.** Primero:
1. Revisa el historial: `señales EURUSD`
2. Analiza si las pérdidas son del modelo o de condiciones de mercado excepcionales
3. Si es mercado excepcional (noticia inesperada, gap de apertura), puedes resetear:
   ```
   Tú: circuit reset
   ```
4. Si son pérdidas del modelo, espera el cooldown de 24h y ajusta los parámetros.

#### `[DATASET] Filas train: X | BUY: 20% | SELL: 80%`

**Causa:** desbalance extremo en las etiquetas. Con rr_ratio=1.0, el mercado actual
es muy bajista o muy alcista en los datos de entrenamiento.

**Solución:** el sistema aplica SMOTE automáticamente para balancear. Si el desbalance
es mayor de 80/20, considera actualizar el CSV con datos más recientes.

---

### 9.11 Flujo recomendado para un par nuevo

Si vas a añadir un par nuevo que nunca has entrenado, sigue este flujo exacto:

```bash
# Paso 1: Obtener datos (si usas yfinance)
python creando.py --modo yfinance --pares GBPJPY --dias 730

# Paso 2: Verificar el CSV
Tú: analiza forex GBPJPY CSVs/H1/GBPJPY.csv

# Paso 3: Pipeline completo (tune + train + signal + backtest)
Tú: full forex CSVs/H1/GBPJPY.csv

# Paso 4: Revisar métricas
#   - WFV avg_prec ≥ 65% → continuar
#   - Win Rate ≥ 52% → continuar
#   - PF ≥ 1.5 → continuar

# Paso 5: Verificar circuit breaker
Tú: circuit status

# Paso 6: Calcular position sizing para la primera operación
Tú: position size GBPJPY 10000

# Paso 7: Activar monitoreo continuo
Tú: schedule forex GBPJPY CSVs/H1/GBPJPY.csv 60

# Paso 8 (OBLIGATORIO antes de dinero real):
# Opera en demo al menos 60 días y registra los resultados manualmente.
# Solo pasa a real si el win rate real >= 50% y el P&L es positivo.
```

**Ejemplo de resultado esperado tras `full forex CSVs/H1/GBPJPY.csv`:**

```
[WFV] avg_prec=67.80%  median_prec=66.50%  avg_acc=62.10%
[WFV] ✓ APROBADO — avg=67.80%  median=66.50%

╔══ ASTRA FOREX SIGNAL ══╗
  Signal     : ▲ BUY
  Pair       : GBPJPY
  Confidence : 0.79
  Strength   : [███████░░░] 72.3/100
  ADX        : 31.4
  Regime     : moderate trend

Trades: 847  |  Win Rate: 58.2%  |  PF: 1.87  |  Sharpe: 0.74
```

Con estos números el modelo es candidato para paper trading. Con Sharpe > 1.0
y 90+ días de demo positivos, es candidato para trading real con capital pequeño.

---

### 9.12 Resumen del flujo de producción (diagrama)

```
                    ┌─────────────────────┐
                    │   Nuevo par / CSV   │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  full forex <csv>   │  ← tune + train + signal + backtest
                    └──────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                 │
         WFV ≥ 65%?      Win Rate ≥ 52%?    PF ≥ 1.5?
              │                │                 │
           SI ✓             SI ✓              SI ✓
              └────────────────┴─────────────────┘
                               │
                    ┌──────────▼──────────┐
                    │  60+ días de demo   │  ← schedule forex + registrar resultados
                    └──────────┬──────────┘
                               │
                    ¿Demo P&L positivo?
                               │
                            SI ✓
                               │
                    ┌──────────▼──────────┐
                    │  circuit status     │  ← antes de CADA operación
                    └──────────┬──────────┘
                               │
                    ¿Circuit ABIERTO?
                               │
                            SI ✓
                               │
                    ┌──────────▼──────────┐
                    │  position size      │  ← cuánto arriesgar
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  Abrir posición     │  ← stop loss + take profit definidos
                    │  en el broker       │
                    └─────────────────────┘
```

---

*Parte 9 añadida el 30 de junio de 2026 — ASTRA v3.0 (Risk Management integrado)*

## PARTE 14 — PREDICTION LAB (FASE 5, COMPLETA)

Sistema que toma una idea en lenguaje natural + un CSV y evalúa si se puede
construir un predictor útil, antes de invertir tiempo entrenando modelos.
Estado actual: 7 de 7 módulos construidos, probados end-to-end con datos
reales (COTTON) e integrados a `main.py`. Los resultados de `lab valida` se
persisten como JSON en `lab_reports/` y se consultan con 5.7 (abajo).

### 5.1 — Analizar una idea
```
lab analiza "quiero predecir si el precio sube o baja en las próximas 10 velas usando RSI y MACD"
```
Extrae un `ProblemSpec`: tipo de problema, dominio, variable objetivo,
features candidatas, horizonte, tipo de salida esperada. Usa LLM
(Groq/Llama) si hay API key; si no, cae a un heurístico por keywords/regex.

### 5.2 — Analizar un dataset
```
lab dataset ruta/al/archivo.csv [target_variable]
```
Analiza el CSV en profundidad: filas/columnas, % de NaN, balance del
target, correlaciones, multicolinealidad (VIF), outliers, skew/kurtosis.
Devuelve un score de calidad 0-100 por 6 dimensiones. Si no se especifica
`target_variable`, intenta detectarlo por nombre común (target, label,
churn, signal, etc.) y lo valida contra las columnas reales del CSV.

### 5.3 — Evaluar viabilidad ⭐
```
lab viabilidad ruta/al/archivo.csv "describe tu idea aquí"
```
Componente central: encadena 5.1 + 5.2 y calcula un Índice de Viabilidad
0-100 (datos 25%, calidad 20%, balance 15%, señal 20%, complejidad 10%,
horizonte 10%). Si no se puede identificar un target real, fuerza
viabilidad = 0 y "NO VIABLE" — nunca reporta un score calculado sobre
datos inexistentes. Umbral de viabilidad: 40/100.

### 5.4 — Generar plan de modelo
```
lab planea ruta/al/archivo.csv "describe tu idea aquí"
```
Encadena 5.1 + 5.2 + 5.3 y, si la viabilidad alcanza el umbral, genera un
plan concreto: qué algoritmos usar (XGBoost/LightGBM/RandomForest/baseline,
según tamaño del dataset y tipo de problema), qué features crear/imputar/
codificar/descartar, qué estrategia de validación aplicar (walk-forward
para series de tiempo/forex, k-fold o holdout según el tamaño), si conviene
SMOTE (balance <55) y calibración. Si el dominio es forex o business,
señala explícitamente que ya existe un pipeline propio (`forex/prediction/`
o `forex/business/`) antes de sugerir construir uno nuevo desde cero. Si la
viabilidad es insuficiente, no genera plan — explica el motivo.

### 5.5 — Generar pipeline ejecutable
```
lab genera ruta/al/archivo.csv "describe tu idea aquí"
```
Encadena 5.1-5.4 y, si el plan es válido, construye un `sklearn.Pipeline`
real y ejecutable (`ColumnTransformer` con imputación numérica/categórica +
OneHotEncoder + el ensemble de algoritmos del plan vía Voting), más el
código Python equivalente para copiar y correr fuera del CLI. Si falta
xgboost/lightgbm, sustituye por un equivalente sklearn del mismo tipo de
problema (nunca cambia classifier↔regressor) y lo deja registrado en las
notas — nunca en silencio. Si el tipo de problema no quedó claro en la
idea, se infiere del target real del dataset (numérico → regresión,
categórico → clasificación) en vez de asumir clasificación por defecto.
Las features de dominio sugeridas (RSI, lags, etc.) no se generan
automáticamente — si el dominio es forex/business, recuerda reutilizar
los módulos de feature engineering ya existentes.


### 5.6 — Entrenar y validar (score real)
```
lab valida ruta/al/archivo.csv "describe tu idea aquí"
```
Encadena 5.1-5.5 y entrena de verdad el pipeline con la estrategia que
definió el Model Planner: holdout, k-fold (con StratifiedKFold si aplica),
o walk-forward con purge gap para forex/timeseries (ventana/step se
adaptan al tamaño real del dataset, se degrada solo si es muy chico).
Aplica SMOTE si el plan lo indica (con fallback si `imblearn` no está
instalado). Reporta score medio ± desviación entre folds, veredicto
PASA/NO PASA contra la métrica mínima esperada, y las features más
importantes (alineadas correctamente incluso con columnas one-hot
expandidas). Para regresión, el veredicto usa R² (0-1, comparable con
clasificación) en vez de una métrica derivada de RMSE que dependía de la
magnitud absoluta del target.

### 5.7 — Generar reporte final y consultar proyectos
```
lab reporte ruta/al/archivo.csv "describe tu idea aquí" [target_variable]
lab proyectos
lab info proyecto <nombre_o_id>
```
`lab reporte` encadena 5.1-5.6 completo y arma un reporte final PASA/NO
PASA con el veredicto, el score real de validación, las features más
importantes y una recomendación (desplegar / reentrenar / descartar). Se
guarda automáticamente como JSON en `lab_reports/`. `lab proyectos` lista
todos los reportes generados hasta ahora (uno por corrida). `lab info
proyecto <nombre>` muestra el detalle completo de un reporte guardado.
Los 5 comandos `lab` (viabilidad/planea/genera/valida/reporte) aceptan un
`target_variable` explícito opcional al final del comando — si no se
especifica, se usa la misma heurística de detección de 5.2.

---

## PARTE 15 — FEEDBACK SYSTEM (FASE 6, COMPLETA)

Sistema de retroalimentación humana sobre señales y modelos: permite votar
si una señal fue acertada o no, analiza el patrón de aprobación por par/
componente, ajusta umbrales de confianza/ADX de forma adaptativa según ese
feedback, y guarda una capa de "memoria contextual" con lo aprendido.
Todo se persiste en `memoria.db` (misma DB que usa el resto de ASTRA).

```
feedback votar <target_id> <voto>      # voto: 1 (acierto) o -1 (fallo)
feedback ver <target_id>               # historial de votos de una señal/componente
feedback analisis                      # patrón de aprobación agregado por componente
feedback dashboard                     # resumen visual del estado del feedback
thresholds ver                         # umbrales de confianza/ADX actuales por par
contextual memoria                     # qué ha "aprendido" el sistema del feedback reciente
```

> **Nota importante:** los umbrales que ajusta `thresholds` (Fase 6) todavía
> NO son leídos por el predictor real (`forex/prediction/predictor.py` usa
> siempre `MIN_CONFIDENCE=0.65`/`MIN_ADX=22.0` fijos). Por ahora esta capa
> es de seguimiento/aprendizaje y alimenta las propuestas de Fase 7 — la
> conexión directa con el predictor queda pendiente para una fase futura.

Al terminar cada `full forex`, el sistema imprime `Signal ID: <PAR>_<id>` —
ese es el ID que se usa en `feedback votar <id> <voto>`.

---

## PARTE 16 — EVOLUTION ENGINE (FASE 7, COMPLETA)

Motor que analiza el estado del sistema (feedback, modelos, señales) y
detecta oportunidades de mejora reales (reentrenar un par con pocos datos,
ajustar umbrales de un componente con feedback consistente, etc.), las
convierte en propuestas concretas, y las aplica cuando corresponde.

```
monitor snapshot                       # estado actual: señales, modelos, feedback
monitor historial [n]                  # snapshots anteriores
mejoras detectar                       # detecta oportunidades de mejora sin generar propuestas
evolucionar                            # detecta oportunidades Y genera propuestas formales
propuestas ver [status]                # lista propuestas (pending/approved/rejected/applied)
propuesta aplicar <id>                 # aplica una propuesta ya aprobada
```
`propuesta aprobar <id>` y `propuesta rechazar <id>` viven ahora en la
Parte 17 (Constitution) — el aprobar de Fase 7 fue reemplazado por el
flujo constitucional real.

El feedback de un par específico (ej. EURUSD) solo mueve los umbrales de
ESE par — nunca se mezcla con el de otros pares/commodities.

---

## PARTE 17 — CONSTITUTION ENGINE (FASE 8, COMPLETA)

Capa de gobernanza sobre la Fase 7: ninguna propuesta de ajuste de
umbrales se aplica sin pasar antes por reglas constitucionales duras
(ej. nunca por debajo de 65% de confianza o ADX 22, alineado con los
valores reales del predictor de producción). Cada aprobación crea un
punto de restauración (rollback point) automático, y toda decisión queda
en un registro de auditoría inmutable.

```
reglas ver                             # las 7 reglas constitucionales activas
propuesta validar <id>                 # vista previa: valida una propuesta sin aprobarla
propuesta aprobar <id>                 # valida + aprueba + crea rollback point automático
propuesta rechazar <id>                # rechaza una propuesta pendiente
audit ver [n]                          # historial de decisiones (aprobar/rechazar/bloquear)
rollback ver                           # lista los rollback points disponibles
rollback aplicar <id>                  # restaura los umbrales de un par a un punto anterior
```

Si un ajuste de umbral (Fase 6/7) intentaría bajar la confianza o el ADX
por debajo del mínimo constitucional, `propuesta aplicar <id>` lo
**bloquea automáticamente** (queda como `rejected` con el motivo exacto)
en vez de aplicarlo silenciosamente — esto es lo que impide que el
sistema se auto-debilite con el tiempo.

---

## PARTE 18 — CICLO EVOLUTIVO COMPLETO (FASE 9, COMPLETA)

Orquesta en un solo comando las Fases 6, 7 y 8: monitorea el rendimiento del
sistema, detecta oportunidades de mejora, genera propuestas, las valida
contra la constitución, las aprueba o rechaza, ajusta umbrales de feedback
y registra todo en el audit log — de punta a punta, sin intervención manual
paso a paso.

```
evolucionar ciclo                # ciclo completo, sin auto-aprobar ajustes menores
evolucionar ciclo auto           # igual, pero auto-aprueba ajustes menores de umbral
salud sistema                    # reporte combinado: snapshot + propuestas + audit log
```

**Flujo interno de `evolucionar ciclo`:**

```
monitor snapshot (toma foto del estado actual)
      ↓
detecta oportunidades de mejora (Fase 7)
      ↓
genera propuestas concretas
      ↓
valida cada propuesta contra la constitución (Fase 8)
      ↓
aprueba o rechaza (con rollback point automático si aprueba)
      ↓
ajusta umbrales de feedback donde corresponda (Fase 6)
      ↓
registra todo en el audit log (Fase 8)
```

Probado de punta a punta con datos 100% reales de COTTON: `full forex`
generó una señal real → se votó feedback real sobre ella → `evolucionar
ciclo` detectó 1 oportunidad real, generó 1 propuesta, la validó y la
aprobó → `salud sistema` confirmó el estado consistente (señales, modelos,
pares activos, eventos evolutivos y entradas de audit log, todo cuadrando).

Con esto, el roadmap de Fases 1 a 9 queda cerrado: ASTRA no solo predice y
opera, sino que monitorea su propio rendimiento, propone sus propias
mejoras, las valida contra reglas fijas y aprende de la aprobación/rechazo
del usuario — el ciclo evolutivo autónomo completo.

---

*Parte 18 añadida el 3 de julio de 2026 — ASTRA Roadmap v4.0 completo (Fases 1–9) ✅*

## PARTE 19 — WORKSPACE (ROADMAP IV, SECCIONES 1-3)

Transformación de ASTRA de aplicación de consola a un entorno de trabajo
visual. Sirve una SPA conectada al mismo motor real que usa `main.py` —
nada de datos simulados.

```
pip install -r requirements.txt   # incluye fastapi, uvicorn, python-multipart
python workspace/server.py
```

Abre **http://localhost:8000** en el navegador.

### Sección 1 — Workspace Principal
- Barra superior (1.1): estado de conexión, modelo LLM activo, proyecto
  activo (real, desde `project_memory.py`), cantidad de herramientas
  cargadas, hora.
- Navegación (1.2) entre las 7 ramas: Chat, Forex Lab, Prediction Lab,
  Business Lab, Cognitive Core, Evolution Engine, Configuración. Las 6
  ramas no-Chat quedan como placeholders navegables — se conectan en las
  Secciones 4, 5, 6, 7 y 8 del Roadmap IV.

### Sección 2 — Barra de Estado Permanente
Barra inferior con telemetría real, en vivo (poll cada 5s):
- CPU / RAM reales vía `psutil` (GPU: reportado honestamente como "no
  disponible" — el proyecto no tiene librería de monitoreo GPU integrada).
- Active Engine: watchers de `forex_watcher.py` y jobs programados de
  `active_engine.py`, conteos reales.
- Cognitive Core: total de entradas en `memoria.db` + turnos de la sesión
  actual.
- Evolution Engine: eventos evolutivos totales + propuestas pendientes
  reales (`feedback/evolution_memory.py`, `evolution/proposal_store.py`).
- Contador de peticiones a la API y tiempo promedio de respuesta, medidos
  en el propio proceso del servidor del Workspace.

### Sección 3 — Chat Center (mejorado)
- **Motor real completo**: el chat ahora pasa por `main.dispatch_command()`
  — el mismo dispatcher estricto que usa la consola (`full forex`, `monitor
  snapshot`, `reglas ver`, `feedback votar`, `evolucionar ciclo`, etc.),
  con fallback automático a `process_request()` (intent_router + chat)
  cuando el mensaje no calza con ningún comando estricto. Antes (Sección 1
  inicial) el chat del Workspace solo tenía acceso al fallback — ahora
  tiene acceso a TODAS las Fases 1-9 igual que la consola.
- **3.1 Entrada enriquecida**: botón para adjuntar archivo, botón para
  adjuntar carpeta completa, y arrastrar-y-soltar directamente sobre la
  ventana de chat. Los archivos se guardan en `workspace/uploads/` y su
  ruta se referencia automáticamente en el siguiente mensaje enviado.
- **3.2 Historial y gestión**: el chat carga el historial real de
  `memoria.db` al abrir la página (`cargar_turnos()`), botón "Copiar" por
  mensaje, y botón "Exportar" que descarga la conversación visible como
  `.txt`.
- **3.3 Metadatos de respuesta**: cada respuesta de ASTRA muestra el tiempo
  de ejecución real (medido en el servidor) y una etiqueta del módulo que
  respondió (Forex Lab, Prediction Lab, Evolution Engine, Constitution
  Engine, Cognitive Core, Sistema, o Chat General).

Todo lo que se conversa desde el Workspace también se registra en
`memoria.db` (`log_command` + `guardar_memoria`), igual que la consola —
por lo que el "acciones recientes del usuario" y el historial de comandos
reflejan uso desde ambas interfaces por igual.

**Endpoints disponibles:**
`GET /api/status` · `GET /api/telemetry` · `POST /api/chat {"message": "..."}`
· `GET /api/chat/history?limit=N` · `POST /api/upload` (multipart/form-data).

---

*Parte 19 actualizada el 6 de julio de 2026 — Roadmap IV, Secciones 1, 2 y 3
completas. Próximo en la cola: Sección 4 (Forex Lab Workspace).*

## PARTE 20 — PREDICCIÓN MÚLTIPLE DE CSVs + REPORTES EN TEXTO

Antes, `predict forex <csv>` solo aceptaba un archivo a la vez. Ahora acepta
uno o varios, separados por coma:

```
predict forex CSVs/H1/COTTON.csv
predict forex CSVs/H1/COTTON.csv,CSVs/H1/EURUSD.csv,CSVs/H1/XAUUSD.csv
predecir forex <csv1>,<csv2>,...      # alias en español, mismo comportamiento
```

**Un solo archivo:** comportamiento idéntico a siempre — la señal se muestra
en pantalla, nada se guarda en disco extra.

**Múltiples archivos:** cada uno se predice en secuencia y, además de
mostrarse en pantalla, se guarda como un reporte `.txt` individual en
`prediction/reports/`, nombrado `<PAR>_<YYYYMMDD_HHMMSS>.txt` (fecha y hora
de generación). Si dos reportes caen en el mismo segundo (ej. mismo par
analizado dos veces seguidas), se agrega un sufijo `_2`, `_3`, etc. para no
sobreescribir. Cada archivo incluye encabezado (par, CSV de origen, fecha de
generación) + la señal completa (BUY/SELL/HOLD, confianza, fuerza, ADX,
régimen), sin códigos de color ANSI. Errores en un archivo (ej. ruta
inexistente) no detienen el resto — se reporta al final cuántos reportes se
guardaron de cuántos se pidieron.

Disponible también desde el Chat del Workspace (Sección 3) sin cambios
adicionales, ya que usa el mismo `dispatch_command()` de `main.py`.

---

*Parte 20 añadida el 6 de julio de 2026.*

## PARTE 21 — PREDICTION LAB WORKSPACE (ROADMAP IV, SECCIÓN 5)

Interfaz visual completa sobre `prediction_lab/` (Fase 5, ya auditada e
integrada desde antes). Todo con datos reales — nada simulado.

**5.1 Sandbox unificado:** selector de CSV (detecta automáticamente los CSVs
de Forex + archivos subidos al Workspace, o se puede escribir cualquier otra
ruta), campo de variable objetivo opcional y campo de texto libre para
describir el problema. Al correr, ejecuta `run_full_lab()` real en un hilo de
fondo (prompt→dataset→viabilidad→plan→pipeline→validación) y guarda el
reporte como JSON en `lab_reports/`.

**5.2 Comparador de modelos:** tabla ordenable (click en cualquier columna)
con todos los proyectos guardados — viabilidad, score, veredicto PASA/NO
PASA, fecha. Click en una fila abre el detalle completo.

**5.3 Visualizaciones (todas reales, calculadas sobre el test set real del
último fold/holdout):**
- Matriz de confusión (clasificación).
- Curva ROC y Precision-Recall (solo clasificación binaria, cuando el
  modelo expone `predict_proba`).
- Feature Importance (ya existía, ahora graficado).
- Rendimiento por fold (score real de cada fold de la validación — sustituto
  honesto de "learning curves": el roadmap pedía curvas de aprendizaje
  (tamaño de dataset vs. score) que requerirían reentrenar el modelo a
  múltiples tamaños crecientes — no implementado en esta pasada, documentado
  como pendiente si se quiere más adelante).
- SHAP: no incluido — requeriría agregar la librería opcional `shap` al
  proyecto; pendiente si se solicita.

**5.4 Comparación antes/después:** baseline honesto (accuracy de predecir
siempre la clase mayoritaria en clasificación, o R²=0 en regresión — el
propio baseline matemático de R²) vs. el score real del modelo entrenado,
con la mejora en puntos.

**Cambio real en `prediction_lab/validation_engine.py` (aditivo, sin romper
nada):** `ValidationResult` ahora también captura, del último fold/holdout
real: `confusion_matrix`, `classes`, `roc_curve`, `pr_curve`,
`baseline_score`, `is_classification`. Se hilaron los test sets reales
(`X_test`/`y_test`) de `_holdout`/`_kfold`/`_wfv` de vuelta a
`validate_pipeline()` para poder calcular estos diagnósticos sin re-entrenar
nada. Verificado con dataset sintético de clasificación (600 filas, churn
binario, 65/35): accuracy 96%, matriz de confusión real `[[76,2],[6,36]]`,
ROC/PR curves reales, sin ninguna regresión en `lab reporte`/`lab
proyectos`/`lab info proyecto` (comandos CLI existentes probados de nuevo,
idénticos a antes).

**Bug real encontrado y corregido durante esta sección: la Sección 4 (Forex
Lab) tenía su archivo `forex_lab.js` completamente perdido** — el HTML y los
endpoints backend estaban intactos, pero el JS que los conectaba no existía
en disco (aparentemente no se guardó correctamente en la sesión anterior).
Se reconstruyó `forex_lab.js` desde cero verificando cada ID de HTML y cada
endpoint contra el backend real. En el proceso se encontró y corrigió un bug
real: el Circuit Breaker devuelve `open` (bool) y porcentajes YA
multiplicados por 100, pero el primer borrador del JS reconstruido asumía
`trading_allowed` (campo inexistente) y una re-multiplicación por 100 —
corregido antes de dar por cerrada la sección, verificado contra la
respuesta real de `/api/forex/circuit`.

**Verificación realizada:** sintaxis JS con `node --check` (ambos archivos),
cruce automatizado de todos los `getElementById` contra los `id=` reales del
HTML (sin faltantes), cruce de todas las rutas `fetch()` contra las rutas
`@app.get/post` reales del backend (sin faltantes ni desajustes), y pruebas
curl end-to-end de cada endpoint nuevo con datos reales (dashboard, csvs,
ohlc, circuit, lab/run, lab/projects, lab/projects/{id}).

---

*Parte 21 añadida el 6 de julio de 2026 — Roadmap IV, Sección 5 completa.
Bonus: se reparó una regresión real en la Sección 4 (forex_lab.js perdido).*

## PARTE 22 — BUSINESS LAB WORKSPACE (ROADMAP IV, SECCIÓN 6)

Dashboard visual completo sobre `forex/business/` (KPIEngine +
BusinessPredictor, ya existentes y probados por CLI desde antes). Todo con
datos reales — nada simulado.

**6.1 Análisis de negocio (un solo botón, un solo paso):**
- Selector de archivo (CSV/Excel subido al Workspace, o ruta manual) + campo
  de meses de proyección.
- Al correr `POST /api/business/analyze`, hace en un solo paso síncrono
  (KPIEngine y la regresión logística sobre datos tabulares de negocio son
  rápidos — a diferencia del entrenamiento Forex/Optuna, no necesitan hilo de
  fondo):
  1. Normaliza el archivo real (`business_csv_adapter.adapt_business_csv`).
  2. Calcula KPIs reales (`KPIEngine.compute_all()`): ingresos totales/
     promedio/último período, crecimiento, márgenes bruto/neto, ratio de
     gastos, tendencia, health score, nivel de riesgo, anomalías (caídas
     >20%).
  3. Entrena el predictor real sobre el propio dataset
     (`BusinessPredictor.train()`).
  4. Predicción real del próximo período con el modelo recién entrenado (o
     heurística de tendencia si hay pocos datos — mismo fallback real que ya
     usa `predice negocio` por CLI).
  5. Proyección de forecast real a N meses — misma fórmula matemática que
     `sme_consultant.sme_forecast()` (extrapolación lineal sobre
     `trend_slope` real + banda de incertidumbre según `trend_strength`/R²
     real), pero calculada server-side y devuelta como JSON estructurado en
     vez de un string coloreado para consola.

**Frontend:** tarjetas de KPI (ingresos, márgenes, crecimiento, tendencia,
health score, riesgo — con colores semánticos verde/rojo según sea bueno o
malo), lista de anomalías si las hay, tarjeta de señal ML (acción
GROWING/STABLE/DECLINING + confianza + estado del entrenamiento), gráfico de
proyección a N meses (Chart.js: banda optimista/esperado/conservador) y
vista previa de los datos normalizados.

**Bugs reales encontrados y corregidos en `forex/business/` durante esta
sección (no relacionados con el Workspace en sí, existían desde antes):**
1. `kpi_engine.py` calculaba internamente `trend_slope`/`trend_strength`
   pero nunca los incluía en el diccionario devuelto por `compute_all()` —
   `sme_forecast()` (comando CLI `forecast negocio`) siempre recibía
   `None`/0 para ambos campos vía `.get()`, por lo que la proyección
   *siempre* mostraba pendiente $0/mes y 0% de confianza sin importar la
   tendencia real de los datos. Corregido agregando ambas claves al
   resultado de `compute_all()`. Verificado con datos reales de
   `pyme_ecommerce.csv`: pendiente real +1,327.61/mes, R² 0.88, confianza
   88%, proyección final +11.3% — antes de la corrección esto mostraba
   0%/0.
2. El comando `forecast negocio <csv>` estaba **documentado en la ayuda**
   (`_ayuda()`) pero **nunca conectado al dispatcher** — al escribirlo en
   consola no hacía nada (caía al chat genérico). Se agregó el dispatch real
   en `main.py` (`_bi_forecast()` + rama `elif` en `dispatch_command()`),
   con soporte para meses opcionales (`forecast negocio archivo.csv 12`).
   Verificado con sesión interactiva real y sin regresión en
   `analiza negocio` / `predice negocio` / `entrena negocio` / `consulta
   negocio`.

**Verificación realizada:** sintaxis JS con `node --check`, cruce
automatizado de `getElementById` contra `id=` del HTML (sin faltantes),
cruce de rutas `fetch()` contra rutas reales del backend (sin desajustes),
pruebas curl end-to-end de los 3 endpoints nuevos
(`/api/business/csvs`, `/api/business/csv/info`, `/api/business/analyze`)
con datos reales, y manejo correcto de casos límite (archivo inexistente →
error claro sin crash; CSV no financiero como un OHLC de Forex → degrada a
`business_type: "generic"` con KPIs en `null`/valores neutros, sin romper la
UI).

---

*Parte 22 añadida el 6 de julio de 2026 — Roadmap IV, Sección 6 completa.
Bonus: se corrigieron 2 bugs reales preexistentes en `forex/business/`
(forecast con pendiente/confianza siempre en 0, y el comando `forecast
negocio` documentado pero nunca conectado).*

---

## PARTE 23 — COGNITIVE CENTER WORKSPACE (ROADMAP IV, SECCIÓN 7)

**Objetivo:** ventana exclusiva del Workspace para explorar y consultar toda
la memoria de ASTRA (conversaciones, proyectos, modelos, comandos ejecutados,
preferencias/umbrales aprendidos) sin salir del navegador — más una barra de
búsqueda en lenguaje natural que responde sobre esos mismos datos reales.

**Backend nuevo (`cognitive_center.py`, standalone, graceful-fail en cada
función pública):**
- `get_conversations(limit)` — lee `memoria.db` tabla `memoria` (creada por
  `memory.py`), más reciente primero.
- `get_projects_overview()` — agrega `project_memory.py`: proyectos, tareas
  (con `done`/`completed_at`), y modelos entrenados (`models` table, con
  métricas guardadas por `register_model()`).
- `get_tools_usage(limit)` — agrega la tabla `command_log` (creada en la
  sesión de v2, Parte 13/14 de esta bitácora): conteo por comando, por
  categoría, por par, y los comandos más recientes.
- `get_learned_preferences()` — lee `feedback/adaptive_thresholds.py`
  (umbrales de confianza/ADX ajustados por par vs. los defaults de
  producción 0.65/22.0) y `feedback/contextual_memory.py` (tasa de éxito
  por contexto de mercado guardado, si existe).
- `get_timeline(limit)` — fusiona conversaciones + comandos + modelos +
  proyectos + tareas en una sola lista cronológica ordenada por timestamp
  real (no simulado), con `kind` para diferenciar el tipo de evento en la UI.
- `build_knowledge_graph()` — nodos (`pair`, `project`, `category`) y
  aristas (`used_in`) derivados de `command_log` + `models` + `projects`;
  vista relacional simple pensada para crecer a medida que se acumula uso
  real del sistema.
- `search_memory(query)` — **7.2, la pieza central de esta sección.** Intenta
  extraer intención + palabras clave vía LLM (Groq/Llama, mismo cliente que
  `prompt_analyzer.py`); si no hay API key o falla, cae a un heurístico de
  keywords/regex (detecta menciones a pares, "tarea"/"pendiente",
  "modelo"/"accuracy", "proyecto", "preferencia"/"umbral", etc.) para decidir
  qué fuentes consultar (`conversations`/`commands`/`models`/`projects`/
  `tasks`/`preferences`) y con qué filtro. Si no hay coincidencias exactas,
  degrada a devolver lo más reciente de las fuentes relevantes en vez de una
  respuesta vacía (`used_fallback_unfiltered: true` en la respuesta, visible
  en la UI).

**Wireado también por CLI** (mismo patrón que Fases 5-9): comandos
`memoria explorar` y `memoria buscar <consulta>` en `main.py`
(`cmd_memoria_explorar`, `cmd_memoria_buscar`), categoría `cognitive_center`
en `intent_router.py`, y entradas `cognitive_*` / `memoria_*_cmd` en
`tool_registry.py`.

**Backend Workspace (`workspace/server.py`):** 7 endpoints nuevos, todos
delegando a `cognitive_center.py` sin lógica propia (`/api/cognitive/overview`,
`/conversations`, `/projects`, `/tools_usage`, `/preferences`, `/timeline`,
`/knowledge_graph`, y `POST /search`).

**Frontend (`workspace/static/js/cognitive_center.js` + panel en
`index.html`):**
- Barra de búsqueda en lenguaje natural (7.2) con resultados agrupados por
  fuente (conversaciones, comandos, modelos, proyectos, tareas,
  preferencias) y meta-info visible del motor usado (LLM vs. heurístico) y
  si se degradó a resultados no filtrados.
- Tarjetas de resumen (conversaciones, proyectos, modelos, tareas
  pendientes, comandos registrados, pares con umbral propio).
- Línea de tiempo unificada (scrolleable) con ícono por tipo de evento.
- Knowledge Graph: layout circular simple en SVG nativo (sin dependencias
  nuevas — reutiliza el patrón "sin librerías extra si no son
  imprescindibles" del resto del Workspace), con tooltips nativos
  (`<title>`) mostrando accuracy/precision o estado por nodo.
- Tabla de herramientas más usadas y tabla de preferencias aprendidas
  (confianza/ADX por par vs. default), con estado vacío explícito cuando no
  hay umbrales personalizados aún.

**Verificación realizada:** sintaxis JS con `node --check`, cruce
automatizado de `getElementById`/`querySelector` contra `id=`/`data-section`
del HTML (sin faltantes), cruce de rutas `fetch()` contra rutas reales del
backend (sin desajustes), servidor FastAPI levantado en vivo y probado con
curl end-to-end contra los 7 endpoints con datos reales insertados a mano
(conversaciones, comando_log, modelo entrenado, proyecto+tarea, umbral
adaptativo) — incluyendo la búsqueda en lenguaje natural con y sin
coincidencia exacta. Datos de prueba limpiados de `memoria.db` al finalizar
para no dejar residuos en la base real del proyecto.

---

*Parte 23 añadida el 7 de julio de 2026 — Roadmap IV, Sección 7 completa.*

## PARTE 24 — EVOLUTION CENTER WORKSPACE (ROADMAP IV, SECCIÓN 8)

**Objetivo:** ventana del Workspace sobre "cómo evoluciona ASTRA" —
panel del ciclo evolutivo completo (Fases 7-9, ya operativas por CLI desde
antes de esta sesión) y revisión/aprobación/rechazo real de propuestas de
mejora, sin salir del navegador.

**Backend nuevo (`evolution_center.py`, standalone, graceful-fail en cada
función pública, agregador puro — no reimplementa lógica de negocio, solo
lee/orquesta los módulos reales de `evolution/`, `constitution/` y
`evolutionary_cycle.py`):**
- `get_cycle_overview()` — resumen agregado: propuestas por estado, último
  snapshot de `performance_monitor`, totales de audit log y rollback points.
- `get_evolution_timeline(limit)` / `get_performance_history(limit)` — leen
  `evolution_events` y `performance_snapshots` (tablas de `feedback/
  evolution_memory.py` y `evolution/performance_monitor.py`).
- `get_proposals_list(status, limit)` / `get_proposal_detail(id)` — listan y
  detallan propuestas de `evolution/proposal_store.py`; el detalle incluye
  una **validación constitucional en vivo** (preview, vía
  `ConstitutionValidator.validate()`) mostrando reglas verificadas,
  violaciones y warnings — sin cambiar el estado de la propuesta.
- `approve_proposal(id, justification)` / `reject_proposal(id, reason)` —
  aprobación/rechazo manual real (mismo flujo que `cmd_aprobar_propuesta`/
  `cmd_rechazar_propuesta` del CLI): la aprobación crea un rollback point
  real vía `rollback_manager.py`.
- `validate_proposal_constitutional(id)` — expone el flujo completo de
  `approval_flow.py` (valida contra la constitución y aprueba/rechaza según
  el resultado); usado internamente por el ciclo evolutivo automático.
- `get_constitution_rules()` — catálogo de las 7 reglas builtin de
  `constitution_rules.py` (riesgo máx. por operación, confianza/ADX mínimos,
  WFV obligatorio para deploy, drawdown diario máx., aprobación obligatoria,
  máx. 3 rollbacks automáticos).
- `get_audit_log(target, limit)` / `get_rollback_points(limit)` /
  `apply_rollback(id)` — lectura del registro inmutable (`audit_log.py`) y
  gestión real de snapshots (`rollback_manager.py`).
- `trigger_evolutionary_cycle(auto_approve_minor)` — dispara
  `evolutionary_cycle.run_evolutionary_cycle()` real: monitor → detecta
  oportunidades → propone → valida contra la constitución → aprueba/rechaza
  → registra en feedback → audit log. Mismo ciclo que corre en producción,
  ahora también invocable desde el botón del panel.

**Sin wireo CLI adicional:** a diferencia de Cognitive Center, la capacidad
de fondo (propuestas, aprobación, reglas, rollback, ciclo evolutivo) ya
tenía comandos CLI completos desde las Fases 7-9 (`propuestas ver`,
`aprobar propuesta`, `rechazar propuesta`, `reglas ver`, `audit log`, etc. en
`main.py`/`intent_router.py`/`tool_registry.py`). `evolution_center.py` es
puramente un agregador nuevo para el Workspace, sin duplicar esa capa.

**Backend Workspace (`workspace/server.py`):** 13 endpoints nuevos, todos
delegando a `evolution_center.py` sin lógica propia (`/api/evolution/overview`,
`/timeline`, `/performance_history`, `/proposals`, `/proposals/{id}`,
`POST /proposals/{id}/approve`, `POST /proposals/{id}/reject`,
`POST /proposals/{id}/validate`, `/rules`, `/audit`, `/rollback_points`,
`POST /rollback_points/{id}/apply`, `POST /cycle/run`), con un traductor
`_evo_response()` que mapea el patrón `{"ok": bool, "error": ...}` a status
codes HTTP (404 si la propuesta/rollback no existe, 400 en otros errores).

**Frontend (`workspace/static/js/evolution_center.js` + panel en
`index.html`):**
- Tarjetas de resumen del ciclo evolutivo + botón para correr el ciclo
  completo en vivo, con mensaje de resultado real (oportunidades, propuestas
  creadas/aprobadas/rechazadas, umbrales ajustados).
- Historial de eventos (timeline con ícono por tipo) y tabla de snapshots de
  rendimiento del sistema.
- Tabla de propuestas con filtro por estado, botones "Ver"/"Aprobar"/
  "Rechazar" (solo visibles si `status == pending`), y vista de detalle
  expandible con la validación constitucional en vivo (reglas verificadas,
  violaciones en rojo, warnings en gris) y los rollback points asociados.
- Tabla de reglas constitucionales, tabla de rollback points con botón
  "Revertir" (con confirmación), y audit log con pills de estado por
  resultado (aprobado/aplicado en color primario, rechazado/revertido en
  color destructivo).

**Verificación realizada:** sintaxis JS con `node --check`, cruce
automatizado de `getElementById`/`querySelector` contra `id=` del HTML y de
rutas `fetch()` contra las rutas reales del backend (sin desajustes reales —
los dos "faltantes" detectados por el script eran falsos positivos: un id
creado dinámicamente en runtime dentro de un template, y una variable JS
capturada literalmente por el regex). Servidor FastAPI levantado en vivo dos
veces y probado con curl end-to-end contra los 13 endpoints, incluyendo el
flujo completo de aprobar/rechazar/validar/revertir/correr-ciclo sobre
propuestas de prueba reales — con limpieza total de residuos en `memoria.db`
(proposals, rollback_points, performance_snapshots, audit_log,
evolution_events, adaptive_thresholds) al finalizar cada ronda, dejando la
base exactamente en el estado real previo a las pruebas.

---

*Parte 24 añadida el 7 de julio de 2026 — Roadmap IV, Sección 8 completa.*

## PARTE 25 — ACTIVITY CENTER WORKSPACE (ROADMAP IV, SECCIÓN 9)

**Objetivo:** "qué está pasando ahora mismo en ASTRA" — feed unificado y en
vivo (poll cada 5s) que fusiona 4 fuentes reales en una sola línea de
tiempo, sin salir del navegador.

**Backend nuevo (`activity_center.py`, standalone, graceful-fail):**
- **Alertas del Workspace movidas aquí desde `workspace/server.py`**: el
  store en memoria (`push_alert`/`get_alerts`, antes `_push_alert`/`_alerts`
  vivían como estado global del server) ahora vive en este módulo para que
  sea testeable sin levantar FastAPI — mismo patrón que `cognitive_center.py`
  / `evolution_center.py`. `server.py` mantiene `_push_alert` como alias fino
  para no tocar los ~10 call-sites existentes (Forex Lab, Business Lab,
  Prediction Lab ya disparaban alertas antes de esta sección).
- `get_recent_commands(limit)` — `memory.get_command_log()`.
- `get_recent_signals(limit)` — `signal_tracker.get_signals()`.
- `get_recent_evolution_events(limit)` — `feedback/evolution_memory.
  get_evolution_history()`.
- `get_activity_feed(limit, sources)` — fusiona las 4 fuentes, normaliza
  timestamps mixtos (ctime de `command_log` vs. isoformato de eventos de
  evolución vs. `YYYY-MM-DD HH:MM:SS` de alertas/señales) con el mismo
  parser multi-formato de Cognitive Center, ordena cronológico descendente,
  filtra por fuente opcionalmente.
- `get_activity_stats()` — conteos totales por fuente (sin el límite
  artificial de la vista fusionada) + alertas por severidad + señales por
  acción, para las tarjetas resumen del panel.

**Backend Workspace (`workspace/server.py`):** 2 endpoints nuevos
(`/api/activity/feed?sources=alert,signal&limit=N`, `/api/activity/stats`),
más el endpoint legacy `/api/forex/alerts` (Sección 4) que ahora delega al
mismo store de `activity_center.py` en vez de tener su propio estado —
verificado que sigue funcionando igual (compatibilidad hacia atrás).

**Frontend (`workspace/static/js/activity_center.js` + panel en
`index.html`):**
- Tarjetas de resumen (alertas, comandos, señales, eventos de evolución).
- Feed en vivo con ícono por fuente, pill de severidad por color
  (`.act-kind-pill`, nueva clase CSS — ver bugs corregidos abajo), filtro
  por fuente, y auto-actualización cada 5s (toggle para pausar).

**2 bugs reales de CSS pre-existentes encontrados y corregidos durante esta
sección (no introducidos ahora, pero detectados al reutilizar el patrón de
pills de Evolution Engine):**
1. **`--destructive` / `--destructive-foreground` nunca estaban definidas**
   en `:root` pese a usarse en `.tbl-action-btn.destructive` y
   `.evo-status-pill.rejected/.rolled_back` (Parte 24, esta misma sesión) —
   los pills de "rechazado"/"revertido" en Evolution Center renderizaban con
   `hsl()` inválido (color indefinido del navegador) en vez de rojo
   destructivo. Corregido: variables agregadas en modo claro y oscuro.
2. **`--success` / `--danger` solo estaban definidas en el bloque `:root`
   claro, no en `@media (prefers-color-scheme: dark)`** — afectaba
   `.status-dot.online/.offline` (Sección 2) y `.alert-item.kind-success/
   .kind-error` (Forex Lab, Sección 4) en modo oscuro desde que existen.
   Corregido: agregadas también al bloque dark con tonos ajustados.

**Nota de diseño no bloqueante encontrada:** `forex_lab.js` (Sección 4)
renderiza alertas con clases `alert-row alert-{kind}`, pero el CSS real
define `.alert-item.kind-{kind}` — mismatch de nombres que hace que el
borde de color por severidad no se aplique en la lista de alertas de Forex
Lab. No se corrigió en esta sesión (fuera del alcance de Sección 9, y no
afecta datos/funcionalidad — solo estética de una lista ya funcional);
queda anotado para una futura pasada de pulido visual.

**Verificación realizada:** sintaxis JS con `node --check`, cruce
automatizado de `getElementById`/`querySelector` contra `id=`/`data-section`
del HTML (sin faltantes reales), cruce de rutas `fetch()` contra el backend
(sin desajustes reales — el único "faltante" detectado por el script era
una variable JS, no un literal), clases CSS usadas verificadas contra
`style.css` antes de asumir que existían. Servidor FastAPI levantado en
vivo dos veces: primera ronda probando `push_alert`/`get_recent_commands`/
`get_recent_signals`/`get_recent_evolution_events` con datos reales
insertados a mano (comando, señal) y limpiados después (por id exacto, no
por campo — un intento inicial de limpiar por `csv_path` falló
silenciosamente porque `signal_tracker.save_signal()` ignora ese campo del
dict de entrada y usa su propio parámetro separado; detectado y corregido
antes de confirmar la base limpia). Segunda ronda: página completa servida
con los 3 scripts de Cognitive/Evolution/Activity Center presentes, panel
`#panel-activity` presente, CSS nuevo servido, y los 2 endpoints nuevos
respondiendo con datos reales del proyecto (6 eventos de evolución
existentes desde la Parte 24).

---

*Parte 25 añadida el 7 de julio de 2026 — Roadmap IV, Sección 9 completa.*

## PARTE 26 — NOTIFICATION CENTER (ROADMAP IV, SECCIÓN 10)

**Objetivo (según spec real, `astra-roadmap-iv.html`):** notificaciones
PERSISTIDAS y consultables — predicciones listas, entrenamientos
completados, problemas detectados, actualizaciones. Diferencia clave con
Activity Center (Sección 9): Activity Center es un feed en vivo/efímero
(alertas viven en memoria, se pierden al reiniciar el server); Notification
Center es una bandeja formal que sobrevive a un reinicio — tabla SQLite
real (`notifications` en `memoria.db`).

**Backend nuevo (`notification_center.py`, standalone, graceful-fail):**
- Tabla `notifications` (id, ntype, title, message, data JSON, is_read,
  created_at), creada de forma idempotente por `init_notifications_db()`.
- 5 tipos soportados: `training_completed`, `prediction_ready`,
  `problem_detected`, `business_analysis_ready`, `system_update` (tipo
  inválido cae a `system_update` en vez de perderse — graceful).
- `push_notification(ntype, title, message, data)`,
  `get_notifications(limit, unread_only, ntype)`, `mark_read(id)`,
  `mark_all_read()`, `get_notification_stats()` (total, no leídas, no
  leídas por tipo — para el badge de la campana).

**Backend Workspace (`workspace/server.py`):** 4 endpoints nuevos
(`GET /api/notifications`, `GET /api/notifications/stats`,
`POST /api/notifications/{id}/read`, `POST /api/notifications/read-all`).
`push_notification()` conectado a 4 puntos reales de finalización de tareas
(no a cada alerta menor — solo a los eventos que la spec pide poder
"consultar después"): entrenamiento Forex completado/error, Prediction Lab
completado/detenido/fallido, Business Lab análisis completado. Cada
notificación queda junto a su `_push_alert()` correspondiente (Sección 9),
sin reemplazarlo — son dos sistemas complementarios, no uno reemplaza al
otro.

**Frontend:** campana 🔔 en la topbar (visible desde cualquier sección,
no solo dentro de un panel — a diferencia de Activity/Evolution/Cognitive
Center que son paneles de navegación), con badge de no-leídas (poll cada
8s) y dropdown con la lista completa, click en un ítem lo marca como leído,
botón "marcar todas leídas". CSS nuevo: `.notif-wrap/.notif-bell/
.notif-badge/.notif-dropdown/.notif-item` — sin colores hardcodeados,
reutiliza los tokens `--primary/--destructive/--muted` ya corregidos en la
Parte 25.

**Verificación realizada:** módulo standalone probado con 5 casos (push de
3 tipos incl. uno inválido→system_update, listar, stats con no-leídas,
marcar 1 leída, unread_only, filtro por tipo, marcar todas leídas) — todo
limpiado por id exacto después. Server levantado en vivo: bell+dropdown
presentes en el HTML servido, script cargado, endpoint stats en 0 al
arrancar, disparo real de `/api/business/analyze` generó una notificación
real end-to-end (`business_analysis_ready`, health=97/100), marcar leída de
un id inexistente devolvió `false` correctamente (comportamiento esperado,
no un bug), marcar todas leídas sí afectó la real. Un bug encontrado y
corregido en `notification_center.py` durante el propio desarrollo (no en
producción): un helper `_row_to_dict` quedó sin usar y con una condición
sin sentido (`row[3] if False else row[2]`) — se detectó por revisión
antes de wirear y se eliminó, `get_notifications()` nunca lo llamaba.

---

*Parte 26 añadida el 7 de julio de 2026 — Roadmap IV, Sección 10 completa.*

## PARTE 27 — LIVE THINKING (ROADMAP IV, SECCIÓN 11)

**Objetivo (spec real, `astra-roadmap-iv.html`):** razonamiento operativo
VISIBLE — que el usuario nunca perciba que ASTRA "solo está pensando" sin
mostrar qué hace. A diferencia de las Secciones 8-10 (paneles de
navegación dedicados), esta es una primitiva **TRANSVERSAL**: no vive en
un tab propio, sino como franja flotante bajo la topbar, visible desde
cualquier panel mientras corre una tarea larga.

**Backend nuevo (`live_thinking.py`, standalone, graceful-fail):**
- Modelo singleton en memoria por `task_key` (mismo patrón que
  `_lab_state`/`_train_state` de `workspace/server.py` — un job activo a
  la vez por tarea). No persiste a disco: es "qué está pasando ahora", no
  historial (para eso ya existen Activity Center y Notification Center).
- API: `start_thinking(task_key, step_labels, task_label)`,
  `set_step(task_key, index, status, detail)` (status:
  pending/running/done/error/skipped), `finish_thinking(task_key, ok,
  error)` (cierra cualquier paso que haya quedado "running" sin marcar
  explícito — evita que la UI muestre un paso "pensando" para siempre),
  `get_thinking(task_key)`, `get_all_thinking()`. Todo con fallos
  silenciosos ante task_key/índice inexistente (nunca rompe el job real
  que está corriendo).

**Instrumentación de `prediction_lab/report_generator.py::run_full_lab()`:**
nuevo parámetro opcional `progress_cb(step_index, status, detail)`, llamado
en los 6 puntos reales de transición de etapa (0=Prompt, 1=Dataset,
2=Viabilidad, 3=Plan, 4=Pipeline, 5=Validación). Si la viabilidad resulta
insuficiente, los pasos 3-5 se marcan `skipped` explícitamente (no quedan
en `pending` para siempre). El callback está envuelto en su propio
try/except — si el callback mismo revienta, el lab real jamás se ve
afectado (graceful fail, mismo principio de todo ASTRA). Retrocompatible:
si no se pasa `progress_cb`, el comportamiento es idéntico al de antes de
esta sección.

**Wireo en `workspace/server.py`:**
- `_run_lab_job()` (Prediction Lab): abre sesión `live_thinking` con los 6
  labels al iniciar, pasa el callback real a `run_full_lab()`, cierra la
  sesión en success/except.
- `_run_training_job()` / `_TrainingStreamTee.write()` (Forex full
  pipeline): retrofit del tracking de etapas YA existente (parseo real de
  stdout `[1/4]..[4/4]`) para publicar también en `live_thinking` bajo
  `task_key="forex_train"` — reutiliza los 4 labels de `_STAGE_LABELS` sin
  inventar nada nuevo, solo alimenta el mismo primitivo transversal desde
  una fuente de datos que ya existía.
- 2 endpoints nuevos: `GET /api/thinking` (todas las sesiones conocidas,
  activas o no) y `GET /api/thinking/{task_key}` (una sesión puntual).

**Frontend:** franja `.thinking-strip` fija bajo la topbar (`index.html`),
oculta por defecto. `live_thinking.js` hace polling de `/api/thinking` cada
2s: si hay una sesión activa la muestra con pills por paso (○ pending, ◐
running con animación de pulso, ✓ done, ✕ error, — skipped tachado); si
ninguna está activa pero una terminó hace <15s, la deja visible ese tiempo
para que el usuario vea el resultado final y luego oculta la franja sola.
CSS nuevo (`.thinking-strip`, `.think-step*`) sin colores hardcodeados,
reutiliza tokens `--primary/--success/--destructive/--muted` ya existentes.

**Verificación realizada:** `run_full_lab()` probado standalone con
callback real en 2 casos (dataset no viable → pasos 3-5 correctamente
`skipped`; dataset viable con target explícito → los 6 pasos corren
`running`→`done` en vivo, incluyendo detalle real como
`score=0.027 (NO PASA)`). Server levantado en vivo: franja + script
presentes en el HTML servido, `/api/thinking` vacío al arrancar, disparo
real de `POST /api/lab/run` vía HTTP generó una sesión `prediction_lab`
completa end-to-end (6/6 pasos `done`, detalle real en cada uno) —
corrió demasiado rápido (18 filas) para capturarlo a medio camino, pero
confirma la integración real servidor↔job↔live_thinking sin mocks.
Compilación final: 105 archivos Python + todo el JS sin errores. Residuos
de testing (notificación de prueba, reporte de lab de prueba) limpiados
antes de cerrar la sesión.

**Pendiente Roadmap IV:** Sección 12 (Identidad Visual — tema oscuro/claro,
iconografía por Lab, animaciones de pulido final). Es la última sección.

---

*Parte 27 añadida el 8 de julio de 2026 — Roadmap IV, Sección 11 completa.*

## PARTE 28 — IDENTIDAD VISUAL (ROADMAP IV, SECCIÓN 12 — FINAL)

**Objetivo:** última sección del Roadmap IV — pasada de pulido y consistencia
visual sobre las 11 secciones ya construidas, sin agregar paneles nuevos.
No hubo un archivo de spec dedicado para esta sección (a diferencia de las
anteriores); el alcance se definió con 2 fuentes reales: (1) una nota de
diseño deferida explícitamente en la Parte 25 (Sección 9), y (2) una
auditoría propia de todo `style.css` + los 4 archivos JS de gráficos
buscando color hardcodeado / tokens rotos.

**3 bugs reales encontrados y corregidos (no cosméticos):**

1. **Mismatch de clases CSS en alertas de Forex Lab (deferido desde la
   Parte 25)**: `forex_lab.js::forexLoadAlerts()` generaba
   `class="alert-row alert-{kind}"`, pero el CSS real define
   `.alert-item.kind-{kind}`. Resultado: el borde de color por severidad
   (verde/rojo/ámbar/gris) nunca se aplicaba en la lista de alertas de
   Forex Lab, pese a que el dato y el CSS eran correctos por separado.
   Corregido: JS ahora genera `class="alert-item kind-{kind}"`, alineado
   1:1 con las 4 clases reales (`success/error/warning/info`) que emite
   `_push_alert()` en `server.py`.

2. **`--secondary` / `--secondary-foreground` usados pero NUNCA
   definidos**: `.tbl-action-btn` (botones de acción del Evolution
   Center — aprobar/rechazar/rollback de propuestas, Sección 8) referencia
   `hsl(var(--secondary))` / `hsl(var(--secondary-foreground))`, pero
   ninguno de los 2 bloques de tokens (`:root` claro /
   `@media (prefers-color-scheme: dark)`) los declaraba. Sin fallback,
   esto cae a transparente/heredado del navegador — los botones de acción
   del Evolution Center llevaban rota su apariencia por defecto (no la
   variante `.primary`/`.destructive`, que sí tienen sus tokens) desde que
   existen. Corregido: agregados ambos tokens en los 2 bloques
   (`0 0% 96%` / `0 0% 9%` en claro, `0 0% 18%` / `0 0% 99%` en oscuro,
   consistentes con el resto de la paleta neutra). Verificado con script
   propio: cruce de todas las `var(--x)` usadas en `style.css` contra
   todas las declaradas — 0 faltantes tras el fix (16/16 tokens usados
   están definidos en ambos temas).

3. **5 colores hex hardcodeados en Business Lab** (`.kpi-tile.kpi-good/
   kpi-bad`, `.biz-anomalies .anomaly-row`,
   `.biz-signal-action.action-growing/declining`): usaban `#2e9e5b` /
   `#d1483f` fijos en vez de los tokens `--success`/`--danger` ya
   existentes. Funcionaban visualmente en ambos temas por coincidencia
   (son iguales en claro/oscuro salvo el fix ya aplicado a `--danger` en
   la Parte 25), pero quedaban desacoplados del sistema de diseño —
   cualquier ajuste futuro de paleta los habría dejado desincronizados en
   silencio. Corregidos a `hsl(var(--success))` / `hsl(var(--danger))`.

**Consistencia de marca entre los 3 Labs (no era un bug, pulido):**
Prediction Lab y Business Lab ya leían `--primary` en vivo vía
`getComputedStyle(document.body)` para sus gráficos Chart.js. Forex Lab
(lightweight-charts) tenía la línea SMA y la línea de precio horizontal
con un acento fijo `#d98e5c` — visualmente similar a `--primary` pero no
el mismo token. Unificado: ambas ahora leen `--primary` en vivo, igual
patrón que los otros 2 Labs.

**Iconografía por Lab:** los 8 ítems del menú lateral (`.nav-item`)
tenían un punto (`.nav-dot`) genérico e idéntico para las 8 secciones —
sin identidad visual propia por Lab. Reemplazados por 8 íconos SVG
inline distintivos (`stroke="currentColor"`, sin colores propios —
heredan el color del texto del nav-item activo/hover/inactivo, cero
tokens nuevos): mensaje (Chat), barras (Forex Lab), matraz (Prediction
Lab), maletín (Business Lab), chip/CPU (Cognitive Core), refresh cíclico
(Evolution Engine), pulso de actividad (Activity Center), engranaje
(Configuración). CSS `.nav-icon` con transición de opacidad/escala sutil
en hover/activo — mismo lenguaje visual restringido del resto del
proyecto (sin arcoíris de colores por ítem).

**Animación de pulido final:** transición `panel-fade-in` (opacity +
translateY sutil, 0.18s) al cambiar entre las 8 secciones del workspace —
antes el cambio de panel era instantáneo (`display:none`↔`flex` sin
transición). Respeta `prefers-reduced-motion: reduce` (sin animación para
usuarios que la desactivan a nivel de sistema).

**Verificación realizada:** compilación completa (105 archivos Python +
todo el JS con `node --check`) sin errores. Script propio de auditoría de
tokens CSS (`var(--x)` usados vs. declarados) confirmando 0 faltantes.
Servidor FastAPI levantado en vivo y verificado con `curl` contra los
archivos realmente servidos (no solo el disco): los 8 `class="nav-icon"`
presentes en el HTML servido, `--secondary` y `panel-fade-in` presentes en
el CSS servido, `#d98e5c` ausente y `alert-item kind` presente en el JS
servido — confirma que el fix llegó a lo que el navegador realmente
recibe, no solo al archivo fuente. Servidor apagado limpio al cerrar
(un primer intento de `pkill` no mató el proceso real por diferencia de
patrón de cmdline; confirmado con `/proc/*/cmdline` y matado por PID
directo — sin residuos).

**Roadmap IV — Workspace & UX: 12/12 secciones completas.** El workspace
visual queda con las 12 secciones funcionando con datos reales (sin
mocks): Workspace Principal, Barra de Estado, Chat Center, Forex Lab,
Prediction Lab, Business Lab, Cognitive Core, Evolution Center, Activity
Center, Notification Center, Live Thinking e Identidad Visual.

---

*Parte 28 añadida el 9 de julio de 2026 — Roadmap IV, Sección 12 completa.
ROADMAP IV CERRADO (12/12 secciones).*

## PARTE 29 — REVISIÓN OPERATIVA FINAL Y 2 BUGS REALES CORREGIDOS (POST-CIERRE ROADMAP IV)

**Contexto:** con las 12 secciones del Roadmap IV ya cerradas (Parte 28), se
hizo una revisión operativa final de punta a punta (servidor real levantado,
barrido de endpoints, entrenamiento Forex real, análisis Business Lab real,
Prediction Lab real) antes de empaquetar el proyecto. Se encontraron y
corrigieron 2 bugs reales adicionales en `workspace/server.py`.

**1. Gap de observabilidad — Cognitive Center ciego a las acciones del
Workspace.** Entrenar desde el Forex Lab, correr el Prediction Lab o
analizar en el Business Lab vía la interfaz web generaba alertas y
notificaciones correctamente, pero nunca quedaba registrado en
`command_log` (la tabla que alimenta `/api/cognitive/tools_usage` y el
timeline). Corregido agregando `memory.log_command(...)` en los 3 lugares:
fin de `_run_training_job()` (Forex, categoría `forex`, con el par
detectado), rama de éxito completo de `_run_lab_job()` (Prediction Lab,
categoría `prediction_lab`), y `business_analyze()` (Business Lab,
categoría `business`). Verificado con las 3 acciones reales vía curl:
`tools_usage` pasó de `total_logged: 0` a reflejar cada acción con su
categoría, comando y resumen reales.

**2. Bug real más serio — el panel de Forex Lab mostraba SIEMPRE "el
modelo no pasó la validación WFV" tras entrenar, incluso cuando el
entrenamiento fue exitoso.** Causa raíz: `_forex_full()` en `main.py`
imprime todo el resultado por stdout y SIEMPRE hace `return ""` al final
(éxito, fallo o bloqueo por WFV reprobado — los 3 casos devuelven el mismo
valor falsy). `_run_training_job()` en `server.py` decidía el mensaje final
con `if respuesta: ... else: "Sin señal — el modelo no pasó la validación
WFV..."` — como `respuesta` es SIEMPRE `""`, el mensaje de fallo se mostraba
el 100% de las veces, sin importar el resultado real. Confirmado con datos
reales de COTTON: WFV aprobado al 88.76%, señal y backtest generados
correctamente, y aun así el Workspace reportaba "no pasó la validación".

Fix aplicado: se agregó detección del marcador real `[BLOQUEADO]` que ya
imprime `main.py` cuando el WFV reprueba (`_train_state["wfv_blocked"]`,
parseado en vivo del stream de stdout, igual patrón que el resto de
`_TrainingStreamTee`), y se reemplazó la decisión por lógica basada en el
estado real ya capturado: si `wfv_blocked` → mensaje de bloqueo explícito;
si se alcanzó la etapa 4/4 → "Pipeline completado"; en cualquier otro caso
→ mensaje de que no llegó a completarse. Verificado con 2 corridas reales
de `full forex COTTON`: antes del fix mostraba el mensaje erróneo pese a
WFV aprobado; después del fix mostró correctamente "Pipeline completado —
ver métricas y log." con las mismas métricas reales (accuracy 66.27%,
precision 83.59%, WFV avg 88.76%).

**Verificación operativa final realizada:** sintaxis válida en TODOS los
`.py` reales del proyecto (`ast.parse`) y TODOS los `.js` del Workspace
(`node --check`); `check_startup.py` sin issues críticos (solo paquetes
opcionales ausentes, esperado); servidor real levantado y barrido de ~13
endpoints de las 12 secciones — todos 200 OK; `full forex` end-to-end con
datos reales de COTTON sin regresión.

**Limpieza final antes de empaquetar:** se eliminaron artefactos generados
durante las pruebas de esta sesión (no deben ir al entregable, se
regeneran solos al usar la app): `memoria.db`/`astra_memory.db` de prueba,
6 modelos `.pkl` de COTTON generados en las corridas de test, reportes de
`lab_reports/`, entradas de prueba en `data/forex_analytics/COTTON`, un
CSV de upload duplicado, todos los `__pycache__`/`.pyc`, y la carpeta
`_quarantine_root_forex_junk/` (basura confirmada en la Parte 6 —
`cmd.exe`, duplicados de descarga, archivos corruptos — nunca debió
empaquetarse, quedó aislada ahí desde entonces para excluirla del zip).

`requirements.txt` actualizado: el comentario de referencia por fase ahora
cubre explícitamente las 12 secciones del Roadmap IV (antes solo mencionaba
hasta la Sección 6) y la fecha/alcance de la verificación de instalación
limpia se actualizó al 9 de julio de 2026.

---

*Parte 29 añadida el 9 de julio de 2026 — revisión operativa final post-cierre
del Roadmap IV, 2 bugs reales corregidos, proyecto limpio y listo para
empaquetar.*

---

## PARTE 30 — Roadmap V · Dashboard Activo y Sistema Autónomo

*Añadida el 19 de julio de 2026 — integración del Dashboard Activo (V.16) en el Workspace y documentación completa del Roadmap V.*

---

### Qué es el Roadmap V

El Roadmap V es la capa de **autonomía e inteligencia avanzada** de ASTRA. Mientras que el Roadmap IV construyó el Workspace web (Secciones 1–12), el Roadmap V añade un sistema que opera **sin intervención manual**: vigila mercados 24/7, actualiza datasets, reentrena modelos cuando se degradan y emite señales de alta calidad solo cuando la confiabilidad es suficiente.

Está organizado en **4 clusters**:

| Cluster | Componentes | Propósito |
|---|---|---|
| A — Predicción | V.5, V.9 | Quality Gate + Backtesting Protocol |
| B — Inteligencia | V.3, V.4, V.6, V.7 | Régimen, MTF, Features, Model Selection |
| C — Decisión | V.1, V.2, V.8 | Decision Engine, Risk Engine, Reliability Score |
| D — Autonomía | V.10, V.11, V.12, V.13, V.15, V.16, V.18 | Sentinel, Datasets, Scheduler, Retraining, Notificaciones, Dashboard, Portfolio |

---

### Módulos del Roadmap V — Referencia rápida

| Código | Módulo | Archivo | Descripción |
|---|---|---|---|
| V.1 | Decision Engine | `forex/prediction/decision_engine.py` | Decisión final BUY/SELL/HOLD/NO OPERAR con justificación |
| V.2 | Risk Engine | `forex/prediction/risk_engine.py` | SL/TP recomendados, tamaño de posición, riesgo % |
| V.3 | MTF Intelligence | `forex/prediction/mtf_coherence.py` | Coherencia multi-timeframe H1/H4/D1 |
| V.4 | Regime Detection | `forex/prediction/regime_detector.py` | Régimen actual: trending/ranging/volatile/breakout |
| V.5 | Quality Gate | `forex/prediction/quality_analyzer.py` | Valida calidad del CSV antes de entrenar |
| V.6 | Feature Importance | `forex/prediction/feature_importance.py` | SHAP + permutation importance, features óptimos |
| V.7 | Model Selection | `forex/prediction/model_selector.py` | Compara XGB/LGB/RF y selecciona el mejor |
| V.8 | Reliability Score | `forex/prediction/reliability_score.py` | Score compuesto 0–100 de confiabilidad de señal |
| V.9 | Backtest Protocol | `forex/prediction/backtest_protocol.py` | Protocolo estándar: Sharpe, Calmar, WFV, Monte Carlo |
| V.10 | Market Sentinel | `forex/market_sentinel.py` | Daemon de vigilancia continua de activos |
| V.11 | Dataset Updater | `forex/data/dataset_updater.py` | Actualización incremental de CSVs |
| V.12 | Scheduler Inteligente | `forex/scheduler/task_manager.py` | Orquestador de tareas periódicas |
| V.13 | Reentrenamiento Adaptativo | `forex/prediction/retrain_manager.py` | Detecta degradación y reentrena cuando es necesario |
| V.15 | Notificaciones Multi-Canal | `notifications/notifier.py` | Telegram, Discord, Desktop |
| V.16 | Dashboard Activo | `workspace/static/js/active_dashboard.js` | Sección 13 del Workspace — estado en tiempo real |
| V.18 | Portfolio Intelligence | `forex/portfolio/portfolio_ranker.py` | Ranking de oportunidades multi-activo por confiabilidad |

Todos los módulos están integrados en `forex/prediction/roadmap_v_integration.py`, que provee funciones de alto nivel y comandos CLI para cada uno.

---

### Comandos CLI del Roadmap V

Los comandos de Roadmap V se invocan desde `python main.py` igual que cualquier otro:

```bash
# V.5 — Quality Gate: analiza un CSV antes de entrenar
quality CSVs/H1/EURUSD.csv EURUSD H1

# V.4 — Regime Detection: régimen actual del mercado
regime CSVs/H1/EURUSD.csv EURUSD H1

# V.3 — MTF Coherence: coherencia multi-timeframe
mtf CSVs/D1/EURUSD.csv CSVs/H4/EURUSD.csv CSVs/H1/EURUSD.csv EURUSD

# V.8 — Reliability Score: calcula confiabilidad de señal
reliability 0.72 BUY 68.5 trending_bullish

# V.1 — Decision Engine: decisión final
decision BUY 0.72 trending_bullish 70

# V.2 — Risk Engine: cálculo de riesgo
risk BUY 1.2150 0.0035 78 trending_bullish EURUSD

# V.10 — Market Sentinel: estado del sentinel
sentinel status
sentinel signals

# V.18 — Portfolio Intelligence: ranking de oportunidades
portfolio ranking
portfolio export
```

También disponibles en el Workspace web vía Chat Center (mismos comandos en texto natural).

---

### Sección 13 — Dashboard Activo (V.16)

El Dashboard Activo es la **Sección 13 del Workspace** (icono de escudo en el sidebar). Muestra en tiempo real el estado de todo el sistema autónomo y se actualiza automáticamente cada **10 segundos**.

#### Cómo acceder

1. Lanzar el Workspace: `python workspace/server.py`
2. Abrir `http://localhost:8000`
3. Hacer clic en **Dashboard Activo** (icono de escudo 🛡️) en el sidebar

#### Paneles del Dashboard

| Panel | Qué muestra |
|---|---|
| **Market Sentinel** | Estado (idle/running), Circuit Breaker, activos bajo vigilancia, scans totales, señal y reliability por par |
| **Scheduler** | Estado (activo/pausado), lista de tareas programadas con estado y conteo de ejecuciones |
| **Signals Activas** | Señales con Reliability ≥ 50 desde `forex_analytics` en `memoria.db` — par, señal, confianza, régimen |
| **Datasets** | CSVs disponibles por timeframe (H1/H4/D1), filas y antigüedad en horas |

#### Controles disponibles

| Control | Acción |
|---|---|
| **Pausar / Reanudar Scheduler** | Pausa o reanuda el Scheduler Inteligente |
| **Añadir par al Sentinel** | Registra un nuevo par para vigilancia continua |
| **Forzar actualización** | Actualiza incrementalmente el dataset de un par (llama `actualizar csv`) |
| **Forzar reentrenamiento** | Lanza `full forex <csv>` en background para el par seleccionado |

#### Endpoints de la API (server.py)

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/sentinel/status` | Estado del Market Sentinel |
| GET | `/api/scheduler/tasks` | Tareas del Scheduler |
| GET | `/api/signals/active` | Señales activas (Reliability ≥ 50) |
| GET | `/api/datasets/status` | Antigüedad y filas de CSVs |
| POST | `/api/sentinel/add` | `{"pair": "EURUSD"}` |
| POST | `/api/sentinel/remove` | `{"pair": "EURUSD"}` |
| POST | `/api/scheduler/pause` | Pausa el Scheduler |
| POST | `/api/scheduler/resume` | Reanuda el Scheduler |
| POST | `/api/datasets/force_update` | `{"pair": "EURUSD", "timeframe": "H1"}` |
| POST | `/api/retrain/force` | `{"pair": "EURUSD", "timeframe": "H1"}` |

---

### Integración del Roadmap V en el pipeline existente

El Roadmap V se integra en `IntegratedPipeline` de forma **no bloqueante** (wrapped en try/except). Esto significa:

- Si un módulo V falla o no está instalado, el pipeline base (XGB+LGB+RF + WFV) **continúa funcionando normalmente**.
- Los resultados de Roadmap V enriquecen la salida pero no son requisito para obtener señal.

El módulo `roadmap_v_integration.py` centraliza todas las llamadas y puede usarse también standalone desde CLI o desde el Workspace vía Chat Center.

---

### Estado de implementación del Roadmap V

| Módulo | Estado | Notas |
|---|---|---|
| V.1–V.9 (Clusters A, B, C) | ✅ Implementado | Todos los módulos presentes y en funcionamiento |
| V.10 Market Sentinel | ✅ Implementado | `market_sentinel.py` presente; se activa vía Workspace o CLI |
| V.11 Dataset Updater | ✅ Implementado | Integrado con `force_update` endpoint |
| V.12 Scheduler | ✅ Implementado | `task_manager.py` + endpoint `/api/scheduler/tasks` |
| V.13 Retrain Manager | ✅ Implementado | Endpoint `/api/retrain/force` lanza full pipeline en background |
| V.15 Notificaciones | ✅ Implementado | `notifications/notifier.py` con Telegram/Discord/Desktop |
| V.16 Dashboard Activo | ✅ Implementado | Sección 13 del Workspace, 10 endpoints, polling cada 10s |
| V.18 Portfolio Intelligence | ✅ Implementado | `portfolio_ranker.py` + comandos `portfolio ranking/export` |

---

*Parte 30 añadida el 19 de julio de 2026 — integración de V.16 Dashboard Activo en Workspace, 10 endpoints nuevos en server.py, CSS del Dashboard Activo, MANUAL.md actualizado con índice completo (Partes 1–30) y documentación de todos los módulos del Roadmap V.*
