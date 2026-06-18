import numpy as np

from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report

from .model_storage import ModelStorage


class ForexXGBTrainer:

    def __init__(self):

        # Storage system (versioned models)
        self.storage = ModelStorage()

        # Core model
        self.model = XGBClassifier(
            n_estimators=500,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss"
        )

        self.best_score = 0
        self.best_model = None

    # -----------------------------
    # TIME-BASED SPLIT (NO LEAKAGE)
    # -----------------------------
    def train_test_split(self, X, y, train_ratio=0.8):

        split = int(len(X) * train_ratio)

        X_train = X.iloc[:split]
        X_test = X.iloc[split:]

        y_train = y.iloc[:split]
        y_test = y.iloc[split:]

        return X_train, X_test, y_train, y_test

    # -----------------------------
    # TRAIN MODEL
    # -----------------------------
    def train(self, X, y, save=True):

        X_train, X_test, y_train, y_test = (
            self.train_test_split(X, y)
        )

        print("\n[XGB TRAINER] Training model...")

        self.model.fit(X_train, y_train)

        preds = self.model.predict(X_test)

        acc = accuracy_score(y_test, preds)

        print("\n=== MODEL PERFORMANCE ===")
        print(f"Accuracy: {acc:.4f}\n")

        print(classification_report(y_test, preds))

        # Track best model
        if acc > self.best_score:

            self.best_score = acc
            self.best_model = self.model

            print("[XGB TRAINER] New BEST model found ✔")

            if save:

                self.storage.save_model(
                    model=self.model,
                    name="xgb_forex_best"
                )

        else:

            print("[XGB TRAINER] Model not better than best.")

        return acc

    # -----------------------------
    # FEATURE IMPORTANCE
    # -----------------------------
    def feature_importance(self, feature_names):

        importance = self.model.feature_importances_

        ranking = sorted(
            zip(feature_names, importance),
            key=lambda x: x[1],
            reverse=True
        )

        print("\n=== FEATURE IMPORTANCE ===")

        for name, score in ranking:

            print(f"{name}: {score:.5f}")

        return ranking

    # -----------------------------
    # SAVE BEST MODEL MANUALLY
    # -----------------------------
    def save_best(self):

        if self.best_model is None:

            raise ValueError(
                "No model trained yet."
            )

        return self.storage.save_model(
            self.best_model,
            name="xgb_forex_best_manual"
        )
