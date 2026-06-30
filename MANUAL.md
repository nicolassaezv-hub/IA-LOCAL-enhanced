# ASTRA — Manual de Usuario
**Sistema AI Modular · Consultor PYME · Análisis Forex · v2.2 — Fases 1-4**

---

## ÁNDICE

1. [Instalación](#parte-1--instalación-y-arranque)
2. [Generación de CSVs Forex](#parte-2--generación-de-csvs-forex-creandopy)
3. [Análisis y Predicción Forex](#parte-3--análisis-y-predicción-forex)
4. [Documentos y Web](#parte-4--documentos-web-y-utilidades)
5. [Consultor PYME](#parte-5--consultor-pyme-avanzado)
6. [Business Intelligence](#parte-6--business-intelligence-bi-engine)
7. [Sistema y Auto-Análisis](#parte-7--sistema-y-auto-análisis)
8. [Estructura de archivos CSV](#parte-8--formato-de-archivos-csv)

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
