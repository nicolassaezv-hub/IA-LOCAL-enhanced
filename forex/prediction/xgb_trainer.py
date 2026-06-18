import os
import joblib
import numpy as np

from xgboost import XGBClassifier
from sklearn.metrics import accuracy_score, classification_report


class ForexXGBTrainer:

    def __init__(
        self,
        model_path="models/xgb_forex.pkl"
    ):

        self.model_path = model_path

        self.model = XGBClassifier(
            n_estimators=400,
            max_depth=6,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            eval_metric="logloss"
        )

    # -----------------------------
    # TIME-SAFE SPLIT (VERY IMPORTANT)
    # -----------------------------
    def train_test_split_time(self, X, y, train_ratio=0.8):

        split_index = int(len(X) * train_ratio)

        X_train = X.iloc[:split_index]
        X_test = X.iloc[split_index:]

        y_train = y.iloc[:split_index]
        y_test = y.iloc[split_index:]

        return X_train, X_test, y_train, y_test

    # -----------------------------
    # TRAIN MODEL
    # -----------------------------
    def train(self, X, y):

        X_train, X_test, y_train, y_test = (
            self.train_test_split_time(X, y)
        )

        self.model.fit(
            X_train,
            y_train
        )

        predictions = self.model.predict(X_test)

        acc = accuracy_score(
            y_test,
            predictions
        )

        print("\n=== XGBOOST RESULTS ===")
        print(f"Accuracy: {acc:.4f}\n")

        print(
            classification_report(
                y_test,
                predictions
            )
        )

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
    # SAVE MODEL
    # -----------------------------
    def save_model(self):

        os.makedirs(
            os.path.dirname(self.model_path),
            exist_ok=True
        )

        joblib.dump(
            self.model,
            self.model_path
        )

        print(
            f"\nModel saved at {self.model_path}"
        )

    # -----------------------------
    # LOAD MODEL
    # -----------------------------
    def load_model(self):

        if not os.path.exists(self.model_path):

            raise FileNotFoundError(
                "Model not found. Train first."
            )

        self.model = joblib.load(
            self.model_path
        )

        print(
            "Model loaded successfully."
        )

    # -----------------------------
    # PREDICT SINGLE STEP
    # -----------------------------
    def predict(self, X):

        prediction = self.model.predict(X)

        probability = self.model.predict_proba(X)

        return {
            "prediction": int(prediction[0]),
            "confidence": float(
                np.max(probability[0])
            )
        }
