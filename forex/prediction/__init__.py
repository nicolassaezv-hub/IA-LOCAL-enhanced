"""
Forex Prediction Module — Roadmap V

Handles dataset building, feature engineering, model training
(XGBoost + LightGBM + RandomForest ensemble), hyperparameter
tuning via Optuna, prediction inference, and backtesting.

Roadmap V adds: Decision Engine, Risk Engine, Regime Detection,
MTF Intelligence, Reliability Score, Quality Gate, Feature Importance,
Backtest Protocol, Model Selector, Outcome Tracker, Retrain Manager.

Fully independent from Astra core logic.
"""

from .dataset_builder        import DatasetBuilder, get_pair_config
from .xgb_trainer            import ForexEnsembleTrainer, train_with_wfv, WalkForwardValidator
from .predictor              import ForexPredictor
from .integrated_pipeline    import ForexIntegratedPipeline
from .hyperparameter_tuner   import ForexHyperparameterTuner
from .csv_adapter            import adapt_csv, check_compatibility
from .multi_pair_scanner     import MultiPairScanner
from .model_storage          import ModelStorage

from .feature_engineering import build_features

# Roadmap V is part of the production pipeline. Import failures here must remain
# visible instead of silently disabling every Roadmap V export.
from .decision_engine    import DecisionEngine, DecisionResult
from .risk_engine        import RiskEngine, RiskAssessment
from .regime_detector    import RegimeDetector, RegimeAssessment, Regime
from .mtf_coherence      import MTFIntelligence, MTFCoherenceResult
from .reliability_score  import ReliabilityScorer, ReliabilityReport
from .quality_analyzer   import QualityAnalyzer
from .backtest_protocol  import BacktestProtocol
from .feature_importance import FeatureImportanceAnalyzer
from .model_selector     import ModelSelectionEngine
from .outcome_tracker    import OutcomeTracker
from .retrain_manager    import RetrainManager

# Backward compatibility for the name previously advertised by this package.
ModelSelector = ModelSelectionEngine
_HAS_ROADMAP_V = True


__all__ = [
    # Core
    "DatasetBuilder",
    "get_pair_config",
    "ForexEnsembleTrainer",
    "train_with_wfv",
    "WalkForwardValidator",
    "ForexPredictor",
    "ForexIntegratedPipeline",
    "ForexHyperparameterTuner",
    "ModelStorage",
    "adapt_csv",
    "check_compatibility",
    "MultiPairScanner",
    "build_features",
    # Roadmap V
    "DecisionEngine",
    "DecisionResult",
    "RiskEngine",
    "RiskAssessment",
    "RegimeDetector",
    "RegimeAssessment",
    "Regime",
    "MTFIntelligence",
    "MTFCoherenceResult",
    "ReliabilityScorer",
    "ReliabilityReport",
    "QualityAnalyzer",
    "BacktestProtocol",
    "FeatureImportanceAnalyzer",
    "ModelSelectionEngine",
    "ModelSelector",
    "OutcomeTracker",
    "RetrainManager",
    "_HAS_ROADMAP_V",
]
