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

---

## PARTE 9 — Predicción Forex para Inversión Real (Guía Paso a Paso)

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
