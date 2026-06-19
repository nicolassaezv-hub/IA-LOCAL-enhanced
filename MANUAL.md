# ASTRA — User Manual
## Complete Guide to Getting the Most Out of Your AI System

---

## Table of Contents

1. [What is ASTRA?](#1-what-is-astra)
2. [Requirements & Setup](#2-requirements--setup)
3. [Starting ASTRA](#3-starting-astra)
4. [Forex Prediction Pipeline](#4-forex-prediction-pipeline)
5. [Document Commands](#5-document-commands)
6. [Web Tools](#6-web-tools)
7. [AI & Machine Learning Demos](#7-ai--machine-learning-demos)
8. [Security & Cryptography](#8-security--cryptography)
9. [Visualization](#9-visualization)
10. [System & Utilities](#10-system--utilities)
11. [Memory & Database](#11-memory--database)
12. [Audio & Video](#12-audio--video)
13. [GPT Fallback (Free Chat)](#13-gpt-fallback-free-chat)
14. [CSV Format Guide for Forex](#14-csv-format-guide-for-forex)
15. [Tips for Full Potential](#15-tips-for-full-potential)
16. [Limitations in Hosted Mode](#16-limitations-in-hosted-mode)

---

## 1. What is ASTRA?

ASTRA is a local AI-powered modular system with **66 registered tools**. It combines:

- **Forex ML pipeline** — XGBoost model that learns from your OHLCV data and predicts price direction
- **Technical analytics** — RSI, MACD, EMA, ATR, Bollinger Bands, volatility, session analysis, market regime detection
- **Document tools** — read and write PDF, Word, Excel, CSV
- **Web tools** — scraping, translation, YouTube download
- **Security utilities** — bcrypt hashing, JWT tokens, Fernet encryption
- **AI models** — PyTorch, TensorFlow, Keras, Scikit-learn running locally
- **GPT integration** — any unrecognized input is sent to OpenAI's GPT for free-form response

Type `ayuda` at any time to see the command reference.

---

## 2. Requirements & Setup

### Required

| Item | Details |
|---|---|
| **OpenAI API Key** | Add as secret `OPENAI_API_KEY`. Without it, chat/GPT commands return an error, but all other tools work fine. |
| **CSV data** | For Forex ML features, your CSV must have specific columns (see Section 14). |

### Optional

| Item | Details |
|---|---|
| Redis | For `redis set` / `redis get` commands. Not required to run. |
| Microphone/speakers | For `voz a texto` / `texto a voz` — not available in hosted/cloud mode. |

---

## 3. Starting ASTRA

ASTRA starts automatically via the **"Start application"** workflow. You will see:

```
╔══════════════════════════════════════════╗
║        ASTRA  —  Modular AI System       ║
║  Forex · ML · Security · Documents · Web ║
╚══════════════════════════════════════════╝
  66 tools loaded  |  type 'ayuda' for commands

Tú: _
```

Type any command and press Enter. Type `salir` or `exit` to quit.

---

## 4. Forex Prediction Pipeline

This is ASTRA's most powerful feature. The pipeline uses **XGBoost** (gradient boosting) to learn from historical OHLCV data and predict whether the next candle will close higher (bullish) or lower (bearish).

### Workflow — Do This in Order

#### Step 1 — Train the model

```
train forex data/eurusd_h1.csv
```

What happens:
- Loads your CSV
- Applies feature engineering (lag features, rolling stats, price structure, momentum, market regime)
- Builds target labels (next candle up/down)
- Splits data 80% train / 20% test (time-ordered — no lookahead leakage)
- Trains XGBoost with 500 trees, learning rate 0.05, early stopping at 30 rounds
- Auto-balances bullish/bearish classes
- Prints accuracy, precision, recall, F1 per class
- Shows top-10 feature importance ranking
- Saves model to `models/forex/latest_model.pkl`

You only need to train once per dataset. After training, the model persists.

#### Step 2 — Predict on new data

```
predict forex data/eurusd_new.csv
```

Output example:
```json
{
  "type": "prediction",
  "rows_processed": 1420,
  "signal": "bullish",
  "confidence": 0.7312,
  "interpretation": "Strong signal — act with care"
}
```

Confidence > 0.70 = strong signal. Below = wait for confirmation.

#### Step 3 — Backtest the model

```
backtest forex data/eurusd_h1.csv
```

Runs the model on the **held-out test portion** (last 20% of data — never seen during training). Simulates trading with 1% risk per trade, confidence-scaled position sizing.

Output includes:
- `win_rate` — percentage of profitable trades
- `profit_factor` — ratio of total wins to total losses (> 1.0 is profitable)
- `max_drawdown` — worst peak-to-trough loss
- `total_return` and `total_return_pct`

#### Step 4 (optional) — Full pipeline in one shot

```
full forex data/eurusd_h1.csv
```

Runs train + predict + backtest together. Best for a first look at a new dataset.

---

### Technical Analytics (no model needed)

```
analiza forex data/eurusd.csv EUR/USD
```

Generates a full technical report including:
- Dataset profile (rows, columns, missing values)
- Session breakdown (Tokyo / London / New York volume, spread, volatility)
- RSI analysis (mean, max, min, overbought/oversold counts)
- MACD (bullish/bearish periods, histogram average)
- Volatility stats (mean, std, max, min)
- EMA trend (bullish/bearish candle ratios: EMA20 > EMA50 > EMA200)
- Market regime clustering (KMeans on returns + ATR + volatility)
- Report is **automatically saved** to `data/forex_analytics/`

You can also pass just the symbol name if the market is already in memory:
```
analiza forex EUR/USD
```

---

### Market & History Commands

| Command | What it does |
|---|---|
| `lista mercados` | Show all 27 Forex pairs and 20 commodities supported |
| `mercados analizados` | List all markets that have been analyzed and saved |
| `historial forex EUR/USD` | Show all past analysis reports for EUR/USD |
| `compara forex EUR/USD` | Compare the last 5 reports for EUR/USD side-by-side |

Supported pair aliases (no slash needed):
`eurusd`, `gbpusd`, `usdjpy`, `audusd`, `nzdusd`, `usdcad`, `usdchf`, `eurjpy`, `gbpjpy`, `eurgbp` and more.

Commodity aliases: `brent`, `wti`, `natgas`, `robusta`, `feeder cattle`, etc.

---

## 5. Document Commands

### Read Files

| Command | Example |
|---|---|
| `lee pdf <path>` | `lee pdf reports/quarterly.pdf` |
| `lee word <path>` | `lee word notes/meeting.docx` |
| `lee excel <path>` | `lee excel data/budget.xlsx` |
| `lee csv <path>` | `lee csv data/prices.csv` |
| `analiza csv <path>` | `analiza csv data/prices.csv` |

`lee csv` shows the first 50 rows. `analiza csv` shows full column stats (mean, std, min, max, count, nulls).

### Write Files

| Command | Example |
|---|---|
| `escribe pdf <path> <text>` | `escribe pdf output/report.pdf "Quarterly Results 2025"` |
| `escribe word <path> <text>` | `escribe word output/notes.docx "Meeting notes from June"` |
| `escribe excel <path> <data>` | `escribe excel output/data.xlsx "Name,Score\nAlice,95\nBob,87"` |
| `escribe csv <path> <data>` | `escribe csv output/log.csv "time,value\n12:00,100"` |

### Generate Python Script with GPT

```
crea py output/scraper.py "a web scraper that gets news headlines"
```

Sends the topic to GPT, gets Python code back, saves it as a `.py` file.

---

## 6. Web Tools

### Scrape a Webpage

```
extrae web https://example.com
```

Returns the first 1000 characters of visible text from the page.

### Translate Text

```
traducir Hola mundo, esto es ASTRA en acción
```

Auto-detects source language, translates to English. To specify a different target:
modify the command to use `deep_translator.GoogleTranslator(target="es")` in `web_tools.py`.

### Download YouTube Video

```
youtube https://www.youtube.com/watch?v=XXXXXXXXXXX
```

Downloads the highest resolution stream to the current directory.

### Framework Demos

These initialize framework objects without starting servers — useful to verify the libraries work:

```
httpx demo
aiohttp demo
socketio demo
fastapi demo
flask demo
```

---

## 7. AI & Machine Learning Demos

These run locally — no API key needed.

### PyTorch

```
torch demo
```
Creates two tensors `[1,2,3]` and `[4,5,6]`, multiplies them element-wise. Output: `[4, 10, 18]`. Confirms PyTorch is running on CPU.

### TensorFlow

```
tensorflow demo
```
Creates constant tensors and adds them. Confirms TF is installed and running.

### Keras

```
keras demo
```
Builds a Sequential model with Dense layers. Confirms Keras can construct neural networks.

### Scikit-learn

```
sklearn demo
```
Splits a small dataset 80/20, confirms train/test sizes. Quick sanity check.

### Symbolic Integration (SymPy)

```
integral
```
Computes ∫₀¹ x² dx symbolically. Returns exact result: `1/3`.

### Analyze Python Code with GPT

```
analiza codigo main.py
analiza codigo main.py security.py visualization.py
```

Parses each file with Python's `ast` module, lists all functions, then sends the code to GPT for improvement suggestions. Multiple files supported.

---

## 8. Security & Cryptography

All cryptographic operations run **locally** — nothing is sent externally.

### Password Hashing

```
hash pass mysecretpassword
```
Returns a bcrypt hash. Bcrypt is slow by design — resistant to brute-force attacks.

```
verify pass $2b$12$... mysecretpassword
```
Returns `True` or `False`. Use the exact hash output from `hash pass`.

### Passlib (alternative hashing context)

```
passlib hash mysecretpassword
passlib verify $2b$... mysecretpassword
```
Uses the Passlib CryptContext — same bcrypt algorithm, alternative interface.

### JWT Tokens

```
crear jwt
```
Creates a signed JWT token with payload `{"user": "astra", "role": "admin"}` and secret `mi_clave_secreta`.

```
verificar jwt eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```
Decodes and verifies the token. Returns the payload dict.

> **For production:** Change the secret in `security.py` and pass your own payload via code.

### File Encryption

```
cifra archivo data/sensitive.txt
```
Encrypts the file using **Fernet** (AES-128-CBC with HMAC). Creates `data/sensitive.txt.cifrado`. The encryption key is printed — **save it**, it cannot be recovered.

### SSH Client Demo

```
paramiko demo
```
Initializes a Paramiko SSH client (does not connect to any server). Confirms the library is ready.

---

## 9. Visualization

All charts are saved as **image files** (no display in hosted mode).

### Plot a CSV Column

```
grafica csv data/prices.csv
```
Reads the first numeric column, generates a histogram + KDE curve, saves as `grafico.png`.

### Pretty-print CSV as Table

```
tabla data/prices.csv
```
Renders the CSV as a formatted grid table in the console (first 10 rows).

### Rich Text

```
rich This is styled output
```
Prints text using the Rich library (color + formatting support in terminal).

### Create PDF

```
crear pdf output/report.pdf Hello from ASTRA
```
Creates a simple single-page PDF with the given text using ReportLab.

### Image Processing Demo

```
imagen
```
Loads a built-in scikit-image sample (coins image), runs Sobel edge detection, prints the resulting shape. Confirms image processing pipeline works.

---

## 10. System & Utilities

### System Status

```
estado pc
```
Returns current CPU usage (%) and RAM usage (%). Fast, no external calls.

### Current Date/Time

```
fecha
```
Returns the current UTC datetime using Arrow. Example: `Fecha actual: 2025-06-19T14:30:00+00:00`

### JSON Serialization Demo

```
json
```
Serializes `{"msg": "ok", "sistema": "ASTRA"}` with orjson and prints the result. Confirms the fast JSON library works.

### Progress Bar Demo

```
barra progreso
```
Runs a tqdm progress bar over 10 iterations with 0.2s sleep. Shows what progress bars look like in your terminal.

### Scheduled Task Demo

```
tarea programada
```
Registers a schedule that would print a message every minute. Returns instructions for wiring it into a loop.

### File Lock Demo

```
bloquear archivo data/myfile.txt
```
Acquires an exclusive file lock on `data/myfile.txt.lock`, holds it 2 seconds, releases it. Useful for multi-process file access patterns.

### File System Monitor

```
monitor archivos data/
```
Starts a Watchdog observer on the given directory. Prints a message whenever any file inside is modified. Runs in background thread.

---

## 11. Memory & Database

### Redis Key-Value Store

Requires Redis to be running (optional).

```
redis set         →  stores "clave" = "Hola desde Redis"
redis get         →  retrieves the value of "clave"
```

### SQLAlchemy Demo

```
sqlalchemy usuario
```
Creates an in-memory SQLite database, inserts a user named "Nico", confirms the write. Demonstrates SQLAlchemy ORM usage.

### FAISS Vector Memory

```
faiss add         →  Instructions for adding vectors
faiss search      →  Instructions for searching vectors
```

FAISS enables similarity search over high-dimensional vectors — useful for semantic memory. You can use it programmatically:
```python
from modules_extra import FaissMemory
mem = FaissMemory(dim=128)
mem.add(my_vector, "my text")
results = mem.search(query_vector, k=3)
```

### LlamaIndex Document Memory

```
llama add         →  Instructions for indexing documents
llama query       →  Instructions for querying
```

LlamaIndex wraps OpenAI embeddings for semantic document search. Requires `OPENAI_API_KEY`. Use it programmatically:
```python
from modules_extra import LlamaMemory
mem = LlamaMemory()
mem.add_doc("Forex pair EUR/USD analysis report...")
answer = mem.query("What was the trend?")
```

### Symbolic Math (SymPy)

```
sympy integral
```
Computes ∫₀^π sin(x) dx symbolically. Returns exact value: `2`.

---

## 12. Audio & Video

> **Note:** These commands require hardware (microphone, speakers) not available in hosted/cloud environments. They work correctly when running ASTRA locally on your machine.

### Speech to Text

```
voz a texto
```
Listens to your microphone, transcribes in Spanish using Google Speech Recognition API (free tier, requires internet).

### Text to Speech

```
texto a voz Buenos días, soy ASTRA
```
Speaks the text aloud using pyttsx3 (local TTS engine, no API needed).

### Audio Analysis

```
analiza audio recordings/sample.mp3
```
Loads audio with Librosa, computes duration (seconds) and estimated BPM.

### Audio Playback

```
reproducir audio recordings/sample.wav
```
Plays audio through your speakers using SoundDevice.

### Audio Conversion

```
convertir audio recordings/sample.wav mp3
```
Converts audio format using PyDub. Supports mp3, wav, ogg, flac, etc.

### YouTube Audio Download

```
descargar audio youtube https://www.youtube.com/watch?v=XXXXXXXXXXX
```
Downloads only the audio track from a YouTube video.

---

## 13. GPT Fallback (Free Chat)

Any input not matched by a command is **automatically sent to GPT**:

```
Tú: What is the best timeframe for scalping EUR/USD?
Copilot: [GPT response...]

Tú: Explícame qué es el MACD
Copilot: [GPT response in Spanish...]

Tú: Write me a Python function that computes RSI
Copilot: [GPT code response...]
```

**Requirements:** `OPENAI_API_KEY` must be set as an environment secret.

GPT also has access to:
- The last 10 conversation turns (memory)
- Current CPU/RAM status (injected automatically)

This means GPT knows the context of your session and can answer follow-up questions.

---

## 14. CSV Format Guide for Forex

For the ML prediction pipeline (`train forex`, `predict forex`, `backtest forex`), your CSV must contain these columns:

### Required Columns

| Column | Description | Example |
|---|---|---|
| `timestamp` | Datetime of the candle | `2024-01-15 08:00:00` |
| `open` | Opening price | `1.08542` |
| `high` | High price | `1.08680` |
| `low` | Low price | `1.08490` |
| `close` | Closing price | `1.08621` |
| `volume` | Volume (tick or lot) | `12540` |
| `spread` | Bid-ask spread in pips | `0.8` |
| `RSI_14` | RSI with period 14 | `54.3` |
| `MACD` | MACD line | `0.00042` |
| `MACD_signal` | Signal line | `0.00031` |
| `MACD_hist` | MACD histogram | `0.00011` |
| `ATR_14` | Average True Range, 14 periods | `0.00085` |
| `EMA20` | Exponential MA 20 | `1.08410` |
| `EMA50` | Exponential MA 50 | `1.08200` |
| `EMA200` | Exponential MA 200 | `1.07900` |
| `volatility_24h` | Rolling 24h volatility | `0.00062` |
| `BB_upper` | Bollinger Band upper | `1.09010` |
| `BB_lower` | Bollinger Band lower | `1.07830` |
| `returns` | Log return: ln(close/prev_close) | `0.00073` |
| `session` | Trading session | `London` |
| `pair` | Currency pair | `EUR/USD` |

### Session Values

The `session` column must be one of: `Tokyo`, `London`, `NewYork`

### Minimum Rows

- Training: at least **50 rows** recommended (more is better — 1000+ for reliable results)
- Prediction: at least **25 rows** (for lag features and rolling calculations)

### How to Prepare Your CSV

Most brokers and data providers export OHLCV data in MT4/MT5 format. You can compute the indicators with any tool (TradingView Pine Script, pandas-ta, ta-lib, etc.) and add them as columns before feeding to ASTRA.

Example with pandas-ta:
```python
import pandas as pd
import pandas_ta as ta

df = pd.read_csv("eurusd_raw.csv")
df.ta.rsi(length=14, append=True)
df.ta.macd(fast=12, slow=26, signal=9, append=True)
df.ta.ema(length=20, append=True)
df.ta.ema(length=50, append=True)
df.ta.ema(length=200, append=True)
df.ta.atr(length=14, append=True)
df.ta.bbands(length=20, append=True)
df["returns"] = df["close"].pct_change().apply(lambda x: __import__("math").log(1 + x))
df["pair"] = "EUR/USD"
df["session"] = "London"   # or compute based on hour
df.to_csv("eurusd_ready.csv", index=False)
```

---

## 15. Tips for Full Potential

### Forex ML

1. **Use at least 2000+ candles** for training — XGBoost needs enough data to learn patterns. H1 bars: 2 years ≈ 17,000 rows. M15 bars: 6 months ≈ 16,000 rows.
2. **Retrain regularly** — markets evolve. Retrain monthly or when drawdown exceeds 15%.
3. **Check feature importance** — the trainer prints which features matter most. If RSI_14 ranks very low, your RSI data may be incorrect.
4. **Confidence threshold** — only act on signals with confidence > 0.65. Confidence < 0.55 is essentially random.
5. **Backtest on clean data** — use data from a different time period than training data for the most honest backtest.
6. **Profit factor > 1.5** means the model is consistently earning more than it loses on the test set.

### GPT Integration

1. Use GPT for analysis after running Forex commands: "What does a win rate of 52% mean for my strategy?"
2. Use `analiza codigo` to get GPT to review and suggest improvements to any `.py` file in the project.
3. Combine tools: `lee pdf research.pdf` → then ask GPT "Summarize what I just read".

### Security

1. Never use `crear jwt` default secret in production — edit `security.py` to use `os.environ["JWT_SECRET"]`.
2. When using `cifra archivo`, save the printed key somewhere safe — there is no recovery without it.

### Memory

1. All chat turns are saved in `memoria.db` (SQLite) — GPT remembers the last 10 exchanges.
2. Use `LlamaMemory` programmatically to build a searchable knowledge base from your own documents.

---

## 16. Limitations in Hosted Mode

When running ASTRA in Replit's cloud environment (instead of your local machine):

| Feature | Status | Reason |
|---|---|---|
| `voz a texto` | ❌ Not available | No microphone hardware |
| `texto a voz` | ❌ Not available | No audio output device |
| `reproducir audio` | ❌ Not available | No speakers |
| `gui` (PyQt5) | ❌ Not available | No display server (headless) |
| `redis set/get` | ⚠️ Only if Redis is running | Installed separately |
| All Forex ML commands | ✅ Fully functional | Pure Python/CPU |
| All document commands | ✅ Fully functional | File-based |
| All web tools | ✅ Fully functional | HTTP-based |
| All security tools | ✅ Fully functional | Pure Python |
| GPT fallback | ✅ Requires API key | Set `OPENAI_API_KEY` secret |

---

*ASTRA — Built for experimentation, learning, and real Forex analysis.*
*Type `ayuda` in the console to see all commands at any time.*
