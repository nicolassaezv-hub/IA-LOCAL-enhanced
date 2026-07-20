# Flujo Oficial de Predicción — ASTRA

## Diagrama completo

```
CSV (datos históricos)
        │
        ▼
┌──────────────────┐
│  Quality Gate    │  V.5 — Valida calidad del dataset
│  (quality_analyzer) │  Checks: NaN, outliers, gaps temporales,
└────────┬─────────┘  distribución de señales, completitud
         │ ✅ OK
         ▼
┌──────────────────┐
│ Feature Eng.     │  85 features: OHLCV + RSI + MACD + EMA +
│ (feature_engineering.py) │  ATR + BB + CCI + MFI + ROC + session +
└────────┬─────────┘  lag features + rolling stats
         │
         ▼
┌──────────────────┐
│  Train / Cache   │  VI.1 — ¿Existe caché válido? → reutilizar
│  (hyperparameter_cache) │  Si no → Optuna (budget adaptativo VI.1.B)
│  (adaptive_trainer)   │  XGBoost + LightGBM + RandomForest ensemble
└────────┬─────────┘
         │
         ▼
┌──────────────────┐
│  Regime Detect.  │  V.4 — Clasifica el régimen de mercado:
│  (regime_detector.py) │  trending_bullish / trending_bearish /
└────────┬─────────┘  ranging / high_volatility / breakout / news
         │
         ▼
┌──────────────────┐
│  MTF Coherence   │  V.3 — Coherencia Multi-Timeframe D1→H4→H1
│  (mtf_coherence.py)  │  Si D1, H4 y H1 no son coherentes → HOLD forzado
└────────┬─────────┘  Score de coherencia: 0–100
         │
         ▼
┌──────────────────┐
│  Candlestick     │  VI.5.D — Patrones japoneses: Doji, Engulfing,
│  (candlestick_patterns) │  Hammer, Morning Star, Evening Star, Harami,
└────────┬─────────┘  Shooting Star → confirmación o divergencia
         │
         ▼
┌──────────────────┐
│  Reliability     │  V.8 — Score compuesto 0–100 (7 factores):
│  (reliability_score.py) │  Confianza ML + Coherencia MTF + Régimen +
└────────┬─────────┘  Win rate histórico + Calidad datos + Spread + ATR
         │
         ▼
┌──────────────────┐
│  Decision Engine │  V.1 — BUY / SELL / HOLD / NO OPERAR
│  (decision_engine.py) │  Umbral mínimo Reliability: 65
└────────┬─────────┘  Si régimen adverso → NO OPERAR
         │
         ▼
┌──────────────────┐
│  Risk Engine     │  V.2 — SL/TP basado en ATR
│  (risk_engine.py)     │  Position sizing: Kelly criterion
└────────┬─────────┘  R/R mínimo: 1.5
         │
         ▼
┌──────────────────┐
│  Opportunity     │  VI.8.A — Score compuesto 0–100:
│  Score           │  (Reliability×0.35) + (WinRate×0.30) +
└────────┬─────────┘  (Régimen×0.20) + (MTF×0.15) ± bonos
         │ Si OpScore ≥ 60 y Reliability ≥ 70
         ▼
  Notificación + API
```

## Cómo ejecutar el flujo completo

### Método 1: Pipeline integrado (recomendado)
```
full forex EURUSD.csv
```
Ejecuta todo el flujo de una vez: Quality Gate → Train → Predict → Decision → Risk.

### Método 2: Paso a paso
```
quality EURUSD.csv EURUSD H1        ← Quality Gate
full forex EURUSD.csv               ← Train + Predict
regime EURUSD.csv EURUSD H1         ← Régimen de mercado
mtf D1/EURUSD.csv H4/EURUSD.csv H1/EURUSD.csv  ← Coherencia MTF
reliability 0.75 BUY                ← Reliability Score
decision BUY 0.75                   ← Decisión final
risk BUY 1.08500 0.0012             ← SL/TP + position sizing
candlestick H1/EURUSD.csv           ← Patrones de vela
```

### Método 3: Scanner multi-par
```
scan forex EURUSD GBPUSD USDJPY     ← Analiza varios pares en secuencia
portfolio_ranking BUY 60            ← Ranking de las mejores oportunidades
```

## Salida típica del Decision Engine

```
══════════════════════════════════════════════════
  🤖 DECISION ENGINE — EURUSD / H1
══════════════════════════════════════════════════
  Señal ML:           BUY  (confianza 74.3%)
  Régimen:            trending_bullish
  Coherencia MTF:     ✅ D1+H4+H1 alineados (score: 82/100)
  Patrón vela:        Bullish Engulfing (+10 pts)
  Reliability Score:  78.5 / 100
  ─────────────────────────────────────────────
  DECISIÓN FINAL:     ✅ BUY
  Stop Loss:          1.08240  (23 pips)
  Take Profit:        1.08970  (47 pips)
  R/R Ratio:          2.04
  Position Size:      0.12 lotes (Kelly criterion)
══════════════════════════════════════════════════
```
