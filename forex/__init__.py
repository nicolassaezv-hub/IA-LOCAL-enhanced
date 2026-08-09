"""
forex — Módulo principal ASTRA para análisis y predicción Forex.

Subpaquetes:
  forex.prediction  — pipeline ML completo (features, dataset, trainer, predictor, backtester…)
  forex.data        — Data Router, Rolling Dataset, proveedores MT5/Yahoo/Binance
  forex.portfolio   — Opportunity Score y Portfolio Ranker
  forex.scheduler   — Autonomous Scheduler y Auto Updater
  forex.business    — Business Pipeline y KPI Engine

Acceso rápido:
  from forex import adapt_csv, build_features, ForexIntegratedPipeline
"""

# ── Lazy imports para evitar ciclos y acelerar arranque ──────────────────────
def __getattr__(name):
    _map = {
        "adapt_csv":               "forex.prediction.csv_adapter",
        "build_features":          "forex.prediction.feature_engineering",
        "DatasetBuilder":          "forex.prediction.dataset_builder",
        "ForexEnsembleTrainer":    "forex.prediction.xgb_trainer",
        "ForexPredictor":          "forex.prediction.predictor",
        "ForexBacktester":         "forex.prediction.backtester",
        "ForexIntegratedPipeline": "forex.prediction.integrated_pipeline",
        "DataRouter":              "forex.data.data_router",
        "RollingDataset":          "forex.data.rolling_dataset",
        "PortfolioRanker":         "forex.portfolio.portfolio_ranker",
        "get_scheduler":           "forex.scheduler.autonomous_scheduler",
        "MarketSentinel":          "forex.market_sentinel",
        "ForexMemory":             "forex.forex_memory",
    }
    if name in _map:
        import importlib
        mod = importlib.import_module(_map[name])
        return getattr(mod, name)
    raise AttributeError(f"module 'forex' has no attribute {name!r}")

__version__ = "6.0.0"
__all__ = [
    "adapt_csv", "build_features", "DatasetBuilder", "ForexEnsembleTrainer",
    "ForexPredictor", "ForexBacktester", "ForexIntegratedPipeline",
    "DataRouter", "RollingDataset", "PortfolioRanker", "get_scheduler",
    "MarketSentinel", "ForexMemory",
]
