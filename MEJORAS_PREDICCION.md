# Mejoras al Sistema de Predicción — ASTRA Forex

## Resumen

Se mejoraron 5 archivos clave del módulo `forex/prediction/` con el objetivo de
**maximizar la calidad de las señales de trading** (BUY / SELL) y reducir las falsas alarmas.

---

## 1. Target más inteligente — `dataset_builder.py`

### Antes (problema raíz)
```
target = close[t+1] > close[t]   # ¿el siguiente precio es más alto?
```
Esto es básicamente ruido. El modelo aprendía a predecir si la siguiente vela sube o baja,
lo cual no tiene relación directa con si la operación es **rentable**.

### Ahora — Target Riesgo/Recompensa
```
¿Dentro de los próximos N velas (horizon=10), el precio alcanza TP (+1.5 * ATR)
ANTES de alcanzar SL (-1.0 * ATR)?
```
- **1 = BUY** → el TP fue alcanzado primero (operación habría ganado)
- **0 = SELL** → el SL fue alcanzado primero (operación habría perdido)
- Usa ATR como base porque refleja la volatilidad real del par

**Por qué importa:** Con rr_ratio=1.5, incluso con 50% de precisión la estrategia es
rentable. El modelo ahora aprende a detectar setups con alta probabilidad de ganar.

**Parámetros configurables:**
- `horizon=10` — cuántas velas mirar hacia adelante
- `rr_ratio=1.5` — múltiplo de recompensa vs riesgo

---

## 2. Nuevas Features — `feature_engineering.py`

Se agregaron **15+ features nuevas** organizadas en 6 grupos:

| Grupo | Features | Por qué ayuda |
|-------|----------|---------------|
| **ADX** | ADX_14, +DI, -DI | Mide fuerza del trend; señales en mercados con tendencia son más confiables |
| **Stochastic** | stoch_k, stoch_d, stoch_cross | Detecta sobrecompra/sobreventa y cruces de señal |
| **Williams %R** | williams_r | Complementa RSI para confirmar reversals |
| **OBV** | obv, obv_ema, obv_diverge | El volumen confirma o niega el movimiento de precio |
| **Bollinger** | bb_width, bb_squeeze, bb_pct_b | El squeeze detecta momentos antes de movimientos explosivos |
| **Patrones de velas** | doji, hammer, shooting_star, bull_engulf, bear_engulf | Señales visuales clásicas convertidas en features numéricas |
| **EMA signals** | ema20>50, ema50>200, crossover | Sesgo direccional del trend |
| **RSI extendido** | sobrecompra, sobreventa, slope | Zonas extremas + dirección del RSI |
| **Estructura de velas** | upper_shadow, lower_shadow | Presión compradora/vendedora en la vela |

---

## 3. Modelo Ensemble — `xgb_trainer.py`

### Antes
- Solo XGBoost
- Optimizaba **accuracy** (porcentaje de aciertos totales)

### Ahora
- **XGBoost + LightGBM + RandomForest** con soft voting
- Optimiza **precision** (de las veces que dice BUY, ¿cuántas son correctas?)
- Calibración isotónica de probabilidades → confianza más realista

**Por qué ensemble:** Cada modelo tiene fortalezas distintas. Cuando los tres coinciden,
la señal es genuinamente más confiable. El promedio de probabilidades es más estable que
un único modelo.

**Por qué precision > accuracy:** Si el modelo dice BUY 100 veces y acierta 70, eso es
70% de precision. Aunque el accuracy global sea menor, **las operaciones que tomas son
rentables**. Preferimos menos señales pero mejores.

---

## 4. Filtro de Señal — `predictor.py`

El predictor ahora retorna **BUY / SELL / HOLD** en lugar de solo dirección.

### Filtros aplicados antes de disparar señal:

| Filtro | Valor por defecto | Motivo |
|--------|-------------------|--------|
| Confianza mínima | 62% | Bajo este umbral, el modelo no está seguro → HOLD |
| ADX mínimo | 22 | Mercado ranging/choppy → señales poco confiables → HOLD |

### Output enriquecido:
```python
{
  "action":          "BUY",          # BUY / SELL / HOLD
  "direction":       "bullish",
  "confidence":      0.74,
  "signal_strength": 71.5,           # 0-100, combina confianza + ADX
  "regime":          "moderate trend",
  "adx":             28.3,
  "hold_reason":     None,           # explicación si es HOLD
  "interpretation":  "High-quality BUY signal..."
}
```

---

## 5. Multi-Horizonte — `integrated_pipeline.py`

Nuevo modo `multi_horizon`: entrena 3 modelos (horizon=5, 10, 20) y solo emite
señal si **al menos 2 de 3 horizons coinciden**.

```python
pipeline = ForexIntegratedPipeline()
result = pipeline.predict_multi_horizon("EURUSD_H1.csv", pair="EURUSD")
```

Esto reduce drásticamente las señales falsas. Un BUY que aparece en los 3 horizontes
es mucho más confiable que uno que solo aparece en el horizonte de 1 vela.

---

## Cómo usar

```python
from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

pipeline = ForexIntegratedPipeline(
    horizon=10,        # velas hacia adelante para construir target
    rr_ratio=1.5,      # relación recompensa/riesgo
    min_confidence=0.62,  # confianza mínima para señal
    min_adx=22.0          # ADX mínimo para mercado trending
)

# Entrenar
pipeline.train("EURUSD_H1.csv")

# Predecir (una sola señal)
result = pipeline.predict("EURUSD_H1.csv", pair="EURUSD")
print(result["action"])         # BUY / SELL / HOLD
print(result["signal_strength"]) # 0-100

# Predecir con múltiples horizontes (más conservador, más confiable)
result = pipeline.predict_multi_horizon("EURUSD_H1.csv", pair="EURUSD")

# Entrenamiento + predicción + backtest en uno
result = pipeline.run("EURUSD_H1.csv", mode="full")
```

---

## Instalar LightGBM (nuevo requerimiento)

```bash
pip install lightgbm
```

Si LightGBM no está instalado, el ensemble funciona igual con XGBoost + RandomForest.

---

---

## 6. Optuna Hyperparameter Tuner — `hyperparameter_tuner.py` (NUEVO)

### ¿Qué hace?
Optuna busca automáticamente la mejor combinación de hiperparámetros para XGBoost
y LightGBM, específicamente para **tu par** y **tus datos**.

Por ejemplo, para EURUSD puede que `max_depth=4` funcione mejor, pero para XAUUSD
puede que `max_depth=8` sea óptimo. El tuner descubre esto automáticamente.

### ¿Por qué Optuna en lugar de GridSearch?
- **TPE Sampler** (Tree-structured Parzen Estimator): aprende qué zonas del espacio
  de búsqueda son prometedoras y concentra los trials ahí. Es 10-100x más eficiente
  que búsqueda exhaustiva.
- **MedianPruner**: corta trials malos temprano → ahorra tiempo de cómputo.
- **Optimiza precision**, no accuracy (lo que importa para tus operaciones).

### ¿Cuántos trials recomienda?
El tuner calcula automáticamente la cantidad de trials según el tamaño de tu dataset:

| Filas | Trials recomendados |
|-------|---------------------|
| < 500 | 30 |
| 500–2000 | 50 |
| 2000–10000 | 75 |
| > 10000 | 100 |

### Persistencia: los params se guardan por par
Los mejores params se guardan en `models/forex/params/best_params_EURUSD.json`.
La próxima vez que entrenes EURUSD, los carga automáticamente — no necesitas
tunear de nuevo salvo que cambies tus datos.

### Cómo usar

```python
from forex.prediction.integrated_pipeline import ForexIntegratedPipeline

pipeline = ForexIntegratedPipeline()

# OPCIÓN 1: Tunear + entrenar en un solo comando (recomendado la primera vez)
result = pipeline.tune("EURUSD_H1.csv", pair="EURUSD")
print(result["precision"])          # precision del modelo final
print(result["signal"]["action"])   # BUY / SELL / HOLD

# OPCIÓN 2: Solo tunear (sin entrenar)
from forex.prediction.hyperparameter_tuner import ForexHyperparameterTuner
tuner = ForexHyperparameterTuner(pair="EURUSD")
best = tuner.tune(X_train, y_train, X_val, y_val, n_trials=50)
# best = {"xgb": {max_depth: 5, learning_rate: 0.038, ...}, "lgb": {...}}

# OPCIÓN 3: Entrenar usando params guardados (automático)
result = pipeline.train("EURUSD_H1.csv", pair="EURUSD")
# Si existen params guardados para EURUSD → los usa automáticamente
```

### Flujo recomendado (primera vez por par)

```
1. tune("EURUSD_H1.csv", pair="EURUSD")   ← busca mejores params, entrena
2. predict("EURUSD_H1.csv", pair="EURUSD") ← señal usando modelo optimizado
```

### Flujo recomendado (uso regular, después de tunear)

```
1. train("EURUSD_H1.csv", pair="EURUSD")  ← re-entrena con datos nuevos (usa params guardados)
2. predict("EURUSD_H1.csv")               ← señal
```

---

## Archivos modificados

| Archivo | Cambio |
|---------|--------|
| `forex/prediction/feature_engineering.py` | +15 features: ADX, Stochastic, Williams %R, OBV, BB squeeze, patrones de velas, EMA signals, RSI extendido |
| `forex/prediction/dataset_builder.py` | Target R/R aware: TP/SL con ATR en horizonte configurable |
| `forex/prediction/xgb_trainer.py` | Ensemble XGB+LGB+RF, calibración isotónica, optimiza precision, carga params de Optuna |
| `forex/prediction/predictor.py` | Filtro de confianza + filtro ADX, output BUY/SELL/HOLD |
| `forex/prediction/integrated_pipeline.py` | Modo `tune`, modo `multi_horizon`, parámetros configurables |
| `forex/prediction/forex_prediction_bridge.py` | Actualizado para usar signal() y filtros |
| `forex/prediction/hyperparameter_tuner.py` | **NUEVO** — Optuna TPE search para XGB + LGB, guarda params por par |
| `forex/prediction/__init__.py` | Exports actualizados |

## Instalar nuevas dependencias

```bash
pip install lightgbm optuna
```

Si alguna no está disponible, el sistema hace fallback graceful (no rompe nada).
