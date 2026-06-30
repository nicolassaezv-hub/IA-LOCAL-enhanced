"""
Forex Prediction Module

Handles dataset building, feature engineering, model training
(XGBoost + LightGBM + RandomForest ensemble), hyperparameter
tuning via Optuna, prediction inference, and backtesting.

Fully independent from Astra core logic.
"""

from .dataset_builder        import DatasetBuilder
from .xgb_trainer            import ForexEnsembleTrainer, train_with_wfv, WalkForwardValidator
from .predictor              import ForexPredictor
from .integrated_pipeline    import ForexIntegratedPipeline
from .hyperparameter_tuner   import ForexHyperparameterTuner
from .csv_adapter            import adapt_csv, check_compatibility
from .multi_pair_scanner     import MultiPairScanner
from .model_storage          import ModelStorage

try:
    from .feature_engineering import build_features
except ImportError:
    build_features = None


__all__ = [
    "DatasetBuilder",
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
]
