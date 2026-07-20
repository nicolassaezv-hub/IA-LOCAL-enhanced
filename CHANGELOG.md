# ASTRA — Development Log (Releases)

Historial permanente de cambios del sistema. Cada entrada sigue el formato semántico `vX.Y.Z`.

---

## v6.1.0 — Integración & Validación Completa
**Fecha:** 2026-07-20
**Tipo:** Improvement + Feature
**Estado:** ✅ Done

### Nuevos módulos

**astra_doctor.py — Diagnóstico unificado (10 categorías)**
- Verifica: dependencias críticas/opcionales, configuración (keys, índice CSV), modelos ML, APIs externas (Groq, Binance, Yahoo), MT5, bases de datos (memoria.db, hparam_cache, model_quality), scheduler, integridad de datasets, integración de módulos, API interna.
- Resultado: 42 OK, 10 Avisos (opcionales), 0 Fallos.
- Genera reporte JSON: `astra_doctor_report.json`.
- Comando CLI: `astra doctor`.

**astra_api.py — API REST interna (puerto 8766)**
- Servidor HTTP Python puro (sin dependencias adicionales).
- Endpoints: `/api/astra/health`, `/status`, `/predictions`, `/ranking`, `/outcomes`, `/history`, `/datasets`, `/scheduler`, `/doctor`.
- POST: `/api/astra/signal`, `/api/astra/state`.
- Comandos CLI: `api start`, `api stop`, `api status`.
- Desacoplamiento total backend Python ↔ frontend Node.js/Workplace.

**dev_log.py — Development Log (reemplaza nuevos Roadmaps)**
- Almacena features, bugfixes, optimizaciones y releases en SQLite (`dev_log.db`).
- Genera Release Notes por versión.
- Comandos: `dev log`, `dev log add [tipo] título | detalle`, `dev log release <ver>`, `dev log versions`.
- Pre-cargado con historial completo v5.0.0 → v6.0.0.

**scheduler_service.py — Servicio independiente**
- Punto de entrada para el scheduler en Oracle Cloud como servicio systemd.
- Inicia AutonomousScheduler + API REST en background.
- Configura tareas H1 (3600s) y H4 (14400s) automáticamente.

**docs/ORACLE_CLOUD.md — Guía Oracle Cloud Always Free**
- Arquitectura completa: Scheduler + API + Nginx en VM ARM (4 OCPUs, 24 GB).
- Pasos de despliegue, systemd units, configuración Nginx.
- Tabla de endpoints y sincronización Workplace ↔ Oracle Cloud.

### Integración API Server (Node.js)
- `artifacts/api-server/src/routes/astra.ts` — 13 endpoints proxy → Python ASTRA API.
- Todos los endpoints `/api/astra/*` disponibles desde el api-server de Replit.
- Proxy HTTP interno con timeout 10s, CORS, error handling.

### Comandos nuevos en el CLI
`astra doctor`, `api start`, `api stop`, `api status`, `dev log`, `dev log add`, `dev log bugfix`, `dev log feature`, `dev log release`, `dev log versions`

### Optimización — archivos obsoletos eliminados
- `check_functionality.py` — reemplazado por `astra_doctor.py`
- `check_skeleton.py` — reemplazado por `check_system.py`
- `test_main.py` — tests primitivos de redis/sympy sin utilidad

### Validación final
- 0 errores de sintaxis en todos los archivos .py (139 archivos)
- astra doctor: 42 OK, 10 Avisos esperados, 0 Fallos
- Todos los módulos de integración importan OK con LD_LIBRARY_PATH
- TypeScript api-server typecheck: sin errores

---

## v6.0.0 — Roadmap VI: Autonomización & Data Intelligence
**Fecha:** 2026-07
**Tipo:** Feature mayor
**Estado:** ✅ Done

### Nuevos módulos

**VI.1 — Hyperparameter Optimization Cache**
- `forex/prediction/hyperparameter_cache.py` — SmartHyperparameterCache: caché SQLite por par/horizonte, TTL 7 días, invalida si el dataset cambia >5%. Elimina el 70-90% del tiempo de tune.
- `forex/prediction/adaptive_trainer.py` — AdaptiveTrainer: ajusta n_trials de Optuna automáticamente. Modos: production (50), adaptive (15), quick (8), initial (30). Aprende del historial.
- `forex/prediction/model_cache.py` — ModelCacheManager: evita reentrenar si el dataset cambió <5%. Versioning de modelos con hash de datos.

**VI.2 — System Tools Expansion**
- `check_system.py` — Self-Test completo: imports, modelos, DBs, CSVs, scheduler, memoria, APIs. Semáforo ✅/⚠️/❌ por módulo. Comando: `self-test`.

**VI.5 — Scheduler & Candlestick**
- `forex/scheduler/autonomous_scheduler.py` — AutonomousScheduler: hilo background con jobs por timeframe (H1/H4/D1). Diseñado para Oracle Cloud 24/7.
- `forex/scheduler/auto_updater.py` — AutoUpdater: actualiza incrementalmente todos los CSVs del índice usando RollingDataset.
- `forex/prediction/candlestick_patterns.py` — CandlestickPatternDetector: 9 patrones japoneses (Doji, Engulfing, Hammer, Morning Star, Evening Star, Harami, Shooting Star). Implementación pura Python, sin TA-Lib.

**VI.6 — Rolling Dataset**
- `forex/data/rolling_dataset.py` — RollingDataset: tamaño fijo (5000 filas), actualización O(1) por vela. De 60s a 0.3s por actualización.
- `forex/data/indicator_delta.py` — IndicatorDelta: recalcula solo los indicadores de las últimas K filas afectadas.
- `forex/data/csv_migrator.py` — CSVMigrator: migra CSVs existentes al formato rolling, genera índice JSON.

**VI.7 — Data Sources Unificadas**
- `forex/data/mt5_provider.py` — MT5Provider: MetaTrader 5 como fuente primaria (Windows only), fallback a Yahoo automático.
- `forex/data/yahoo_provider.py` — YahooProvider: 24+ pares Forex + commodities + índices via yfinance.
- `forex/data/binance_provider.py` — BinanceProvider: criptomonedas via API pública de Binance (sin auth).
- `forex/data/data_router.py` — DataRouter: capa de abstracción, detecta tipo de activo, enruta automáticamente.

**VI.8 — Opportunity Score**
- `forex/portfolio/opportunity_score.py` — OpportunityScoreEngine + OpportunityRanker: Top 10 BUY/SELL. Fórmula: Reliability×0.35 + WinRate×0.30 + Régimen×0.20 + MTF×0.15.
- `forex/prediction/model_quality_history.py` — ModelQualityHistory: precisión histórica verificada (ventana 30 días, mínimo 10 muestras).

**VI.3 — Documentación**
- `docs/GUIA_CSV.md` — Guía completa de creación y migración de CSVs
- `docs/FOREX_COMMANDS_FULL.md` — Referencia completa de comandos V+VI
- `docs/FLUJO_PREDICCION.md` — Diagrama y descripción del flujo oficial
- `docs/INTERPRETACION_RESULTADOS.md` — Guía de interpretación de señales

**Comandos nuevos en el CLI:**
`self-test`, `descargar datos`, `migrar csv`, `escanear csvs`, `csvs activos`, `rolling info`, `candlestick`, `hparam cache`, `hparam invalidar`, `model cache`, `adaptive budget`, `quality history`, `scheduler start/stop/info`, `auto update`, `opportunity ranking`

**Correcciones aplicadas post-test (35/35 tests OK):**
- `candlestick_patterns.py`: `avg_body` usaba `rolling(10)` sin `min_periods` → NaN con <11 filas. Corregido a `rolling(10, min_periods=3)`.
- `main.py` Opportunity Ranking: CLI usaba claves `"buy"`/`"sell"` → corregido a `"top_buy"`/`"top_sell"` (API real del `OpportunityRanker`).
- `main.py` Model Cache: `should_retrain()` devuelve `tuple[bool, str]` → handler desempaqueta correctamente el tuple.
- Tests verificados: **35/35 OK** — Self-Test del sistema: **50 OK, 7 WARN (opcionales), 0 errores**.

---

## v5.2.0 — Roadmap V: Forex Intelligence Avanzada
**Fecha:** 2026-07
**Tipo:** Feature mayor
**Estado:** ✅ Done

Roadmap V completo integrado (18 fases, 32 módulos):
- Decision Engine (V.1) — motor de decisión BUY/SELL/HOLD/NO OPERAR
- Risk Engine (V.2) — SL/TP automático + Kelly criterion
- MTF Coherence (V.3) — coherencia D1/H4/H1, HOLD forzado si incoherente
- Regime Detector (V.4) — trending/ranging/breakout/high_vol/news
- Model Selector (V.5) — selección adaptiva de modelo por régimen
- Feature Importance (V.6) — análisis SHAP post-entrenamiento
- Reliability Scorer (V.8) — índice compuesto 0-100 (7 componentes)
- Backtest Protocol (V.9) — evaluación estandarizada Walk-Forward
- Market Sentinel (V.10) — monitoreo 24/7 de señales
- Outcome Tracker (V.14) + Retrain Manager (V.13) — seguimiento de predicciones reales
- Multi-Pair Scanner (V.18) — análisis simultáneo de múltiples pares

**Fixes de compatibilidad:**
- sklearn 1.9.0: SoftVotingEnsemble + WalkForwardValidator (sin CalibratedClassifierCV)
- `compute_atr_relative` agregada a `forex/indicators.py`
- `get_pair_config` agregada a `dataset_builder.py`
- `_PreFitEnsemble` shim para compatibilidad con pickles anteriores
- Normalización de pares en `csv_adapter.py` (_normalize_pair)

---

## v5.1.0 — Quality Gate + MTF Coherence integrados
**Fecha:** 2026-06
**Tipo:** Improvement
**Estado:** ✅ Done

- Quality Gate integrado automáticamente en `pipeline.train()`
- MTF Coherence V.3 con HOLD forzado si coherencia < umbral
- Feature Engineering expandida a 85+ features
- XGBoost + LightGBM + RandomForest ensemble con Walk-Forward deslizante

---

## v5.0.0 — Migración a roadmap_v_integration.py centralizado
**Fecha:** 2026-05
**Tipo:** Breaking
**Estado:** ✅ Done

- Centralización de todos los comandos Roadmap V en `roadmap_v_integration.py`
- Nuevo punto de entrada CLI con comandos: quality, regime, mtf, reliability, decision, risk, backtest, feature_importance, dataset_update, scheduler_status, retrain_check, sentinel_status, outcome_stats, notify_test, portfolio_ranking

---

## v4.0.0 — Branches 1-4: Core + Forex + BI + PYME Consultant
**Fecha:** 2026-04
**Tipo:** Feature mayor
**Estado:** ✅ Done

- Branch 1: Core (Tool Registry, Memory, File I/O, Security)
- Branch 2: Forex ML pipeline (XGBoost + LightGBM, backtesting)
- Branch 3: Business Intelligence (KPIs, BI Engine, KRR)
- Branch 4: PYME Consultant (Diagnóstico, Forecast, Recomendaciones, Simulación)

---

> **Nota:** A partir del Roadmap VI, los cambios futuros se documentan directamente en este archivo en lugar de crear nuevos HTMLs de roadmap. Solo se creará un nuevo roadmap HTML para versiones mayores (v7.0, v8.0).
