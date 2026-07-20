# Guía Completa de Comandos Forex — ASTRA (Roadmap V + VI)

## Comandos Roadmap V (Forex Lab Avanzado)

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `full forex <csv>` | Pipeline completo: train + predict + decision + risk | `full forex EURUSD.csv` |
| `quality <csv> [par] [tf]` | Quality Gate del dataset | `quality EURUSD.csv EURUSD H1` |
| `regime <csv> [par] [tf]` | Detección de régimen de mercado | `regime EURUSD.csv EURUSD H1` |
| `mtf <d1> <h4> <h1>` | Coherencia Multi-Timeframe | `mtf D1/EU.csv H4/EU.csv H1/EU.csv` |
| `reliability <conf> [señal]` | Reliability Score (0–100) | `reliability 0.75 BUY` |
| `decision <señal> <conf>` | Motor de decisión final | `decision BUY 0.75` |
| `risk <dir> <entry> <atr>` | SL/TP + position sizing | `risk BUY 1.0850 0.0012` |
| `backtest <modelo> <csv>` | Backtesting Walk-Forward | `backtest EURUSD EURUSD.csv` |
| `feature_importance <m> <csv>` | Importancia de features (SHAP) | `feature_importance EURUSD EURUSD.csv` |
| `dataset_update <par> [tf]` | Actualización incremental CSV | `dataset_update EURUSD H1` |
| `scheduler_status` | Estado del scheduler V | `scheduler_status` |
| `retrain_check <par>` | ¿Necesita reentrenar? | `retrain_check EURUSD` |
| `sentinel_status` | Estado del Market Sentinel | `sentinel_status` |
| `sentinel_signals [par] [n]` | Historial de señales | `sentinel_signals EURUSD 10` |
| `outcome_stats [par]` | Estadísticas de resultados reales | `outcome_stats EURUSD` |
| `notify_test <par> <señal> <r>` | Prueba de notificación | `notify_test EURUSD BUY 78` |
| `portfolio_ranking [señal] [min]` | Ranking multi-activo | `portfolio_ranking BUY 60` |
| `circuit status` | Estado del circuit breaker | `circuit status` |
| `circuit reset` | Reset manual del circuit breaker | `circuit reset` |
| `position size <par> [balance]` | Position sizing Kelly | `position size EURUSD 10000` |

## Comandos Roadmap VI (Autonomización & Data Intelligence)

| Comando | Descripción | Ejemplo |
|---------|-------------|---------|
| `self-test` | Diagnóstico completo del sistema (semáforo) | `self-test` |
| `descargar datos <par> [tf] [n]` | Descarga datos Forex/Crypto | `descargar datos EURUSD H1 500` |
| `migrar csv <path> [par] [tf]` | Migra CSV al formato rolling | `migrar csv raw/EURUSD.csv EURUSD H1` |
| `escanear csvs` | Escanea y registra todos los CSVs | `escanear csvs` |
| `csvs activos` | Lista el índice de CSVs activos | `csvs activos` |
| `rolling info <par> [tf]` | Estado del RollingDataset | `rolling info EURUSD H1` |
| `candlestick <csv>` | Detecta patrones de vela japonesa | `candlestick H1/EURUSD.csv` |
| `hparam cache` | Estado del caché de hiperparámetros | `hparam cache` |
| `hparam invalidar <par>` | Fuerza re-tune en próximo train | `hparam invalidar EURUSD` |
| `model cache` | Estado del Model Cache Manager | `model cache` |
| `adaptive budget <par>` | Historial de budgets adaptativos | `adaptive budget EURUSD` |
| `quality history` | Historial de precisión verificada | `quality history` |
| `scheduler start` | Inicia scheduler autónomo (background) | `scheduler start` |
| `scheduler stop` | Detiene el scheduler | `scheduler stop` |
| `scheduler info` | Estado y tareas del scheduler | `scheduler info` |
| `auto update` | Actualiza todos los CSVs activos | `auto update` |
| `opportunity ranking [n]` | Top N BUY/SELL por OpScore | `opportunity ranking 10` |

## Comandos Forex básicos (Roadmap II)

| Comando | Descripción |
|---------|-------------|
| `analiza forex <par> <csv>` | Análisis técnico completo (RSI, MACD, EMA, volatilidad) |
| `history <par>` | Historial de análisis guardados |
| `compare history <par>` | Comparación de los últimos reportes |
| `list markets` | Lista todos los mercados analizados |
| `watch forex <par> <csv>` | Monitoreo continuo en background |
| `watch status` | Ver pares activos en monitoreo |

## API interna — Módulos clave Roadmap VI

### HyperparameterCache (VI.1.A)
```python
c = get_cache()
c.save(pair, horizon, params_dict, csv_path='', accuracy=0.0, n_trials=0)
cached = c.get(pair, horizon, csv_path='')   # None si expirado o datos cambiaron
c.invalidate(pair, horizon)                   # fuerza re-tune
c.list_cached()                               # lista todos los entradas
```

### AdaptiveTrainer (VI.1.B)
```python
at = get_adaptive_trainer()
n = at.get_trials(pair, horizon='H1')                    # int: trials sugeridos
at.log_result(pair, horizon, mode, n_trials, accuracy, duration_s)
mode = at.recommended_mode(is_scheduler=False, is_first_train=False)
```

### ModelCacheManager (VI.1.C)
```python
mc = get_model_cache()
mc.register_model(pair, horizon, model_path, csv_path, accuracy)
should, reason = mc.should_retrain(pair, horizon, csv_path)  # tuple[bool, str]
```

### SignalInput (VI.8.A) — campos reales
```python
sig = SignalInput(
    pair='EURUSD',
    direction='BUY',          # 'BUY', 'SELL', 'HOLD'
    reliability_score=76.0,   # 0–100
    win_rate_pct=65.0,        # 0–100 (porcentaje, no fracción)
    regime='trending_bullish',
    mtf_coherent=True,        # bool
    candlestick_confirm=True, # bool
    current_price=1.0850,
)
result = calculate_op_score(sig)   # -> OpportunityResult
ranking = ranker.rank([sig1, sig2, ...])
# ranking['top_buy']  → list[OpportunityResult]
# ranking['top_sell'] → list[OpportunityResult]
```

### RollingDataset (VI.6.A)
```python
rd = get_rolling_dataset(pair, tf)
rd.load()               # carga desde CSV
rd.initialize(df)       # primer carga desde DataFrame
rd.update(candle_dict)  # añade vela, mantiene max_rows=5000
v = rd.validate()       # {'ok': bool, 'rows': int, ...}
rd.info()               # str resumen
```

### ModelQualityHistory (VI.8.C)
```python
qh = get_quality_history()
qh.record_prediction(pair, horizon, model_name, predicted_dir, op_score=0.0)
qh.record_outcome(pair, horizon, model_name, prediction_ts, actual_dir)
acc = qh.get_accuracy(pair, horizon, model_name)  # float | None
wr  = qh.get_win_rate(pair, horizon)              # float (0.0 si sin historial)
```

## Fuentes de datos (Roadmap VI.7)

| Fuente | Tipo de activo | Disponibilidad |
|--------|---------------|----------------|
| **MT5 (MetaTrader 5)** | Forex primario | Solo Windows con MT5 instalado |
| **Yahoo Finance** | Forex + acciones + índices | Siempre (requiere `pip install yfinance`) |
| **Binance** | Criptomonedas | Siempre (no requiere API key para datos históricos) |

ASTRA selecciona automáticamente la mejor fuente disponible con fallback:
```
MT5 → Yahoo Finance → Error
Binance (crypto) → Yahoo Finance → Error
```

## Patrones de vela detectados (VI.5.D)

| Patrón | Sesgo | Descripción |
|--------|-------|-------------|
| Doji | Neutral | Cuerpo muy pequeño, indecisión |
| Hammer | Alcista | Sombra inferior larga, cuerpo arriba |
| Shooting Star | Bajista | Sombra superior larga, cuerpo abajo |
| Bullish Engulfing | Alcista | Vela alcista engulle a la bajista anterior |
| Bearish Engulfing | Bajista | Vela bajista engulle a la alcista anterior |
| Bullish Harami | Alcista | Vela pequeña alcista dentro de la bajista anterior |
| Bearish Harami | Bajista | Vela pequeña bajista dentro de la alcista anterior |
| Morning Star | Alcista | Patrón de 3 velas: bajista + indecisión + alcista |
| Evening Star | Bajista | Patrón de 3 velas: alcista + indecisión + bajista |
