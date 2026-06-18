"""
Forex Prediction Module (XGBoost Layer)

This package handles:
- Dataset building
- Model training (XGBoost)
- Prediction inference
- Optional feature engineering

It is fully independent from Astra core logic.
"""

# Core ML pipeline
from .dataset_builder import DatasetBuilder
from .xgb_trainer import ForexXGBTrainer
from .predictor import ForexPredictor

# Optional (only if you use it actively)
try:
    from .feature_engineering import build_features
except ImportError:
    build_features = None


__all__ = [
    "DatasetBuilder",
    "ForexXGBTrainer",
    "ForexPredictor",
    "build_features"
]
