# ASTRA — Manual de Usuario
**Sistema AI Modular · Consultor PYME · v2.0**

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

:: 5. Configurar la API key de Groq (una sola vez)
setx GROQ_API_KEY "gsk_tu_key_aqui"
:: Cierra y vuelve a abrir el terminal para que tome efecto

:: 6. Lanzar ASTRA
cd artifacts\astra
python main.py
```

> **Alternativa a setx**: crea un archivo `.env` dentro de `artifacts\astra\` con:
> ```
> GROQ_API_KEY=gsk_tu_key_aqui
> ```
> Luego instala `pip install python-dotenv` y añade al inicio de `main.py`:
> ```python
> from dotenv import load_dotenv; load_dotenv()
> ```

---

### Instalación en Linux / Replit

```bash
# 1. Instalar dependencias
pip install -r artifacts/astra/requirements.txt

# 2. La API key ya está configurada en Replit Secrets como GROQ_API_KEY
#    (no se necesita ningún paso extra en Replit)

# 3. Lanzar ASTRA
cd artifacts/astra && python main.py
```

En Replit el workflow **"ASTRA AI"** hace el paso 3 automáticamente al abrir el proyecto.

---

### Diagnóstico antes de arrancar (opcional pero útil)

```bash
cd artifacts/astra
python check_startup.py
```

Resultado esperado:
- Phase 2: 35 paquetes OK, 0 critical failures
- Phase 3: 18/18 módulos OK
- Phase 4: 12/12 módulos Forex/BI OK
- Phase 5: 4/4 smoke tests OK
- Final: `No critical issues found`

Los `WARN` (torch, tensorflow, redis, librosa…) son **opcionales** — no bloquean el arranque.

---

### Instalar paquetes opcionales (si los necesitas)

```bash
pip install torch           # PyTorch — deep learning
pip install tensorflow      # TensorFlow
pip install redis           # cliente Redis
pip install scikit-image    # procesamiento de imagen
pip install librosa         # análisis de audio
pip install python-dotenv   # carga .env automáticamente
```

---

## PARTE 2 — COMANDOS DISPONIBLES

Una vez dentro del asistente (prompt `Tú:`), escribe en lenguaje natural.
El archivo CSV/Excel puede estar en cualquier ruta relativa a `artifacts/astra/`.

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

#### Sistema
| Comando | Qué hace |
|---|---|
| `estado pc` | CPU, RAM, disco y uptime |
| `ayuda` | Lista todos los comandos disponibles |

---

### Branch 2 — Análisis Forex

El sistema reconoce 41 pares: EUR/USD, GBP/USD, USD/JPY, BTC/USD, commodities, etc.

| Comando | Qué hace |
|---|---|
| `analiza forex eurusd datos.csv` | Análisis técnico completo: RSI, MACD, EMA, CCI, MFI, ROC, volatilidad, señal ML |
| `forex eurusd` | Reconoce el par y muestra estado del mercado |
| `history eurusd` | Historial de análisis guardados para ese par |
| `compare history eurusd` | Compara los últimos reportes guardados |
| `list markets` | Lista todos los mercados analizados hasta ahora |

#### Indicadores técnicos incluidos en el análisis

| Grupo | Indicadores |
|---|---|
| Momentum | RSI-14, Williams %R, Estocástico (14,3) |
| Tendencia | MACD (12/26/9), EMA 20/50/150, ADX-14, cruce EMA |
| Volatilidad | ATR-14, Bollinger Bands (20), ATR relativo |
| Ciclo / extremos | **CCI-20** — sobrecompra/sobreventa sin límite |
| Volumen | OBV, **MFI-14** — RSI ponderado por volumen |
| Momentum % | **ROC-10** — cambio normalizado, comparable entre pares |
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

El archivo debe tener columnas como `revenue`/`ingresos`, `expenses`/`gastos`, `date`/`fecha`.
Formatos soportados: `.csv`, `.xlsx`, `.xls`

---

### Branch 4 — Consultor PYME Avanzado

Los cuatro módulos del consultor estratégico. Todos generan narración automática de **Llama-3.3-70B** al finalizar.

#### `diagnóstico pyme`
```
diagnóstico pyme ventas.csv
```
Genera un **Scorecard Multidimensional** con tres dimensiones independientes:
- **Salud Financiera** (40%): márgenes bruto/neto, ratio de gastos, saldo mínimo
- **Salud de Crecimiento** (35%): CAGR, tendencia MoM, YoY
- **Nivel de Riesgo** (25%): volatilidad, concentración, estabilidad

Resultado: puntuación 0–100 por dimensión + puntuación global + KPI table + alertas.

---

#### `forecast negocio`
```
forecast negocio ventas.csv
forecast negocio ventas.csv 12
```
Proyección de ingresos con tres bandas:
- **Optimista**: tendencia + 1σ
- **Esperado**: extrapolación lineal (R² como confianza)
- **Conservador**: tendencia − 1σ

Por defecto 6 meses; añade un número al final para otro plazo (ej: `12`).

---

#### `plan de accion`
```
plan de accion ventas.csv
```
Llama-3.3-70B analiza el diagnóstico y genera un **Plan Estratégico** con 5 recomendaciones priorizadas, cada una con:
- Acción concreta
- Impacto esperado (en % o puntos KPI)
- Plazo de implementación (corto / medio / largo)

---

#### `simular escenario`
```
que pasa si reduzco costos 15% ventas.csv
si aumento ventas ventas.csv 20%
que ocurre si mejoro margen 10% datos.csv
```
Simulación What-If: el sistema interpreta el escenario en lenguaje natural, aplica el cambio sobre los datos reales y muestra una tabla **Antes / Después** con:
- Todas las dimensiones del scorecard
- KPIs clave (ingresos, ratio gastos, márgenes)
- Delta (Δ) de cada métrica

---

### Auto-Análisis del sistema

| Comando | Qué hace |
|---|---|
| `analiza astra` | Genera reporte completo del sistema |
| `self analysis` | Alias en inglés |
| `reporte sistema` | Alias en español |
| `reporte astra` | Alias alternativo |

El reporte se guarda como `REPORT DD-MM.md` en `artifacts/astra/` (un archivo por día).
Incluye: estado del sistema, motor AI activo, herramientas registradas, módulos opcionales, roadmap.

---

## PARTE 3 — ESTRUCTURA DE ARCHIVOS DE DATOS

### CSV Forex (Branch 2)

El sistema acepta el formato de exportación estándar de plataformas de trading. Las columnas OHLCV son obligatorias; el resto puede estar en `NaN` — si falta un valor, el sistema lo calcula automáticamente desde OHLCV y lo escribe en su lugar.

| Columna | Obligatoria | Descripción |
|---|---|---|
| `timestamp` | ✅ Sí | Fecha y hora (cualquier formato ISO 8601) |
| `open` | ✅ Sí | Precio de apertura |
| `high` | ✅ Sí | Precio máximo |
| `low` | ✅ Sí | Precio mínimo |
| `close` | ✅ Sí | Precio de cierre |
| `volume` | ✅ Sí | Volumen (necesario para MFI y OBV) |
| `rsi_14` | ☑ Opcional | RSI de 14 períodos (se recalcula si NaN) |
| `macd` / `macd_signal` / `macd_histogram` | ☑ Opcional | MACD 12/26/9 (se recalcula si NaN) |
| `atr_14` | ☑ Opcional | ATR de 14 períodos (se recalcula si NaN o = 0) |
| `ema_20` / `ema_50` / `ema_150` | ☑ Opcional | EMAs (se recalcula si NaN) |
| `bollinger_upper_20` / `bollinger_lower_20` | ☑ Opcional | Bandas de Bollinger (se recalcula si NaN) |
| `return_5` | ☑ Opcional | Retorno a 5 períodos en % (se recalcula si NaN) |
| `volatility_20` | ☑ Opcional | Volatilidad rolling 20 (se recalcula si NaN) |

> **Comportamiento NaN:** si una celda de indicador está en NaN, el sistema la computa desde OHLCV y la sobreescribe. El valor original no-NaN nunca se toca.
>
> **ATR = 0.0:** los valores ATR de exactamente 0.0 son tratados como NaN y recalculados (un ATR real nunca es cero para precios OHLCV reales).

Los pares se detectan automáticamente desde el nombre del archivo (ej: `aud_usd_dataset.csv` → AUDUSD). También puedes indicarlo en el comando: `analiza forex audusd datos.csv`.

---

### CSV Negocio / PYME (Branches 3 y 4)

Para que los módulos BI y Branch 4 funcionen correctamente, el CSV/Excel debe tener al menos estas columnas (los nombres son flexibles — el sistema los detecta automáticamente):

| Columna | Alias aceptados | Tipo |
|---|---|---|
| Fecha | `date`, `fecha`, `periodo`, `mes` | fecha o texto |
| Ingresos | `revenue`, `ingresos`, `ventas`, `sales` | numérico |
| Gastos | `expenses`, `gastos`, `costos`, `costs` | numérico |
| Ganancia bruta | `gross_profit`, `ganancia_bruta` | numérico (opcional) |
| Ingreso neto | `net_income`, `ingreso_neto`, `beneficio` | numérico (opcional) |
| Saldo | `balance`, `saldo`, `cash` | numérico (opcional) |

Mínimo viable: `date` + `revenue` + `expenses` (el resto se calcula internamente).

---

## PARTE 4 — MOTOR AI Y MEMORIA

### Motor de lenguaje
ASTRA usa **Llama-3.3-70B** (vía Groq). Si `GROQ_API_KEY` no está configurada, intenta con `OPENAI_API_KEY` (GPT-3.5-turbo) como fallback.

### Memoria
- **Sesión activa**: ASTRA recuerda los últimos 20 turnos de la conversación en memoria RAM. Puede referirse a respuestas anteriores de la misma sesión.
- **Persistencia**: Los turnos se guardan en `memoria.db` (SQLite). Al reiniciar, carga los últimos 6 intercambios automáticamente.
- La memoria se limpia sola cuando supera el límite. No necesitas hacer nada.

---

## PARTE 5 — ROADMAP

| Branch | Nombre | Estado |
|---|---|---|
| 1 | Core (Tool Registry, Memory, File I/O, Security) | ✅ Completo |
| 2 | Prediction Framework (Forex ML pipeline) | ✅ Completo |
| 3 | Business Intelligence Engine (KPIs, BI pipeline) | ✅ Completo |
| 4 | SME/PYME Consultant (Diagnostic, Forecast, Recommend, Simulate) | ✅ Completo |
| 5 | Industry Packs (Retail, Restaurante, E-Commerce, Manufactura) | 🔄 Próximo |
| 6 | Multi-Agent ASTRA | 🕐 Futuro |
| 7 | Executive Copilot | 🕐 Futuro |

---

## PARTE 6 — SOLUCIÓN DE PROBLEMAS

| Síntoma | Causa probable | Solución |
|---|---|---|
| `GROQ_API_KEY not found` | Key no configurada | Sigue los pasos de la Parte 1 |
| `ModuleNotFoundError: openai` | Falta el paquete | `pip install openai` |
| `lightgbm` crash en Linux | Falta libgomp | El workflow lo configura automáticamente vía `LD_LIBRARY_PATH` |
| Torch/TensorFlow WARN | Son opcionales | Ignóralos o instala con `pip install torch` |
| `redis` WARN | Es opcional | Ignóralo o instala con `pip install redis` |
| Sin audio/TTS en Linux | pyttsx3 silenciado | Funcionalidad solo disponible en Windows con dispositivo de audio |
| CSV no reconocido | Columnas con nombres distintos | Renombra a `date`, `revenue`, `expenses` (ver Parte 3) |

---

*Generado para ASTRA v2.1 — Branch 2 actualizado (CCI, MFI, ROC, ATR relativo + imputation NaN) — Branch 4 completo — Junio 2026*
