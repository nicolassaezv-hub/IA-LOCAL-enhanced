# ASTRA — Guía Operativa de Forex Lab

> **Roadmap V — Fase V.17**
> Documentación completa y autónoma de Forex Lab, desde la instalación hasta la interpretación de señales.

---

## 1. Instalación y Configuración Inicial

### Requisitos previos
- Python 3.10+
- pip (gestor de paquetes)
- Conexión a internet (para yfinance y noticias)

### Dependencias
```bash
pip install numpy pandas scikit-learn xgboost lightgbm yfinance colorama shap
```

### Estructura de directorios
```
astra/
├── forex/
│   ├── prediction/
│   │   ├── quality_analyzer.py        # V.5
│   │   ├── quality_report.py          # V.5
│   │   ├── backtest_protocol.py        # V.9
│   │   ├── feature_importance.py       # V.6
│   │   ├── regime_detector.py          # V.4
│   │   ├── mtf_coherence.py            # V.3
│   │   ├── reliability_score.py        # V.8
│   │   ├── model_selector.py           # V.7
│   │   ├── decision_engine.py          # V.1
│   │   ├── decision_explainer.py       # V.1
│   │   ├── risk_engine.py              # V.2
│   │   ├── retrain_manager.py          # V.13
│   │   ├── outcome_tracker.py         # V.14
│   │   └── roadmap_v_integration.py    # Integración
│   ├── data/
│   │   └── dataset_updater.py          # V.11
│   ├── scheduler/
│   │   └── task_manager.py             # V.12
│   ├── portfolio/
│   │   └── portfolio_ranker.py         # V.18
│   └── market_sentinel.py              # V.10
├── notifications/
│   └── notifier.py                     # V.15
├── workspace/
│   └── static/js/active_dashboard.js   # V.16
├── data/forex/                         # CSVs de datos
└── memoria.db                         # SQLite compartido
```

---

## 2. Generación de CSV

### Manual (creando.py)
El método tradicional usa `creando.py` para descargar datos completos vía yfinance:
```bash
python creando.py EURUSD H1
```

### Automático (V.11 Dataset Updater)
El sistema V.11 descarga solo las velas nuevas incrementalmente:
```python
from forex.data.dataset_updater import DatasetUpdater
updater = DatasetUpdater(data_dir="data/forex")
result = updater.update_pair("EURUSD", "H1")
print(f"Nuevas velas: {result.new_rows}")
```

O desde CLI:
```bash
python -c "from forex.data.dataset_updater import cmd_dataset_update; print(cmd_dataset_update('EURUSD H1'))"
```

---

## 3. Entrenamiento de Modelos

### Pipeline completo con Quality Gate
Antes de entrenar, el Quality Gate (V.5) valida el dataset:
```python
from forex.prediction.roadmap_v_integration import run_full_roadmap_v_evaluation

result = run_full_roadmap_v_evaluation(
    df=df,
    model=model,
    X_train=X_train, y_train=y_train,
    X_test=X_test, y_test=y_test,
    returns=returns,
    feature_names=feature_names,
    pair="EURUSD",
    timeframe="H1",
    model_name="RandomForest",
)
```

### Model Selection (V.7)
Para comparar múltiples algoritmos automáticamente:
```python
from forex.prediction.roadmap_v_integration import run_model_selection
result = run_model_selection(X_train, y_train, X_test, y_test, pair="EURUSD", timeframe="H1")
print(f"Ganador: {result.winner.name} (WFV accuracy: {result.winner.wfv_accuracy:.4f})")
```

---

## 4. Interpretación del Decision Engine (V.1)

El Decision Engine produce una de cuatro decisiones posibles:

| Decisión | Significado | Cuándo ocurre |
|----------|-------------|---------------|
| **BUY** | Comprar | Señal alcista + reliability alta + MTF coherente + circuit breaker OK |
| **SELL** | Vender | Señal bajista + reliability alta + MTF coherente + circuit breaker OK |
| **HOLD** | Mantener | Señal débil, MTF incoherente, o reliability < 50 |
| **NO_OPERAR** | No operar | Circuit breaker activo, volatilidad extrema, o noticias de alto impacto |

### Explicación
Cada decisión incluye una explicación en lenguaje natural (Español) con factores a favor y en contra.

```python
from forex.prediction.decision_explainer import explain_decision
explanation = explain_decision(decision_result)
print(explanation)
# "Señal BUY con fiabilidad 85.0/100. El régimen trending_bullish es favorable..."
```

---

## 5. Lectura del Reliability Score (V.8)

El Reliability Score es un índice compuesto de 0 a 100:

| Rango | Significado | Acción |
|-------|-------------|--------|
| **85–100** | Señal de alta calidad | Notificar al usuario |
| **70–84** | Señal válida | Mostrar en dashboard |
| **50–69** | Señal débil | Registrar, no notificar |
| **< 50** | HOLD automático | No operar |

### Componentes del Score
1. Confidence del modelo (30%)
2. Acuerdo entre modelos del ensemble (20%)
3. Coherencia Multi-Timeframe V.3 (15%)
4. Régimen favorable V.4 (15%)
5. Ausencia de noticias de alto impacto (10%)
6. Volatilidad dentro de rango (5%)
7. Historial reciente del modelo (5%)

---

## 6. Circuit Breaker

El Circuit Breaker se activa automáticamente cuando hay demasiados errores en poco tiempo.

- **Activación**: 5+ errores en 30 minutos
- **Efecto**: Fuerza `NO_OPERAR` en todas las señales
- **Reset**: Manual o automático tras 30 minutos sin errores

```python
from forex.market_sentinel import MarketSentinel
sentinel = MarketSentinel()
sentinel.reset_circuit_breaker()
```

---

## 7. Multi-Timeframe Intelligence (V.3)

ASTRA valida que D1 → H4 → H1 sean coherentes antes de emitir una señal:

- **D1** → Tendencia principal (peso 40%)
- **H4** → Confirmación (peso 35%)
- **H1** → Punto de entrada (peso 25%)

**Coherence Score ≥ 65** = señal válida
**Coherence Score < 65** = HOLD forzado

---

## 8. Market Sentinel (V.10) y Scheduler (V.12)

### Configuración del Sentinel
```python
from forex.market_sentinel import MarketSentinel

sentinel = MarketSentinel(config={
    "scan_interval_sec": 60,
    "reliability_notify_threshold": 85.0,
})
sentinel.add_pair("EURUSD")
sentinel.add_pair("GBPUSD")
sentinel.start()  # Inicia vigilancia 24/7
```

### Configuración del Scheduler
```python
from forex.scheduler.task_manager import TaskManager

mgr = TaskManager()
mgr.register("dataset_update", func=update_func, interval_sec=3600)
mgr.register("sentinel_scan", func=scan_func, interval_sec=60)
mgr.start()
```

### Estado desde CLI
```bash
sentinel_status
scheduler_status
```

---

## 9. Configuración de Notificaciones (V.15)

### Canales disponibles
- **Console**: Salida por terminal (siempre activo)
- **Desktop**: Notificaciones del sistema operativo
- **Telegram**: Bot de Telegram
- **Discord**: Webhook de Discord
- **Email**: Correo electrónico vía SMTP

### Configuración
```python
from notifications.notifier import Notifier

notifier = Notifier(config={
    "enabled_channels": ["console", "telegram", "desktop"],
    "reliability_threshold": 85.0,
    "telegram_token": "YOUR_BOT_TOKEN",
    "telegram_chat_id": "YOUR_CHAT_ID",
    "cooldown_minutes": 30,
})
```

### Prueba
```bash
notify_test EURUSD BUY 88.5
```

---

## 10. Interpretación del Dashboard Activo (V.16)

El Dashboard Activo muestra en tiempo real:

- **Market Sentinel**: Estado del daemon, activos vigilados, circuit breaker
- **Scheduler**: Tareas programadas, próxima ejecución, estado
- **Signals Activas**: Señales con reliability ≥ 70, ordenadas por score
- **Datasets**: Última actualización de cada par/timeframe

### Controles disponibles
- Añadir/quitar activos del Sentinel
- Pausar/reanudar el Scheduler
- Forzar actualización de dataset
- Forzar reentrenamiento de un par
- Configurar umbrales de notificación

---

## 11. Portfolio Intelligence (V.18)

ASTRA genera un ranking de las mejores oportunidades entre todos los activos vigilados:

```bash
portfolio_ranking
portfolio_export ranking.csv
```

El ranking ordena las oportunidades por un composite score que pondera:
- Reliability Score (40%)
- Win Rate del modelo (20%)
- WFV Accuracy (15%)
- Coherencia MTF (10%)
- Régimen favorable (10%)
- Risk-adjusted (5%)

---

## 12. Reentrenamiento Adaptativo (V.13)

El sistema monitoriza señales de degradación y reentrena solo cuando es necesario:

| Trigger | Condición |
|---------|-----------|
| Win rate drop | Cae >10% vs. baseline |
| Accuracy drop | Cae >5% vs. baseline |
| Regime change | Cambio de régimen de mercado |
| New data | 500+ filas nuevas acumuladas |
| Scheduled | Semanal (configurable) |
| Manual | Solicitud del usuario |

```bash
retrain_check EURUSD 0.50 RF
retrain_history EURUSD
```

---

## 13. Aprendizaje Basado en Resultados (V.14)

Cada predicción se evalúa automáticamente contra el resultado real del mercado:

```bash
outcome_stats EURUSD
outcome_history EURUSD
```

El sistema calcula win rate real, accuracy, y alimenta al Reentrenamiento Adaptativo (V.13).

---

## Flujo Recomendado

1. **Configurar** datos (V.11) y activos del Sentinel (V.10)
2. **Entrenar** modelo con Quality Gate (V.5) y Model Selection (V.7)
3. **Iniciar** Sentinel + Scheduler para vigilancia 24/7
4. **Configurar** notificaciones (V.15) con tu canal preferido
5. **Monitorear** vía Dashboard Activo (V.16)
6. **Revisar** Portfolio Ranking (V.18) para mejores oportunidades
7. **Dejar** que V.13 y V.14 optimicen el modelo automáticamente

---

*ASTRA — Roadmap V · Intelligent Forecasting & Active Automation*
