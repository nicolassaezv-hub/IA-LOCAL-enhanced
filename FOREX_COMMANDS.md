# ASTRA — Referencia de Comandos CLI de Forex

> **Roadmap V — Fase V.17**
> Todos los comandos CLI disponibles para Forex Lab.

---

## Comandos por Fase

### V.5 — Quality Gate

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `quality` | `quality <csv_path> [pair] [timeframe]` | Analiza calidad del dataset |

### V.9 — Backtesting Protocol

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `backtest` | `backtest <model_name> <csv_path> [pair] [timeframe]` | Ejecuta protocolo de backtesting |
| `model_comparison` | `model_comparison <csv_path> [pair] [timeframe]` | Compara múltiples modelos |

### V.6 — Feature Importance

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `feature_importance` | `feature_importance <model_name> <csv_path> [pair]` | Analiza importancia de features |

### V.4 — Regime Detection

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `regime` | `regime <csv_path> [pair] [timeframe]` | Detecta régimen de mercado actual |

### V.3 — Multi-Timeframe Intelligence

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `mtf` | `mtf <d1_csv> <h4_csv> <h1_csv> [pair]` | Analiza coherencia MTF |

### V.8 — Reliability Score

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `reliability` | `reliability <confidence> [signal=BUY] [mtf_score=50] [regime=ranging]` | Calcula reliability score |

### V.7 — Model Selection

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `model_selection` | `model_selection <csv_path> [pair] [timeframe]` | Selecciona mejor modelo |

### V.1 — Decision Engine

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `decision` | `decision <signal> <confidence> [regime] [mtf_score]` | Ejecuta motor de decisión |

### V.2 — Risk Engine

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `risk` | `risk <BUY\|SELL> <entry_price> <atr> [reliability] [regime] [pair]` | Calcula análisis de riesgo |

El sizing monetario V.2 usa `RiskConfigResolver` como frontera canónica. Un
`ForexIntegratedPipeline()` normal consulta por par el JSON indicado por
`ASTRA_RISK_CONFIG_PATH`; el archivo se vuelve a leer en cada resolución para
que el estado de cuenta pueda actualizarse sin codificarlo en el repositorio.
También se puede inyectar un `account_state_provider` o `currency_converter`.

Son obligatorios `account.account_equity`, `account.account_currency` y, bajo
`instruments.<pair>`, `symbol`, `asset_class`, `base_currency`,
`quote_currency`, `pip_size` y `contract_size`. Para un cross también debe
existir una tasa explícita en `conversion_rates` o un conversor. Son opcionales
`available_margin`, `leverage`, `min_lot`, `max_lot`, `lot_step` y los costos
declarados (`commission_per_lot`, `spread_price`, `slippage_price`,
`costs_in_entry_stop`). No se reutiliza `supported_symbols.pip_value` como
metadata contractual.

Si falta información obligatoria, el resultado es inválido y la acción final
queda en `HOLD`; no se supone equity, moneda, contract size, apalancamiento ni
tasa 1:1. `ForexIntegratedPipeline(risk_config=...)` se conserva como override
explícito y tiene prioridad sobre el resolver automático. Los costos se marcan
por componente como `embedded`, `explicitly_declared` o
`unknown/not_included`; `costs_included=True` sólo significa cobertura completa
de los componentes declarables, no una suposición implícita de riesgo all-in.

### V.11 — Dataset Update

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `dataset_update` | `dataset_update <pair> <timeframe> [data_dir]` | Actualización incremental de dataset |

### V.12 — Scheduler

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `scheduler_status` | `scheduler_status` | Estado del scheduler |
| `scheduler_log` | `scheduler_log [limit]` | Historial de ejecuciones |

### V.13 — Adaptive Retrain

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `retrain_check` | `retrain_check <pair> [current_win_rate] [model_name]` | Verifica si necesita reentrenamiento |
| `retrain_history` | `retrain_history [pair] [limit]` | Historial de reentrenamientos |

### V.10 — Market Sentinel

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `sentinel_status` | `sentinel_status` | Estado del sentinel |
| `sentinel_signals` | `sentinel_signals [pair] [limit]` | Historial de signals |

### V.14 — Outcome Tracker

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `outcome_stats` | `outcome_stats [pair]` | Estadísticas de resultados |
| `outcome_history` | `outcome_history [pair] [limit]` | Historial de predicciones evaluadas |

### V.15 — Notifications

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `notify_test` | `notify_test <pair> <signal> <reliability>` | Prueba notificación |
| `notify_log` | `notify_log [limit]` | Historial de notificaciones |

### V.18 — Portfolio Intelligence

| Comando | Uso | Descripción |
|---------|-----|-------------|
| `portfolio_ranking` | `portfolio_ranking [filter_signal] [min_reliability]` | Ranking de oportunidades |
| `portfolio_export` | `portfolio_export [filename]` | Exporta ranking a CSV |

---

## Ejemplos

```bash
# Analizar calidad del dataset
quality data/forex/EURUSD_H1.csv EURUSD H1

# Detectar régimen
regime data/forex/EURUSD_H1.csv EURUSD H1

# Análisis MTF
mtf data/forex/EURUSD_D1.csv data/forex/EURUSD_H4.csv data/forex/EURUSD_H1.csv EURUSD

# Calcular reliability
reliability 0.75 BUY 85 trending_bullish

# Ejecutar decision engine
decision BUY 0.75 trending_bullish 85

# Calcular riesgo
risk BUY 1.0850 0.0065 85 trending_bullish EURUSD

# Actualizar dataset
dataset_update EURUSD H1

# Estado del sentinel
sentinel_status

# Ranking de portfolio
portfolio_ranking BUY 70

# Exportar ranking
portfolio_export mi_ranking.csv
```

---

## Integración con main.py

Para registrar todos los comandos en el CLI principal de ASTRA:

```python
from forex.prediction.roadmap_v_integration import (
    cmd_quality, cmd_backtest, cmd_feature_importance,
    cmd_regime, cmd_mtf, cmd_reliability,
    cmd_decision, cmd_risk,
)
from forex.data.dataset_updater import cmd_dataset_update
from forex.scheduler.task_manager import cmd_scheduler_status
from forex.prediction.retrain_manager import cmd_retrain_check, cmd_retrain_history
from forex.market_sentinel import cmd_sentinel_status, cmd_sentinel_signals
from forex.prediction.outcome_tracker import cmd_outcome_stats, cmd_outcome_history
from notifications.notifier import cmd_notify_test, cmd_notify_log
from forex.portfolio.portfolio_ranker import cmd_portfolio_ranking, cmd_portfolio_export

# Registrar en tool_registry
TOOL_REGISTRY = {
    "quality": cmd_quality,
    "backtest": cmd_backtest,
    "feature_importance": cmd_feature_importance,
    "regime": cmd_regime,
    "mtf": cmd_mtf,
    "reliability": cmd_reliability,
    "decision": cmd_decision,
    "risk": cmd_risk,
    "dataset_update": cmd_dataset_update,
    "scheduler_status": cmd_scheduler_status,
    "retrain_check": cmd_retrain_check,
    "retrain_history": cmd_retrain_history,
    "sentinel_status": cmd_sentinel_status,
    "sentinel_signals": cmd_sentinel_signals,
    "outcome_stats": cmd_outcome_stats,
    "outcome_history": cmd_outcome_history,
    "notify_test": cmd_notify_test,
    "notify_log": cmd_notify_log,
    "portfolio_ranking": cmd_portfolio_ranking,
    "portfolio_export": cmd_portfolio_export,
}
```

---

*ASTRA — Roadmap V · Referencia de Comandos CLI*

---

## Generación masiva de CSVs (nuevo)

> **Sólo desarrollo/pruebas.** Este generador histórico puede crear datos
> sintéticos y no forma parte de la ruta productiva. Producción adquiere datos
> reales mediante `DataRouter`; un fallo de provider termina en error y nunca
> habilita fallback sintético. No promuevas CSVs sintéticos a rolling datasets o
> modelos productivos.

```
generar csvs forex                          # majors × H1,H4,D1 · 500 velas · Yahoo→sintético
generar csvs forex H1,H4 800                # solo H1 y H4, 800 velas
generar csvs forex EURUSD,GBPUSD H1 300     # pares específicos
generar csvs forex sinteticos               # fuerza fuente sintética (sin red)
generate forex csvs                         # alias inglés
```

Guarda en la estructura estándar `CSVs/<TF>/<PAIR>.csv`. Si `yfinance` está
instalado y hay conexión descarga datos reales; en caso contrario genera
OHLCV sintético válido (mismo motor que `generate_test_csv.py`) para poder
entrenar y probar sin depender de la red.
