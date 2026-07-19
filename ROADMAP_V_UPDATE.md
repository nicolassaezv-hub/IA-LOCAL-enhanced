# Roadmap V — Actualizacion Implementada

## Fases completadas: V.1 a V.18 (TODAS)

### Build order step 1 (Cluster A — Fundamentos): V.5, V.9
### Build order step 2 (Cluster B — Inteligencia): V.4, V.3, V.6, V.7
### Build order step 3 (Cluster C — Decision): V.8, V.1, V.2
### Build order step 4 (Cluster D — Autonomia): V.11, V.12, V.13, V.10, V.14
### Build order step 5 (Cluster E — Comunicacion): V.15, V.16, V.18
### Build order step 6 (Cluster F — Documentacion): V.17

---

## Resumen

| Fase | Nombre | Complejidad | Estado |
|------|--------|-------------|--------|
| V.5  | Dataset Quality Analyzer | Alta | Implementado |
| V.9  | Backtesting Protocol | Media | Implementado |
| V.4  | Regime Detection | Alta | Implementado |
| V.6  | Feature Importance Analyzer | Media | Implementado |
| V.3  | Multi-Timeframe Intelligence | Alta | Implementado |
| V.8  | Prediction Reliability Score | Alta | Implementado |
| V.7  | Model Selection Engine | Alta | Implementado |
| V.1  | Forex Decision Engine | Critica | Implementado |
| V.2  | Risk Engine | Alta | Implementado |
| V.11 | Dataset Update | Alta | Implementado |
| V.12 | Scheduler Inteligente | Alta | Implementado |
| V.13 | Reentrenamiento Adaptativo | Alta | Implementado |
| V.10 | Market Sentinel ⭐⭐⭐⭐⭐ | Critica | Implementado |
| V.14 | Outcome Tracker | Media | Implementado |
| V.15 | Notificaciones | Media | Implementado |
| V.16 | Dashboard Activo | Alta | Implementado |
| V.18 | Portfolio Intelligence | Media | Implementado |
| V.17 | Guia Operativa | Baja | Implementado |

---

## V.5 — Dataset Quality Analyzer

**Archivos:** `forex/prediction/quality_analyzer.py`, `forex/prediction/quality_report.py`

Gate de calidad obligatorio antes de entrenar. Evalua: valores faltantes, outliers (IQR*3), duplicados, balance de clases, cobertura temporal, calidad de indicadores. Score 0-100, bloquea entrenamiento si hay criticos.

```python
from forex.prediction.roadmap_v_integration import run_quality_gate
approved, report = run_quality_gate(df, pair="EURUSD", timeframe="H1")
```

## V.9 — Backtesting Protocol

**Archivo:** `forex/prediction/backtest_protocol.py`

Protocolo estandar con 20+ metricas: Accuracy, Precision, Recall, F1, Win Rate, Profit Factor, Drawdown, Sharpe, Calmar, Expected Return, consecutive wins/losses. Incluye Walk-Forward Validation, Monte Carlo simulation, reporte HTML exportable, comparacion de modelos.

```python
from forex.prediction.roadmap_v_integration import run_backtest_protocol
report = run_backtest_protocol(model, X_test, y_test, returns=ret_test, model_name="RF")
```

## V.4 — Regime Detection

**Archivo:** `forex/prediction/regime_detector.py`

Detecta regimen de mercado: trending_bullish, trending_bearish, ranging, high_volatility, low_volatility, news_impact, breakout, transitional. Usa ADX, ATR percentil, EMA alignment, bias direccional, noticias. Almacena historico en SQLite.

```python
from forex.prediction.roadmap_v_integration import run_regime_detection
regime = run_regime_detection(df, pair="EURUSD", timeframe="H1")
# regime.primary → "trending_bullish"
# regime.confidence → 85.0
```

## V.6 — Feature Importance Analyzer

**Archivo:** `forex/prediction/feature_importance.py`

Analiza importancia nativa, correlacion Spearman, SHAP values, permutation importance. Score compuesto: 50% native + 25% permutation + 15% SHAP - 10% correlation penalty. Clasifica en keep/discard/review. Respeta regla MTF. Recomienda nuevos indicadores.

```python
from forex.prediction.roadmap_v_integration import run_feature_importance
fi_report = run_feature_importance(model, X_train, y_train, X_test, y_test, feature_names=cols)
# fi_report.optimal_features → ["rsi_14", "atr_14", ...]
# fi_report.discarded_features → ["useless_feature", ...]
```

## V.3 — Multi-Timeframe Intelligence

**Archivo:** `forex/prediction/mtf_coherence.py`

Sistema de validacion de coherencia D1 → H4 → H1. Score 0-100 con pesos 40%/35%/25%. Solo emite señal cuando los tres TFs apuntan en la misma direccion. HOLD forzado automatico si coherencia < 65. Componente del Reliability Score (V.8).

```python
from forex.prediction.roadmap_v_integration import run_mtf_coherence
mtf = run_mtf_coherence(d1_df=d1, h4_df=h4, h1_df=h1, pair="EURUSD")
# mtf.coherent → True/False
# mtf.coherence_score → 85.0
# mtf.forced_hold → False
```

## V.8 — Prediction Reliability Score

**Archivo:** `forex/prediction/reliability_score.py`

Indice de confiabilidad compuesto 0-100 con 7 componentes ponderados:
- Model confidence (30%)
- Ensemble agreement (20%)
- MTF coherence (15%)
- Regime favorable (15%)
- News absent (10%)
- Volatility normal (5%)
- Model history (5%)

Escala: 85+ notificar, 70-84 dashboard, 50-69 debil, <50 HOLD automatico.

```python
from forex.prediction.roadmap_v_integration import run_reliability_score
report = run_reliability_score(
    model_confidence=0.85,
    ensemble_predictions=["BUY","BUY","BUY"],
    mtf_coherence_score=88.0,
    regime_primary="trending_bullish",
    regime_confidence=85.0,
    model_win_rate=0.62,
    model_recent_predictions=50,
    signal="BUY",
)
# report.reliability_score → 89.3
# report.should_notify → True
# report.quality_tier → "high_quality"
```

## V.7 — Model Selection Engine

**Archivo:** `forex/prediction/model_selector.py`

Motor de seleccion automatica de algoritmos. Compara candidatos (RF, GBM, SVM, Logistic, ExtraTrees, AdaBoost) con Walk-Forward Validation, ranking por score compuesto (accuracy + stability + sharpe). `ModelRegistry` almacena resultados en SQLite para trazabilidad.

```python
from forex.prediction.roadmap_v_integration import run_model_selection
result = run_model_selection(
    X_train, y_train, X_test, y_test, returns=ret_test,
    feature_names=cols, pair="EURUSD", timeframe="H1",
)
# result.winner.name → "SVM"
# result.winner.wfv_accuracy → 0.7047
# result.registry_id → 12
```

## V.1 — Forex Decision Engine

**Archivos:** `forex/prediction/decision_engine.py`, `forex/prediction/decision_explainer.py`

Motor de decision final con prioridades jerarquicas:
1. Circuit breaker (errores recientes) → NO_OPERAR
2. Volatilidad extrema → NO_OPERAR
3. Impacto de noticias → WAIT
4. MTF incoherente → HOLD
5. Fiabilidad baja (<50) → HOLD
6. Senal fuerte + fiabilidad → BUY/SELL
7. Default → HOLD

Genera explicacion en lenguaje natural (Espanol) con factores a favor y en contra.

```python
from forex.prediction.roadmap_v_integration import run_decision_engine
decision = run_decision_engine(
    signal="BUY",
    reliability_score=85.0,
    mtf_coherent=True,
    mtf_coherence_score=88.0,
    regime_primary="trending_bullish",
    regime_confidence=82.0,
    news_impact="low",
    volatility_percentile=45.0,
    circuit_breaker_triggered=False,
)
# decision.decision → "BUY"
# decision.explanation → "Senal BUY con fiabilidad 85.0/100..."
```

## V.2 — Risk Engine

**Archivo:** `forex/prediction/risk_engine.py`

Motor de gestion de riesgo basado en ATR:
- SL/TP con multiplicadores ATR (regimen-especifico)
- Kelly Criterion fraccional (×0.25) para position sizing
- Riesgo clamped entre 0.5% y 2.0% del capital
- Ajuste por regimen (high_volatility reduce posicion)
- Metricas: risk-reward ratio, valor en pips

```python
from forex.prediction.roadmap_v_integration import run_risk_engine
risk = run_risk_engine(
    signal="BUY", entry_price=1.08500, atr=0.0065,
    account_balance=10000, regime="trending_bullish",
    pair="EURUSD",
)
# risk.stop_loss → 1.07825
# risk.take_profit → 1.09175
# risk.risk_pct → 2.0
# risk.position_size → 3076.92
```

---

## Modulo de Integracion

**Archivo:** `forex/prediction/roadmap_v_integration.py`

Conecta las 9 fases con el pipeline existente:

- `run_quality_gate()` — V.5 gate antes de entrenar
- `run_regime_detection()` — V.4 contexto de mercado
- `run_mtf_coherence()` — V.3 coherencia multi-timeframe
- `run_feature_importance()` — V.6 analisis post-entrenamiento
- `run_backtest_protocol()` — V.9 evaluacion estandar
- `run_reliability_score()` — V.8 indice de confiabilidad
- `run_model_selection()` — V.7 seleccion de modelo
- `run_decision_engine()` — V.1 decision final
- `run_risk_engine()` — V.2 gestion de riesgo
- `run_full_roadmap_v_evaluation()` — ciclo completo V.1-V.9
- `run_dataset_update()` — V.11 actualizacion incremental
- `run_scheduler_status()` — V.12 estado del scheduler
- `run_retrain_check()` — V.13 check de reentrenamiento
- `run_sentinel_status()` — V.10 estado del sentinel
- `run_outcome_stats()` — V.14 estadisticas de resultados
- `run_notification()` — V.15 envio de notificaciones
- `run_portfolio_ranking()` — V.18 ranking de oportunidades
- `run_model_comparison()` — comparacion multiple (V.9)
- `run_walk_forward()` — WFV (V.9)
- `apply_feature_filter()` — filtrado dinamico (V.6)
- Comandos CLI: `cmd_quality()`, `cmd_backtest()`, `cmd_feature_importance()`, `cmd_regime()`, `cmd_mtf()`, `cmd_reliability()`, `cmd_decision()`, `cmd_risk()`, `cmd_dataset_update()`, `cmd_scheduler_status()`, `cmd_retrain_check()`, `cmd_retrain_history()`, `cmd_sentinel_status()`, `cmd_sentinel_signals()`, `cmd_outcome_stats()`, `cmd_outcome_history()`, `cmd_notify_test()`, `cmd_notify_log()`, `cmd_portfolio_ranking()`, `cmd_portfolio_export()`

### Como aplicar al IntegratedPipeline

```python
# En IntegratedPipeline.train():
from forex.prediction.roadmap_v_integration import run_quality_gate
approved, quality_report = run_quality_gate(df, pair=pair, timeframe=timeframe)
if not approved:
    return {"ok": False, "error": "Quality gate rechazado"}

# En IntegratedPipeline.predict():
from forex.prediction.roadmap_v_integration import (
    run_regime_detection, run_mtf_coherence, run_reliability_score
)
regime = run_regime_detection(df, pair=pair, timeframe=timeframe)
mtf = run_mtf_coherence(d1_df=d1, h4_df=h4, h1_df=h1, pair=pair)
reliability = run_reliability_score(
    model_confidence=confidence,
    ensemble_predictions=predictions,
    mtf_coherence_score=mtf.coherence_score,
    regime_primary=regime.primary,
    signal=signal,
)
```

---

## V.11 — Dataset Update

**Archivo:** `forex/data/dataset_updater.py`

Actualizacion incremental de datasets. Descarga solo velas nuevas via yfinance, recalcula indicadores (RSI, EMA, MACD, ATR, ADX), filtra gaps de fin de semana, log en SQLite.

```python
from forex.prediction.roadmap_v_integration import run_dataset_update
result = run_dataset_update("EURUSD", "H1")
# result.new_rows → 5
```

## V.12 — Scheduler Inteligente

**Archivo:** `forex/scheduler/task_manager.py`

Planificador de tareas periodicas con retry y backoff. Registro de tareas, ejecucion en thread daemon, estado persistente en SQLite, log de ejecuciones.

```python
from forex.prediction.roadmap_v_integration import run_scheduler_status
status = run_scheduler_status()
```

## V.13 — Reentrenamiento Adaptativo

**Archivo:** `forex/prediction/retrain_manager.py`

Monitor de degradacion del modelo. 5 triggers: win rate drop >10%, accuracy drop >5%, cambio de regimen, nuevas filas >= 500, programado semanal. Baseline almacenado en SQLite.

```python
from forex.prediction.roadmap_v_integration import run_retrain_check
decision = run_retrain_check("EURUSD", current_win_rate=0.50, model_name="RF")
# decision.needed → True, decision.trigger → "win_rate_drop"
```

## V.10 — Market Sentinel ⭐⭐⭐⭐⭐

**Archivo:** `forex/market_sentinel.py`

Daemon de vigilancia continua 24/7. Escanea activos configurados, ejecuta pipeline, evalua reliability, activa circuit breaker automatico, almacena signals en SQLite.

```python
from forex.prediction.roadmap_v_integration import run_sentinel_status
status = run_sentinel_status()
# status.state → "idle"/"running", status.circuit_breaker_active → False
```

## V.14 — Outcome Tracker

**Archivo:** `forex/prediction/outcome_tracker.py`

Evalua automaticamente cada prediccion contra el resultado real del mercado. Calcula win rate, direction_correct, price_change. Alimenta a V.13 (retrain) y V.8 (reliability calibration).

```python
from forex.prediction.roadmap_v_integration import run_outcome_stats
stats = run_outcome_stats("EURUSD")
# stats.win_rate → 0.65, stats.evaluated → 42
```

## V.15 — Sistema de Notificaciones

**Archivo:** `notifications/notifier.py`

Dispatcher multi-canal: console, desktop (notify-send/MessageBox), Telegram (Bot API), Discord (webhook), email (SMTP). Cooldown configurable, threshold de reliability, formato texto y HTML.

```python
from forex.prediction.roadmap_v_integration import run_notification
results = run_notification("EURUSD", "BUY", 88.5, explanation="...", regime="trending_bullish")
```

## V.16 — Dashboard Activo

**Archivo:** `workspace/static/js/active_dashboard.js`

Panel web en tiempo real. Polling cada 10s a endpoints del Sentinel, Scheduler, Signals, Datasets. Controles: anadir/quitar pares, pausar scheduler, forzar update/retrain.

## V.18 — Portfolio Intelligence

**Archivo:** `forex/portfolio/portfolio_ranker.py`

Ranking de oportunidades multi-activo. Composite score ponderado: reliability 40%, win rate 20%, WFV accuracy 15%, MTF 10%, regimen 10%, risk-adjusted 5%. Exportable a CSV.

```python
from forex.prediction.roadmap_v_integration import run_portfolio_ranking
ranking = run_portfolio_ranking(opportunities=[...], filter_signal="BUY")
# ranking.ranking[0].pair → "AUDUSD", ranking.ranking[0].composite_score → 85.8
```

## V.17 — Guia Operativa

**Archivos:** `FOREX_USER_GUIDE.md`, `FOREX_COMMANDS.md`

Documentacion completa: instalacion, configuracion, generacion de CSV, entrenamiento, interpretacion del Decision Engine, Reliability Score, Circuit Breaker, MTF, Sentinel, Scheduler, notificaciones, dashboard, portfolio, reentrenamiento, outcome tracker. Referencia de todos los comandos CLI.

---

## Tests ejecutados

```
=== V.1-V.9 PASSED === (roadmap_v_integration.py)
=== V.10 PASSED === (market_sentinel.py)
=== V.11 PASSED === (dataset_updater.py)
=== V.12 PASSED === (task_manager.py)
=== V.13 PASSED === (retrain_manager.py)
=== V.14 PASSED === (outcome_tracker.py)
=== V.15 PASSED === (notifier.py)
=== V.18 PASSED === (portfolio_ranker.py)
=== FULL 18-PHASE INTEGRATION PASSED ===
```

---

## Roadmap V — COMPLETO

Las 18 fases han sido implementadas y verificadas. ASTRA ahora opera como plataforma de inteligencia predictiva activa y autonoma.
